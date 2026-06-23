"""Render the HiddenBench evaluation metrics as a single multi-panel PNG.

eval の metrics.json を読み、条件別に集計して 1 枚の図 (複数パネル) に可視化する。
Labels are kept ASCII so no CJK font is required.

Usage:
    python eval/src/plot_report.py <eval_dir-or-metrics.json> [-o out.png]
    # default input:  results/local_run/hiddenbench_flat/eval/metrics.json
    # default output: <eval_dir>/plots.png
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Canonical condition order + short labels for the x axis.
# Experimental conditions in canonical order, plus optional reference groups appended at the
# right (gold_script = the generated exemplar scripts themselves; human = human-vs-human logs).
# Only groups actually present in metrics.json are drawn.
ORDER = [
    ("baseline", "1 base"),
    ("analysis_only", "2 anal"),
    ("utterance_fewshot", "3 utt"),
    ("utterance_fewshot_analysis", "4 utt+a"),
    ("situation_fewshot", "5 situ"),
    ("situation_fewshot_analysis", "6 situ+a"),
    ("script_fewshot", "7 scr"),
    ("script_fewshot_analysis", "8 scr+a"),
    ("gold_script", "★gold"),
    ("human", "human"),
]


def _mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


# The 6 experimental conditions only (gold_script / human are reference groups, excluded from
# the ranking). Each: (metric_key, direction, short_label). direction +1 = higher is better,
# -1 = lower is better. Broken/ambiguous metrics (surfacing=0, premature/terminal) are omitted.
RANK_CONDS = [
    "baseline", "analysis_only", "utterance_fewshot", "utterance_fewshot_analysis",
    "situation_fewshot", "situation_fewshot_analysis", "script_fewshot", "script_fewshot_analysis",
]
RANK_METRICS = [
    ("post_accuracy", +1, "事後正答率↑"),
    ("integration_gain", +1, "統合ゲイン↑"),
    ("conformity_conformity_rate", -1, "同調率↓"),
    ("conformity_independence_rate", +1, "独立率↑"),
    ("distinct_1", +1, "distinct-1↑"),
    ("distinct_2", +1, "distinct-2↑"),
    ("self_repetition_diversity", +1, "自己反復多様性↑"),
    ("convergence_round", +1, "収束ラウンド↑(尚早回避)"),
    ("subj_naturalness", +1, "自然さ↑"),
    ("subj_coherence", +1, "噛み合い↑"),
    ("subj_topic_development", +1, "話題展開↑"),
]
_RANK_SHORT = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
               "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
               "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
               "script_fewshot_analysis": "⑧scr+a"}


def _avg_ranks(values: dict[str, float], direction: int) -> dict[str, float]:
    """Rank conditions (1=best) with ties getting the average position."""
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


def ranking_markdown(grp: dict[str, dict[str, list[float]]]) -> str:
    """Build the 6-condition overall ranking (mean of per-metric ranks)."""
    conds = [c for c in RANK_CONDS if c in grp]
    if len(conds) < 2:
        return ""
    per_metric_rank: dict[str, dict[str, float]] = {}
    for key, direction, _ in RANK_METRICS:
        vals = {c: _mean(grp[c].get(key, [])) for c in conds}
        per_metric_rank[key] = _avg_ranks(vals, direction)
    mean_rank = {c: _mean([per_metric_rank[k][c] for k, _, _ in RANK_METRICS]) for c in conds}
    ordered = sorted(conds, key=lambda c: mean_rank[c])

    _ns = [len(next(iter(grp[c].values()), [])) for c in conds] or [0]
    _nmin, _nmax = min(_ns), max(_ns)
    _ncap = f"n={_nmin}" if _nmin == _nmax else f"n={_nmin}–{_nmax}"

    lines = [
        "## このドメイン単体ランキング（指標別内訳つき） / Single-domain ranking (this domain, per-metric breakdown)",
        "",
        "このレポートのドメインだけで、各指標を順位付け（同点は平均順位）→平均した順位。"
        "ドメイン横断（HB単体／aiwolf単体／総合）の順位は下の「ドメイン別ランキング」を参照。"
        "指標の読み方は [METRICS.ja.md](../../../../docs/METRICS.ja.md)。手本(gold)・人間ログは除外。"
        f" 矢印は良い方向。条件あたり{_ncap}。",
        "",
    ]
    header = ["総合", "条件", "平均順位", *[lbl for _, _, lbl in RANK_METRICS]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for pos, c in enumerate(ordered, 1):
        row = [str(pos), _RANK_SHORT.get(c, c), f"{mean_rank[c]:.2f}",
               *[f"{per_metric_rank[k][c]:.1f}" for k, _, _ in RANK_METRICS]]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def _group(per_game: list[dict]) -> dict[str, dict[str, list[float]]]:
    g: dict[str, dict[str, list[float]]] = {}
    for r in per_game:
        c = r.get("condition", "?")
        d = g.setdefault(c, {})
        for k, v in r.items():
            if isinstance(v, bool):
                d.setdefault(k, []).append(1.0 if v else 0.0)
            elif isinstance(v, (int, float)):
                d.setdefault(k, []).append(float(v))
    return g


def _series(grp: dict, metric: str) -> list[float]:
    return [_mean(grp.get(cond, {}).get(metric, [])) for cond, _ in ORDER]


def _bar(ax, metric_groups: list[tuple[str, str]], grp: dict, title: str, ylabel: str, ymax: float | None = None) -> None:
    """Grouped bar chart: one cluster per condition, one bar per metric."""
    labels = [lbl for _, lbl in ORDER]
    n = len(metric_groups)
    width = 0.8 / max(n, 1)
    x = range(len(labels))
    for i, (metric, legend) in enumerate(metric_groups):
        vals = _series(grp, metric)
        offs = [xi - 0.4 + width * (i + 0.5) for xi in x]
        bars = ax.bar(offs, vals, width=width, label=legend)
        if n == 1:
            for rect, v in zip(bars, vals, strict=False):
                ax.text(rect.get_x() + rect.get_width() / 2, v, f"{v:.2f}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=8)
    if ymax is not None:
        ax.set_ylim(0, ymax)
    if n > 1:
        ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.3)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot HiddenBench eval metrics into one PNG")
    parser.add_argument("input", nargs="?", default="results/local_run/hiddenbench_flat/eval/metrics.json")
    parser.add_argument("-o", "--out", default=None)
    args = parser.parse_args()

    inp = Path(args.input)
    metrics_path = inp / "metrics.json" if inp.is_dir() else inp
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    per_game = data.get("per_game", [])
    grp = _group(per_game)
    # Keep only condition groups actually present (so optional gold_script / human reference
    # groups appear only when evaluated; absent ones are not drawn as empty bars).
    ORDER[:] = [(c, lbl) for (c, lbl) in ORDER if c in grp]
    n_per = len(grp.get("baseline", {}).get("post_accuracy", []))
    out = Path(args.out) if args.out else metrics_path.parent / "plots.png"

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.suptitle(
        f"HiddenBench evaluation by condition (n={n_per}/condition, local gemma-4-31B, jp)",
        fontsize=13,
        fontweight="bold",
    )

    _bar(axes[0][0], [("pre_accuracy", "pre"), ("post_accuracy", "post")], grp,
         "Accuracy: pre vs post", "accuracy", ymax=1.15)
    _bar(axes[0][1], [("integration_gain", "gain")], grp,
         "Information integration gain (post - pre)", "gain", ymax=1.0)
    _bar(axes[0][2], [("conformity_conformity_rate", "conformity"), ("conformity_independence_rate", "independence")],
         grp, "Conformity vs independence (failure mode)", "rate", ymax=1.15)
    _bar(axes[1][0], [("distinct_1", "distinct-1"), ("distinct_2", "distinct-2"),
                      ("self_repetition_diversity", "self-rep div")],
         grp, "Lexical diversity (higher = less stagnation)", "score", ymax=0.5)
    _bar(axes[1][1], [("convergence_round", "conv. round"), ("premature_consensus", "premature rate")],
         grp, "Convergence (round# and premature-consensus rate)", "value")
    _bar(axes[1][2], [("subj_naturalness", "natural"), ("subj_coherence", "coherence"),
                      ("subj_topic_development", "topic dev")],
         grp, "Subjective (gemma judge, 1-5)", "score 1-5", ymax=5.2)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out, dpi=140)
    print(f"wrote {out}")

    # Embed the plot into report.md (idempotent) so `make judge` -> plots keeps the link even
    # though evaluate_with_judge rewrites report.md each run.
    report = out.parent / "report.md"
    if report.exists():
        text = report.read_text(encoding="utf-8")
        if out.name not in text:
            text += (
                f"\n## 可視化 / Visualization\n\n![HiddenBench metrics by condition]({out.name})\n\n"
                "*6条件別の主要指標（正答率・統合ゲイン・同調/独立・多様性・収束・主観）。"
                "`make plots`（または `python eval/src/plot_report.py`）で再生成可能。*\n"
            )
        ranking = ranking_markdown(grp)
        if ranking:
            begin, end = "<!-- BEGIN single-domain-ranking -->", "<!-- END single-domain-ranking -->"
            block = f"{begin}\n\n{ranking}\n{end}\n"
            if begin in text and end in text:  # replace prior block (idempotent across runs)
                text = text[: text.index(begin)] + block + text[text.index(end) + len(end):]
            elif "## 総合ランキング" in text:  # migrate a legacy un-marked section
                text = text[: text.index("## 総合ランキング")].rstrip() + "\n\n" + block
            else:
                text = text.rstrip() + "\n\n" + block
        report.write_text(text, encoding="utf-8")
        print(f"updated {report} (plot link + ranking)")


if __name__ == "__main__":
    main()
