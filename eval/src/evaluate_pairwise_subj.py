"""eval-v2 PAIRWISE subjective judge — cross-check for the listwise ranking.

For every pair of conditions, on matched seeds, show the two transcripts (anonymized A/B,
order randomized per pair+seed) and ask the judge which is better per criterion (A / B / tie).
Aggregate to a per-condition win-rate = (wins + 0.5*ties) / comparisons, then rank.

Same rubric/criteria/exclusions as the listwise judge (judge.listwise.yml), filtered by --domain.
Sampling: --n-seeds seeds PER PAIR (a "sample" is fine; pairwise is O(pairs) so keep it small).

Complements evaluate_listwise_subj.py: listwise forces one global ordering; pairwise builds the
ordering from independent head-to-heads. Agreement between the two = robust; disagreement = the
signal is fragile (low 分解能).
"""
from __future__ import annotations

import argparse
import collections
import glob
import itertools
import json
import re
import statistics as st
from pathlib import Path

from judge import _llm_call, build_transcript_text, load_config

CONDS = ["baseline", "analysis_only", "utterance_fewshot", "utterance_fewshot_analysis",
         "situation_fewshot", "situation_fewshot_analysis", "script_fewshot",
         "script_fewshot_analysis"]
SH = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
      "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
      "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
      "script_fewshot_analysis": "⑧scr+a"}


def _game_idx(fname: str) -> str | None:
    m = re.search(r"__(?:g)(\d+)_", fname)
    return f"g{m.group(1)}" if m else None


def _hash(s: str) -> int:
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return h


def _build_prompt(t_a: str, t_b: str, criteria: list[dict], exclusions: list[str]) -> str:
    crit_block = "\n".join(f'- "{c["key"]}": {c["en"]}' for c in criteria)
    excl_block = "\n".join(f"- {e}" for e in exclusions)
    schema = ", ".join(f'"{c["key"]}": "A"|"B"|"tie"' for c in criteria)
    return (
        "You are an expert evaluator of multi-party discussions. Below are TWO discussions "
        "(A and B) of the SAME underlying scenario, produced by different systems.\n\n"
        'For EACH criterion, decide which discussion is better: answer "A", "B", or "tie".\n\n'
        "## Criteria\n" + crit_block + "\n\n"
        "## Important constraints (judge the discussion text ONLY)\n" + excl_block + "\n\n"
        "## Discussion A\n" + t_a + "\n\n## Discussion B\n" + t_b + "\n\n"
        "Respond with ONLY this JSON (no prose):\n"
        '{"verdicts": {' + schema + "}}"
    )


def _parse(raw: str, crit_keys: list[str]) -> dict[str, str]:
    for m in re.finditer(r"\{.*\}", raw, flags=re.DOTALL):
        try:
            obj = json.loads(m.group(0))
        except (ValueError, TypeError):
            continue
        v = obj.get("verdicts") if isinstance(obj, dict) else None
        if isinstance(v, dict):
            out = {}
            for k in crit_keys:
                val = str(v.get(k, "")).strip().lower()
                if val in ("a", "b", "tie"):
                    out[k] = val
            if out:
                return out
    return {}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--flat", action="append", required=True)
    p.add_argument("--domain", choices=["aiwolf", "hb"], required=True)
    p.add_argument("--judge-config", default="eval/config/judge.listwise.yml")
    p.add_argument("--conds", default=None, help="comma-sep subset (default all 8)")
    p.add_argument("--n-seeds", type=int, default=8, help="seeds per pair")
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

    by_cond: dict[str, dict[str, str]] = {c: {} for c in conds}
    for fl in args.flat:
        for f in sorted(glob.glob(f"{fl}/*__g*.json")):
            base = Path(f).name
            c = base.split("__")[0]
            gi = _game_idx(base)
            if c in by_cond and gi and gi not in by_cond[c]:
                by_cond[c][gi] = f
    common = sorted(set.intersection(*[set(by_cond[c]) for c in conds]), key=lambda g: int(g[1:]))
    seeds = common[: args.n_seeds]
    pairs = list(itertools.combinations(conds, 2))
    print(f"domain={args.domain} conds={len(conds)} pairs={len(pairs)} seeds/pair={len(seeds)} "
          f"criteria={crit_keys}")

    # win[c][k] = [wins, ties, games]
    rec: dict[str, dict[str, list[int]]] = {c: {k: [0, 0, 0] for k in crit_keys} for c in conds}
    cache: dict[str, str] = {}

    def txt(c: str, gi: str) -> str:
        key = f"{c}|{gi}"
        if key not in cache:
            cache[key] = build_transcript_text(json.load(open(by_cond[c][gi])))
        return cache[key]

    done = 0
    for ci, cj in pairs:
        for gi in seeds:
            swap = _hash(f"{args.domain}:{ci}:{cj}:{gi}") & 1
            a_cond, b_cond = (cj, ci) if swap else (ci, cj)
            prompt = _build_prompt(txt(a_cond, gi), txt(b_cond, gi), criteria, exclusions)
            verd = _parse(_llm_call(prompt, cfg), crit_keys)
            if not verd:
                continue
            for k, v in verd.items():
                rec[a_cond][k][2] += 1
                rec[b_cond][k][2] += 1
                if v == "a":
                    rec[a_cond][k][0] += 1
                elif v == "b":
                    rec[b_cond][k][0] += 1
                else:
                    rec[a_cond][k][1] += 1
                    rec[b_cond][k][1] += 1
        done += 1
        print(f"  pair {done}/{len(pairs)} {SH[ci]} vs {SH[cj]} done")

    def wr(c, k):
        w, t, g = rec[c][k]
        return (w + 0.5 * t) / g if g else float("nan")

    comp = {c: st.mean([wr(c, k) for k in crit_keys]) for c in conds}
    ranking = sorted(conds, key=lambda c: -comp[c])

    out = [f"# eval-v2 PAIRWISE subjective win-rate — {args.label} ({args.domain})",
           f"judge={cfg.get('model')} | {len(conds)}条件 {len(pairs)}ペア × {len(seeds)}シード/ペア | "
           "win_rate=(勝+0.5*分)/対戦数, ↑良い。\n",
           "## 条件 × criterion 勝率",
           "| 条件 | " + " | ".join(crit_keys) + " | 総合 |",
           "|" + "---|" * (len(crit_keys) + 2)]
    for c in conds:
        out.append("| " + SH[c] + " | " + " | ".join(f"{wr(c,k):.3f}" for k in crit_keys) +
                   f" | {comp[c]:.3f} |")
    out.append("\n## 総合ランキング(勝率↓=高い順)")
    out.append("| 順 | 条件 | 勝率 |")
    out.append("|---|---|---|")
    for i, c in enumerate(ranking, 1):
        out.append(f"| {i} | {SH[c]} | {comp[c]:.3f} |")
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
