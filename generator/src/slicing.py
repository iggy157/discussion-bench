"""Derive the ③ utterance few-shot slot by slicing utterances from a ⑤ script.

⑤台本から ③発話few-shot スロットを「スライス」して導出する.

This is the fairness backbone (METHODOLOGY L112-113 / EXEMPLARS control 3): the utterance
few-shot examples are the SAME utterances taken from the SAME script, with the whole-discussion
flow removed (round/turn structure dropped, order shuffled, speaker attribution stripped). The
only manipulated variable between ③ and ⑤ is the *presentation form*, never the content — so
"③ got a weaker/different prompt than ⑤" cannot be argued. Claude is NOT called again here.
"""

from __future__ import annotations

import random
import re

# Bullet utterance line: ``- **Speaker**: text``.
_UTTERANCE_RE = re.compile(r"^- \*\*(?P<speaker>.+?)\*\*:\s*(?P<text>.+)$")
# Section headers to SKIP when slicing (private/structured, not free discussion). Talk lines use
# ``- **name**: text`` and only appear under talk sections; vote/night/result lines use a
# ``- label: ...`` form (no bold name) so they already fail the utterance regex, but we also skip
# their sections defensively so role-revealing night results can never leak into ③.
_SKIP_SECTION_MARKERS = (
    "囁き",  # werewolf whisper (none in 5p, but be safe)
    "whisper",
    "pre-answer",
    "post-answer",
    "事前回答",
    "事後回答",
    "投票",  # vote
    "vote",
    "夜",  # night (divine / attack)
    "night",
    "決着",  # result / outcome
    "result",
)
# A line is a section header if it starts with ``#`` or ``###``.
_HEADER_RE = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")
# Inline pre/post-answer label at the START of an utterance (robustness for scripts that label
# answers inline instead of under a ``## …`` section — e.g. ``- **Agent 1**: 事後回答: {...}``).
# These carry the vote (the answer), so they must NOT leak into the utterance few-shot.
_INLINE_ANSWER_LABEL_RE = re.compile(
    r"^(?:事前回答|事後回答|pre-?answers?|post-?answers?)\s*[:：]",
    re.IGNORECASE,
)
# Leading flow label to strip from kept utterances so each reads as a standalone example
# (e.g. ``ラウンド3: 本文`` / ``Round 2: text`` / ``0日目: …``). Removing it furthers the
# "whole-discussion flow removed" goal.
_LEADING_FLOW_LABEL_RE = re.compile(
    r"^(?:ラウンド\s*\d+|round\s*\d+|turn\s*\d+|\d+\s*日目)\s*[:：]\s*",
    re.IGNORECASE,
)


def extract_utterances(script_md: str) -> list[str]:
    """Return the free-discussion utterance texts from a script, in document order.

    台本から「自由議論」の発話本文を文書順で抽出する. 囁き・事前/事後回答 (JSON) のセクションは除外.
    見出しが無く回答がインライン (``事後回答: {...}`` 等) でラベル付けされていても除外する.

    Args:
        script_md: The full script markdown.

    Returns:
        Utterance bodies (speaker labels and leading round/turn labels stripped), excluding
        whisper / pre-answer / post-answer content (both section-headed and inline-labelled).
    """
    out: list[str] = []
    skip = False
    for line in script_md.splitlines():
        header = _HEADER_RE.match(line)
        if header:
            title = header.group("title").lower()
            skip = any(marker in title for marker in _SKIP_SECTION_MARKERS)
            continue
        if skip:
            continue
        m = _UTTERANCE_RE.match(line)
        if not m:
            continue
        text = m.group("text").strip()
        # Drop pre/post-answer lines even when labelled inline (no ``## …`` header) — they
        # carry the vote/answer and must not leak into the utterance few-shot.
        if _INLINE_ANSWER_LABEL_RE.match(text):
            continue
        # Strip a leading round/turn/day flow label so the utterance stands alone.
        text = _LEADING_FLOW_LABEL_RE.sub("", text).strip()
        # Drop structured (JSON-looking) lines (a bare answer, or one left after a label).
        if not text or text.startswith("{"):
            continue
        out.append(text)
    return out


def build_utterance_block(script_md: str, *, lang: str, seed: int) -> str:
    """Slice ``script_md`` into a shuffled, flow-free single-utterance few-shot block.

    台本を「流れを取り除いた」単発発話の few-shot ブロックに変換する.
    順序をシャッフルし話者ラベルを外すことで, 議論全体の流れ (誰が誰に応答したか等) を除去する.

    Args:
        script_md: The full script markdown (⑤).
        lang: ``en`` | ``jp`` (selects the header text).
        seed: Deterministic shuffle seed (use the script index for reproducibility).

    Returns:
        A markdown block of standalone example utterances (③). Empty utterances -> empty body.
    """
    utterances = extract_utterances(script_md)
    rng = random.Random(seed)
    rng.shuffle(utterances)

    if lang == "jp":
        header = (
            "# 良い議論で見られた発話例\n\n"
            "以下は、ある良い議論から抜き出した個々の発話例です（議論全体の流れは含みません）。\n"
        )
    else:
        header = (
            "# Example utterances from a good discussion\n\n"
            "The following are individual utterances sliced from a good discussion "
            "(the whole-discussion flow is not included).\n"
        )
    body = "\n".join(f"- {u}" for u in utterances)
    return f"{header}\n{body}\n"
