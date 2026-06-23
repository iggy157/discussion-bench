#!/usr/bin/env bash
# Run the discussion-bench locally without docker (development).
# docker を使わずローカルで起動する開発用スクリプト. リポジトリ直下から実行する.
#
# Usage:
#   ./run_local.sh hiddenbench      # HiddenBench server + 4 agents
#   ./run_local.sh aiwolf           # Werewolf server (go) + agents
#
# Reads the single root ./.env (secrets + LANG_CODE/CONDITION). Requires the agent's
# .venv (cd agent && uv sync) which has websockets, websocket-client, langchain, ...
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="${1:-hiddenbench}"

# Single central .env.
[ -f "$ROOT/.env" ] && set -a && . "$ROOT/.env" && set +a

LANG_CODE="${LANG_CODE:-en}"
CONDITION="${CONDITION:-baseline}"
VENV="$ROOT/agent/.venv/bin/python"
AGENT_DIR="$ROOT/agent"

# Unified log tree at the repo root: servers + agents write under $ROOT/log/<domain>/...,
# the same place Docker writes to (LOG_SCOPE is left empty -> non-web). The browser UI sets
# LOG_SCOPE=web to split web games into <domain>/web/.
export LOG_ROOT="$ROOT/log"

[ -x "$VENV" ] || { echo "agent venv not found at $VENV — run: (cd agent && uv sync)"; exit 1; }

pids=()
cleanup() { echo "stopping..."; for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if [ "$DOMAIN" = "hiddenbench" ]; then
  echo "[local] starting HiddenBench server on :8090 (lang=$LANG_CODE)"
  ( cd "$ROOT/server/hidden-bench" && HB_LANG="$LANG_CODE" CONDITION="$CONDITION" \
      PYTHONPATH=src "$VENV" src/server.py -c config/hiddenbench.yml ) &
  pids+=("$!")
  sleep 2
  echo "[local] launching 4 HiddenBench agents (condition=$CONDITION)"
  "$VENV" "$ROOT/launcher/launch_agents.py" \
    --agent-dir "$AGENT_DIR" --domain hiddenbench --lang "$LANG_CODE" \
    --condition "$CONDITION" --server-url ws://127.0.0.1:8090/ws --team discussion-bench-hb --num 4 &
  pids+=("$!")
elif [ "$DOMAIN" = "aiwolf" ]; then
  echo "[local] starting werewolf (Go) server on :8080"
  ( cd "$ROOT/server/aiwolf" && go run . -c ./config/default_5.yml ) &
  pids+=("$!")
  sleep 3
  echo "[local] launching 5 werewolf agents (lang=$LANG_CODE condition=$CONDITION)"
  "$VENV" "$ROOT/launcher/launch_agents.py" \
    --agent-dir "$AGENT_DIR" --domain aiwolf --lang "$LANG_CODE" \
    --condition "$CONDITION" --server-url ws://127.0.0.1:8080/ws --team discussion-bench-wolf --num 5 &
  pids+=("$!")
else
  echo "unknown domain: $DOMAIN (use hiddenbench | aiwolf)"; exit 2
fi

echo "[local] running. Ctrl-C to stop. HiddenBench results: $ROOT/server/hidden-bench/log/results"
wait
