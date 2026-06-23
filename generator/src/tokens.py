"""Approximate token counting for the ③ utterance ↔ ⑤ script token-match check.

③発話few-shot ↔ ⑤台本few-shot のトークン一致確認用の近似トークン計測.

METHODOLOGY: the *authoritative* match is measured with the discussion agent's (Gemma's)
tokenizer and reported per cell. This module provides a fast, dependency-free *approximation*
used during generation to report the ratio and flag large mismatches; it is intentionally
labelled "approximate" (config ``token_match: approximate``). Re-measure with Gemma's
tokenizer before publishing the per-cell token table.
"""

from __future__ import annotations


def _is_cjk(ch: str) -> bool:
    """Return whether ``ch`` is a CJK character (counted as one token).

    文字が CJK (1 文字 ≒ 1 トークン換算) かどうかを返す.
    """
    code = ord(ch)
    return (
        0x3040 <= code <= 0x30FF  # hiragana + katakana
        or 0x4E00 <= code <= 0x9FFF  # CJK unified ideographs
        or 0x3400 <= code <= 0x4DBF  # CJK extension A
        or 0xFF00 <= code <= 0xFFEF  # full-width forms
    )


def approx_tokens(text: str) -> int:
    """Return an approximate token count for ``text``.

    ``text`` の近似トークン数を返す. CJK は 1 文字 1 トークン, 非 CJK は概ね 4 文字 1 トークン.

    Args:
        text: Input text (any mix of CJK / Latin).

    Returns:
        An approximate, deterministic token count.
    """
    cjk = sum(1 for ch in text if _is_cjk(ch))
    non_cjk_chars = sum(1 for ch in text if not _is_cjk(ch) and not ch.isspace())
    return cjk + (non_cjk_chars + 3) // 4
