"""Evaluate HiddenBench game-result JSON into failure-mode metrics + a bilingual report.

HiddenBenchの結果JSONを失敗様態指標へ集計し, 日英レポートを書き出す.

Consumes the per-game JSON written by hiddenbench-server (game.GameResult). Computes, per
game and aggregated across games:
  - Accuracy family (HiddenBench-native): pre/post accuracy, integration gain, majority.
  - Information surfacing rate (self-defined; Stasser&Titus/Lu adaptation).
  - Early convergence: convergence round, premature-consensus flag, terminal agreement.
  - Diversity/stagnation: distinct-1, distinct-2, self-repetition diversity.
  - Conformity/independence proxies (BenchForm-adapted).
All non-native metrics are flagged in the report. See INLG_METHODOLOGY.md §4.

werewolf logs use a different schema; a thin transcript extractor can feed the same
domain-general metrics (distinct-n / convergence / conformity) later.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from conformity import conformity_independence
from convergence import (
    consensus_agreement_rate,
    convergence_round,
    per_round_stances,
    premature_consensus,
)
from diversity import distinct_n, self_repetition_diversity
from surfacing import first_round_each_fact_surfaced, surfacing_rate

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("inlg.eval")


def _rounds_from_transcript(transcript: list[dict[str, Any]]) -> tuple[list[list[str]], dict[str, list[str]]]:
    """Group transcript into per-round utterance lists + per-agent utterance lists.

    トランスクリプトをラウンド毎/エージェント毎の発話列に整理する.
    Round index = the ``day`` field set by the server (discussion round).
    """
    by_round: dict[int, list[str]] = defaultdict(list)
    by_agent: dict[str, list[str]] = defaultdict(list)
    for t in transcript:
        by_round[int(t.get("day", 0))].append(t.get("text", ""))
        by_agent[str(t.get("agent", "?"))].append(t.get("text", ""))
    rounds = [by_round[r] for r in sorted(by_round)]
    return rounds, dict(by_agent)


def _agent_round_stances(transcript: list[dict[str, Any]], options: list[str]) -> dict[str, list[str | None]]:
    """Per-agent stance per round (last utterance of the agent that round) / 立場列."""
    from stance import stance_of  # local import to keep module import graph flat

    rounds = sorted({int(t.get("day", 0)) for t in transcript})
    agents = sorted({str(t.get("agent", "?")) for t in transcript})
    table: dict[str, list[str | None]] = {a: [None] * len(rounds) for a in agents}
    round_index = {r: i for i, r in enumerate(rounds)}
    for t in transcript:
        a = str(t.get("agent", "?"))
        ri = round_index[int(t.get("day", 0))]
        s = stance_of(t.get("text", ""), options)
        if s is not None:
            table[a][ri] = s
    return table


def evaluate_game(result: dict[str, Any], threshold: float = 0.5) -> dict[str, Any]:
    """Compute all metrics for one HiddenBench game / 1ゲームの全指標を計算する."""
    lang = str(result.get("lang", "en"))
    options = list((result.get("metadata") or {}).get("options") or _infer_options(result))
    hidden = list((result.get("metadata") or {}).get("hidden_information") or [])
    transcript = list(result.get("transcript") or [])
    rounds_utts, by_agent = _rounds_from_transcript(transcript)
    all_utts = [t.get("text", "") for t in transcript]

    surf = surfacing_rate(hidden, all_utts, lang, threshold)
    fact_rounds = first_round_each_fact_surfaced(hidden, rounds_utts, lang, threshold)
    rstances = per_round_stances(rounds_utts, options)
    conv = convergence_round(rstances)

    return {
        "game_id": result.get("game_id"),
        "task_id": result.get("task_id"),
        "condition": result.get("condition"),
        "lang": lang,
        # --- HiddenBench-native accuracy family ---
        "pre_accuracy": result.get("pre_accuracy"),
        "post_accuracy": result.get("post_accuracy"),
        "integration_gain": result.get("integration_gain"),
        "post_majority_correct": result.get("post_majority_correct"),
        # --- information surfacing (self-defined) ---
        "surfacing_rate": surf["surfacing_rate"],
        "num_hidden": surf["num_hidden"],
        # --- early convergence (self-defined) ---
        "convergence_round": conv,
        "premature_consensus": premature_consensus(conv, fact_rounds),
        "terminal_agreement_rate": consensus_agreement_rate(rstances),
        # --- diversity / stagnation ---
        "distinct_1": distinct_n(all_utts, 1, lang),
        "distinct_2": distinct_n(all_utts, 2, lang),
        "self_repetition_diversity": self_repetition_diversity(by_agent, lang),
        # --- conformity (BenchForm-adapted proxy) ---
        **{f"conformity_{k}": v for k, v in conformity_independence(_agent_round_stances(transcript, options)).items()},
    }


def _infer_options(result: dict[str, Any]) -> list[str]:
    """Best-effort recovery of the option set from decisions / 選択肢の復元 (フォールバック)."""
    opts: list[str] = []
    for bucket in ("post_decisions", "pre_decisions"):
        for d in (result.get(bucket) or {}).values():
            o = d.get("option")
            if o and o not in opts:
                opts.append(o)
    if result.get("correct_answer") and result["correct_answer"] not in opts:
        opts.append(result["correct_answer"])
    return opts


def _mean(values: list[float]) -> float:
    vals = [v for v in values if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else 0.0


def aggregate(per_game: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-game metrics by condition (and overall) / 条件別 (+全体) に集計."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for g in per_game:
        groups[str(g.get("condition", "unknown"))].append(g)
    groups["__all__"] = list(per_game)

    numeric_keys = [
        "pre_accuracy",
        "post_accuracy",
        "integration_gain",
        "surfacing_rate",
        "terminal_agreement_rate",
        "distinct_1",
        "distinct_2",
        "self_repetition_diversity",
        "conformity_conformity_rate",
        "conformity_independence_rate",
    ]
    # Subjective LLM-judge keys (subj_*) are included when present (make judge).
    subj_keys = sorted({k for g in per_game for k in g if k.startswith("subj_")})
    out: dict[str, Any] = {}
    for cond, games in groups.items():
        agg = {"n_games": len(games)}
        for k in numeric_keys + subj_keys:
            agg[k] = _mean([g.get(k) for g in games])
        agg["premature_consensus_rate"] = _mean([1.0 if g.get("premature_consensus") else 0.0 for g in games])
        agg["post_majority_correct_rate"] = _mean([1.0 if g.get("post_majority_correct") else 0.0 for g in games])
        conv_rounds = [g.get("convergence_round") for g in games if g.get("convergence_round") is not None]
        agg["mean_convergence_round"] = _mean(conv_rounds) if conv_rounds else None
        agg["converged_fraction"] = _mean([0.0 if g.get("convergence_round") is None else 1.0 for g in games])
        out[cond] = agg
    return out


_LABELS = {
    "pre_accuracy": ("事前正答率", "Pre-discussion accuracy"),
    "post_accuracy": ("事後正答率 (主指標)", "Post-discussion accuracy (primary)"),
    "integration_gain": ("情報統合ゲイン", "Information integration gain"),
    "post_majority_correct_rate": ("事後多数決正答率", "Post majority-correct rate"),
    "surfacing_rate": ("情報表面化率※自作", "Information surfacing rate*self-defined"),
    "premature_consensus_rate": ("尚早合意率※自作", "Premature-consensus rate*self-defined"),
    "mean_convergence_round": ("平均収束ラウンド※自作", "Mean convergence round*self-defined"),
    "converged_fraction": ("収束した割合", "Converged fraction"),
    "terminal_agreement_rate": ("終端合意率", "Terminal agreement rate"),
    "distinct_1": ("distinct-1", "distinct-1"),
    "distinct_2": ("distinct-2", "distinct-2"),
    "self_repetition_diversity": ("自己反復多様性", "Self-repetition diversity"),
    "conformity_conformity_rate": ("同調率※適応", "Conformity rate*adapted"),
    "conformity_independence_rate": ("独立率※適応", "Independence rate*adapted"),
}


def render_markdown(agg: dict[str, Any]) -> str:
    """Render the aggregate as a bilingual Markdown report / 集計を日英Markdownへ整形."""
    lines = [
        "# INLG evaluation report / INLG評価レポート",
        "",
        "Metrics marked `*self-defined` / `*adapted` are NOT verbatim from the cited "
        "source — see INLG_METHODOLOGY.md §4. / `*自作`・`*適応` は出典の式そのままではない.",
        "",
    ]
    conds = [c for c in agg if c != "__all__"] + (["__all__"] if "__all__" in agg else [])
    header = ["metric / 指標", *conds]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    metric_order = [
        "n_games",
        "pre_accuracy",
        "post_accuracy",
        "integration_gain",
        "post_majority_correct_rate",
        "surfacing_rate",
        "premature_consensus_rate",
        "mean_convergence_round",
        "converged_fraction",
        "terminal_agreement_rate",
        "distinct_1",
        "distinct_2",
        "self_repetition_diversity",
        "conformity_conformity_rate",
        "conformity_independence_rate",
    ]
    # Append any subjective LLM-judge rows present (make judge).
    subj_keys = sorted({k for c in agg for k in agg[c] if k.startswith("subj_")})
    for m in metric_order + subj_keys:
        jp, en = _LABELS.get(m, (m.replace("subj_", "subjective: "), m.replace("subj_", "主観: ")))
        label = m if m == "n_games" else f"{en} / {jp}"
        row = [label]
        for c in conds:
            v = agg[c].get(m)
            row.append("-" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    """CLI: read result JSONs from a dir, write metrics.json + report.md / CLIエントリ."""
    parser = argparse.ArgumentParser(description="Evaluate HiddenBench results into failure-mode metrics")
    parser.add_argument("results_dir", type=str, help="directory of per-game *.json (hiddenbench-server output)")
    parser.add_argument("-o", "--out", type=str, default=None, help="output dir (default: <results_dir>/eval)")
    parser.add_argument("--threshold", type=float, default=0.5, help="surfacing token-overlap threshold")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out) if args.out else results_dir / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(results_dir.glob("*.json"))
    per_game = []
    for fp in files:
        try:
            with fp.open(encoding="utf-8") as f:
                result = json.load(f)
            per_game.append(evaluate_game(result, threshold=args.threshold))
        except Exception:
            logger.exception("failed to evaluate %s", fp)
    agg = aggregate(per_game)

    with (out_dir / "metrics.json").open("w", encoding="utf-8") as f:
        json.dump({"per_game": per_game, "aggregate": agg}, f, ensure_ascii=False, indent=2)
    (out_dir / "report.md").write_text(render_markdown(agg), encoding="utf-8")
    logger.info("evaluated %d game(s) -> %s", len(per_game), out_dir)
    print(render_markdown(agg))


if __name__ == "__main__":
    main()
