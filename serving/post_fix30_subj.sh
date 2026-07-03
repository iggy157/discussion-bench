#!/usr/bin/env bash
# post_fix30_subj.sh — fx_big2 + fx_small2 (30試合拡張) の両完了を待ち、listwise 主観評価を
# n-seeds=30 で4本 (big/small × HB/aiwolf) 自動実行。setsid nohup で分離起動する前提。
# 完了マーカー: serving/SUBJ_FIX30_DONE
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
set -a; [ -f ./.env ] && . ./.env; set +a
EV="$ROOT/eval/.venv/bin/python"
LOG="$ROOT/serving/subj_fix30.log"
log(){ echo "[$(date '+%F %H:%M:%S')] $*" >>"$LOG"; }

log "=== post_fix30_subj: waiting for both matrices (max 14h) ==="
t=0
while [ "$t" -lt 50400 ]; do
  if grep -q "ALL DONE" serving/matrix_fx_big2.log 2>/dev/null \
     && grep -q "ALL DONE" serving/matrix_fx_small2.log 2>/dev/null; then break; fi
  sleep 180; t=$((t+180))
done
if [ "$t" -ge 50400 ]; then log "!! timeout waiting for matrices — abort"; exit 1; fi
log "both matrices DONE — starting listwise subjective evals n=30 (judge on :8000)"

C8="baseline,analysis_only,utterance_fewshot,utterance_fewshot_analysis,situation_fewshot,situation_fewshot_analysis,script_fewshot_k5,script_fewshot_analysis_k5"
C10="$C8,script_fewshot_k1,script_fewshot_analysis_k1"

run_subj(){ # flat domain conds out label
  log ">> $5"
  PYTHONPATH="$ROOT/eval/src" "$EV" "$ROOT/eval/src/evaluate_listwise_subj.py" \
    --flat "$1" --domain "$2" --conds "$3" --n-seeds 30 --out "$4" --label "$5" >>"$LOG" 2>&1 \
    && log "<< $5 OK -> $4" || log "!! $5 FAILED"
}

run_subj "results/run_fix10_big/hiddenbench_flat"   hb     "$C8"  "results/run_fix10_big/subj30_hb.md"      fx30_big_hb
run_subj "results/run_fix10_big/aiwolf_flat"        aiwolf "$C8"  "results/run_fix10_big/subj30_aiwolf.md"  fx30_big_aiwolf
run_subj "results/run_fix10_small/hiddenbench_flat" hb     "$C10" "results/run_fix10_small/subj30_hb.md"     fx30_small_hb
run_subj "results/run_fix10_small/aiwolf_flat"      aiwolf "$C10" "results/run_fix10_small/subj30_aiwolf.md" fx30_small_aiwolf

log "=== post_fix30_subj: ALL DONE ==="
touch "$ROOT/serving/SUBJ_FIX30_DONE"
