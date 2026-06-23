#!/usr/bin/env bash
# LOCAL validation matrix: conditions × domains × N games, all on local gemma (vLLM).
# Fully detached & resilient: each server/agent group runs in its own process group; completion
# is detected by counting per-game result JSONs; groups are then killed before the next cell.
#
# Configurable via env:
#   CONDS="baseline analysis_only ..."   (default: all 6)
#   DOMAINS="hiddenbench aiwolf"          (default: both)
#   GAMES=3                               (games per cell)
#   LANG_CODE=jp
#   CELL_TIMEOUT=5400                     (seconds to wait per cell)
#   DO_EVAL=1                             (run eval at the end; default 1)
#
# Usage: setsid nohup serving/run_matrix.sh > serving/matrix.log 2>&1 &
set -uo pipefail

ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
# Capture caller overrides BEFORE sourcing .env (which exports its own LANG_CODE/CONDITION and
# would otherwise clobber them). .env is sourced only for secrets (API keys).
_LANG_OVERRIDE="${LANG_CODE:-}"
set -a; [ -f ./.env ] && . ./.env; set +a
export LOG_ROOT="$ROOT/log"
unset LOG_SCOPE 2>/dev/null || true

# Caller's LANG_CODE wins; if unset, default jp (ignore .env's value — lang is per-run here).
LANG_CODE="${_LANG_OVERRIDE:-jp}"
GAMES="${GAMES:-3}"
CELL_TIMEOUT="${CELL_TIMEOUT:-5400}"
DO_EVAL="${DO_EVAL:-1}"
PY="$ROOT/agent/.venv/bin/python"
RESULTS="$ROOT/results/local_run"
LOGD="$ROOT/serving/matrix_logs"
DEFAULT_CONDS="baseline analysis_only utterance_fewshot utterance_fewshot_analysis script_fewshot script_fewshot_analysis"
read -r -a CONDS <<<"${CONDS:-$DEFAULT_CONDS}"
read -r -a DOMAINS <<<"${DOMAINS:-hiddenbench aiwolf}"
mkdir -p "$RESULTS" "$LOGD"

log(){ echo "[$(date '+%F %H:%M:%S')] $*"; }

# wait until $1 has >= $2 *.json files OR $3 seconds pass. echo final count; return 0 if reached.
wait_results(){
  local dir="$1" want="$2" max="$3" t=0 n=0
  while [ "$t" -lt "$max" ]; do
    n=$(ls "$dir"/*.json 2>/dev/null | wc -l)
    [ "$n" -ge "$want" ] && { echo "$n"; return 0; }
    sleep 10; t=$((t+10))
  done
  echo "$n"; return 1
}

# aiwolf writes its per-game JSON incrementally; win_side is the string "NONE" while the game is
# ONGOING/undecided (truthy!) and only becomes "VILLAGER"/"WEREWOLF" when it FINISHES. Counting
# mere truthiness reports completion at game start (day-0, ~2 utterances). Count only games that
# finished with a real winning team. echo final count; return 0 when >= want.
wait_aiwolf(){
  local dir="$1" want="$2" max="$3" t=0 n=0
  while [ "$t" -lt "$max" ]; do
    n=$("$PY" - "$dir" <<'PYEOF'
import json,glob,sys,os
d=sys.argv[1]; n=0
for f in glob.glob(os.path.join(d,"*.json")):
    try:
        if json.load(open(f)).get("win_side") in ("VILLAGER","WEREWOLF"): n+=1
    except Exception: pass
print(n)
PYEOF
)
    [ "${n:-0}" -ge "$want" ] && { echo "$n"; return 0; }
    sleep 10; t=$((t+10))
  done
  echo "${n:-0}"; return 1
}

killgrp(){ local pg; for pg in "$@"; do kill -TERM -"$pg" 2>/dev/null || true; done; sleep 3; for pg in "$@"; do kill -KILL -"$pg" 2>/dev/null || true; done; }

run_hb(){
  # One game per server launch. The HB server's multi-game cycle is unreliable (it closes the
  # listener after the first game), but single-game launches are rock-solid — so we launch a
  # fresh server+agents per game, each pinned to a distinct task id via HB_TASK_IDS. Tasks
  # 1..GAMES are the evaluation set (disjoint from the exemplar tasks 21..23 -> L1 preserved).
  local cond="$1" rdir="$LOG_ROOT/hidden-bench/results"
  mkdir -p "$RESULTS/hiddenbench/$cond" "$RESULTS/hiddenbench_flat"
  log "HB $cond: starting ($GAMES games, one server launch per game)"
  local done_n=0 srv ag got gi
  for gi in $(seq 1 "$GAMES"); do
    mkdir -p "$rdir"; rm -f "$rdir"/*.json 2>/dev/null || true
    setsid bash -c "cd '$ROOT/server/hidden-bench' && HB_LANG='$LANG_CODE' CONDITION='$cond' HB_TASK_IDS='$gi' LOG_ROOT='$LOG_ROOT' PYTHONPATH=src '$PY' src/server.py -c config/hiddenbench.yml" >"$LOGD/hb_${cond}_g${gi}_server.log" 2>&1 &
    srv=$!
    sleep 6
    setsid bash -c "DOMAIN=hiddenbench LANG_CODE='$LANG_CODE' CONDITION='$cond' LOG_ROOT='$LOG_ROOT' '$PY' '$ROOT/launcher/launch_agents.py' --agent-dir '$ROOT/agent' --domain hiddenbench --lang '$LANG_CODE' --condition '$cond' --server-url ws://127.0.0.1:8090/ws --num 4" >"$LOGD/hb_${cond}_g${gi}_agents.log" 2>&1 &
    ag=$!
    got=$(wait_results "$rdir" 1 "$CELL_TIMEOUT")
    killgrp "$ag" "$srv"
    bash "$ROOT/serving/cleanup_runs.sh" >/dev/null 2>&1 || true
    if [ "${got:-0}" -ge 1 ]; then
      done_n=$((done_n+1))
      for f in "$rdir"/*.json; do
        [ -e "$f" ] || continue
        cp "$f" "$RESULTS/hiddenbench/$cond/" 2>/dev/null || true
        cp "$f" "$RESULTS/hiddenbench_flat/${cond}__$(basename "$f")" 2>/dev/null || true
      done
    else
      log "HB $cond game $gi: TIMEOUT (no result)"
    fi
    sleep 3
  done
  log "HB $cond: DONE ($done_n/$GAMES)"
}

run_aiwolf(){
  local cond="$1" jdir="$LOG_ROOT/aiwolf/json"
  mkdir -p "$jdir"; rm -f "$jdir"/*.json 2>/dev/null || true
  log "aiwolf $cond: starting (games=$GAMES)"
  setsid bash -c "cd '$ROOT/server/aiwolf' && LOG_ROOT='$LOG_ROOT' go run . -c ./config/default_5_test.yml" >"$LOGD/aiwolf_${cond}_server.log" 2>&1 &
  local srv=$!
  sleep 15
  setsid bash -c "DOMAIN=aiwolf LANG_CODE='$LANG_CODE' CONDITION='$cond' LOG_ROOT='$LOG_ROOT' '$PY' '$ROOT/launcher/launch_agents.py' --agent-dir '$ROOT/agent' --domain aiwolf --lang '$LANG_CODE' --condition '$cond' --server-url ws://127.0.0.1:8080/ws --num 5" >"$LOGD/aiwolf_${cond}_agents.log" 2>&1 &
  local ag=$!
  # aiwolf JSON is written incrementally; count only COMPLETED games (win_side set).
  local got; got=$(wait_aiwolf "$jdir" "$GAMES" "$CELL_TIMEOUT")
  if [ "$got" -ge "$GAMES" ]; then log "aiwolf $cond: DONE ($got/$GAMES)"; else log "aiwolf $cond: TIMEOUT ($got/$GAMES)"; fi
  killgrp "$ag" "$srv"
  bash "$ROOT/serving/cleanup_runs.sh" >/dev/null 2>&1 || true
  # Collect only FINISHED game JSONs (win_side is a real team, not "NONE"=ongoing) into results.
  mkdir -p "$RESULTS/aiwolf/$cond"
  "$PY" - "$jdir" "$RESULTS/aiwolf/$cond" <<'PYEOF' || true
import json,glob,os,sys,shutil
src,dst=sys.argv[1],sys.argv[2]
for f in glob.glob(os.path.join(src,"*.json")):
    try:
        if json.load(open(f)).get("win_side") in ("VILLAGER","WEREWOLF"): shutil.copy(f,dst)
    except Exception: pass
PYEOF
  sleep 4
}

log "=== MATRIX START lang=$LANG_CODE games=$GAMES domains=(${DOMAINS[*]}) conds=(${CONDS[*]}) ==="
bash "$ROOT/serving/cleanup_runs.sh" >/dev/null 2>&1 || true
for domain in "${DOMAINS[@]}"; do
  for cond in "${CONDS[@]}"; do
    if [ "$domain" = "hiddenbench" ]; then run_hb "$cond"; else run_aiwolf "$cond"; fi
  done
done
log "=== MATRIX RUNS DONE -> $RESULTS ==="

if [ "$DO_EVAL" = "1" ]; then
  EVAL_PY="$ROOT/eval/.venv/bin/python"
  log "=== gold_script reference: evaluate the generated exemplars themselves ==="
  PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/evaluate_exemplars.py" \
    --lang "$LANG_CODE" --agent-dir "$ROOT/agent" --out "$RESULTS/hiddenbench_flat" >>"$LOGD/eval_hb.log" 2>&1 || true
  log "=== EVAL (objective + subjective gemma judge) over HB results + gold ==="
  PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/evaluate_with_judge.py" "$RESULTS/hiddenbench_flat" -c "$ROOT/eval/config/judge.local.yml" >>"$LOGD/eval_hb.log" 2>&1 \
    && log "eval HB OK -> $LOGD/eval_hb.log" || log "eval HB FAILED (see $LOGD/eval_hb.log)"
  log "=== plots ==="
  "$EVAL_PY" "$ROOT/eval/src/plot_report.py" "$RESULTS/hiddenbench_flat/eval/metrics.json" >>"$LOGD/eval_hb.log" 2>&1 \
    && log "plots OK -> $RESULTS/hiddenbench_flat/eval/plots.png" || log "plots FAILED (see $LOGD/eval_hb.log)"
  log "=== aiwolf eval (domain-general metrics + judge) for per-domain ranking ==="
  PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/evaluate_aiwolf.py" --src "$RESULTS/aiwolf" --out "$RESULTS/aiwolf_flat" >>"$LOGD/eval_aiwolf.log" 2>&1 || true
  PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/evaluate_with_judge.py" "$RESULTS/aiwolf_flat" -c "$ROOT/eval/config/judge.local.yml" >>"$LOGD/eval_aiwolf.log" 2>&1 || true
  log "=== rankings (HiddenBench / aiwolf / overall) ==="
  PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/rankings.py" \
    --hb "$RESULTS/hiddenbench_flat/eval/metrics.json" --aiwolf "$RESULTS/aiwolf_flat/eval/metrics.json" \
    --out "$RESULTS/rankings.md" >>"$LOGD/eval_aiwolf.log" 2>&1 \
    && log "rankings OK -> $RESULTS/rankings.md" || log "rankings FAILED (see $LOGD/eval_aiwolf.log)"
fi
log "=== ALL DONE ==="
touch "$ROOT/serving/MATRIX_DONE"
