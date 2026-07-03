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
         "situation_fewshot", "situation_fewshot_analysis",
         # script conditions: bare + K-tagged variants (only the present one is used per grp)
         "script_fewshot", "script_fewshot_k5", "script_fewshot_k1", "script_fewshot_k3", "script_fewshot_k10",
         "script_fewshot_analysis", "script_fewshot_analysis_k5", "script_fewshot_analysis_k1",
         "script_fewshot_analysis_k3", "script_fewshot_analysis_k10"]
SHORT = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
         "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
         "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
         "script_fewshot_analysis": "⑧scr+a",
         "script_fewshot_k5": "⑦scr", "script_fewshot_analysis_k5": "⑧scr+a",
         "script_fewshot_k1": "⑦scr·k1", "script_fewshot_analysis_k1": "⑧scr+a·k1",
         "script_fewshot_k3": "⑦scr·k3", "script_fewshot_analysis_k3": "⑧scr+a·k3",
         "script_fewshot_k10": "⑦scr·k10", "script_fewshot_analysis_k10": "⑧scr+a·k10"}

# (key, direction, label). +1 higher better, -1 lower better.
# OBJECTIVE = computed from transcripts/answers (no LLM). SUBJECTIVE = LLM-judge Likert (1-5).
# We aggregate them SEPARATELY: subjective scores can be unreliable (judge ceiling/self-preference),
# so mixing them into one rank can mask or distort the objective signal.
_ACC = [("post_accuracy", +1, "事後正答率↑"), ("integration_gain", +1, "統合ゲイン↑")]
_OBJ_SHARED = [
    ("conformity_conformity_rate", -1, "同調率↓"),
    ("conformity_independence_rate", +1, "独立率↑"),
    ("distinct_1", +1, "distinct-1↑"),
    ("distinct_2", +1, "distinct-2↑"),
    ("self_repetition_diversity", +1, "自己反復多様性↑"),
    ("convergence_round", +1, "収束ラウンド↑"),
]
_SUBJ = [
    ("subj_naturalness", +1, "自然さ↑"),
    ("subj_coherence", +1, "噛み合い↑"),
    ("subj_topic_development", +1, "話題展開↑"),
]
# Objective ranking sets (HB adds accuracy/gain); subjective sets are the 3 judge metrics.
HB_OBJ = _ACC + _OBJ_SHARED
AIWOLF_OBJ = _OBJ_SHARED
HB_SUBJ = _SUBJ
AIWOLF_SUBJ = _SUBJ
# Back-compat combined sets (used only if something still imports them).
HB_METRICS = HB_OBJ + _SUBJ
AIWOLF_METRICS = AIWOLF_OBJ + _SUBJ


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


def ranking_group(label: str, note: str, hb_grp: dict, aw_grp: dict | None,
                  hb_metrics: list, aw_metrics: list) -> tuple[str, dict[str, float]]:
    """HB + aiwolf + overall tables for ONE metric group; return (markdown, overall mean-rank)."""
    secs = [f"## {label}", "", note, ""]
    hb_mean, hb_pm = domain_ranking(hb_grp, hb_metrics)
    secs.append(_table(f"HiddenBench — {label}", "", hb_mean, hb_pm, hb_metrics))
    comp = {c: [hb_mean[c]] for c in hb_mean}
    if aw_grp is not None:
        aw_mean, aw_pm = domain_ranking(aw_grp, aw_metrics)
        secs.append(_table(f"aiwolf — {label}", "", aw_mean, aw_pm, aw_metrics))
        for c in aw_mean:
            comp.setdefault(c, []).append(aw_mean[c])
    overall = {c: _mean(v) for c, v in comp.items()}
    ordered = sorted(overall, key=lambda c: overall[c])
    lines = [f"### 総合 — {label} / Overall (domains equal-weight)", "",
             "| 総合 | 条件 | 総合平均順位 | HB | aiwolf |", "|---|---|---|---|---|"]
    for pos, c in enumerate(ordered, 1):
        cc = comp[c]
        lines.append(f"| {pos} | {SHORT.get(c, c)} | {overall[c]:.2f} | {cc[0]:.2f} | "
                     f"{(f'{cc[1]:.2f}' if len(cc) > 1 else '-')} |")
    secs.append("\n".join(lines) + "\n")
    return "\n".join(secs), overall


def _corr(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation of two equal-length vectors (used on mean-ranks ≈ Spearman)."""
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx > 0 and dy > 0 else float("nan")


def subjective_validity(hb_grp: dict, aw_grp: dict | None,
                        obj_overall: dict[str, float], subj_overall: dict[str, float]) -> str:
    """Diagnose whether the LLM-judge subjective scores are trustworthy / discriminating."""
    lines = ["## 主観の妥当性チェック / Subjective validity", "",
             "**(1) 弁別力（天井効果）**: 条件平均の範囲が狭く高得点なら judge が条件を見分けられていない。",
             "", "| ドメイン | 指標 | 最小 | 最大 | 範囲 | 判定 |", "|---|---|---|---|---|---|"]
    for dom, grp in [("HiddenBench", hb_grp), ("aiwolf", aw_grp)]:
        if grp is None:
            continue
        conds = [c for c in CONDS if c in grp]
        for key, _, lbl in _SUBJ:
            means = [_mean(grp[c].get(key, [])) for c in conds if grp[c].get(key)]
            if not means:
                continue
            lo, hi = min(means), max(means)
            flag = "⚠天井(弁別不可)" if (lo >= 4.5 and hi - lo < 0.3) else ("△弱" if hi - lo < 0.5 else "○")
            lines.append(f"| {dom} | {lbl} | {lo:.2f} | {hi:.2f} | {hi - lo:.2f} | {flag} |")
    common = [c for c in obj_overall if c in subj_overall]
    rho = _corr([obj_overall[c] for c in common], [subj_overall[c] for c in common])
    lines += ["",
              f"**(2) 客観順位 vs 主観順位の一致（総合, rank corr）**: ρ={rho:.2f} "
              "（+1=一致, 0=無相関, 負=逆）。低い/負なら主観は客観と別物を測っている疑い。",
              "", "主観がjudge天井で潰れている／客観と乖離する場合、結論は客観主体で述べ、"
              "主観は本番（別系統の強judge）で測り直すのが安全。"]
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
    aw_grp = _group(Path(args.aiwolf)) if args.aiwolf and Path(args.aiwolf).exists() else None

    _ns = [len(next(iter(hb_grp[c].values()), [])) for c in CONDS if c in hb_grp] or [0]
    _nmin, _nmax = min(_ns), max(_ns)
    _ncap = f"n={_nmin}" if _nmin == _nmax else f"n={_nmin}–{_nmax}"

    # OBJECTIVE and SUBJECTIVE aggregated SEPARATELY (subjective judge can be unreliable).
    obj_md, obj_overall = ranking_group(
        "客観 (Objective)", "正答率・統合ゲイン（HBのみ）＋同調/独立・多様性・収束。LLM不使用の計測指標。",
        hb_grp, aw_grp, HB_OBJ, AIWOLF_OBJ)
    subj_md, subj_overall = ranking_group(
        "主観 (Subjective)", "LLM-judge の 自然さ・噛み合い・話題展開（1-5）。妥当性は下の診断を参照。",
        hb_grp, aw_grp, HB_SUBJ, AIWOLF_SUBJ)
    valid_md = subjective_validity(hb_grp, aw_grp, obj_overall, subj_overall)

    body = "\n".join([
        "# 条件ランキング（客観／主観 分離） / Condition rankings — objective vs subjective\n",
        "各指標で順位付け（同点=平均順位）→ 平均で各ドメイン順位 → ドメイン等重みで総合。"
        f"gold・human はランキング除外。HiddenBench {_ncap}（条件あたりゲーム数）。\n",
        obj_md, subj_md, valid_md,
    ])
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
