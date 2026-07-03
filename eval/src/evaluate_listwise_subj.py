"""eval-v2 LISTWISE subjective judge.

Repurposes the aiwolf team-relative 6-criteria rubric: instead of ranking the 5 PLAYERS
inside one game, we rank the N CONDITION-logs of one MATCHED SEED (same game index = same HB
task / same aiwolf role assignment) against each other, per criterion, ties allowed.

WHY listwise (not absolute Likert, not pairwise):
  - Absolute Likert floored/ceilinged on every prior gemma run (no discrimination). A ranking
    CANNOT floor — the judge is forced to order the conditions, so we always get separation
    *if the judge perceives any*. The headline output is the rank SPREAD (分解能); if even a
    forced ranking can't separate conditions, the judge is genuinely blind and we say so.
  - Closest to the rubric's native design (rank items within one log).
  - Cheap: one call per (seed x criterion), not 28 pairs x n x criteria.

Per seed the condition order is shuffled (deterministic, seed-derived) and conditions are shown
as anonymous "Discussion A/B/..." so neither condition name nor position leaks to the judge.

Reads <cond>__g<idx>_*.json flat files. Pools multiple --flat dirs (reps). Writes a report with
per-criterion mean rank, the rank spread (discrimination), and the composite ranking.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import statistics as st
import string
from pathlib import Path

from judge import _llm_call, build_transcript_text, load_config

CONDS = ["baseline", "analysis_only", "utterance_fewshot", "utterance_fewshot_analysis",
         "situation_fewshot", "situation_fewshot_analysis",
         "script_fewshot", "script_fewshot_k5", "script_fewshot_k1", "script_fewshot_k3", "script_fewshot_k10",
         "script_fewshot_analysis", "script_fewshot_analysis_k5", "script_fewshot_analysis_k1",
         "script_fewshot_analysis_k3", "script_fewshot_analysis_k10"]
SH = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
      "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
      "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
      "script_fewshot_analysis": "⑧scr+a",
      "script_fewshot_k5": "⑦scr", "script_fewshot_analysis_k5": "⑧scr+a",
      "script_fewshot_k1": "⑦scr·k1", "script_fewshot_analysis_k1": "⑧scr+a·k1",
      "script_fewshot_k3": "⑦scr·k3", "script_fewshot_analysis_k3": "⑧scr+a·k3",
      "script_fewshot_k10": "⑦scr·k10", "script_fewshot_analysis_k10": "⑧scr+a·k10"}


def _game_idx(fname: str) -> str | None:
    """Extract the matched-seed game index 'g<N>' from a flat filename."""
    m = re.search(r"__(?:g)(\d+)_", fname)
    return f"g{m.group(1)}" if m else None


def _perm(seed_key: str, n: int) -> list[int]:
    """Deterministic permutation of range(n) derived from the seed key (no global RNG)."""
    h = 0
    for ch in seed_key:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    order = list(range(n))
    # Fisher-Yates with the LCG-advanced hash as the entropy source.
    for i in range(n - 1, 0, -1):
        h = (h * 1103515245 + 12345) & 0x7FFFFFFF
        j = h % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def _build_prompt(transcripts: list[str], criteria: list[dict], exclusions: list[str], n: int) -> str:
    labels = list(string.ascii_uppercase[:n])
    crit_block = "\n".join(f'- "{c["key"]}": {c["en"]}' for c in criteria)
    excl_block = "\n".join(f"- {e}" for e in exclusions)
    disc_block = "\n\n".join(f"### Discussion {labels[i]}\n{transcripts[i]}" for i in range(n))
    rank_obj = "{" + ", ".join(f'"{lab}": <rank>' for lab in labels) + "}"
    schema = ", ".join(f'"{c["key"]}": {rank_obj}' for c in criteria)
    return (
        f"You are an expert evaluator of multi-party discussions. Below are {n} DIFFERENT "
        f"discussions (Discussion {', '.join(labels)}) of the SAME underlying scenario, produced "
        "by different systems.\n\n"
        "For EACH criterion, RANK all discussions from best (rank 1) to worst (rank "
        f"{n}). Ties are allowed (give the same rank to equally-good discussions). Every "
        "discussion must receive a rank for every criterion.\n\n"
        "## Criteria\n" + crit_block + "\n\n"
        "## Important constraints (judge the discussion text ONLY)\n" + excl_block + "\n\n"
        "## Discussions\n" + disc_block + "\n\n"
        "Respond with ONLY this JSON (no prose), mapping each criterion to each discussion's "
        "integer rank:\n"
        "{\"ranks\": {" + schema + "}}"
    )


def _parse_ranks(raw: str, crit_keys: list[str], labels: list[str], n: int) -> dict[str, dict[str, int]]:
    for m in re.finditer(r"\{.*\}", raw, flags=re.DOTALL):
        try:
            obj = json.loads(m.group(0))
        except (ValueError, TypeError):
            continue
        ranks = obj.get("ranks") if isinstance(obj, dict) else None
        if not isinstance(ranks, dict):
            continue
        out: dict[str, dict[str, int]] = {}
        for k in crit_keys:
            row = ranks.get(k)
            if not isinstance(row, dict):
                continue
            clean = {}
            for lab in labels:
                v = row.get(lab)
                try:
                    iv = int(round(float(v)))
                    clean[lab] = max(1, min(n, iv))
                except (TypeError, ValueError):
                    pass
            if len(clean) == n:
                out[k] = clean
        if out:
            return out
    return {}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--flat", action="append", required=True, help="flat dir(s) with <cond>__g*.json")
    p.add_argument("--domain", choices=["aiwolf", "hb"], required=True)
    p.add_argument("--judge-config", default="eval/config/judge.listwise.yml")
    p.add_argument("--conds", default=None, help="comma-sep condition subset (default: all 8)")
    p.add_argument("--n-seeds", type=int, default=10)
    p.add_argument("--out", required=True)
    p.add_argument("--label", default="run")
    args = p.parse_args()

    conds = args.conds.split(",") if args.conds else list(CONDS)
    for c in conds:
        SH.setdefault(c, c)
    cfg = load_config(Path(args.judge_config))
    criteria = [c for c in cfg.get("criteria", []) if args.domain in c.get("domains", [])]
    crit_keys = [c["key"] for c in criteria]
    exclusions = cfg.get("exclusions", [])
    n = len(conds)

    # gather files per condition keyed by matched-seed game index
    by_cond: dict[str, dict[str, str]] = {c: {} for c in conds}
    for fl in args.flat:
        for f in sorted(glob.glob(f"{fl}/*__g*.json")):
            base = Path(f).name
            c = base.split("__")[0]
            gi = _game_idx(base)
            if c in by_cond and gi and gi not in by_cond[c]:
                by_cond[c][gi] = f
    # seeds present in ALL conditions
    common = sorted(set.intersection(*[set(by_cond[c]) for c in conds]),
                    key=lambda g: int(g[1:]))
    seeds = common[: args.n_seeds]
    print(f"domain={args.domain} conds={n} criteria={crit_keys} common_seeds={len(common)} using={len(seeds)}")

    labels = list(string.ascii_uppercase[:n])
    # ranks_acc[cond][crit] = list of ranks across seeds
    ranks_acc: dict[str, dict[str, list[int]]] = {c: collections.defaultdict(list) for c in conds}
    judged = 0
    for gi in seeds:
        order = _perm(f"{args.domain}:{gi}", n)  # display position -> cond index
        disp_conds = [conds[order[i]] for i in range(n)]
        transcripts = []
        for c in disp_conds:
            d = json.load(open(by_cond[c][gi]))
            transcripts.append(build_transcript_text(d))
        prompt = _build_prompt(transcripts, criteria, exclusions, n)
        parsed = _parse_ranks(_llm_call(prompt, cfg), crit_keys, labels, n)
        if not parsed:
            print(f"  {gi}: parse failed, skip")
            continue
        judged += 1
        for k in crit_keys:
            row = parsed.get(k)
            if not row:
                continue
            for pos, lab in enumerate(labels):
                ranks_acc[disp_conds[pos]][k].append(row[lab])
        print(f"  {gi}: ok")

    def mrank(c, k):
        v = ranks_acc[c][k]
        return st.mean(v) if v else float("nan")

    # composite = mean over criteria of per-criterion mean rank
    comp = {c: st.mean([mrank(c, k) for k in crit_keys]) for c in conds}
    ranking = sorted(conds, key=lambda c: comp[c])

    out = [f"# eval-v2 LISTWISE subjective ranking — {args.label} ({args.domain})",
           f"judge={cfg.get('model')} | seeds judged={judged}/{len(seeds)} | conds={n} | "
           "rank 1=best (ties allowed). 平均順位↓良い。\n",
           "## 分解能チェック (mean-rank spread per criterion: 大きいほど判別できている)"]
    out.append("| criterion | min | max | spread(max-min) | stdev |")
    out.append("|---|---|---|---|---|")
    for k in crit_keys:
        vals = [float(mrank(c, k)) for c in conds]
        _m = sum(vals) / len(vals)
        _sd = (sum((v - _m) ** 2 for v in vals) / len(vals)) ** 0.5  # population stdev (avoid st.pstdev 3.12 quirk)
        out.append(f"| {k} | {min(vals):.2f} | {max(vals):.2f} | {max(vals)-min(vals):.2f} | "
                   f"{_sd:.3f} |")
    out.append("\n## 条件 × criterion 平均順位")
    out.append("| 条件 | " + " | ".join(crit_keys) + " | 総合 |")
    out.append("|" + "---|" * (len(crit_keys) + 2))
    for c in conds:
        out.append("| " + SH[c] + " | " + " | ".join(f"{mrank(c,k):.2f}" for k in crit_keys) +
                   f" | {comp[c]:.2f} |")
    out.append("\n## 総合ランキング(平均順位↓良い)")
    out.append("| 順 | 条件 | 平均順位 |")
    out.append("|---|---|---|")
    for i, c in enumerate(ranking, 1):
        out.append(f"| {i} | {SH[c]} | {comp[c]:.2f} |")
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
