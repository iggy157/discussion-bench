"""Per-domain + overall condition rankings (6 experimental conditions only).

ドメイン別（HiddenBench / aiwolf）と総合の条件ランキングを出力する。各指標で順位付け（同点は平均
順位）→ その平均で各ドメインの総合順位。最終「総合」はドメインごとの平均順位を更に平均して算出。
手本(gold)・人間ログは除外。aiwolf には正答率/統合ゲインが無いので、その2指標はaiwolf順位から除外。

Usage:
    python eval/src/rankings.py --hb <hb_metrics.json> --aiwolf <aiwolf_metrics.json> --out <rankings.md>
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path
from typing import Any

CONDS = ["baseline", "analysis_only", "utterance_fewshot", "utterance_fewshot_analysis",
         "situation_fewshot", "situation_fewshot_analysis", "script_fewshot", "script_fewshot_analysis"]
SHORT = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
         "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
         "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
         "script_fewshot_analysis": "⑧scr+a"}

# (key, direction, label). +1 higher better, -1 lower better.
_ACC = [("post_accuracy", +1, "事後正答率↑"), ("integration_gain", +1, "統合ゲイン↑")]
_SHARED = [
    ("conformity_conformity_rate", -1, "同調率↓"),
    ("conformity_independence_rate", +1, "独立率↑"),
    ("distinct_1", +1, "distinct-1↑"),
    ("distinct_2", +1, "distinct-2↑"),
    ("self_repetition_diversity", +1, "自己反復多様性↑"),
    ("convergence_round", +1, "収束ラウンド↑"),
    ("subj_naturalness", +1, "自然さ↑"),
    ("subj_coherence", +1, "噛み合い↑"),
    ("subj_topic_development", +1, "話題展開↑"),
]
HB_METRICS = _ACC + _SHARED
AIWOLF_METRICS = _SHARED  # no pre/post accuracy in werewolf


def _group(path: Path) -> dict[str, dict[str, list[float]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    g: dict[str, dict[str, list[float]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in data.get("per_game", []):
        c = r.get("condition")
        for k, v in r.items():
            if isinstance(v, bool):
                g[c][k].append(1.0 if v else 0.0)
            elif isinstance(v, (int, float)):
                g[c][k].append(float(v))
    return g


def _mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


def _avg_ranks(values: dict[str, float], direction: int) -> dict[str, float]:
    order = sorted(values.items(), key=lambda kv: kv[1], reverse=(direction > 0))
    ranks: dict[str, float] = {}
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and order[j + 1][1] == order[i][1]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[order[k][0]] = avg
        i = j + 1
    return ranks


def domain_ranking(grp: dict, metrics: list[tuple[str, int, str]]) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Return (condition -> mean_rank, metric_key -> {cond: rank}) for present conditions."""
    conds = [c for c in CONDS if c in grp]
    per_metric: dict[str, dict[str, float]] = {}
    for key, direction, _ in metrics:
        vals = {c: _mean(grp[c].get(key, [])) for c in conds}
        per_metric[key] = _avg_ranks(vals, direction)
    mean_rank = {c: _mean([per_metric[k][c] for k, _, _ in metrics]) for c in conds}
    return mean_rank, per_metric


def _table(title: str, note: str, mean_rank: dict[str, float], per_metric: dict[str, dict[str, float]],
           metrics: list[tuple[str, int, str]]) -> str:
    ordered = sorted(mean_rank, key=lambda c: mean_rank[c])
    lines = [f"## {title}", "", note, ""]
    header = ["総合", "条件", "平均順位", *[lbl for _, _, lbl in metrics]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for pos, c in enumerate(ordered, 1):
        row = [str(pos), SHORT.get(c, c), f"{mean_rank[c]:.2f}",
               *[f"{per_metric[k][c]:.1f}" for k, _, _ in metrics]]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Per-domain + overall condition rankings")
    p.add_argument("--hb", required=True, help="HiddenBench metrics.json")
    p.add_argument("--aiwolf", default=None, help="aiwolf metrics.json (optional)")
    p.add_argument("--out", required=True, help="output rankings.md")
    p.add_argument("--report", action="append", default=[],
                   help="report.md path(s) to also embed the per-domain rankings into (repeatable)")
    args = p.parse_args()

    hb_grp = _group(Path(args.hb))
    hb_mean, hb_pm = domain_ranking(hb_grp, HB_METRICS)

    # Games per condition (HB) for an accurate caption — varies if some games failed to fill.
    # Restrict to the 6 experimental conditions (exclude gold/human, which have few exemplars).
    _ns = [len(next(iter(hb_grp[c].values()), [])) for c in CONDS if c in hb_grp] or [0]
    _nmin, _nmax = min(_ns), max(_ns)
    _ncap = f"n={_nmin}" if _nmin == _nmax else f"n={_nmin}–{_nmax}"

    sections = [
        "# 条件ランキング / Condition rankings (6 conditions, gold & human excluded)\n",
        "各指標で順位付け（同点=平均順位）→ 平均で各ドメイン順位。総合はドメイン平均順位の平均。"
        f"HiddenBench {_ncap}（条件あたりゲーム数）。\n",
        _table("HiddenBench のみ / HiddenBench only",
               "正答率・統合ゲインを含む全指標。", hb_mean, hb_pm, HB_METRICS),
    ]

    overall_components = {c: [hb_mean[c]] for c in hb_mean}
    if args.aiwolf and Path(args.aiwolf).exists():
        aw_grp = _group(Path(args.aiwolf))
        aw_mean, aw_pm = domain_ranking(aw_grp, AIWOLF_METRICS)
        sections.append(_table("aiwolf のみ / aiwolf only",
                               "werewolf には正答率/統合ゲインが無いため、共通の失敗モード・多様性・主観のみ。",
                               aw_mean, aw_pm, AIWOLF_METRICS))
        for c in aw_mean:
            overall_components.setdefault(c, []).append(aw_mean[c])

    # Overall = mean of each domain's mean-rank (domains weighted equally).
    overall = {c: _mean(v) for c, v in overall_components.items()}
    ordered = sorted(overall, key=lambda c: overall[c])
    lines = ["## 総合 / Overall (domains weighted equally)", "",
             "各ドメインの平均順位を更に平均（HiddenBench と aiwolf を等重み）。", "",
             "| 総合 | 条件 | 総合平均順位 | HB平均順位 | aiwolf平均順位 |",
             "|---|---|---|---|---|"]
    for pos, c in enumerate(ordered, 1):
        comps = overall_components[c]
        hb_v = f"{comps[0]:.2f}"
        aw_v = f"{comps[1]:.2f}" if len(comps) > 1 else "-"
        lines.append(f"| {pos} | {SHORT.get(c, c)} | {overall[c]:.2f} | {hb_v} | {aw_v} |")
    sections.append("\n".join(lines) + "\n")

    body = "\n".join(sections)
    Path(args.out).write_text(body, encoding="utf-8")
    print(f"wrote {args.out}")

    # Optionally embed the same per-domain rankings into report.md files (idempotent: the block
    # between the markers is replaced on every run). Lets one report.md carry both the per-domain
    # metric detail (from plot_report) AND the cross-domain rankings (here).
    begin, end = "<!-- BEGIN per-domain-rankings -->", "<!-- END per-domain-rankings -->"
    block = (f"{begin}\n\n# ドメイン別ランキング / Per-domain rankings\n\n"
             "指標の読み方は [METRICS.ja.md](../../../../docs/METRICS.ja.md) を参照"
             "（各指標の意味・良い方向・失敗様態との対応）。\n\n"
             f"{body}\n{end}\n")
    for rep in args.report:
        rp = Path(rep)
        if not rp.exists():
            print(f"skip (no report): {rp}")
            continue
        text = rp.read_text(encoding="utf-8")
        if begin in text and end in text:
            pre = text[: text.index(begin)]
            post = text[text.index(end) + len(end):]
            text = pre + block + post
        else:
            text = text.rstrip() + "\n\n" + block
        rp.write_text(text, encoding="utf-8")
        print(f"embedded per-domain rankings -> {rp}")


if __name__ == "__main__":
    main()
