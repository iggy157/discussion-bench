"""Per-utterance stance extraction over a known option set (rule-based).

既知の選択肢集合に対する発話単位の立場抽出 (ルールベース).

Used by convergence and conformity metrics. For HiddenBench the option set is known, so a
message's stance is the option it most plausibly endorses (last-mentioned option wins,
approximating a concluding lean). For free-form domains without an option set, supply an
LLM-extracted stance instead (hook left to the caller). This is an explicit operational
choice — state it in the paper.

合意・同調指標で使用. HiddenBenchは選択肢が既知なので, 発話の立場 = 最後に言及した選択肢で近似する.
選択肢の無い自由ドメインではLLM抽出の立場を渡す (呼び出し側のフック).
"""

from __future__ import annotations


def stance_of(text: str, options: list[str]) -> str | None:
    """Return the option a message most plausibly endorses, or None / 発話の立場を返す."""
    low = (text or "").lower()
    best: str | None = None
    best_pos = -1
    for opt in options:
        pos = low.rfind(opt.strip().lower())
        if pos > best_pos:
            best_pos = pos
            best = opt
    return best


def majority(stances: list[str | None]) -> str | None:
    """Strict majority option among non-None stances (None if tie/empty) / 厳密多数."""
    counts: dict[str, int] = {}
    for s in stances:
        if s is not None:
            counts[s] = counts.get(s, 0) + 1
    if not counts:
        return None
    top = max(counts.values())
    leaders = [k for k, v in counts.items() if v == top]
    if len(leaders) != 1:
        return None
    if top <= len([s for s in stances if s is not None]) / 2:
        return None
    return leaders[0]
