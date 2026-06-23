#!/usr/bin/env bash
# Kill any stray server/agent processes from runs (NOT the vLLM server).
# Run as a file so the kill patterns don't appear in the caller's own command line
# (pkill -f matches full cmdlines, including the invoking shell — self-match kills the caller).
self=$$
KILL_DRIVER="${KILL_DRIVER:-0}"   # set to 1 to also kill the run_matrix.sh driver
kill_pat() {
  local pat="$1" pid
  for pid in $(pgrep -f "$pat" 2>/dev/null); do
    [ "$pid" = "$self" ] && continue
    [ "$pid" = "$PPID" ] && continue
    kill -9 "$pid" 2>/dev/null || true
  done
}
kill_pat "launch_agents.py"
kill_pat "agent/.venv/bin/python"
kill_pat "hidden-bench/src/server.py"
kill_pat "default_5_test.yml"          # aiwolf go server (run_matrix)
kill_pat "default_5_smoke.yml"         # aiwolf go server (smoke)
kill_pat "go-build"                     # `go run` compiled temp binary
kill_pat "server/aiwolf"               # any aiwolf go process (go run / wrapper shell)
kill_pat "aiwolf-server"               # the compiled aiwolf binary (parallel runs: cmdline is ./aiwolf-server -c ...)
kill_pat "aiwolf_w"                     # per-worker aiwolf config (config/aiwolf_w<N>.yml)
[ "$KILL_DRIVER" = "1" ] && { kill_pat "run_matrix.sh"; kill_pat "run_matrix_parallel.sh"; }
echo "cleanup done"
