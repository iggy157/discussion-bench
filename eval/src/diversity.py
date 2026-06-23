"""Diversity / stagnation metrics (distinct-n, lexical self-repetition).

多様性・停滞指標 (distinct-n, 語彙的な自己反復).

Citations (verified against primary sources; see METHODOLOGY.md §4.2):
- distinct-1 / distinct-2: Li, Galley, Brockett, Gao & Dolan (2016), NAACL, arXiv:1510.03055.
  Original definition: (# distinct n-grams) / (# total tokens) — we use total TOKENS as the
  denominator, matching the paper (some reimplementations divide by total n-grams instead).
- Lexical self-repetition: Self-BLEU originates with Zhu et al. (2018), "Texygen", SIGIR,
  arXiv:1802.01886; the "Diversity = 100 - Self-BLEU" framing is Liang et al. (2024), EMNLP,
  arXiv:2305.19118 (there a single pairwise compare between two sides' answers). We compute a
  dependency-free Self-BLEU surrogate between an utterance and the SAME agent's prior
  utterances and report 1 - Self-BLEU — an ADAPTATION (per-agent self-history), flagged as ours.

NAMING: this is LEXICAL (surface n-gram) self-repetition, NOT semantic — Self-BLEU measures
n-gram overlap, not meaning. / これは語彙的(表層n-gram)な自己反復であって「意味的」ではない.

NOTE: DMAD (ICLR2025) does NOT define distinct-n / Self-BLEU / semantic diversity; its
"diversity" is reasoning-strategy coverage. Do NOT cite DMAD for these.
/ DMADはこれらを定義していない (DMADの多様性は推論戦略の多様性). 引用しない.
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
            max_ref[g] = max(max_ref[g], c)
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
        scores.extend(1.0 - self_bleu(utts[i], utts[:i], lang) for i in range(1, len(utts)))
    if not scores:
        return 1.0
    return sum(scores) / len(scores)
