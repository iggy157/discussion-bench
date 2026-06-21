# eval (metrics)

Transcript **failure-mode metrics** for the INLG study, computed from HiddenBench game
results (and, via a thin extractor later, werewolf logs). Pure-Python, no system deps,
bilingual report.

INLG研究の**失敗様態指標**をトランスクリプトから計算する。依存ゼロ・日英レポート。

## What it computes / 計算する指標

| Metric | Status | Citation (see ../INLG_METHODOLOGY.md §4) |
|--------|--------|------------------------------------------|
| pre/post accuracy, integration gain, majority | HiddenBench-native | Li et al. 2505.11556 |
| **information surfacing rate** | **self-defined** | adaptation of Stasser & Titus 1985; Lu et al. 2012 |
| **convergence round, premature-consensus, terminal agreement** | **self-defined** | Smit et al. ICML2024; Wu et al. 2511.07784 |
| distinct-1 / distinct-2 | as-published | Li et al. NAACL2016 (1510.03055) |
| self-repetition diversity (1 − Self-BLEU) | adapted | Liang et al. EMNLP2024 (2305.19118) |
| conformity / independence proxy | **adapted** | BenchForm ICLR2025 (2501.13381); IR ≠ 1−CR |

Self-defined / adapted metrics are flagged in the report (`*self-defined`, `*adapted`).
This honesty is deliberate: the cited sources do **not** give these exact transcript
formulas. Prefer an LLM-judge per clue / stance as a robustness check in the paper.

## Run / 実行

```bash
uv sync   # (no deps; uv just makes a venv)
uv run src/evaluate.py <results_dir>           # e.g. ../server/hidden-bench/log/results
# writes <results_dir>/eval/metrics.json + report.md (aggregated by condition)
uv run src/evaluate.py <results_dir> --threshold 0.5   # surfacing token-overlap threshold
```

## Notes / 注意

- **Tokenization**: EN = word tokens; JP/JA = character tokens (no MeCab dependency).
  distinct-n divides by total tokens (Li et al. convention). State this in the paper.
- **Stance extraction** for convergence/conformity uses rule-based option-mention matching
  (options are known in HiddenBench). For free-form domains, swap in an LLM stance
  extractor (`src/stance.py` is the seam).
- Aggregation is by `condition`, so running all six conditions populates a single
  comparison table.

## Layout / 構成

```
src/
  tokenize_text.py  -- EN/JP tokenizer + n-grams
  stance.py         -- per-utterance stance over a known option set
  surfacing.py      -- information surfacing rate (self-defined)
  convergence.py    -- convergence round / premature consensus (self-defined)
  diversity.py      -- distinct-n, Self-BLEU self-repetition
  conformity.py     -- conformity/independence proxy (BenchForm-adapted)
  evaluate.py       -- orchestrator + CLI + bilingual Markdown report
```
