"""eval-v2 DISCOURSE — SUBJECTIVE half (gemma judge, self-defined rubric, NOT reference-based).

Parallels evaluate_discourse.py (objective). Uses judge.discourse.yml rubric items
(nonredundancy / topic_progression / expression_diversity / engagement). Subsamples
--max-per-cond games per condition for speed. Writes a separate report (does NOT touch the
reference-eval metrics.json).
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import statistics as st
from pathlib import Path

from judge import judge_game, load_config

CONDS = ["baseline", "analysis_only", "utterance_fewshot", "utterance_fewshot_analysis",
         "situation_fewshot", "situation_fewshot_analysis", "script_fewshot",
         "script_fewshot_analysis"]
SH = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
      "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
      "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
      "script_fewshot_analysis": "⑧scr+a"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--flat", action="append", required=True)
    p.add_argument("--judge-config", default="eval/config/judge.discourse.yml")
    p.add_argument("--max-per-cond", type=int, default=25)
    p.add_argument("--out", required=True)
    p.add_argument("--label", default="run")
    args = p.parse_args()

    cfg = load_config(Path(args.judge_config))
    keys = [it["key"] for it in cfg.get("items", [])]

    # gather files per condition across flat dirs
    files: dict[str, list[str]] = collections.defaultdict(list)
    for fl in args.flat:
        for f in sorted(glob.glob(f"{fl}/*__g*.json")):
            c = Path(f).name.split("__")[0]
            if c in CONDS:
                files[c].append(f)

    by: dict[str, dict[str, list[float]]] = {c: collections.defaultdict(list) for c in CONDS}
    for c in CONDS:
        sel = files[c][: args.max_per_cond]
        for f in sel:
            try:
                d = json.load(open(f))
            except Exception:
                continue
            sj = judge_game(d, cfg)
            for k in keys:
                v = sj.get("scores", {}).get(k)
                if isinstance(v, (int, float)):
                    by[c][k].append(v)
        print(f"  judged {SH[c]}: {len(sel)} games")

    means = {c: {k: (st.mean(by[c][k]) if by[c][k] else float("nan")) for k in keys} for c in CONDS}
    per_rank: dict[str, list[int]] = collections.defaultdict(list)
    for k in keys:
        order = sorted(CONDS, key=lambda c: -(means[c][k] if means[c][k] == means[c][k] else -9))
        for i, c in enumerate(order):
            per_rank[c].append(i + 1)
    comp = {c: st.mean(per_rank[c]) for c in CONDS}
    ranking = sorted(CONDS, key=lambda c: comp[c])

    out = [f"# eval-v2 discourse SUBJECTIVE (gemma judge, 自作rubric) — {args.label}",
           f"(max {args.max_per_cond} games/cond subsample; 全て↑良い 1-5)\n",
           "| 条件 | " + " | ".join(keys) + " |",
           "|" + "---|" * (1 + len(keys))]
    for c in CONDS:
        out.append("| " + SH[c] + " | " + " | ".join(f"{means[c][k]:.2f}" for k in keys) + " |")
    out.append("\n## discourse主観 総合ランキング(平均順位↓良い)")
    out.append("| 順 | 条件 | 平均順位 |")
    out.append("|---|---|---|")
    for i, c in enumerate(ranking, 1):
        out.append(f"| {i} | {SH[c]} | {comp[c]:.2f} |")
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
