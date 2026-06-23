<!-- Language: **English** | [日本語](METRICS.ja.md) -->

# How to read the evaluation metrics

A plain-language cheat sheet for **what each number in the reports means and which direction is good**.
The reports live at `results/<run>/<domain>_flat/eval/report.md` and the cross-domain rankings at
`rankings.md`. For the *research rationale*, citations, and defensibility of each metric, see
[METHODOLOGY.md](METHODOLOGY.md) §4 — this file is purely "how to read the numbers".

Implementations are in `eval/src/` (`evaluate.py` / `convergence.py` / `conformity.py` /
`diversity.py` / `surfacing.py` / `judge.py`). Metrics tagged `*self-defined` / `*adapted` borrow a
name from prior work but the formula is our operationalization (flagged honestly).

> **Notation**: ↑ higher is better, ↓ lower is better, — read as a tendency (not strictly good/bad).
> Ranges are noted. The `__all__` column pools all conditions (reference only).

---

## 0. The three-line version

- **How much closer to the truth the discussion got** → pre/post accuracy, **integration gain** (HiddenBench only).
- **Whether the discussion was healthy** (shared failure modes) → conformity/independence, convergence-round/premature-consensus, diversity (distinct, self-repetition).
- **Whether it read naturally** → subjective scores (naturalness, coherence, topic development; 5-pt LLM judge).

---

## 1. Task success (HiddenBench only)

HiddenBench = "pool the clues each agent privately holds and find the single correct answer." We take
each agent's individual answer (`{vote, rationale}`) **before and after** the discussion.

| Metric | Range | Good | Meaning |
|---|---|---|---|
| **Pre-discussion accuracy** | 0–1 | (baseline) | Fraction picking the correct option **before** discussing, alone. Low = "unsolvable solo" = a good distributed-info task. |
| **Post-discussion accuracy (primary)** | 0–1 | ↑ | Fraction correct **after** discussing. The single most important outcome. |
| **Integration gain** | −1–1 | ↑ | = post − pre. **How many points the discussion added.** Large positive = the discussion worked. |
| Post majority-correct rate | 0–1 | ↑ | Fraction of tasks where a majority landed on the correct option. |

> Intuition: **pre = start, post = finish, integration gain = realized headroom.**
> Werewolf (aiwolf) has no single ground truth, so it has none of these accuracy metrics.

---

## 2. Information hoarding (surfacing)

Failure: never sharing a clue only you hold.

| Metric | Range | Good | Meaning |
|---|---|---|---|
| Information surfacing rate *self-defined | 0–1 | ↑ | Fraction of hidden facts **mentioned at least once** (rule-matched). Low = hoarding. |

> HiddenBench-specific; for werewolf we report a **domain-adapted** version (disclosure rate of private
> info: seer CO, divination results, role claims), not claimed as equivalent.

---

## 3. Premature convergence (convergence)

Failure: everyone jumps to one answer before the evidence is in. Stance = the last option an utterance
mentions (rule-based).

| Metric | Range | Good | Meaning |
|---|---|---|---|
| **Mean convergence round** *self-defined | 0–(T−1) | ↑ (context) | 0-based round where **all stances first agree**. Small = converged fast (risky); large = deliberated first. Late convergence = *premature-consensus avoidance*, so higher is treated as better here. |
| Converged fraction | 0–1 | — | Share of games that reached unanimity. |
| **Premature-consensus rate** *self-defined | 0–1 | ↓ | Share of games that agreed **before all key facts surfaced**. High = deciding before the evidence. |
| Terminal agreement rate | 0–1 | — | Agreement with the majority in the final round. |

> Bad pattern: early convergence × high premature rate (hasty). Ideal: late convergence × low premature
> rate × high post-accuracy (deliberate and correct).

---

## 4. Stagnation / diversity (diversity)

Failure: repeating the same wording/claims. Measured on surface **lexicon** (not semantics).

| Metric | Range | Good | Meaning |
|---|---|---|---|
| **distinct-1** | 0–1 | ↑ | (unique 1-grams) / (total tokens). Vocabulary richness. |
| **distinct-2** | 0–1 | ↑ | Same for 2-grams (phrases). More sensitive to repeated phrasing. |
| **Self-repetition diversity** *adapted | 0–1 | ↑ | = 1 − Self-BLEU vs the **same agent's prior** utterances. High = says new things; low = copies itself. |

> Lexical (surface n-gram), not semantic — only "is it looping the same words," not meaning.

---

## 5. Reflexive conformity / independence (conformity)

Reaction when you are the minority: cave to the majority (conformity) or hold (independence). We look
only at moments where an agent disagreed with the majority-of-others, then count flip vs hold.

| Metric | Range | Good | Meaning |
|---|---|---|---|
| **Conformity rate** *adapted | 0–1 | ↓ | Of those pressured moments, fraction that **flipped to the majority**. High = herding (abandoning one's clue). |
| **Independence rate** *adapted | 0–1 | ↑ | Fraction that **held**. Here independence = 1 − conformity (within the pressured population). |

> The "conformity" failure mode = matching the majority without scrutiny; if a minority holds the right
> clue and caves, the group misses the answer. So **low conformity, high independence** is desirable.
> This proxy only measures "do you fold when outnumbered," and differs from BenchForm's conjunctive IR
> (see METHODOLOGY §4).

---

## 6. Subjective evaluation (LLM judge)

A separate-lineage LLM judge (Gemma here for validation; GPT intended for production) scores the **whole
transcript** on a 1–5 Likert. Self-play, so we use 3 absolute criteria, not AIWolfDial's relative rubric.

| Metric | Range | Good | Meaning |
|---|---|---|---|
| naturalness | 1–5 | ↑ | Reads like a natural human discussion. |
| coherence | 1–5 | ↑ | Replies **engage** each other, no contradictions. |
| topic_development | 1–5 | ↑ | The discussion **deepens / progresses** (not circular). |

> The gold exemplars score much higher here (full human/strong-model scripts); inter-condition gaps are
> small, so read these alongside the objective metrics.

---

## 7. How to read the rankings

`rankings.md` (also embedded into each report.md as "Per-domain rankings") has three tables:

- **HiddenBench only** — all metrics **including** accuracy/integration-gain.
- **aiwolf only** — shared failure-mode / diversity / subjective metrics only (no accuracy).
- **Overall** — mean of each domain's mean-rank (HB and aiwolf **equally weighted**).

Each metric is ranked (1 = best, ties = average rank); the smaller the **mean rank**, the higher the
condition. Good direction per the sections above. Gold/human are **excluded from the rankings** and shown
only as reference rows in the report's metric table.

> Rankings collapse absolute gaps into ordinals. For any real claim, read the **raw metric values** in
> report.md and the n (game count) alongside the rank.

---

## Related docs

- [METHODOLOGY.md](METHODOLOGY.md) — why these metrics (design, sources, defensibility)
- [EXEMPLARS.md](EXEMPLARS.md) — how exemplars (scripts / utterances / analysis) are built
- [SYSTEM.md](SYSTEM.md) — system architecture
