"""Early-convergence / premature-consensus metrics — SELF-DEFINED operationalization.

早期収束・尚早合意の指標 — 自作の操作化.

IMPORTANT (defensibility): HiddenBench names "premature convergence on shared evidence
while critical distributed facts remain unexplored" but gives NO formula. We define:
- convergence_round: the first round at which all speaking agents share one stance.
  (Terminal-agreement style; cf. Smit et al. ICML2024 final-round consensus; round-level
  resolution cf. Wu et al. arXiv:2511.07784.)
- premature_consensus: convergence_round occurs BEFORE all hidden facts have surfaced.
Label these self-defined in the paper.

重要: HiddenBenchは尚早収束の式を持たない. 本指標は自作の操作化 (Smit2024/Wu2025を参照).
"""

from __future__ import annotations

from stance import majority, stance_of


def per_round_stances(rounds_utterances: list[list[str]], options: list[str]) -> list[list[str | None]]:
    """Stance of each utterance per round / ラウンド毎の各発話の立場."""
    return [[stance_of(u, options) for u in utts] for utts in rounds_utterances]


def convergence_round(rounds_stances: list[list[str | None]]) -> int | None:
    """First round where every non-None stance agrees on one option / 全員一致の最初のラウンド.

    Returns the 0-based round index, or None if never converged / 未収束はNone.
    """
    for r, stances in enumerate(rounds_stances):
        resolved = [s for s in stances if s is not None]
        if resolved and len(set(resolved)) == 1:
            return r
    return None


def premature_consensus(
    conv_round: int | None,
    fact_surfaced_rounds: list[int | None],
) -> bool:
    """Whether consensus was reached before all hidden facts surfaced / 尚早合意か.

    True iff the group converged AND at that round at least one hidden fact had not yet
    surfaced (or never surfaced). / 収束時点で未表面化の隠し事実が残っていれば True.
    """
    if conv_round is None:
        return False
    for fr in fact_surfaced_rounds:
        if fr is None or fr > conv_round:
            return True
    return False


def consensus_agreement_rate(rounds_stances: list[list[str | None]]) -> float:
    """Fraction of the final round's resolved stances agreeing with its majority.

    最終ラウンドの解決済み立場のうち多数派と一致する割合 (終端合意率).
    """
    if not rounds_stances:
        return 0.0
    final = [s for s in rounds_stances[-1] if s is not None]
    if not final:
        return 0.0
    maj = majority(rounds_stances[-1])
    if maj is None:
        # No strict majority: agreement is the largest bloc share.
        counts: dict[str, int] = {}
        for s in final:
            counts[s] = counts.get(s, 0) + 1
        return max(counts.values()) / len(final)
    return sum(1 for s in final if s == maj) / len(final)
