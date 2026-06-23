<!-- Language: **English** | [日本語](SYSTEM.ja.md) -->

# System overview

This document is a map you can read top-down to understand what the system is and how it is
built. For day-to-day usage see the [README](../README.md); for the research design see
[METHODOLOGY.md](METHODOLOGY.md) and [VERIFICATION.md](VERIFICATION.md).

## In one line

A platform for running and evaluating multi-agent LLM discussions. There are two
environments: **werewolf** (a social-deduction dialogue game, AIWolfDial protocol, 5 players)
and **HiddenBench** (a hidden-profile collaborative-reasoning task, 4 agents). The same single
agent plays both. Everything is controlled from the repository root, and you can run one
environment or both at once.

## Why it is built this way

Werewolf and HiddenBench are different games with different rules. The naive approach — a
separate agent per environment — would make "comparison under the same conditions"
impossible. So the system **shares the agent's internals (prompt building, example injection,
LLM calls) across both environments and only separates the game-progression rules**.

In other words, fairness is held not by forcing the two games to share mechanics, but by
holding the **intervention layer** (agent side) and the **evaluation** (transcript metrics)
identical. Each game follows its community's canonical protocol. The rationale is in the
methodology doc.

## Components

The repository root is the control surface (`.env`, `config/`, `docker-compose.yml`,
`Makefile`, `launcher/`). Components hang off it:

| Path | Role |
|------|------|
| [../agent/](../agent/) | The **one shared agent**. `src/` is the brain (incl. `src/agent/hiddenbench.py`); `aiwolf/` and `hidden-bench/` hold each environment's config + prompt + example slots. |
| [../server/aiwolf/](../server/aiwolf/) | Werewolf (AIWolfDial) game server (Go). Vendored snapshot, **unmodified**. |
| [../server/hidden-bench/](../server/hidden-bench/) | HiddenBench server (Python). 4 agents, fixed T=15 sequential, pre/post elicitation, scoring. |
| [../eval/](../eval/) | Computes failure-mode metrics from transcripts + a subjective LLM-judge → bilingual report. |
| [../ui/](../ui/) | Browser UI (vendored aiwolf-nlp-demo): werewolf + HiddenBench human play, solo/multi, with a condition selector. |
| [../archive/](../archive/) | Deprecated, reference-only components (e.g. the original `web/` lobby, superseded by `ui/`). Not wired into orchestration. |
| [../launcher/](../launcher/) | Picks environment·condition·lang → builds the agent config → runs the agents. |
| [../docker-compose.yml](../docker-compose.yml) | Both environments, concurrent via profiles (`aiwolf`, `hiddenbench`). |

## Why one agent can drive both environments

The HiddenBench server introduces **no new wire protocol**: it uses only the four request
types already in `aiwolf-nlp-common` 0.7.0 (NAME / INITIALIZE / TALK / FINISH). HiddenBench's
per-turn context (whether it is the pre/discussion/post phase, the clues, the options, the
round) rides in the packet's `info.profile` field as JSON. The agent's `HiddenBenchAgent`
reads that JSON and routes the standard TALK request to phase-specific prompts (`hb_pre` /
`hb_discussion` / `hb_post`). Sequential turn order is enforced by the server eliciting agents
one at a time with the growing transcript (faithful to the paper §4.2). The example (script /
analysis) injection goes through the **same code path** as werewolf.

## How to run (from the repository root)

```bash
cp .env.example .env          # set OPENAI_API_KEY etc., LANG_CODE, CONDITION

# Docker — both environments at once
docker compose --profile aiwolf --profile hiddenbench up --build
#   make both | make hiddenbench | make aiwolf

# Local (no docker)
cd agent && uv sync && cd ..
make local-hb                 # HiddenBench server + 4 agents

# Evaluate
make eval                     # objective only  -> log/hidden-bench/results/eval/report.md
make judge                    # objective + subjective LLM-judge

# Browser UI
cd ui && docker compose up --build   # http://localhost/demo and /hidden-bench
```

## Running a component on its own

Each component is also runnable standalone (the per-directory details that used to live in
component READMEs):

- **HiddenBench server** (`server/hidden-bench`): `uv run src/server.py -c config/hiddenbench.yml`;
  agents then connect to `ws://<host>:8090/ws`. Config knobs (`agent_count`, `total_rounds`,
  `task_ids`/`task_limit`, `seed`, `output_dir`) are documented in `config/hiddenbench.yml`.
  Smoke test without an LLM: run the server, then `python tests/stub_agent.py ws://127.0.0.1:8090/ws P1` ×4.
- **Evaluation** (`eval`): `make eval` (objective only, no API) / `make judge` (objective +
  subjective LLM-judge). Judge model in `eval/config/judge.yml`; judge prompt in
  `eval/prompts/judge.{en,ja}.txt`. For werewolf, first convert logs with
  `eval/src/werewolf_adapter.py`. Metric provenance is in [METHODOLOGY.md](METHODOLOGY.md) §4.
- **UI** (`ui`): `cd ui && docker compose up --build` → `/demo` and `/hidden-bench`. For local
  dev without compose: run `server/aiwolf` (`go run .`), the lobby (`uvicorn main:app`), and the
  viewer (`pnpm dev`) separately. The SvelteKit frontend is not browser-verified in this repo.
- **archive** (`archive/web`): the earlier minimal HiddenBench lobby, superseded by `ui/`;
  retired to `archive/` for reference and not wired into orchestration.

## Status

Servers, the agent's HiddenBench support, the metrics, launcher, compose, and the browser UI
are built and smoke-tested (server↔real-client integration, faithful transcript, scoring,
evaluation report). The example slots (`agent/<env>/exemplars/`) are **intentionally empty** —
add scripts / utterance-fewshot / analysis later; until then non-`baseline` conditions behave
like `baseline`. Running real agents needs LLM provider API keys (or a local vLLM / Ollama serving Gemma).
The SvelteKit UI is not browser-tested in this environment — run it with `docker compose`.
