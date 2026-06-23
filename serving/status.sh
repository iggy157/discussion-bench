#!/usr/bin/env bash
# Accurate run status. Run as a FILE so the grep patterns are not in the caller's cmdline
# (pgrep -f would otherwise self-match the invoking shell). We also filter out any shell
# wrapper / this script from counts.
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"

# count real processes matching $1 (exclude snapshot shells, this script, pgrep/grep)
count() {
  pgrep -af "$1" 2>/dev/null \
    | grep -v "snapshot-bash" | grep -v "status.sh" | grep -v "cleanup_runs.sh" \
    | grep -vE "pgrep|grep " | wc -l
}
list() {
  pgrep -af "$1" 2>/dev/null \
    | grep -v "snapshot-bash" | grep -v "status.sh" | grep -v "cleanup_runs.sh" \
    | grep -vE "pgrep|grep "
}

echo "==== STATUS $(date '+%F %H:%M:%S') ===="
echo "vLLM:            $(pgrep -f 'vllm serve google/gemma-4-31B' >/dev/null && echo UP || echo DOWN)"
echo "HB servers:      $(count 'hidden-bench/src/server.py')"
echo "aiwolf go srv:   $(count 'default_5_test.yml')"
echo "launchers:       $(count 'launch_agents.py')"
echo "agent subprocs:  $(count 'agent/.venv/bin/python -c')"
echo "generator:       $(count 'generator/src/main.py')"
echo "matrix driver:   $(count 'run_matrix.sh')"
echo "-- GPU --"
nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader | sed -n '1,2p'
echo "-- result counts --"
echo "HB live results: $(ls log/hidden-bench/results/*.json 2>/dev/null | wc -l)"
echo "aiwolf live json:$(ls log/aiwolf/json/*.json 2>/dev/null | wc -l)"
if [ -d results/local_run ]; then
  echo "-- collected results/local_run --"
  find results/local_run -name '*.json' 2>/dev/null | sed 's#results/local_run/##' | awk -F/ '{print $1"/"$2}' | sort | uniq -c
fi
echo "-- detail (running cmds) --"
list 'launch_agents.py' | cut -c1-90
