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

The repo root is the control surface (`.env`, `config/inlg.yml`, `config/conditions.yml`,
`docker-compose.yml`, `Makefile`, `launcher/`). Components hang off it:

| Path | Role |
|------|------|
| [../agent/](../agent/) | The **one shared agent**. `src/` is the shared brain (incl. `src/agent/hiddenbench.py`); `aiwolf/` and `hidden-bench/` are domain packs (config + exemplar slots). Drives both domains. |
| [../server/aiwolf/](../server/aiwolf/) | Werewolf (AIWolfDial) game server (Go). Vendored, **unmodified**. |
| [../server/hidden-bench/](../server/hidden-bench/) | **New.** Faithful HiddenBench server (Python). 4 agents, fixed T=15 sequential, pre/post elicitation, scoring. Speaks the aiwolf-nlp-common wire protocol so the same agent drives it. |
| [../eval/](../eval/) | **New.** Transcript failure-mode metrics (surfacing, convergence, diversity, conformity) → bilingual report. Self-defined/adapted metrics flagged. |
| [../web/](../web/) | **New.** Minimal web lobby: a human plays one HiddenBench seat (human-data collection), via the same faithful protocol. |
| [../launcher/](../launcher/) | **New.** Picks domain·condition·lang → builds the agent config (overlays the condition's scenario from `config/conditions.yml`) → runs the agents. |
| [../docker-compose.yml](../docker-compose.yml) | **New.** Both domains, concurrent via profiles (`aiwolf`, `hiddenbench`). |

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

## Quick start / クイックスタート (run from repo root / リポジトリ直下で実行)

```bash
cp .env.example .env          # set OPENAI_API_KEY etc., LANG_CODE, CONDITION

# Docker — both domains at once / 両ドメイン同時
docker compose --profile aiwolf --profile hiddenbench up --build
#   make both | make hiddenbench | make aiwolf

# Local (no docker) / ローカル
cd agent && uv sync && cd ..
make local-hb                 # HiddenBench server + 4 agents

# Evaluate / 評価
make eval                     # -> server/hidden-bench/log/results/eval/report.md

# Human data collection / 人間データ収集
cd web && uv sync && HB_URL=ws://127.0.0.1:8090/ws uv run uvicorn --app-dir src app:app --port 8000
# start the HiddenBench server + 3 LLM agents, then open http://localhost:8000 for the 4th seat
```

## Status / 現状

- HiddenBench server, agent adapter, metrics, launcher, compose, web lobby: **built and
  smoke-tested** (server↔real-client integration, faithful 4×T transcript, scoring, eval
  report all verified).
- **Exemplars are intentionally empty** (`agent/<pack>/exemplars/…`).
  Add scripts / utterance-fewshot / analysis later; non-baseline conditions auto-fall back
  to baseline until their exemplar directory is populated.
- Running real LLM agents needs provider API keys (or a local Ollama/Gemma).
- Open methodology decisions (werewolf protocol variant, Likert vs ranking, Gemma sizes)
  are listed in [INLG_METHODOLOGY.md](INLG_METHODOLOGY.md) §7.
