# INLG 2026 — Scripts + Analysis for Multi-Party Discourse

One self-contained system for the INLG study: giving an LLM agent **full LLM-generated
discussion scripts + analysis** (topic-independent examples) to fix multi-party discourse
failures, evaluated across **two domains** — werewolf (AIWolfDial) and **HiddenBench**
(hidden-profile collaborative reasoning) — with **one shared agent**.

INLG研究の自己完結システム。**LLM生成の完全議論台本＋分析**を話題非依存の手本として与え、
多人数談話の失敗を改善する。**人狼(AIWolfDial)** と **HiddenBench** の2ドメインを、
**1つの共有エージェント**で戦い同一評価する。

## One system, controlled from the root / ルートで一括制御される1システム

The repo root **is** the system. Everything is steered from one place:

| At the root | What it controls |
|-------------|------------------|
| `.env` | the single env everyone reads (secrets + `LANG_CODE`/`CONDITION`/ports) |
| `config/inlg.yml` | human-readable control map of the whole system |
| `config/conditions.yml` | the 6-condition (3×2) registry |
| `docker-compose.yml` | both domains, concurrent via profiles |
| `Makefile` / `run_local.sh` | run with docker / locally |
| `launcher/` | picks domain·condition·lang → builds the agent config → runs |

## Layout / 構成

```
inlg/
├── .env(.example)            # ★ single central env
├── config/                   # ★ central control: inlg.yml + conditions.yml
├── docker-compose.yml        # ★ both domains, profile-gated
├── docker/                   #   Dockerfiles (agent, server-aiwolf, server-hidden-bench)
├── launcher/                 #   domain/condition/lang -> agent config -> run
├── Makefile  run_local.sh
├── agent/                    # ★ ONE shared agent (drives both domains)
│   ├── src/                  #   shared brain (agent.py, hiddenbench.py, starter, utils)
│   ├── prompts/  data/       #   shared blocks + data
│   ├── aiwolf/               #   werewolf domain pack: config/ + exemplars/
│   └── hidden-bench/         #   HiddenBench domain pack: config/ + exemplars/
├── server/
│   ├── aiwolf/               #   werewolf (AIWolfDial) game server (Go, vendored)
│   └── hidden-bench/         #   HiddenBench server (Python, faithful T=15)
├── eval/                     # transcript failure-mode metrics -> bilingual report
├── web/                      # human-in-the-loop HiddenBench lobby (data collection)
└── docs/                     # INLG_SYSTEM / METHODOLOGY / VERIFICATION / ORCHESTRATION / EXEMPLARS
```

`agent/aiwolf/` and `agent/hidden-bench/` hold only the **domain-specific** config/exemplars;
the shared brain lives once in `agent/src/` (this preserves the "one shared agent"
fairness property — see docs/INLG_METHODOLOGY.md P2). `server/aiwolf/` and the agent are
**vendored snapshots**; `aiwolf-nlp-common` is installed from PyPI (`==0.7.0`), not vendored.

## Read first / まず読む
- [docs/INLG_SYSTEM.md](docs/INLG_SYSTEM.md) — the map / 全体図
- [docs/INLG_METHODOLOGY.md](docs/INLG_METHODOLOGY.md) — defensible 6-condition design + citations
- [docs/INLG_VERIFICATION.md](docs/INLG_VERIFICATION.md) — why the Go server can't host HiddenBench

## Quick start / クイックスタート

```bash
cp .env.example .env          # set OPENAI_API_KEY / CLAUDE_API_KEY, LANG_CODE, CONDITION

# Docker — both domains at once / 両ドメイン同時
docker compose --profile aiwolf --profile hiddenbench up --build
#   or: make both | make hiddenbench | make aiwolf

# Local (no docker) / ローカル
cd agent && uv sync && cd ..      # build the agent venv
make local-hb                     # HiddenBench server + 4 agents

# Evaluate / 評価
make eval                         # -> server/hidden-bench/log/results/eval/report.md

# Human data collection / 人間データ収集
cd web && uv sync
HB_URL=ws://127.0.0.1:8090/ws uv run uvicorn --app-dir src app:app --port 8000
```

## Status / 現状
- All components built and smoke-tested (server↔agent integration, faithful transcript,
  scoring, eval report). / 構築・スモークテスト済み。
- **Exemplars are intentionally empty** (`agent/<pack>/exemplars/`). Add scripts /
  utterance-fewshot / analysis later; non-baseline conditions fall back to baseline until
  populated. / 手本は意図的に空。後から追加。
- Running real agents needs LLM provider API keys (or local Ollama/Gemma).
