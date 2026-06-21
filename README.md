<!-- Language: **English** | [日本語](README.ja.md) -->

# Multi-Agent LLM Discussion Platform

A platform for running and evaluating **multi-agent LLM discussions** in two environments:

- **Werewolf** — a social-deduction dialogue game (the AIWolfDial protocol, 5 players).
- **HiddenBench** — a hidden-profile collaborative-reasoning task (4 agents each hold part
  of the information and must discuss to reach the correct answer).

A single configurable LLM agent plays both. You control everything from the repository
root (`.env` + `config/`), run one or both environments with Docker or locally, and score
the resulting transcripts with the bundled metrics toolkit. A small web lobby lets a human
take one seat in a HiddenBench game (e.g. to collect human discussion data).

## What it does

- Runs a full game/task in either environment and writes per-game transcripts and results.
- Uses one agent codebase for both environments; the LLM provider (OpenAI / Google /
  Anthropic / Ollama) and prompts are set in config.
- Optionally injects example material into the agent's prompt (full transcripts,
  single-utterance examples, or analysis notes) selected by a named **condition**; the
  default condition (`baseline`) injects nothing.
- Computes failure-mode metrics from transcripts (information surfacing, early convergence,
  lexical diversity, conformity) and emits a bilingual report.

## Directory layout

The repository **root is the control surface**; everything else is a component.

| Path | Role |
|------|------|
| `.env` / `.env.example` | The single settings file: language, condition, ports, and LLM API keys. Read by Docker Compose, the local runner, and the agent. |
| `config/inlg.yml` | Human-readable map of the run settings (which environments, language, per-environment parameters). |
| `config/conditions.yml` | Presets for the example-injection **conditions** (what gets fed into the agent prompt). |
| `docker-compose.yml` | Defines both environments as Compose **profiles** (`aiwolf`, `hiddenbench`); run one or both. |
| `docker/` | Dockerfiles: the agent image and the two server images. |
| `launcher/` | Given (environment, language, condition), assembles the agent config and starts the agent processes. |
| `Makefile`, `run_local.sh` | Entry points for Docker / local runs. |
| `agent/` | The LLM agent that plays both environments. `src/` is the engine; `aiwolf/` and `hidden-bench/` hold each environment's config and example slots; `prompts/` and `data/` are shared. |
| `server/aiwolf/` | Werewolf game server (Go). |
| `server/hidden-bench/` | HiddenBench server (Python). |
| `eval/` | Computes metrics from transcripts and writes a report. |
| `ui/` | Full browser UI (vendored from aiwolf-nlp-demo): werewolf + HiddenBench human play, solo/multi, with a condition selector. Spawns AI seats via the launcher. |
| `web/` | Minimal earlier prototype lobby for HiddenBench human play (superseded by `ui/`). |
| `docs/` | Design and methodology notes (background; not needed to run the system). |

## Requirements

- Docker + Docker Compose **or**, for local runs, [`uv`](https://docs.astral.sh/uv/),
  Python 3.11+, and Go 1.24+ (only for the werewolf server).
- An LLM provider API key (OpenAI / Google / Anthropic) **or** a local Ollama instance.

## Configure

```bash
cp .env.example .env
# then edit .env:
#   LANG_CODE=en|jp           language for both environments
#   CONDITION=baseline        example-injection preset (see config/conditions.yml)
#   OPENAI_API_KEY=...         (and/or GOOGLE_API_KEY / CLAUDE_API_KEY)
```

The LLM provider and model are set in the agent's environment config
(`agent/aiwolf/config/…` and `agent/hidden-bench/config/…`); OpenAI is the default.

## Run with Docker

```bash
docker compose --profile hiddenbench up --build              # HiddenBench only
docker compose --profile aiwolf up --build                   # Werewolf only
docker compose --profile aiwolf --profile hiddenbench up --build   # both at once

# equivalent Make targets:
make hiddenbench   |   make aiwolf   |   make both   |   make down   |   make logs
```

The two environments use different ports (8080 werewolf, 8090 HiddenBench), so they run
side by side.

## Run locally (no Docker)

```bash
cd agent && uv sync && cd ..      # build the agent's virtualenv once
make local-hb                     # HiddenBench server + 4 agents
make local-aiwolf                 # werewolf server (Go) + 5 agents
# or directly:  ./run_local.sh hiddenbench
```

## Evaluate

```bash
make eval        # reads server/hidden-bench/log/results/, writes .../eval/report.md + metrics.json
```

The report aggregates metrics by condition, so running several conditions produces one
comparison table.

## Human participation (HiddenBench)

```bash
cd web && uv sync
HB_URL=ws://127.0.0.1:8090/ws uv run uvicorn --app-dir src app:app --port 8000
# start the HiddenBench server + 3 agents, then open http://localhost:8000 to take the 4th seat
```

Each human session is saved under `web/log/human/` for later analysis.

## How a run works

1. A server (werewolf or HiddenBench) starts and waits for the required number of agents.
2. The launcher builds the agent config for the chosen environment/language/condition and
   starts the agent processes, which connect to the server over WebSocket.
3. The server drives the game/task; the agent answers each request via its configured LLM.
4. The server writes per-game results; `eval/` turns transcripts into metrics.

## Notes

- `server/aiwolf/` and `agent/` are vendored snapshots. The shared packet library
  `aiwolf-nlp-common` is installed from PyPI (`==0.7.0`), not vendored.
- The example-injection slots (`agent/<env>/exemplars/`) ship **empty**. Until you add
  files, any non-`baseline` condition automatically behaves like `baseline`.
- `.env`, virtualenvs, and `log/` are git-ignored. Never commit real API keys.
