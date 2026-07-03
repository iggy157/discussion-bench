#!/usr/bin/env bash
# English MAIN run (1 pass / no repeat): 8 conditions × HB 62 eval tasks + aiwolf 60 seeds.
# 完全バックグラウンド（setsid+nohup）でWiFi切断に耐える。idempotentなので中断→再実行で続きから。
# judge=gemma(local)。台本K=3（種別分散: task4/12/60）。共通analysis・situation(10場面)使用。
# 追加redoは別RESULTSに走らせて後で合体。
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"

# eval = 65 tasks minus the 3 main script tasks {4,12,60} = 62 (L1: scripts disjoint from eval)
HB_EVAL="$(python3 -c 'print(" ".join(str(i) for i in range(1,66) if i not in (4,12,60)))')"

setsid nohup env \
  CONDS="baseline analysis_only utterance_fewshot utterance_fewshot_analysis situation_fewshot situation_fewshot_analysis script_fewshot script_fewshot_analysis" \
  CONDITIONS_FILE="config/conditions_v2.yml" \
  ENDPOINTS="http://127.0.0.1:8000/v1 http://127.0.0.1:8002/v1" \
  NWORKERS=2 \
  LANG_CODE=en \
  HB_TASK_LIST="$HB_EVAL" \
  AW_GAMES=60 \
  GAME_TIMEOUT=1200 AW_TIMEOUT=600 RETRIES=5 \
  HB_RESP_TIMEOUT_MS=600000 HB_ACTION_TIMEOUT_MS=300000 \
  RESULTS="$ROOT/results/run_en_8cond_rep1" \
  bash serving/run_matrix_parallel.sh > "$ROOT/serving/matrix_en.log" 2>&1 &

echo "EN MAIN run launched (detached) pid=$!"
echo "  results -> results/run_en_8cond_rep1   log -> serving/matrix_en.log"
echo "  HB eval tasks: $(echo $HB_EVAL | wc -w)  | aiwolf seeds: 60  | conditions: 8  | endpoints: 2 (8000,8002)"
