#!/usr/bin/env bash
# Profile ALL HiddenBench tasks once under baseline to label difficulty (pre/post accuracy),
# so eval/script-source tasks can be chosen by validity instead of a leading-id slice.
# 全HBタスクをbaselineで1回ずつ解かせ、pre/post正答率で難易度ラベルを付ける（妥当性に基づく選抜用）。
set +e
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
PY="$ROOT/agent/.venv/bin/python"
ENDPOINT="${ENDPOINT:-http://127.0.0.1:8000/v1}"
COND=baseline
LANG_CODE="${LANG_CODE:-en}"
NTASKS="${NTASKS:-65}"
NWORKERS="${NWORKERS:-3}"
TIMEOUT="${TIMEOUT:-900}"
RETRIES="${RETRIES:-3}"
REPS="${REPS:-1}"                     # games per task (>1 for difficulty statistics; reusable as baseline)
OUT="${PROFILE_OUT:-$ROOT/results/hb_profiling}"
LOGD="$ROOT/serving/profile_logs"
mkdir -p "$OUT" "$LOGD"
rm -f "$ROOT/serving/PROFILE_DONE"

run_task(){
  local gi="$1" w="$2"
  # INSTANCE offsets port + log dir so a 2nd profiler instance (different endpoint) doesn't
  # collide on the HB server port / LOG_ROOT. INSTANCE=0 default keeps legacy behavior.
  local inst="${INSTANCE:-0}"
  local port=$(( 8090 + inst*10 + w ))
  local wlog="$ROOT/log/prof_i${inst}_w$w"
  local exp; exp="$(printf 'hb-%03d-r0-0000.json' "$gi")"
  local rep att
  for rep in $(seq 1 "$REPS"); do
    ls "$OUT/task${gi}_r${rep}_"*.json >/dev/null 2>&1 && continue   # idempotent per (task,rep)
    for att in $(seq 1 "$RETRIES"); do
      rm -rf "$wlog/hidden-bench/results"; mkdir -p "$wlog/hidden-bench/results"
      local slog="$LOGD/t${gi}_r${rep}_a${att}_srv.log" alog="$LOGD/t${gi}_r${rep}_a${att}_ag.log"
      setsid bash -c "cd '$ROOT/server/hidden-bench' && HB_LANG='$LANG_CODE' CONDITION='$COND' HB_TASK_IDS='$gi' HB_PORT='$port' LOG_ROOT='$wlog' HB_RESP_TIMEOUT_MS=600000 HB_ACTION_TIMEOUT_MS=300000 PYTHONPATH=src '$PY' src/server.py -c config/hiddenbench.yml" >"$slog" 2>&1 &
      local srv=$!; sleep 8
      setsid bash -c "DOMAIN=hiddenbench LANG_CODE='$LANG_CODE' CONDITION='$COND' LOG_ROOT='$wlog' LLM_BASE_URL='$ENDPOINT' '$PY' '$ROOT/launcher/launch_agents.py' --agent-dir '$ROOT/agent' --domain hiddenbench --lang '$LANG_CODE' --condition '$COND' --server-url ws://127.0.0.1:$port/ws --num 4" >"$alog" 2>&1 &
      local ag=$!
      local t=0 res=""
      while [ "$t" -lt "$TIMEOUT" ]; do
        [ -f "$wlog/hidden-bench/results/$exp" ] && { res=ok; break; }
        grep -q "game .* failed" "$slog" 2>/dev/null && { res=failed; break; }                     # fast-fail (server)
        grep -qE "maximum context length|BadRequestError" "$alog" 2>/dev/null && { res=failed; break; }  # fast-fail (ctx overflow)
        # watchdog: if the game never STARTED within 150s (agents failed to connect under startup
        # burst), don't burn the full TIMEOUT — fail fast and retry.
        [ "$t" -ge 150 ] && ! grep -q "starting game" "$slog" 2>/dev/null && { res=failed; break; }
        sleep 4; t=$((t+4))
      done
      kill -TERM -"$ag" -"$srv" 2>/dev/null; sleep 1; kill -KILL -"$ag" -"$srv" 2>/dev/null
      if [ "$res" = ok ]; then cp "$wlog/hidden-bench/results/$exp" "$OUT/task${gi}_r${rep}_$exp"; break; fi
      sleep 2
    done
  done
}

echo "profiling $NTASKS tasks, lang=$LANG_CODE, $NWORKERS workers -> $OUT"
# Stagger worker starts so their agent launches don't burst simultaneously (12 agents spawning at
# once → connection-refused → games never start). 20s/worker desyncs the initial launches.
TASK_START="${TASK_START:-1}"; TASK_END="${TASK_END:-$NTASKS}"   # task-id range (for splitting across endpoints)
for w in $(seq 0 $((NWORKERS-1))); do
( sleep $((w*20)); for gi in $(seq $((TASK_START + w)) "$NWORKERS" "$TASK_END"); do run_task "$gi" "$w"; done ) &
done
wait
touch "$ROOT/serving/PROFILE_DONE"
echo "PROFILE DONE: $(ls "$OUT"/task*.json 2>/dev/null | wc -l)/$NTASKS collected"
