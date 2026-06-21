#!/usr/bin/env bash
# Run the INLG system locally without docker (development).
# docker を使わずローカルで起動する開発用スクリプト.
#
# Usage:
#   ./run_local.sh hiddenbench      # HiddenBench server + 4 agents
#   ./run_local.sh aiwolf           # Werewolf server (go) + agents
#
# Reads LANG_CODE / CONDITION / API keys from the environment (or ./.env if present).
# Requires the manyshot project's .venv (has websockets, websocket-client, langchain, ...).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEV="$(cd "$HERE/.." && pwd)"
DOMAIN="${1:-hiddenbench}"

# Load .env if present.
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a

LANG_CODE="${LANG_CODE:-en}"
CONDITION="${CONDITION:-baseline}"
VENV="$DEV/aiwolf-jsai-manyshot_ver0/.venv/bin/python"
AGENT_DIR="$DEV/aiwolf-jsai-manyshot_ver0"

pids=()
cleanup() { echo "stopping..."; for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if [ "$DOMAIN" = "hiddenbench" ]; then
  echo "[local] starting HiddenBench server on :8090"
  ( cd "$DEV/hiddenbench-server" && PYTHONPATH=src "$VENV" src/server.py -c config/hiddenbench.yml ) &
  pids+=("$!")
  sleep 2
  echo "[local] launching 4 HiddenBench agents (lang=$LANG_CODE condition=$CONDITION)"
  "$VENV" "$HERE/launcher/launch_agents.py" \
    --agent-dir "$AGENT_DIR" --domain hiddenbench --lang "$LANG_CODE" \
    --condition "$CONDITION" --server-url ws://127.0.0.1:8090/ws --team inlg-hb --num 4 &
  pids+=("$!")
elif [ "$DOMAIN" = "aiwolf" ]; then
  echo "[local] starting werewolf (Go) server on :8080"
  ( cd "$DEV/aiwolf-nlp-server" && go run . -c ./config/default_5.yml ) &
  pids+=("$!")
  sleep 3
  echo "[local] launching 5 werewolf agents (lang=$LANG_CODE condition=$CONDITION)"
  "$VENV" "$HERE/launcher/launch_agents.py" \
    --agent-dir "$AGENT_DIR" --domain aiwolf --lang "$LANG_CODE" \
    --condition "$CONDITION" --server-url ws://127.0.0.1:8080/ws --team inlg-wolf --num 5 &
  pids+=("$!")
else
  echo "unknown domain: $DOMAIN (use hiddenbench | aiwolf)"; exit 2
fi

echo "[local] running. Ctrl-C to stop. Results: $DEV/hiddenbench-server/log/results (HiddenBench)"
wait
