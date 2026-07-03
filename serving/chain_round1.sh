#!/usr/bin/env bash
# chain_round1.sh — 1周目(HB60問=65−台本出典{4,8,12,14,30} / aiwolf60シード)完成チェーン。
#   1. 現行 matrix (fx_big2/fx_small2) の ALL DONE を待つ
#   2. リークid(8,12,14,30)のHBゲームを flat から *_offsplit へ退避 (4は退避済み)
#   3. 完成フィル: HB残り28問 + aiwolf g31..60 を big/small 並走で実行
#   4. 両完了後 listwise 主観 n=60 を4本実行 → subj60_*.md
# マーカー: serving/ROUND1_DONE / ログ: serving/chain_round1.log
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
set -a; [ -f ./.env ] && . ./.env; set +a
EV="$ROOT/eval/.venv/bin/python"
LOG="$ROOT/serving/chain_round1.log"
log(){ echo "[$(date '+%F %H:%M:%S')] $*" >>"$LOG"; }

wait_done(){ # log1 log2 max_sec
  local t=0
  while [ "$t" -lt "$3" ]; do
    grep -q "ALL DONE" "$1" 2>/dev/null && grep -q "ALL DONE" "$2" 2>/dev/null && return 0
    sleep 180; t=$((t+180))
  done
  return 1
}

log "=== chain_round1: waiting for fx_big2/fx_small2 (max 14h) ==="
wait_done serving/matrix_fx_big2.log serving/matrix_fx_small2.log 50400 \
  || { log "!! timeout on phase-1 matrices"; exit 1; }

log "phase 1 done — retiring leak ids (8,12,14,30) from HB flats"
for R in run_fix10_big run_fix10_small; do
  mkdir -p "results/$R/hiddenbench_flat_offsplit"
  n=0
  for gi in 8 12 14 30; do
    for f in results/$R/hiddenbench_flat/*__g${gi}_*.json; do
      [ -f "$f" ] && mv "$f" "results/$R/hiddenbench_flat_offsplit/" && n=$((n+1))
    done
  done
  log "  $R: retired $n leak-id games"
done

HB_REST="13 22 23 24 31 37 40 41 42 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65"
C8="baseline analysis_only utterance_fewshot utterance_fewshot_analysis situation_fewshot situation_fewshot_analysis script_fewshot_k5 script_fewshot_analysis_k5"
C10="$C8 script_fewshot_k1 script_fewshot_analysis_k1"

log "launching round-1 completion fills (HB 28 ids, aiwolf g31..60)"
setsid nohup env \
  LANG_CODE=en GAMES=60 AW_GAMES=60 NWORKERS=4 RETRIES=3 \
  HB_TASK_LIST="$HB_REST" \
  ENDPOINTS="http://127.0.0.1:8000/v1 http://127.0.0.1:8002/v1" \
  CONDS="$C8" CONDITIONS_FILE="config/conditions_v2_typed10.yml" \
  RESULTS="$ROOT/results/run_fix10_big" RUN_TAG=fx_big \
  bash serving/run_matrix_parallel.sh > serving/matrix_fx_big3.log 2>&1 &
setsid nohup env \
  LANG_CODE=en GAMES=60 AW_GAMES=60 NWORKERS=4 RETRIES=3 AW_TIMEOUT=720 \
  HB_TASK_LIST="$HB_REST" \
  ENDPOINTS="http://127.0.0.1:8004/v1 http://127.0.0.1:8014/v1" \
  CONDS="$C10" CONDITIONS_FILE="config/conditions_v2_typed10.yml" \
  RESULTS="$ROOT/results/run_fix10_small" RUN_TAG=fx_small \
  HB_PORT_BASE=8110 AW_PORT_BASE=8360 \
  bash serving/run_matrix_parallel.sh > serving/matrix_fx_small3.log 2>&1 &
sleep 10

log "waiting for completion fills (max 16h)"
wait_done serving/matrix_fx_big3.log serving/matrix_fx_small3.log 57600 \
  || { log "!! timeout on phase-2 matrices"; exit 1; }

log "round-1 complete — listwise subjective n=60 (judge on :8000)"
CC8="baseline,analysis_only,utterance_fewshot,utterance_fewshot_analysis,situation_fewshot,situation_fewshot_analysis,script_fewshot_k5,script_fewshot_analysis_k5"
CC10="$CC8,script_fewshot_k1,script_fewshot_analysis_k1"
run_subj(){ # flat domain conds out label
  log ">> $5"
  PYTHONPATH="$ROOT/eval/src" "$EV" "$ROOT/eval/src/evaluate_listwise_subj.py" \
    --flat "$1" --domain "$2" --conds "$3" --n-seeds 60 --out "$4" --label "$5" >>"$LOG" 2>&1 \
    && log "<< $5 OK -> $4" || log "!! $5 FAILED"
}
run_subj "results/run_fix10_big/hiddenbench_flat"   hb     "$CC8"  "results/run_fix10_big/subj60_hb.md"      r1_big_hb
run_subj "results/run_fix10_big/aiwolf_flat"        aiwolf "$CC8"  "results/run_fix10_big/subj60_aiwolf.md"  r1_big_aiwolf
run_subj "results/run_fix10_small/hiddenbench_flat" hb     "$CC10" "results/run_fix10_small/subj60_hb.md"     r1_small_hb
run_subj "results/run_fix10_small/aiwolf_flat"      aiwolf "$CC10" "results/run_fix10_small/subj60_aiwolf.md" r1_small_aiwolf

log "=== chain_round1: ALL DONE ==="
touch "$ROOT/serving/ROUND1_DONE"
