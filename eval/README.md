# eval (metrics + LLM-judge)

Evaluation for the INLG study, computed over a WHOLE discussion log (self-play produces one
log per game): **objective failure-mode metrics** (rule-based) + a **subjective LLM-judge**
(3 items). Bilingual report, aggregated by condition.

INLG研究の評価。議論ログ全体に対して、客観的な失敗様態指標（ルールベース）＋主観LLM-judge（3項目）を
計算し、条件別の日英レポートを出す。

## Objective metrics / 客観指標（出典は一次資料で検証済み）

| Metric | Status | Faithful citation (see ../docs/INLG_METHODOLOGY.md §4) |
|--------|--------|--------------------------------------------------------|
| pre/post/full accuracy, integration gain, majority | HiddenBench-native | Li, Naito & Shirado 2025 (arXiv:2505.11556) |
| **information surfacing rate** (= information coverage) | **adaptation** | Lu, Yuan & McLeod 2012; Stasser & Titus 1985 — **NOT** HiddenBench |
| convergence round | matches repo `consensus_round` | jonradoff/hiddenbench (paper fixes T=15, no early stop) |
| premature-consensus, terminal agreement | **self-defined** | cf. Smit et al. ICML2024; Wu et al. 2511.07784 |
| distinct-1 / distinct-2 (÷ total tokens) | as-published | Li et al. NAACL2016 (1510.03055) — **NOT** DMAD |
| lexical self-repetition (1 − Self-BLEU vs own history) | **adaptation** | Self-BLEU = Zhu et al. 2018 (Texygen); 100−Self-BLEU framing = Liang et al. 2024 |
| conformity / independence proxy | **adaptation** | BenchForm ICLR2025 (2501.13381). Our IR = 1−CR (BenchForm's IR is conjunctive Trust∩Doubt, ≠ 1−CR) |

The attributions above were corrected after checking primary sources: surfacing is **not** a
HiddenBench metric (it's Lu/Stasser information coverage); distinct-n / Self-BLEU are **not**
DMAD/DoT; "self-repetition" is **lexical** (surface n-gram), not semantic. Adapted/self-defined
metrics are flagged in the report (`*self-defined`, `*adapted`).

## Subjective LLM-judge / 主観LLM-judge

Three items scored over the whole log: **naturalness / coherence (non-contradiction) /
topic development**. (AIWolfDial's A–F rubric is a relative/ranking scheme for cross-play and
is intentionally not used — self-play makes relative ranking meaningless.) The judge model is
managed in `config/judge.yml` (English) / `config/judge.ja.yml` (Japanese reference):
provider/model/temperature/scale/lang. The API key is read from the root `.env`. A `mock`
provider is included for offline testing.

## Run / 実行 (from repo root via Make)

```bash
make eval     # objective only (no API)   -> server/hidden-bench/log/results/eval/report.md
make judge    # objective + subjective LLM-judge -> same report with subj_* columns
```

Directly:
```bash
PYTHONPATH=src python src/evaluate.py <results_dir>                 # objective only
PYTHONPATH=src python src/evaluate_all.py <results_dir> -c config/judge.yml   # + LLM-judge
PYTHONPATH=src python src/evaluate_all.py <results_dir> --no-judge  # objective only
```

### Werewolf logs / 人狼ログ
The eval consumes HiddenBench result JSON directly. For werewolf, convert the server's JSON
game logs first (HB-native metrics are N/A; distinct-n / self-repetition / the LLM-judge apply):
```bash
PYTHONPATH=src python src/werewolf_adapter.py <server-json-log-dir> -o <out> --condition baseline --lang jp
make judge HB_RESULTS=<out>
```

## Notes / 注意
- **Tokenization**: EN = word tokens; JP/JA = character tokens (no MeCab). distinct-n ÷ total tokens.
- **Stance extraction** for convergence/conformity is rule-based option-mention (faithful to
  BenchForm, which is also rule-based; options are known in HiddenBench). `src/stance.py` is the
  seam if you ever want an LLM extractor.
- Aggregation is by `condition` → running all six conditions fills one comparison table.

## Layout / 構成
```
config/judge.yml (.ja.yml)  -- judge model config
src/
  tokenize_text.py  stance.py
  surfacing.py      -- information coverage (Lu/Stasser; flagged adaptation)
  convergence.py    -- convergence round / premature consensus
  diversity.py      -- distinct-n (Li 2016), lexical self-repetition (Zhu 2018 / Liang 2024)
  conformity.py     -- conformity/independence (BenchForm-adapted; IR = 1−CR)
  evaluate.py       -- objective metrics + report
  judge.py          -- subjective LLM-judge (provider: openai | mock)
  evaluate_all.py   -- combined objective + subjective (make judge)
  werewolf_adapter.py -- aiwolf-nlp-server JSON log -> transcript shape
```
