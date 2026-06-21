"""Diversity / stagnation metrics (distinct-n, Self-BLEU-style self-repetition).

多様性・停滞指標 (distinct-n, Self-BLEU風の自己反復).

Citations (see INLG_METHODOLOGY.md §4.2):
- distinct-1 / distinct-2: Li, Galley, Brockett, Gao & Dolan (2016), NAACL, arXiv:1510.03055.
  Convention here: (# distinct n-grams) / (# total tokens). Stated explicitly per the
  paper; some reimplementations divide by total n-grams instead.
- Self-repetition diversity: adaptation of Liang et al. (2024), EMNLP, arXiv:2305.19118
  ("Diversity = 100 - Self-BLEU"). We compute a dependency-free Self-BLEU surrogate using
  modified n-gram precision (BLEU-style) between an utterance and the agent's own prior
  utterances. NOT corpus-level Self-BLEU of Zhu et al. 2018 — flagged as an adaptation.

NOTE: DMAD (ICLR2025) does NOT define semantic/self-repetition diversity; do not cite it
for these. / DMADは意味的多様性を定義していないので, ここでは引用しない.
"""

from __future__ import annotations

from collections import Counter

from tokenize_text import ngrams, tokenize


def distinct_n(texts: list[str], n: int, lang: str = "en") -> float:
    """distinct-n over a list of texts / テキスト群のdistinct-n.

    Returns (# distinct n-grams) / (# total tokens) following Li et al. (2016).
    """
    all_ngrams: list[tuple[str, ...]] = []
    total_tokens = 0
    for t in texts:
        toks = tokenize(t, lang)
        total_tokens += len(toks)
        all_ngrams.extend(ngrams(toks, n))
    if total_tokens == 0:
        return 0.0
    return len(set(all_ngrams)) / total_tokens


def _modified_ngram_precision(cand: list[str], refs: list[list[str]], n: int) -> float:
    """BLEU-style clipped n-gram precision of cand vs refs / clip付きn-gram精度."""
    cand_ng = Counter(ngrams(cand, n))
    if not cand_ng:
        return 0.0
    max_ref = Counter()
    for ref in refs:
        rc = Counter(ngrams(ref, n))
        for g, c in rc.items():
            if c > max_ref[g]:
                max_ref[g] = c
    clipped = sum(min(c, max_ref[g]) for g, c in cand_ng.items())
    total = sum(cand_ng.values())
    return clipped / total if total else 0.0


def self_bleu(cand: str, refs: list[str], lang: str = "en", max_n: int = 2) -> float:
    """Dependency-free Self-BLEU surrogate of ``cand`` against ``refs`` (0..1).

    candをrefsに対して評価する依存ゼロのSelf-BLEU代理 (高いほど反復的).
    Geometric mean of modified n-gram precision for n=1..max_n (no brevity penalty).
    """
    cand_t = tokenize(cand, lang)
    ref_t = [tokenize(r, lang) for r in refs if r.strip()]
    if not cand_t or not ref_t:
        return 0.0
    prod = 1.0
    for n in range(1, max_n + 1):
        prod *= max(_modified_ngram_precision(cand_t, ref_t, n), 1e-9)
    return prod ** (1.0 / max_n)


def self_repetition_diversity(utterances_by_agent: dict[str, list[str]], lang: str = "en") -> float:
    """Mean (1 - Self-BLEU) of each utterance vs the same agent's prior utterances.

    各発話を同一エージェントの過去発話に対して 1-Self-BLEU で測り平均する.
    Higher = the agent introduces new wording rather than restating itself (Liang et al.
    adaptation). Returns 0..1; 1.0 if no agent ever has a prior utterance.
    """
    scores: list[float] = []
    for utts in utterances_by_agent.values():
        for i in range(1, len(utts)):
            scores.append(1.0 - self_bleu(utts[i], utts[:i], lang))
    if not scores:
        return 1.0
    return sum(scores) / len(scores)
