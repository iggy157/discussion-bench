#!/usr/bin/env bash
# Deadline-bounded repeat driver: run back-to-back full 8-condition passes into
# results/${RESULTS_PREFIX}_rep{N}, stopping before a pass would overrun DEADLINE.
# Adaptive: after each pass, reserve last duration ×1.2 before starting the next.
# Each pass is idempotent (run_matrix_parallel skips already-collected games).
# Namespacing (RUN_TAG / HB_PORT_BASE / AW_PORT_BASE) lets two drivers run in parallel
# on different models/endpoints without port/tmp/log collisions.
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
: "${RESULTS_PREFIX:?set RESULTS_PREFIX}"
: "${ENDPOINTS:?set ENDPOINTS}"
START_REP="${START_REP:-1}"
INIT_BUDGET="${INIT_BUDGET:-72000}"
DEADLINE_STR="${DEADLINE_STR:-2026-06-26 22:00}"
DEADLINE=$(date -d "$DEADLINE_STR" +%s)

HB_EVAL="$(python3 -c 'print(" ".join(str(i) for i in range(1,66) if i not in (4,12,60)))')"
CONDS_ALL="baseline analysis_only utterance_fewshot utterance_fewshot_analysis situation_fewshot situation_fewshot_analysis script_fewshot script_fewshot_analysis"

rep="$START_REP"
est="$INIT_BUDGET"
echo "[$(date '+%F %T')] driver start: prefix=$RESULTS_PREFIX endpoints='$ENDPOINTS' deadline=$DEADLINE_STR tag='${RUN_TAG:-}'"
while [ $(( $(date +%s) + est )) -lt "$DEADLINE" ]; do
  RES="$ROOT/results/${RESULTS_PREFIX}_rep${rep}"
  plog="$ROOT/serving/${RESULTS_PREFIX}_rep${rep}.log"
  echo "[$(date '+%F %T')] >>> START $RESULTS_PREFIX rep$rep (reserve ${est}s)"
  t0=$(date +%s)
  env CONDS="$CONDS_ALL" CONDITIONS_FILE="config/conditions_v2.yml" \
    ENDPOINTS="$ENDPOINTS" NWORKERS="${NWORKERS:-2}" LANG_CODE=en \
    HB_TASK_LIST="$HB_EVAL" AW_GAMES=60 \
    GAME_TIMEOUT=1200 AW_TIMEOUT=600 RETRIES=5 \
    HB_RESP_TIMEOUT_MS=600000 HB_ACTION_TIMEOUT_MS=300000 \
    RESULTS="$RES" \
    RUN_TAG="${RUN_TAG:-}" HB_PORT_BASE="${HB_PORT_BASE:-8090}" AW_PORT_BASE="${AW_PORT_BASE:-8280}" \
    bash serving/run_matrix_parallel.sh > "$plog" 2>&1
  dur=$(( $(date +%s) - t0 ))
  est=$(( dur * 12 / 10 ))
  echo "[$(date '+%F %T')] <<< DONE  $RESULTS_PREFIX rep$rep in ${dur}s -> next reserve ${est}s"
  rep=$((rep+1))
done
echo "[$(date '+%F %T')] driver finished: last completed rep=$((rep-1)) (deadline reached)"
