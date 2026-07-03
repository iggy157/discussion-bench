"""Bootstrap the condition rankings to measure how RELIABLE the average-rank ordering is.

平均順位ランキングの信憑性（安定性）をブートストラップで測る。

The headline `rankings.md` collapses each metric to one number per condition, ranks the 6
conditions, and averages the ranks. With near-tied / ceiling / noisy metrics that average-rank is
fragile: a tiny mean difference flips a 1st into a 6th. This script resamples the per-game results
(with replacement, within each condition) B times, recomputes the whole average-rank each time, and
reports the DISTRIBUTION of each condition's rank — mean±std, 90% CI, and P(rank==1)/P(top-2).
Wide/overlapping CIs ⇒ the ordering is mostly noise; tight, separated CIs ⇒ trustworthy.

平均順位は僅差を増幅する。ゲームを条件内で復元抽出してB回順位を再計算し、各条件の順位分布
（平均±SD・90%CI・1位確率・top2確率）を出す。CIが広く重なれば順位はノイズ、狭く分離すれば信頼できる。

Usage:
    python eval/src/rankings_stability.py --hb <hb_metrics.json> [--aiwolf <aiwolf_metrics.json>] \
        [--b 2000] [--seed 0]
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import statistics
from pathlib import Path
from typing import Any

CONDS = ["baseline", "analysis_only", "utterance_fewshot", "utterance_fewshot_analysis",
         "situation_fewshot", "situation_fewshot_analysis", "script_fewshot", "script_fewshot_analysis"]
SHORT = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
         "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
         "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
         "script_fewshot_analysis": "⑧scr+a"}

_ACC = [("post_accuracy", +1), ("integration_gain", +1)]
_OBJ_SHARED = [
    ("conformity_conformity_rate", -1), ("conformity_independence_rate", +1),
    ("distinct_1", +1), ("distinct_2", +1), ("self_repetition_diversity", +1),
    ("convergence_round", +1),
]
_SUBJ = [("subj_naturalness", +1), ("subj_coherence", +1), ("subj_topic_development", +1)]
# Objective vs subjective aggregated separately (subjective judge can be unreliable).
HB_OBJ = _ACC + _OBJ_SHARED
AIWOLF_OBJ = _OBJ_SHARED
HB_SUBJ = _SUBJ
AIWOLF_SUBJ = _SUBJ
HB_METRICS = HB_OBJ + _SUBJ  # back-compat
AIWOLF_METRICS = AIWOLF_OBJ + _SUBJ


def _per_game(path: Path) -> dict[str, list[dict[str, float]]]:
    """condition -> list of per-game metric dicts (numeric only) / 条件->ゲーム毎の数値dict列."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[dict[str, float]]] = collections.defaultdict(list)
    for r in data.get("per_game", []):
        c = r.get("condition")
        if c not in CONDS:
            continue
        row = {}
        for k, v in r.items():
            if isinstance(v, bool):
                row[k] = 1.0 if v else 0.0
            elif isinstance(v, (int, float)):
                row[k] = float(v)
        out[c].append(row)
    return out


def _avg_ranks(values: dict[str, float], direction: int) -> dict[str, float]:
    """Best=1; ties get the average rank / 最良=1, 同点は平均順位."""
    ordered = sorted(values, key=lambda c: values[c], reverse=(direction > 0))
    ranks: dict[str, float] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and values[ordered[j + 1]] == values[ordered[i]]:
            j += 1
        avg = sum(range(i + 1, j + 2)) / (j - i + 1)
        for k in range(i, j + 1):
            ranks[ordered[k]] = avg
        i = j + 1
    return ranks


def _mean_rank_once(sample: dict[str, list[dict[str, float]]], metrics: list[tuple[str, int]]) -> dict[str, float]:
    """One average-rank vector over conditions for a given (re)sample / 1標本での平均順位ベクトル."""
    conds = [c for c in CONDS if sample.get(c)]
    per_metric: dict[str, list[float]] = {c: [] for c in conds}
    for key, direction in metrics:
        means = {}
        for c in conds:
            vals = [g[key] for g in sample[c] if key in g]
            if vals:
                means[c] = statistics.mean(vals)
        if len(means) < 2:
            continue
        ranks = _avg_ranks(means, direction)
        for c in means:
            per_metric[c].append(ranks[c])
    return {c: statistics.mean(rs) for c, rs in per_metric.items() if rs}


def _resample(pg: dict[str, list[dict[str, float]]], rnd: random.Random) -> dict[str, list[dict[str, float]]]:
    """Resample games WITH REPLACEMENT within each condition / 条件内で復元抽出."""
    return {c: [games[rnd.randrange(len(games))] for _ in games] for c, games in pg.items() if games}


def bootstrap(pg_hb: dict, pg_aw: dict | None, b: int, seed: int,
              hb_metrics: list, aw_metrics: list) -> dict[str, Any]:
    """Per-condition rank distributions (HB / aiwolf / overall) for ONE metric set."""
    rnd = random.Random(seed)
    dists: dict[str, dict[str, list[float]]] = {d: collections.defaultdict(list) for d in ("hb", "aiwolf", "overall")}
    for _ in range(b):
        hb_s = _resample(pg_hb, rnd)
        hb_rank = _mean_rank_once(hb_s, hb_metrics)
        for c, v in hb_rank.items():
            dists["hb"][c].append(v)
        aw_rank = {}
        if pg_aw:
            aw_s = _resample(pg_aw, rnd)
            aw_rank = _mean_rank_once(aw_s, aw_metrics)
            for c, v in aw_rank.items():
                dists["aiwolf"][c].append(v)
        for c in CONDS:
            comps = [r[c] for r in (hb_rank, aw_rank) if c in r]
            if comps:
                dists["overall"][c].append(statistics.mean(comps))
    return dists


def _pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    if not s:
        return float("nan")
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def _report(name: str, dist: dict[str, list[float]], b: int) -> str:
    lines = [f"\n### {name}", "| 条件 | 平均順位 | SD | 90%CI | P(1位) | P(top2) | 最終順位 |", "|---|---|---|---|---|---|---|"]
    order = sorted(dist, key=lambda c: statistics.mean(dist[c]))
    # final rank per bootstrap → P(rank==1), P(top2)
    n_iter = max((len(v) for v in dist.values()), default=0)
    p1 = collections.Counter()
    ptop2 = collections.Counter()
    for i in range(n_iter):
        snap = {c: dist[c][i] for c in dist if i < len(dist[c])}
        ordr = sorted(snap, key=lambda c: snap[c])
        if ordr:
            p1[ordr[0]] += 1
        for c in ordr[:2]:
            ptop2[c] += 1
    for pos, c in enumerate(order, 1):
        xs = dist[c]
        mean = statistics.mean(xs)
        sd = statistics.pstdev(xs) if len(xs) > 1 else 0.0
        lo, hi = _pct(xs, 0.05), _pct(xs, 0.95)
        lines.append(f"| {SHORT.get(c, c)} | {mean:.2f} | {sd:.2f} | [{lo:.2f}, {hi:.2f}] | "
                     f"{100*p1[c]/max(1,n_iter):.0f}% | {100*ptop2[c]/max(1,n_iter):.0f}% | {pos} |")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Bootstrap reliability of the condition rankings")
    p.add_argument("--hb", required=True)
    p.add_argument("--aiwolf", default=None)
    p.add_argument("--b", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default=None, help="optional .md output")
    args = p.parse_args()

    pg_hb = _per_game(Path(args.hb))
    pg_aw = _per_game(Path(args.aiwolf)) if args.aiwolf and Path(args.aiwolf).exists() else None
    n_hb = statistics.mean([len(v) for v in pg_hb.values()]) if pg_hb else 0
    n_aw = statistics.mean([len(v) for v in pg_aw.values()]) if pg_aw else 0

    parts = [f"# ランキング信頼性（ブートストラップ B={args.b}, n_HB≈{n_hb:.0f}, n_aiwolf≈{n_aw:.0f}）",
             "順位を1位=最良で算出。SD・90%CIが大きい/重なるほど順位はノイズ（ゲーム数を増やすと縮むが、"
             "天井・飽和指標の差は増えない）。P(1位)・P(top2)は復元抽出での順位安定性。",
             "**客観**（正答率/統合/distinct/同調/収束 等の計算指標）と**主観**（judgeのLikert 3指標）"
             "を分けて集計（主観judge=gemmaは天井効果で弁別が弱い→[主観の妥当性] 節を参照）。"]
    for grp_name, hb_m, aw_m in (("客観 (Objective)", HB_OBJ, AIWOLF_OBJ),
                                 ("主観 (Subjective)", HB_SUBJ, AIWOLF_SUBJ)):
        dists = bootstrap(pg_hb, pg_aw, args.b, args.seed, hb_m, aw_m)
        parts.append(f"\n## {grp_name}")
        parts.append(_report("HiddenBench", dists["hb"], args.b))
        if pg_aw:
            parts.append(_report("aiwolf", dists["aiwolf"], args.b))
            parts.append(_report("総合 / Overall", dists["overall"], args.b))
    text = "\n".join(parts) + "\n"
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
