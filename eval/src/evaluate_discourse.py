"""eval-v2: DISCOURSE metrics (SELF-DEFINED, NOT reference-based). Kept separate from the
principled reference-based eval (evaluate.py / evaluate_with_judge.py).

談話品質の自作指標。参照文献ベースではない別系統の評価。仮説「台本(流れ)は語り出しが多様で
冗長になりにくい／断片(situ/utt)は局所的だが全体で冗長化」を捉えることを狙う。

This v1 uses LEXICAL/STRUCTURAL proxies (no embeddings) so it runs with no extra deps:
  - opening_diversity : distinct(first-3-words) / #utterances  (語り出しの多様性, ↑good)
  - nonredundancy     : 1 - frac(utterances >=J token-Jaccard to an EARLIER utterance)  (↑good)
  - substantive_rate  : 1 - frac(short agreement-filler utterances)  (↑good = 実質発話率)
  - topic_progression : frac of content tokens in the LATTER half that are NEW (unseen earlier)
                        (↑good = 話題が前進し続ける vs 堂々巡り)
A future v2 can swap the lexical redundancy/progression for sentence-embedding versions.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import statistics as st
from pathlib import Path

_FILLER = re.compile(
    r"\b(i agree|i concur|unanimous|consensus|agreed|let'?s (finalize|proceed|lock|move)|"
    r"fully agree|in (full|complete) agreement|i'?m in|sounds good|exactly)\b",
    re.I,
)
_STOP = {"the", "a", "an", "is", "are", "to", "of", "and", "i", "we", "it", "that", "this",
         "in", "on", "for", "as", "be", "have", "has", "with", "our", "you", "s", "m", "t"}


def _toks(s: str) -> list[str]:
    return re.findall(r"\w+", s.lower())


def _content(s: str) -> set[str]:
    return {t for t in _toks(s) if len(t) >= 3 and t not in _STOP}


def discourse_metrics(utts: list[str], jaccard: float = 0.7) -> dict[str, float]:
    """Compute discourse metrics for one game's utterance list."""
    n = len(utts)
    if n < 2:
        return {}
    # opening diversity
    openings = collections.Counter(" ".join(_toks(u)[:3]) for u in utts)
    opening_diversity = len(openings) / n
    # nonredundancy (token-Jaccard vs any earlier utterance)
    seen_tok: list[set[str]] = []
    dup = 0
    for u in utts:
        tu = set(_toks(u))
        if tu and any(len(tu & p) / len(tu | p) >= jaccard for p in seen_tok):
            dup += 1
        seen_tok.append(tu)
    nonredundancy = 1.0 - dup / n
    # substantive rate (not short filler)
    filler = sum(1 for u in utts if len(_toks(u)) < 25 and _FILLER.search(u))
    substantive_rate = 1.0 - filler / n
    # topic progression: new content tokens in latter half
    half = n // 2
    early = set().union(*[_content(u) for u in utts[:half]]) if half else set()
    latter = utts[half:]
    new = tot = 0
    for u in latter:
        c = _content(u)
        tot += len(c)
        new += len(c - early)
        early |= c
    topic_progression = (new / tot) if tot else 0.0
    return {
        "opening_diversity": opening_diversity,
        "nonredundancy": nonredundancy,
        "substantive_rate": substantive_rate,
        "topic_progression": topic_progression,
    }


def _utts_from_game(d: dict) -> list[str]:
    """Extract utterance texts from an HB transcript or aiwolf entries game JSON."""
    t = d.get("transcript")
    if isinstance(t, list):
        return [e["text"] for e in t if isinstance(e, dict) and e.get("text")]
    e = d.get("entries")
    if isinstance(e, list):
        out = []
        for x in e:
            if isinstance(x, dict):
                tx = x.get("text") or x.get("content")
                if tx:
                    out.append(tx)
        return out
    return []


def main() -> None:
    p = argparse.ArgumentParser(description="eval-v2 discourse metrics (self-defined, lexical)")
    p.add_argument("--flat", action="append", required=True,
                   help="hiddenbench_flat dir(s) with <cond>__g*.json (repeatable to pool reps)")
    p.add_argument("--out", required=True, help="output markdown")
    p.add_argument("--label", default="run")
    p.add_argument("--conds", default=None, help="comma-sep condition subset (default: standard 8)")
    args = p.parse_args()

    conds = args.conds.split(",") if args.conds else [
        "baseline", "analysis_only", "utterance_fewshot", "utterance_fewshot_analysis",
        "situation_fewshot", "situation_fewshot_analysis", "script_fewshot",
        "script_fewshot_analysis"]
    sh = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
          "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
          "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
          "script_fewshot_analysis": "⑧scr+a"}
    for c in conds:
        sh.setdefault(c, c)
    metrics = ["opening_diversity", "nonredundancy", "substantive_rate", "topic_progression"]

    by: dict[str, dict[str, list[float]]] = {c: collections.defaultdict(list) for c in conds}
    for flatdir in args.flat:
        for f in glob.glob(f"{flatdir}/*__g*.json"):
            cond = Path(f).name.split("__")[0]
            if cond not in conds:
                continue
            try:
                d = json.load(open(f))
            except Exception:
                continue
            m = discourse_metrics(_utts_from_game(d))
            for k, v in m.items():
                by[cond][k].append(v)

    means = {c: {k: (st.mean(by[c][k]) if by[c][k] else float("nan")) for k in metrics} for c in conds}
    # composite = mean of per-metric ranks (all higher=better); also a 0-1 normalized score
    per_rank: dict[str, list[int]] = collections.defaultdict(list)
    for k in metrics:
        order = sorted(conds, key=lambda c: -means[c][k])
        for i, c in enumerate(order):
            per_rank[c].append(i + 1)
    comp = {c: st.mean(per_rank[c]) for c in conds}
    ranking = sorted(conds, key=lambda c: comp[c])

    out = [f"# eval-v2 discourse (自作・非参照) — {args.label}\n",
           "指標(全て↑良い): opening_diversity(語り出し多様性) / nonredundancy(非冗長) / "
           "substantive_rate(実質発話率) / topic_progression(話題前進度)\n",
           "| 条件 | open_div | nonredund | substant | topic_prog |",
           "|---|---|---|---|---|"]
    for c in conds:
        m = means[c]
        out.append(f"| {sh[c]} | {m['opening_diversity']:.3f} | {m['nonredundancy']:.3f} | "
                   f"{m['substantive_rate']:.3f} | {m['topic_progression']:.3f} |")
    out.append("\n## discourse 総合ランキング(平均順位↓良い)")
    out.append("| 順 | 条件 | 平均順位 |")
    out.append("|---|---|---|")
    for i, c in enumerate(ranking, 1):
        out.append(f"| {i} | {sh[c]} | {comp[c]:.2f} |")
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
