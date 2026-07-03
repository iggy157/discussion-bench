#!/usr/bin/env bash
# Lightweight-model run (gemma-3-4b-it, served under the gemma-2-27b-it alias): 8 conditions × K=3
# × HB 62 eval tasks + aiwolf 60 seeds. Same harness/eval/conditions as run_en_8cond_rep1 so the
# CHEAP-model effect can be compared directly against the 31B run. Detached (setsid+nohup), idempotent.
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"

# Same eval set as rep1: 65 minus the 3 script-source tasks {4,12,60} = 62 (L1 disjoint).
HB_EVAL="$(python3 -c 'print(" ".join(str(i) for i in range(1,66) if i not in (4,12,60)))')"

setsid nohup env \
  CONDS="baseline analysis_only utterance_fewshot utterance_fewshot_analysis situation_fewshot situation_fewshot_analysis script_fewshot script_fewshot_analysis" \
  CONDITIONS_FILE="config/conditions_v2.yml" \
  ENDPOINTS="http://127.0.0.1:8004/v1 http://127.0.0.1:8005/v1" \
  NWORKERS=2 \
  LANG_CODE=en \
  HB_TASK_LIST="$HB_EVAL" \
  AW_GAMES=60 \
  GAME_TIMEOUT=1200 AW_TIMEOUT=600 RETRIES=5 \
  HB_RESP_TIMEOUT_MS=600000 HB_ACTION_TIMEOUT_MS=300000 \
  RESULTS="$ROOT/results/run_en_8cond_small4b" \
  bash serving/run_matrix_parallel.sh > "$ROOT/serving/matrix_en_small.log" 2>&1 &

echo "EN SMALL-model run launched (detached) pid=$!"
echo "  model: gemma-3-4b-it (alias google/gemma-2-27b-it)  endpoints: 8004,8005 (GPU3,5)"
echo "  results -> results/run_en_8cond_small4b   log -> serving/matrix_en_small.log"
echo "  HB tasks: $(echo $HB_EVAL | wc -w)  | aiwolf seeds: 60  | conditions: 8  | K=3"
