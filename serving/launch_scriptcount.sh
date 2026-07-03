#!/usr/bin/env bash
# Script-COUNT sweep (1 pass): K=0(baseline),1,3,5,10 injected scripts × HB 20 tasks + aiwolf 20 seeds.
# Same harness/metrics as run_en_8cond_rep1 → integrable. Fully detached (setsid+nohup), idempotent.
# K-dirs are nested subsets of scripts_pool. reply=ack (script-only, no analysis).
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"

# 20 HB eval tasks: leakage-safe (disjoint from script-source ids 4,8,12,14,30,32,34,48,58,60),
# trivial/saturated tasks dropped so an exemplar-count effect can be detected; broken kept (may be rescued).
HB_EVAL="2 3 6 9 10 11 13 15 17 18 19 20 21 22 23 24 25 26 27 28"

setsid nohup env \
  CONDS="baseline script_k1 script_k3 script_k5 script_k10" \
  CONDITIONS_FILE="config/conditions_scriptcount.yml" \
  ENDPOINTS="http://127.0.0.1:8000/v1 http://127.0.0.1:8002/v1" \
  NWORKERS=2 \
  LANG_CODE=en \
  HB_TASK_LIST="$HB_EVAL" \
  AW_GAMES=20 \
  GAME_TIMEOUT=1200 AW_TIMEOUT=600 RETRIES=5 \
  HB_RESP_TIMEOUT_MS=600000 HB_ACTION_TIMEOUT_MS=300000 \
  RESULTS="$ROOT/results/run_en_scriptcount" \
  bash serving/run_matrix_parallel.sh > "$ROOT/serving/matrix_scriptcount.log" 2>&1 &

echo "script-count sweep launched (detached) pid=$!"
echo "  results -> results/run_en_scriptcount   log -> serving/matrix_scriptcount.log"
echo "  K levels: 0(baseline),1,3,5,10  | HB tasks: $(echo $HB_EVAL | wc -w)  | aiwolf seeds: 20  | endpoints: 8000,8002"
