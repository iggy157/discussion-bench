# INLG System — one system, two domains, six conditions

This document is the map of the system that implements the INLG study (LLM-generated full
discussion **scripts + analysis** as topic-independent examples to fix multi-party
discourse failures), evaluated across **two domains** with **one shared agent**.

本書はINLG研究（話題非依存の手本＝完全議論台本＋分析で多人数談話失敗を改善）を実装する
システム全体図です。**2ドメイン**を**1つの共有エージェント**で戦い、同一評価します。

設計判断の根拠は [INLG_VERIFICATION.md](INLG_VERIFICATION.md)、手法の防御設計は
[INLG_METHODOLOGY.md](INLG_METHODOLOGY.md) を参照。

## Design principle / 設計原則

> **(P1)** Each domain runs its community's **canonical** harness (faithfulness-first).
> **(P2)** The **intervention layer** (script/utterance/analysis injection, LLM, decoding,
> token budget, #exemplars) is held **identical** across domains.
> **(P3)** Failure-mode **transcript metrics** are computed by the **same** procedure in
> both domains.
> Fairness comes from P2/P3 — NOT from forcing the two games to share mechanics.

## Components / 構成要素

| Path | Role |
|------|------|
| [aiwolf-nlp-server/](aiwolf-nlp-server/) | Werewolf (AIWolfDial) game server (Go). **Unmodified.** |
| [hiddenbench-server/](hiddenbench-server/) | **New.** Faithful HiddenBench server (Python). 4 agents, fixed T=15 sequential rounds, pre/post elicitation, scoring. Speaks the aiwolf-nlp-common wire protocol so the same agent drives it. |
| [aiwolf-jsai-manyshot_ver0/](aiwolf-jsai-manyshot_ver0/) | The **shared agent**. Adds a HiddenBench adapter (`src/agent/hiddenbench.py`) + JP/EN HiddenBench prompts + the 6-condition exemplar slots. Werewolf behaviour unchanged. |
| [inlg-eval/](inlg-eval/) | **New.** Transcript failure-mode metrics (surfacing, convergence, diversity, conformity) → bilingual report. Self-defined/adapted metrics are flagged. |
| [inlg-system/](inlg-system/) | **New.** Orchestration: docker compose (both domains concurrent via profiles) + launcher (one config selects domain/condition/lang) + local runner. |
| [inlg-web/](inlg-web/) | **New.** Minimal web lobby: a human plays one HiddenBench seat in the browser (human-data collection), via the same faithful protocol. |

## How the agent drives both domains / 1エージェントで両ドメイン

The HiddenBench server reuses only request types that exist in aiwolf-nlp-common 0.7.0
(NAME / INITIALIZE / TALK / FINISH) — **no library change**. HiddenBench per-turn context
(phase / clues / options / round) rides in `info.profile` as JSON. The agent's
`HiddenBenchAgent` parses it and routes the standard TALK to phase-specific prompts
(`hb_pre` / `hb_discussion` / `hb_post`). Sequential turn order is enforced by the server
eliciting agents strictly in order with the growing transcript — faithful to HiddenBench
§4.2. The script/analysis injection (`_feed_scenario_chunk`) is the SAME code path as
werewolf (P2).

HiddenBenchサーバは aiwolf-nlp-common 0.7.0 既存のリクエスト型のみ使用（ライブラリ無改変）。
フェーズ等は `info.profile` のJSONで運ぶ。逐次ターン順はサーバが順番に発話を引き出すことで担保。

## Quick start / クイックスタート

### Docker (both domains at once) / docker（両ドメイン同時）
```bash
cd inlg-system
cp .env.example .env          # set OPENAI_API_KEY etc., LANG_CODE, CONDITION
docker compose --profile aiwolf --profile hiddenbench up --build
# HiddenBench only:  docker compose --profile hiddenbench up --build
# Werewolf only:     docker compose --profile aiwolf up --build
```

### Local (no docker) / ローカル
```bash
# 1) deps (per project, with uv): cd hiddenbench-server && uv sync ; cd ../aiwolf-jsai-manyshot_ver0 && uv sync
cd inlg-system
LANG_CODE=en CONDITION=baseline ./run_local.sh hiddenbench
```

### Evaluate / 評価
```bash
cd inlg-eval
uv run src/evaluate.py ../hiddenbench-server/log/results   # -> report.md + metrics.json
```

### Human data collection / 人間データ収集
```bash
cd inlg-web && uv run uvicorn --app-dir src app:app --port 8000
# Start hiddenbench-server + 3 LLM agents, then open http://localhost:8000 to take the 4th seat.
```

## Status / 現状

- HiddenBench server, agent adapter, metrics, launcher, compose, web lobby: **built and
  smoke-tested** (server↔real-client integration, faithful 4×T transcript, scoring, eval
  report all verified).
- **Exemplars are intentionally empty** (`aiwolf-jsai-manyshot_ver0/data/exemplars/…`).
  Add scripts / utterance-fewshot / analysis later; non-baseline conditions auto-fall back
  to baseline until their exemplar directory is populated.
- Running real LLM agents needs provider API keys (or a local Ollama/Gemma).
- Open methodology decisions (werewolf protocol variant, Likert vs ranking, Gemma sizes)
  are listed in [INLG_METHODOLOGY.md](INLG_METHODOLOGY.md) §7.
