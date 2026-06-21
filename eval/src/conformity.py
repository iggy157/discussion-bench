"""Conformity / independence proxies via per-round stance polling — ADAPTED metric.

同調率・独立率の代理指標 (ラウンド毎の立場ポーリング) — 適応指標.

IMPORTANT (defensibility, verified against primary sources): BenchForm (Weng, Chen & Wang,
ICLR2025, arXiv:2501.13381) defines Conformity Rate and Independence Rate for a
scripted-confederate reasoning-QA setup with a Raw solo baseline. Its CR = |Q✗^P ∩ Q✓^R| /
|Q✓^R| (correct-under-Raw answers that flip to wrong under misleading protocol P), and its
IR = |Q✓^T ∩ Q✓^D ∩ Q✓^R| / |Q✓^R| is a CONJUNCTIVE robustness measure (correct under both
Trust AND Doubt) — explicitly NOT 1 - CR. BenchForm extracts answers by RULE-BASED string
parsing (not an LLM).

Our setting (self-play free discussion, no Raw baseline, no scripted confederate, known
option set) cannot use BenchForm's formula as-is. We report an ADAPTATION: restrict to
transitions where an agent is in the minority vs the majority-of-others (this replaces the
confederate-induced pressure), then measure flip-vs-hold. By construction our
independence_rate = 1 - conformity_rate within that pressured population — this differs from
BenchForm's conjunctive IR, and we say so. Cf. the per-round re-prompt + correct->incorrect
transition taxonomy of "Talk Isn't Always Cheap" (Wynn et al., arXiv:2509.05396).

重要(一次資料で確認): BenchFormのCR/IRは台本付き推論QA＋Raw基準線向けで, IRはTrust∩Doubtの
連言(=1-CRではない), 抽出はルールベース. 自由議論(自己対戦)では基準線も台本も無いため厳密適用
できず, 「多数派に対し少数派のとき」の反転/維持にもとづく適応版を報告する. 我々のIRは構成上
1-CR（BenchFormの連言IRとは別物）であることを明記する.

Proxy definitions / 代理定義 (per agent, across the rounds it speaks):
- conformity_flip: agent's stance changes to match the majority-of-others at the previous
  round, when it previously disagreed with that majority.
- independence_hold: agent disagrees with the majority-of-others and KEEPS its stance.
- conformity_rate = conformity_flips / (conformity_flips + independence_holds)
  i.e. of all moments under majority pressure, the fraction where the agent caved.
"""

from __future__ import annotations

from stance import majority


def _majority_of_others(round_stances_by_agent: dict[str, str | None], me: str) -> str | None:
    others = [s for a, s in round_stances_by_agent.items() if a != me]
    return majority(others)


def conformity_independence(
    agent_round_stances: dict[str, list[str | None]],
) -> dict[str, float | int]:
    """Compute the adapted conformity/independence proxies / 適応同調/独立代理を計算.

    Args:
        agent_round_stances: agent name -> list of stances, one per round (None = no
            resolvable stance that round) / エージェント名 -> ラウンド毎の立場列.

    Returns:
        dict with conformity_flips, independence_holds, conformity_rate, independence_rate.
    """
    agents = list(agent_round_stances)
    num_rounds = max((len(v) for v in agent_round_stances.values()), default=0)
    flips = 0
    holds = 0
    for r in range(1, num_rounds):
        prev = {a: agent_round_stances[a][r - 1] if r - 1 < len(agent_round_stances[a]) else None for a in agents}
        cur = {a: agent_round_stances[a][r] if r < len(agent_round_stances[a]) else None for a in agents}
        for a in agents:
            maj_others_prev = _majority_of_others(prev, a)
            if maj_others_prev is None or prev[a] is None or cur[a] is None:
                continue
            disagreed = prev[a] != maj_others_prev
            if not disagreed:
                continue
            if cur[a] == maj_others_prev:
                flips += 1  # caved to the prior majority of others
            else:
                holds += 1  # kept its independent stance
    denom = flips + holds
    conformity_rate = flips / denom if denom else 0.0
    independence_rate = holds / denom if denom else 0.0
    return {
        "conformity_flips": flips,
        "independence_holds": holds,
        "conformity_rate": conformity_rate,
        "independence_rate": independence_rate,
    }
