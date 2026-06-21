"""Lightweight tokenization for transcript metrics (EN whitespace / JP char fallback).

トランスクリプト指標用の軽量トークナイザ (英語=空白 / 日本語=文字フォールバック).

We deliberately avoid heavy tokenizers (MeCab, sentencepiece) so the eval module has no
system dependencies. distinct-n is computed over these tokens; the README states the
convention explicitly (Li et al. 2016 divide by total tokens). For Japanese, where
whitespace is sparse, we fall back to character tokens — state this in the paper.

重い形態素解析を避け依存ゼロにする. distinct-n はこのトークン列で計算し, 規約は明記する
(Li et al. 2016 は総トークン数で割る). 日本語は空白が少ないため文字単位にフォールバックする.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str, lang: str = "en") -> list[str]:
    """Tokenize text into a list of tokens / テキストをトークン列へ分割する.

    Args:
        text: Input text / 入力テキスト.
        lang: ``en`` -> word tokens; ``jp``/``ja`` -> character tokens (whitespace-free) /
            ``en`` は単語, ``jp``/``ja`` は文字単位.

    Returns:
        list[str]: tokens / トークン列.
    """
    text = (text or "").strip()
    if not text:
        return []
    if lang.lower() in {"jp", "ja"}:
        return [c for c in text if not c.isspace()]
    return _WORD_RE.findall(text.lower())


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    """Return the list of n-grams of ``tokens`` / トークン列のn-gramを返す."""
    if n <= 0 or len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
