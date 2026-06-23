<!-- Language: **English** | [日本語](README.ja.md) -->

# Multi-Agent LLM Discussion Platform

A platform for running and evaluating **multi-agent LLM discussions** in two environments:

- **Werewolf** — a social-deduction dialogue game (the AIWolfDial protocol, 5 players).
- **HiddenBench** — a hidden-profile collaborative-reasoning task (4 agents each hold part
  of the information and must discuss to reach the correct answer).

A single configurable LLM agent plays both. You control everything from the repository
root (`.env` + `config/`), run one or both environments with Docker or locally, and score
the resulting transcripts with the bundled metrics toolkit. A browser UI (`ui/`) lets a human
take a seat in a game (e.g. to collect human discussion data).

## What it does

- Runs a full game/task in either environment and writes per-game transcripts and results.
- Uses one agent codebase for both environments; the LLM provider (vLLM / OpenAI / Ollama /
  Google / Anthropic) and prompts are set in config.
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
| `config/system.yml` | Human-readable map of the run settings (which environments, language, per-environment parameters). |
| `config/conditions.yml` | Presets for the example-injection **conditions** (what gets fed into the agent prompt). |
| `docker-compose.yml` | Defines both environments as Compose **profiles** (`aiwolf`, `hiddenbench`); run one or both. |
| `docker/` | Dockerfiles: the agent image and the two server images. |
| `launcher/` | Given (environment, language, condition), assembles the agent config and starts the agent processes. |
| `Makefile`, `run_local.sh` | Entry points for Docker / local runs. |
| `agent/` | The LLM agent that plays both environments. `src/` is the engine; `aiwolf/` and `hidden-bench/` hold each environment's config and example slots; `prompts/` and `data/` are shared. |
| `server/aiwolf/` | Werewolf game server (Go). |
| `server/hidden-bench/` | HiddenBench server (Python). |
| `generator/` | Builds the example-injection slots (`scripts`/`utterances`/`analysis`) by calling Claude (the fixed generator family). Writes drafts into `agent/<env>/exemplars/`. |
| `eval/` | Computes metrics from transcripts and writes a report. |
| `ui/` | Full browser UI (vendored from aiwolf-nlp-demo): werewolf + HiddenBench human play, solo/multi, with a condition selector. Spawns AI seats via the launcher. |
| `docs/` | Design and methodology notes (background; not needed to run the system). |
| `archive/` | Deprecated components kept for reference only (e.g. the original `web/` lobby, superseded by `ui/`). Not wired into orchestration. |

## Documentation

Deeper docs live under `docs/` (each has an English `.md` and a Japanese `.ja.md`):

- [docs/SYSTEM.md](docs/SYSTEM.md) — system map + how to run each component
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) — the research design (6 conditions) + verified citations
- [docs/METRICS.md](docs/METRICS.md) — how to read the evaluation metrics (what each number means, which direction is good)
- [docs/VERIFICATION.md](docs/VERIFICATION.md) — why the werewolf server can't host HiddenBench
- [docs/EXEMPLARS.md](docs/EXEMPLARS.md) — how to author the example slots
- [docs/PROMPTS.md](docs/PROMPTS.md) — how agent prompts are managed as files

`docs/` covers the **whole system**. Component-internal docs that travel with a vendored
snapshot live next to that component (e.g. `agent/doc/`, `agent/ARCHITECTURE.md` document the
agent's internals; `server/*/doc/`). When in doubt, start from `docs/`.

## Requirements

- Docker + Docker Compose **or**, for local runs, [`uv`](https://docs.astral.sh/uv/),
  Python 3.11+, and Go 1.24+ (only for the werewolf server).
- An LLM provider API key (OpenAI / Anthropic / Google) **and/or** a local **vLLM** or Ollama
  server. The shipped default discussion model is Gemma served by vLLM (no key needed); the
  generator defaults to Claude and the judge to GPT (those need keys).

## Configure

```bash
cp .env.example .env
# then edit .env:
#   LANG_CODE=en|jp           language for both environments
#   CONDITION=baseline        example-injection preset (see config/conditions.yml)
#   OPENAI_API_KEY=...         (and/or GOOGLE_API_KEY / ANTHROPIC_API_KEY)
```

### Models — any provider, with sensible defaults

Every component picks its LLM independently and **any provider/model works** (Anthropic,
OpenAI, Google, or **anything served by vLLM or Ollama via an OpenAI-compatible endpoint**).
The shipped defaults follow the three-family separation in `docs/METHODOLOGY.md` (L3):

| Role | Default | Where it's set | Swap to anything via |
|------|---------|----------------|----------------------|
| Example generation | **Claude** (`claude-opus-4-8`) | `generator/config/generator.yml` | `provider:` (+ `base_url:`) |
| Discussion agent | **Gemma upper via vLLM** (`google/gemma-2-27b-it` @ `localhost:8000/v1`) | `agent/<env>/config/config.multi_turn.<lang>.yml` (`llm.type` + the `vllm:` section) | `llm.type:` + the matching provider section |
| LLM judge | **GPT** (`gpt-4o`) | `eval/config/judge.yml` | `provider:` (+ `base_url:`) |

All three use the **same setting method**: pick the backend with **`provider`** and configure
it with **`model` / `temperature` / `base_url` / `api_key_env`** — these keys mean the same
thing everywhere, and the provider vocabulary is shared: **`vllm`, `openai`, `ollama`,
`google`, `anthropic`** (plus `mock` for generator/judge). generator and the judge put those
keys at the top level of their config; the agent puts them under `llm:` (and may also use
per-provider sections like `vllm:`/`openai:` and per-role `llm.talk`/`llm.action` as
extensions). For the discussion agent the default is `llm.provider: vllm` with the model id and
endpoint in the `vllm:` section; switch backend by changing `llm.provider`. vLLM/Ollama need no
API key (a placeholder is used); otherwise `api_key_env` defaults per provider
(`OPENAI_API_KEY` / `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`).

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

## Generate the example slots

The six conditions (see `docs/METHODOLOGY.md`) inject example material that ships **empty**.
`generator/` produces it by calling Claude (the default generator family; any provider/model
is selectable in `config/generator.yml`) and writes drafts
into `agent/<env>/exemplars/<lang>/{scripts,utterances,analysis}/` for human review.

```bash
cd generator && uv sync
uv run src/main.py --dry-run          # render prompts only — no API calls, no writes
uv run src/main.py                    # generate (reads config/generator.yml + root .env)
```

Per example, Claude is called **twice**: once for the full transcript (⑤), once for the
topic-independent analysis (②). The single-utterance few-shot slot (③) is **sliced** from the
same transcript — not generated by a separate prompt — so the only difference between ③ and ⑤
is presentation form, never content (the comparison can't be called unfair). Leakage control
(L1) is mechanical: HiddenBench scripts are built from tasks beyond the evaluation slice;
werewolf scripts use generation-only seeds. The analysis prompt enforces L2 (topic-independent;
answers, option names, and proper nouns stripped). Set `provider: mock` in
`config/generator.yml` to exercise the pipeline offline with no API budget.

## Evaluate

```bash
cd eval && uv sync && cd ..    # build eval's virtualenv once
make eval        # objective metrics: reads log/hidden-bench/results/, writes .../results/eval/report.md + metrics.json
make judge       # objective + subjective LLM-judge in one pass (judge model = eval/config/judge.yml)
```

The report aggregates metrics by condition, so running several conditions produces one
comparison table. The judge is GPT by default but accepts any provider/model (see the model
table above and `eval/config/judge.yml`).

## Logs

All run logs collect under a **single `log/` tree at the repo root — the same location for
local and Docker runs**; only browser-UI (`ui/`) games are split into a `web/` sub-folder.

```
log/
  aiwolf/
    json/  game/  realtime/  match_optimizer.json   # werewolf game records (server)
    agents/<timestamp>/                              # agent logs + cost_summary.json/.md
    web/                                             # browser-UI games only
      json/  game/  realtime/   agents/<timestamp>/
  hidden-bench/
    results/*.json                                   # HiddenBench game results (server)
    results/eval/{report.md,metrics.json}            # eval output
    agents/<timestamp>/
    web/
      results/*.json   agents/<timestamp>/
```

The destination is driven by two env vars the orchestrators set for you: `LOG_ROOT` (the
repo-root `log/`, set by `run_local.sh`, Docker Compose, and the UI) and `LOG_SCOPE` (empty
normally; `web` for the UI). Override `LOG_ROOT` to relocate the whole tree. `log/` is
git-ignored.

## Human participation (browser UI)

Use `ui/` — the full browser UI for werewolf + HiddenBench human play (it spawns the AI seats
via the launcher and lets a human take a seat):

```bash
cd ui && make up        # builds + starts servers, agents, and the lobby
# then open http://localhost/hidden-bench (or /demo for werewolf)
```

See `ui/` for its own configuration (`ui/.env`, `ui/Makefile`). The earlier minimal `web/`
lobby has been retired to `archive/web/`.

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
