"""Information surfacing rate (hidden-profile disclosure) — SELF-DEFINED metric.

情報表面化率 (隠れプロファイルの開示) — 自作指標.

IMPORTANT (defensibility): HiddenBench (Li et al., arXiv:2505.11556) does NOT define a
transcript surfacing-rate formula. This is our adaptation of the classic free-recall /
mention measure of Stasser & Titus (1985, JPSP) and the "information coverage" of Lu,
Yuan & McLeod (2012). Label it as a self-defined metric in the paper, and prefer an
LLM-judge per clue as a robustness check over this rule-based matcher.

重要: HiddenBenchは表面化率の式を定義していない. 本指標は Stasser&Titus(1985)/Lu(2012)の
言及測度の自作適応である. 論文では自作と明記し, LLM審査での裏取りを推奨.

Definition / 定義:
    surfacing_rate = (# distinct hidden facts surfaced) / (# total hidden facts)
A hidden fact is "surfaced" if some single utterance shares at least ``threshold`` of the
fact's distinctive content tokens (rule-based overlap). / ある発話が当該事実の特徴語の
``threshold`` 割合以上を含めば「表面化した」とみなす.
"""

from __future__ import annotations

from tokenize_text import tokenize

# Short, generic tokens carry little identifying signal; ignore them when matching facts.
_MIN_TOKEN_LEN = 4


def _content_tokens(text: str, lang: str) -> set[str]:
    toks = tokenize(text, lang)
    if lang.lower() in {"jp", "ja"}:
        # Character tokens: use overlapping bigrams as the matching unit for JP.
        return {"".join(toks[i : i + 2]) for i in range(len(toks) - 1)} or set(toks)
    return {t for t in toks if len(t) >= _MIN_TOKEN_LEN}


def fact_surfaced(fact: str, utterances: list[str], lang: str, threshold: float) -> bool:
    """Whether ``fact`` is surfaced by any single utterance / 事実が表面化したか."""
    fact_tokens = _content_tokens(fact, lang)
    if not fact_tokens:
        return False
    for utt in utterances:
        utt_tokens = _content_tokens(utt, lang)
        if not utt_tokens:
            continue
        overlap = len(fact_tokens & utt_tokens) / len(fact_tokens)
        if overlap >= threshold:
            return True
    return False


def surfacing_rate(
    hidden_facts: list[str],
    utterances: list[str],
    lang: str = "en",
    threshold: float = 0.5,
) -> dict[str, float | list[bool]]:
    """Compute the surfacing rate over the hidden facts / 隠し事実の表面化率を計算.

    Returns a dict with the rate and per-fact booleans / 表面化率と事実別フラグを返す.
    """
    flags = [fact_surfaced(f, utterances, lang, threshold) for f in hidden_facts]
    rate = (sum(flags) / len(flags)) if flags else 0.0
    return {"surfacing_rate": rate, "per_fact_surfaced": flags, "num_hidden": len(flags)}


def first_round_each_fact_surfaced(
    hidden_facts: list[str],
    rounds_utterances: list[list[str]],
    lang: str = "en",
    threshold: float = 0.5,
) -> list[int | None]:
    """For each hidden fact, the earliest round index it is surfaced (or None).

    各隠し事実が最初に表面化したラウンド番号 (未表面化はNone). 早期収束の判定に使う.
    """
    result: list[int | None] = []
    for fact in hidden_facts:
        found: int | None = None
        cumulative: list[str] = []
        for r, utts in enumerate(rounds_utterances):
            cumulative.extend(utts)
            if fact_surfaced(fact, cumulative, lang, threshold):
                found = r
                break
        result.append(found)
    return result
