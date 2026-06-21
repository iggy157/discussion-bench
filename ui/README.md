<!-- Language: **English** | [日本語](README.ja.md) -->

# ui/ — Web UI (based on aiwolf-nlp-demo)

The browser-playable UI layer. It vendors aiwolf-nlp-demo's rich werewolf UI (SvelteKit
viewer + FastAPI lobby + Caddy) and **replaces only the agent spawning with this repo's
`launcher`**. So the AI seats run the same shared agent the experiments use, and you can
**pick the experiment condition (with/without script, etc.) from the UI** when launching.

> ⚠️ The backend (lobby agent spawning / config generation) is replaced and verified, but the
> frontend (nav, condition selector, HiddenBench page) has **not** been browser- or
> SvelteKit-build-verified.

## Current state

| Item | Status |
|---|---|
| Demo UI vendored (viewer / lobby / Caddy / configs) | ✅ |
| Lobby AI spawn replaced with this repo's `launcher` (werewolf, condition-aware) | ✅ code-level verified |
| Lobby extended to HiddenBench (domain switch, fixed 4, HB URL) | ✅ code-level verified |
| Solo/multi, matchmaking, takeover on leave (from demo) | ✅ reused as-is |
| Human plays on the same `server/aiwolf` + same config | ✅ by design |
| `/api/conditions` returns the condition list | ✅ |
| Condition selector on the werewolf page | ✅ implemented (browser-verify needed) |
| Top nav (AIWolf / HiddenBench switch, `+layout.svelte`) | ✅ implemented (browser-verify needed) |
| HiddenBench page (`/hidden-bench`, condition select + discussion UI) | ✅ implemented (browser-verify needed) |
| One-shot `docker compose` (game-server=server/aiwolf, lobby=our agent, caddy=viewer, HB server) | ✅ wired (build-verify needed) |
| Lobby Docker image bundles this repo's agent | ✅ Dockerfile done |
| End-to-end run in a real browser / SvelteKit build | ⬜ not yet (needs a real machine) |

> The Python side (lobby spawning / config generation) is verified via `py_compile` + a real
> `build_config` call. The SvelteKit frontend is not build-verified here (no pnpm/Node22), so
> **it needs verification on a real machine**.

## How it works (the replacement point)

- `lobby/main.py`'s `_build_agent_config()` calls `launcher/launch_agents.py`'s
  `build_config()` to generate **this repo's agent config** from `domain` (aiwolf/hiddenbench)
  + the selected `condition` + language.
- The AI-seat processes are launched with the same Popen mechanism as the demo, but the target
  is `agent/` (this repo's shared agent).
- The target / launcher / condition are overridable via env vars:
  - `AGENT_LLM_DIR` (default `../agent`), `LAUNCHER_DIR` (default `../launcher`),
    `CONDITIONS_FILE` (default `../config/conditions.yml`), `CONDITION` (default `baseline`),
    `AGENT_LLM_PYTHON` (the agent's Python).
- The LLM model/provider are decided by the **agent config (`agent/aiwolf/config`)** — so
  humans play with the same settings as the experiments; the demo's `LLM_PROVIDER/LLM_MODEL`
  are not applied.

## Run with docker compose (recommended)

```bash
# prepare the root .env (API keys, CONDITION, LANG_CODE)
cp ../.env.example ../.env   # if not yet

cd .   # discussion-bench/ui
docker compose up --build
# in the browser:
#   http://localhost/demo          … werewolf (AIWolf)
#   http://localhost/hidden-bench   … HiddenBench
# switch via the top nav. AI seats launch with the condition picked in the on-screen selector.
```

Compose brings up game-server (=`server/aiwolf`), hidden-bench-server (=`server/hidden-bench`),
lobby (bundling this repo's `agent` + `launcher`), and caddy (serves the viewer + WS reverse proxy).

## Run locally (without compose, interim)

```bash
# 1) start the werewolf server (separate terminal)
cd ../server/aiwolf && go run . -c ./config/default_5.yml

# 2) start the lobby (needs fastapi/uvicorn; uses the agent's Python)
cd lobby
AGENT_LLM_PYTHON=../../agent/.venv/bin/python \
GAME_WS_INTERNAL_URL=ws://127.0.0.1:8080/ws \
GAME_WS_PUBLIC_URL=ws://127.0.0.1:8080/ws \
CONDITION=baseline \
  uvicorn main:app --port 8002

# 3) start the viewer (SvelteKit; needs node/pnpm)
cd ../viewer && pnpm install && pnpm dev
# open the dev server and go to /demo. AI seats launch with the CONDITION's condition.
```

## Vendored from

`aiwolf-nlp-demo` (lobby / viewer / Caddy / configs / scripts). We do NOT vendor
`repos/aiwolf-nlp-server` or `repos/aiwolf-nlp-agent-llm`; we use this repo's `server/aiwolf`
and `agent/`.
