<!-- Language: **English** | [日本語](METHODOLOGY.ja.md) -->

# Methodology: improving multi-party discussion with examples

Created 2026-06-21.

This document is the research design under the system. It goes from the goal and the overall
policy down to each domain's construction, the operationalization of the intervention (how
examples are given), the evaluation, and the scale. It is written to be as defensible as
possible for a paper.

## Goal

LLM-vs-LLM multi-party discussion has repeatedly-reported failure patterns: withholding
information so distributed knowledge is not pooled, fixating on the first answer and
converging too early, and going along with others / the majority. This study asks whether
these can be fixed **not by instructions, but by showing examples of good discussion**.
Concretely, we give an LLM-generated "complete discussion script (start to finish)" and an
"analysis (the key points / where to look)" extracted from it, as topic-independent examples
with no extra training.

## Backbone: where fairness is held

There are two environments: **werewolf** (a social-deduction game) and **HiddenBench**
(distributed-information collaborative reasoning). Their rules and flows are entirely
different. Naively trying to "make the two games identical for a fair comparison" backfires:
one domain would deviate from its community's standard, inviting "did you really run
HiddenBench (or werewolf)?".

So fairness is held by three points:

- **(P1) Each domain follows its community's canonical flow faithfully.**
- **(P2) The intervention layer — the example (script / utterance / analysis) injection
  mechanism, the LLM, the decoding settings, the token budget, the number of examples — is
  held completely identical across both domains.**
- **(P3) The transcript metrics for failure modes are computed by the same procedure in both
  domains.**

So fairness comes from (P2) and (P3), not from making the game mechanics identical. That the
mechanics differ is the premise of a two-domain study, and is hard to criticize as long as
each follows its canonical spec.

## Why not force a single protocol

The two domains' canonical protocols are fundamentally different. HiddenBench has a central
moderator turning sequential turns with structured pre/post answers (not free group chat: 4
agents, T=15 rounds, round 1 in order, later rounds responding after seeing all others, fixed
rounds — Li, Naito & Shirado, arXiv:2505.11556 §4.2). Werewolf (AIWolfDial) is synchronized
turn-based (5 players, 4 talks/agent/day = 20/day, 125 chars/talk (250 with @mention), 1-min
timeout — AIWolfDial 2024/2025 overview papers).

Forcing both into one free group chat would deviate from one of the canonical specs. So the
system **shares the wire protocol (WebSocket) and the agent's brain (prompt building, example
injection, LLM calls, cost accounting), while the progression logic (turn order, answer
collection, termination) is a separate adapter faithful to each domain's canonical spec.**
This is the only realistic way to keep both faithfulness and reproducibility.

## Domain 1: werewolf (AIWolfDial)

Game setup follows the AIWolfDial 2024/2025 standard: 5 players (1 seer / 1 werewolf / 1
possessed / 2 villagers), synchronized turn-based talk, 4 talks/agent/day = 20/day, 125
chars/talk (250 with @mention), Day 0 greetings only, 1-min timeout. The server is the
existing `aiwolf-nlp-server`, unmodified (the `config/default_5.yml` family). 13-player is a
future extension, which adds a team-play evaluation item.

Whether the production werewolf protocol is synchronized-turn or free group chat is most
defensible to follow whatever the JSAI 2026 production spec uses (the agent supports both).

Task success itself can be read as win rate (macro / micro / villager-doubled standard
aggregations), but both AIWolfDial overview papers explicitly note that win rate is unstable
due to too few games, so this study adds the same caveat and does not make win rate the
primary measure. The main evaluation is the transcript metrics below (shared across domains).

## Domain 2: HiddenBench (faithful reproduction)

HiddenBench is reproduced faithfully. The canonical spec to keep:

| Item | Value | Source |
|---|---|---|
| Number of agents | 4 | paper §4.2 |
| Discussion rounds | **fixed T=15** (no early stop) | paper §4.2 |
| Turn order | round 1 in order; later rounds respond after seeing all others + full history | paper §4.2 |
| Pre/post answer | each agent privately answers `{"vote","rationale"}` in JSON | official impl `prompts.py` |
| Scoring | average rule (proportion correct) / majority rule (>50%) | paper §3 |
| Derived | integration gain = post − pre; collective-reasoning gap = full − post | paper |
| Task validity | Full-Profile accuracy ≥80% AND Hidden-Profile accuracy ≤20% | paper §5.1.2 |
| Data | HuggingFace `YuxuanLi1225/HiddenBench` (65 tasks) | data card |

For citation, cite the **paper (Li et al.)** for the paradigm, metrics, validity filter, and
condition wording, and the **official repo (Radoff)** for concrete prompt strings and the
early-stop heuristic — distinctly. In particular the repo's "stop early on consensus" is an
implementation extra not in the paper, so the main experiment uses the paper's fixed T=15 (no
early stop), prioritizing reproducibility.

Implementation-wise, a small new Python server reproduces the above faithfully. It reuses the
same WebSocket protocol as werewolf but follows HiddenBench's canonical progression. No new
request types are added; the context (which of pre/discussion/post the turn is) rides in the
packet's `info.profile` as JSON. Task success is post-accuracy (primary), pre-accuracy,
Full-Profile accuracy, integration gain, and collective-reasoning gap.

## Operationalizing the intervention: six conditions (the heart of the study)

The core is a 3×2 = six conditions: how the example is given (3) × analysis present (2).

| | no analysis | with analysis |
|---|---|---|
| baseline | ① baseline | ② analysis-only |
| utterance few-shot | ③ utterance few-shot | ④ utterance few-shot + analysis |
| script few-shot | ⑤ script few-shot | ⑥ script few-shot + analysis (expected best) |

The "example" is built the same way in both domains. A **script** is a complete multi-party
discussion transcript start to finish (for werewolf, a full 5-player game; for HiddenBench, a
full task discussion + pre/post). **Utterance few-shot** is single-utterance examples sliced
from the same scripts, without the whole-discussion flow. **Analysis** is key-point notes
extracted from a script ("a good discussion proceeds like this / look here"), given as
observation, not instruction.

### Cutting leakage and topic-dependence (most important for review)

If the example directly hints at the answer, the experiment is void. Three controls are
applied mechanically:

- **(L1) Build from a disjoint instance.** Scripts/utterances/analysis come from games/tasks
  different from the evaluation set. For HiddenBench, evaluate 20 of the 65 tasks and build
  examples from the rest (task-id disjointness guaranteed mechanically). Werewolf uses
  different seeds from evaluation.
- **(L2) No topic-dependence.** Analysis is limited to "how a discussion proceeds / where to
  look"; it must not include a task's correct option or specific facts (that would leak the
  answer). After generation, inspect the analysis text and remove answer terms and
  task-specific names.
- **(L3) Separate model families for generation / discussion / judging.** Script & analysis
  generation is fixed to **Claude**; the discussion agent is **Gemma** (a different family) to
  remove self-imitation confounds; the judge is **GPT** (yet another family) to suppress
  LLM-judge self-preference bias.

### Match token counts

To purely compare "single-utterance example vs whole discussion", ③ utterance few-shot and ⑤
script few-shot are matched on input token count, and likewise ④ utterance+analysis and ⑥
script+analysis. Matching is measured not in characters but with the **discussion agent's
(Gemma's) actual tokenizer**, and the per-cell × per-domain token counts are reported in a
table. ① baseline and ② analysis-only are naturally low-token — that is itself evidence the
effect comes from the quality of the key points, not information volume, so it is shown as-is.
The injection path is identical for all six conditions (the body is a HumanMessage, the
analysis is an AIMessage or a static acknowledgment); the mechanism, history position, and
caching are not varied by condition.

### Difference from the related method PRICoT

PRICoT (Yamazaki et al., INLG2025, `2025.inlg-main.35`) is related in that it also extracts
post-hoc analysis of successes/failures and injects it downstream. Respecting it, we note four
differences. PRICoT (1) requires gold labels for supervised success/failure classification,
(2) distills reusable, generalizable principles and transfers them to other problems, (3)
retrieves and injects per-instance from a vector DB, and (4) is a two-stage offline-build →
online-retrieve pipeline. This study differs on all four: it does not depend on gold labels,
and presents a "how a good discussion proceeds" example all at once at game start — a single
in-context example.

## Evaluation (same procedure across domains is the fairness backbone)

### Subjective evaluation

This study is **self-play** (all seats are the same agent), so AIWolfDial's A–F rubric is not
used: it is a framework premised on **relative ranking between agents**, which is meaningless
without cross-play.

Instead, the **whole discussion log** is scored absolutely on three items: **naturalness /
coherence (non-contradiction) / topic development**. An LLM-judge (GPT by default) rates them
on a 5-point Likert scale, kept in a separate family from the Claude generator and Gemma
discussion agent to suppress self-preference bias (family separation per L3). The judge model
is centrally managed in `eval/config/judge.yml`, with the API key read from the root `.env`.
Implementation: `eval/src/judge.py`; one-shot run: `make judge`.

### Objective evaluation

There is one important caveat per failure mode. After checking primary sources, **some
"metrics" have no formula in their source paper**. Inventing a formula under a borrowed name
collapses under review, so any self-defined formula is honestly flagged "self-defined", and a
proper original source for the underlying measure is cited separately.

| Failure mode | Metric used | Source handling |
|---|---|---|
| Withholding information | **Information surfacing rate** = (# distinct unshared facts mentioned ≥1× in the transcript) ÷ (total unshared facts). Rule-based detection. Post-accuracy reported as the outcome indicator. | Verified against primary sources: **HiddenBench does not define a surfacing rate** (only the accuracy family). The real construct is Lu, Yuan & McLeod 2012 "information coverage", rooted in Stasser & Titus 1985. → attribute to Lu/Stasser, not HiddenBench. |
| Early convergence | **Convergence round** = first round all agents share one option. **Pre-surfacing agreement rate** = fraction where consensus is reached before all critical facts have surfaced. | Convergence round matches the official repo's `consensus_round` (the paper fixes T=15, no early stop). "Pre-surfacing agreement" is **self-defined**. Terminal agreement: Smit et al. ICML2024; round resolution: Wu et al. 2511.07784. |
| Stagnation / diversity | **distinct-1/2** (denominator = total tokens, per Li et al.), **lexical self-repetition** = 1 − Self-BLEU (vs the agent's own prior utterances). | distinct-n is **Li et al. NAACL2016** (not DMAD). Self-BLEU originates with **Zhu et al. 2018 (Texygen)**; the `100−Self-BLEU` framing is Liang et al. 2024. Applying it vs one's own history is a **self-defined variant**. It is surface n-gram overlap, so **lexical**, not semantic. **Do not attribute to DMAD/DoT.** |
| Reflexive conformity | **Conformity / independence rate**. Per round, poll stances (**rule-based**: last-mentioned option) and compute flip/hold when an agent is in the minority vs the majority-of-others. | An **adaptation** of BenchForm's (Weng et al. ICLR2025) CR/IR. BenchForm uses scripted confederates + a Raw baseline + **rule-based extraction**, and its **IR is conjunctive over Trust∩Doubt (≠ 1−CR)**. Free discussion has no baseline, so our IR is 1−CR by construction — a different thing, stated as such. Transition taxonomy: Talk Isn't Always Cheap. |

The cross-domain application is drawn honestly. distinct-n, lexical self-repetition, conformity,
and convergence round are naturally domain-general, so they are computed identically in both
(P3). Information surfacing is HiddenBench-native, so for werewolf an analogous construct
(disclosure rate of private info: seer CO, divination results, role claims) is reported as a
"domain-adapted version", not claimed on par with the HiddenBench version.

## Models and scale

The discussion agent uses two Gemma sizes (upper/lower) to check scale robustness cheaply and
reproducibly (a different family from the Claude generator, so no self-imitation confound).
Script/analysis generation is fixed to Claude, the judge fixed to GPT.

Scale is roughly 6 conditions × 2 domains × 2 model sizes × 20 games = **~240 games**.
HiddenBench's 20 tasks are a distinct 20 of the 65 to avoid bias, with examples built from the
rest (L1); werewolf's 20 games use different seeds. Decoding settings (temperature, max_tokens)
are fixed and stated across all conditions and domains (the HiddenBench paper does not state
temperature, but the official repo default is 0.7, so this study declares a fixed value). The
HiddenBench cooperation–conflict 5 conditions are fixed to one neutral condition in the main
experiment to avoid confounds; sweeping all 5 is left to an appendix robustness check
(optional).

## Open decisions

- Werewolf production protocol (synchronized-turn / free group chat). Recommended to follow
  the JSAI 2026 production spec.
- Subjective LLM-judge model (GPT by default; managed in `eval/config/judge.yml`).
- The two specific Gemma sizes.
- Whether to include HiddenBench's cooperation–conflict 5 conditions (recommended: fix one in
  the main experiment, sweep in an appendix).

## Key citations (distinguishing version / source)

- HiddenBench: Li, Y., Naito, A., & Shirado, H. (2025). arXiv:2505.11556 (paradigm, metrics,
  validity, conditions). Impl reference: `github.com/jonradoff/hiddenbench` (prompt strings /
  early stop are a separate impl). Data: HF `YuxuanLi1225/HiddenBench`.
- AIWolfDial: 2024 `aclanthology.org/2024.aiwolfdial-1.pdf` / 2025 `2025.aiwolfdial-1.pdf`
  (protocol constants; the A–F rubric is relative, so not used in this self-play study).
- Hidden-profile classics / information coverage: Stasser & Titus 1985 (JPSP,
  DOI:10.1037/0022-3514.48.6.1467); Lu, Yuan & McLeod 2012 (PSPR 16(1)).
- Diversity: distinct-n = Li et al. 2016 (NAACL, arXiv:1510.03055, denom = total tokens);
  Self-BLEU = Zhu et al. 2018 (Texygen, SIGIR, arXiv:1802.01886); `100−Self-BLEU` framing =
  Liang et al. 2024 (EMNLP, arXiv:2305.19118). **DMAD = Liu et al. ICLR2025 is not a source for
  distinct-n / Self-BLEU / semantic diversity** (DMAD's diversity is reasoning-strategy diversity).
- Conformity: Weng et al. 2025 (ICLR, arXiv:2501.13381, CR/IR; IR ≠ 1−CR); Wynn et al. 2025
  (arXiv:2509.05396, transition taxonomy).
- Convergence: Smit et al. 2024 (ICML, arXiv:2311.17371); Wu et al. 2025 (arXiv:2511.07784).
- Related method: PRICoT, Yamazaki et al. INLG2025 `2025.inlg-main.35` (differentiated on 4 points).
