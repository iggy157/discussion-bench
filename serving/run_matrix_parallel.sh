#!/usr/bin/env bash
# PARALLEL matrix: 6 conditions × 2 domains × N games, run as a worker pool across multiple vLLM
# endpoints. Each worker owns one condition and runs its HB + aiwolf cells, fully isolated
# (own LOG_ROOT, own server ports, assigned vLLM endpoint). Per-game execution is IDENTICAL to
# the serial run (same model/decoding/protocol) — only games are run concurrently.
#
# Pairing: HB uses fixed seed=42 + HB_TASK_IDS=game_idx (already paired across conditions);
# aiwolf is run one-game-per-launch with AIWOLF_SEED=game_idx so game k has identical
# role/persona/seat assignment across all conditions.
#
# Usage: setsid nohup serving/run_matrix_parallel.sh > serving/matrix.log 2>&1 &
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
_LANG_OVERRIDE="${LANG_CODE:-}"
set -a; [ -f ./.env ] && . ./.env; set +a
LANG_CODE="${_LANG_OVERRIDE:-jp}"
GAMES="${GAMES:-20}"
GAME_TIMEOUT="${GAME_TIMEOUT:-900}"
AW_TIMEOUT="${AW_TIMEOUT:-360}"     # aiwolf games are short; fail fast on this
AW_HEALTH="${AW_HEALTH:-60}"        # aiwolf: frozen-start fast-fail — game JSON must appear within this
AW_STAGNANT="${AW_STAGNANT:-120}"   # aiwolf: mid-game abort fast-fail — JSON must keep being written
RETRIES="${RETRIES:-3}"             # per-game retries (guarantee game counts despite transient failures)
NWORKERS="${NWORKERS:-3}"           # concurrent workers (games in flight). >~3 on one endpoint -> APIConnectionError
PY="$ROOT/agent/.venv/bin/python"
EVAL_PY="$ROOT/eval/.venv/bin/python"
RESULTS="${RESULTS:-$ROOT/results/local_run}"
LOGD="$ROOT/serving/matrix_logs${RUN_TAG:+_$RUN_TAG}"
JUDGE_FLAG="${JUDGE_FLAG:---no-judge}"   # default: skip LLM-judge during runs (objective-only); re-judge in batch later (English prompt)
read -r -a ENDPOINTS <<<"${ENDPOINTS:-http://127.0.0.1:8000/v1 http://127.0.0.1:8001/v1}"
read -r -a CONDS <<<"${CONDS:-baseline analysis_only utterance_fewshot utterance_fewshot_analysis script_fewshot script_fewshot_analysis}"
mkdir -p "$RESULTS/hiddenbench_flat" "$LOGD"

log(){ echo "[$(date '+%F %H:%M:%S')] $*"; }

wait_one_json(){  # dir, max_sec ; returns 0 if a *.json appeared
  local dir="$1" max="$2" t=0
  while [ "$t" -lt "$max" ]; do
    [ -n "$(ls "$dir"/*.json 2>/dev/null)" ] && return 0
    sleep 5; t=$((t+5))
  done
  return 1
}
wait_one_aiwolf(){  # dir, max_sec ; returns 0=finished 1=timeout 2=stall(frozen start / mid-game abort)
  # NOTE: win_side is the string "NONE" for an ONGOING/undecided game (truthy!) — a finished game
  # is "VILLAGER" or "WEREWOLF". Checking mere truthiness collects games right after they start
  # (day-0, ~2 utterances) and kills the server. Require a real winning team.
  # Health checks (np_aw postmortem): a frozen table never writes its game JSON at all, and an
  # aborted game stops updating it — both are detected here and fast-failed instead of burning
  # the full AW_TIMEOUT on a game that will never finish.
  local dir="$1" max="$2" t=0 last_m="" last_t=0 m
  while [ "$t" -lt "$max" ]; do
    if [ -n "$("$PY" - "$dir" <<'P'
import json,glob,sys,os
for f in glob.glob(os.path.join(sys.argv[1],"*.json")):
    try:
        if json.load(open(f)).get("win_side") in ("VILLAGER","WEREWOLF"): print("Y"); break
    except Exception: pass
P
)" ]; then return 0; fi
    m=$(stat -c %Y "$dir"/*.json 2>/dev/null | sort -n | tail -1)
    if [ -z "$m" ]; then
      [ "$t" -ge "$AW_HEALTH" ] && return 2      # table never started (no game JSON yet)
    else
      [ "$m" != "$last_m" ] && { last_m="$m"; last_t="$t"; }
      [ $((t - last_t)) -ge "$AW_STAGNANT" ] && return 2   # started but stopped progressing
    fi
    sleep 5; t=$((t+5))
  done
  return 1
}
killgrp(){  # TERM then KILL each process group, then verify no survivors (direct -9 by PID)
  local pg p i left
  for pg in "$@"; do kill -TERM -"$pg" 2>/dev/null||true; done; sleep 2
  for pg in "$@"; do kill -KILL -"$pg" 2>/dev/null||true; done
  for i in 1 2 3; do
    left=""
    for pg in "$@"; do left="$left $(pgrep -g "$pg" 2>/dev/null | tr '\n' ' ')"; done
    [ -z "${left// /}" ] && return 0
    for p in $left; do kill -KILL "$p" 2>/dev/null||true; done
    sleep 1
  done
}
wait_port_free(){  # port [max_sec] : wait until nothing LISTENs on port; fuser-kill holders as fallback
  local port="$1" max="${2:-20}" t=0
  while [ "$t" -lt "$max" ]; do
    ss -ltn 2>/dev/null | grep -qE "[:.]$port[[:space:]]" || return 0
    [ "$t" -ge 10 ] && fuser -k -TERM "$port/tcp" 2>/dev/null || true
    sleep 2; t=$((t+2))
  done
  fuser -k -KILL "$port/tcp" 2>/dev/null || true; sleep 1
  ! ss -ltn 2>/dev/null | grep -qE "[:.]$port[[:space:]]"
}

# wait for an HB game: echo ok (result written) | failed (server logged a game failure -> retry
# fast, no long wait) | timeout (genuinely slow). Fast-fail avoids burning GAME_TIMEOUT on a game
# that already died (e.g., agent connection error under load).
wait_game(){
  local expfile="$1" slog="$2" max="$3" alog="${4:-}" t=0   # expfile = the EXACT expected result path
  while [ "$t" -lt "$max" ]; do
    [ -f "$expfile" ] && { echo ok; return; }
    grep -q "game .* failed" "$slog" 2>/dev/null && { echo failed; return; }
    # context-overflow: agent gets a 400 (input exceeds max_model_len) and dies; the server then
    # goes SILENT (no "game failed"), so without this check wait_game burns the full GAME_TIMEOUT.
    [ -n "$alog" ] && grep -qE "maximum context length|BadRequestError" "$alog" 2>/dev/null && { echo failed; return; }
    sleep 5; t=$((t+5))
  done
  echo timeout
}

run_worker(){
  local w="$1" cond="$2" endpoint="$3"
  local wlog="$ROOT/log/${RUN_TAG:+${RUN_TAG}_}w$w" hbport=$(( ${HB_PORT_BASE:-8090} + w ))
  local hbrdir="$wlog/hidden-bench/results" awjdir="$wlog/aiwolf/json"
  # aiwolf port ROTATES per attempt within a per-worker block of 8 (np_aw postmortem: a leftover
  # process from the previous launch can reconnect to a fresh server on the SAME port and freeze
  # the new table before its first TALK — a fresh port per attempt makes that impossible).
  # Default base 8280 keeps the rotation range clear of vLLM (8000-8020) and HB (8090+w).
  local awport awrot=0 awcfg="config/aiwolf_${RUN_TAG:+${RUN_TAG}_}w$w.yml"

  # ---- HiddenBench cell (one game per launch; task_id = game_idx, seed fixed in config) ----
  mkdir -p "$RESULTS/hiddenbench/$cond"
  log "w$w $cond: HB cell start (port $hbport, $endpoint)"
  local done_hb=0 gi srv ag slog alog res att
  # HB task ids: explicit eval list (HB_TASK_LIST) or the legacy 1..GAMES contiguous range.
  local hb_ids; if [ -n "${HB_TASK_LIST:-}" ]; then hb_ids="$HB_TASK_LIST"; else hb_ids="$(seq 1 "$GAMES")"; fi
  local hb_total; hb_total=$(echo $hb_ids | wc -w)
  for gi in $hb_ids; do
    # idempotent: skip games already collected (re-running the matrix fills ONLY the gaps)
    ls "$RESULTS/hiddenbench_flat/${cond}__g${gi}_"*.json >/dev/null 2>&1 && { done_hb=$((done_hb+1)); continue; }
    res=fail
    local exp; exp="$(printf 'hb-%03d-r0-0000.json' "$gi")"   # deterministic game_id for task_id=gi
    for att in $(seq 1 "$RETRIES"); do
      mkdir -p "$hbrdir"; rm -f "$hbrdir"/*.json 2>/dev/null||true
      wait_port_free "$hbport" || log "w$w $cond HB g$gi attempt$att: port $hbport still busy (launching anyway)"
      slog="$LOGD/w${w}_hb_${cond}_g${gi}_a${att}_srv.log"; alog="$LOGD/w${w}_hb_${cond}_g${gi}_a${att}_ag.log"
      setsid bash -c "cd '$ROOT/server/hidden-bench' && HB_LANG='$LANG_CODE' CONDITION='$cond' HB_TASK_IDS='$gi' HB_PORT='$hbport' LOG_ROOT='$wlog' HB_RESP_TIMEOUT_MS='${HB_RESP_TIMEOUT_MS:-120000}' HB_ACTION_TIMEOUT_MS='${HB_ACTION_TIMEOUT_MS:-60000}' PYTHONPATH=src '$PY' src/server.py -c config/hiddenbench.yml" >"$slog" 2>&1 &
      srv=$!; sleep 5
      setsid bash -c "DOMAIN=hiddenbench CONDITIONS_FILE='${CONDITIONS_FILE:-}' LANG_CODE='$LANG_CODE' CONDITION='$cond' LOG_ROOT='$wlog' LLM_BASE_URL='$endpoint' DBAGENT_TMP_TAG='${RUN_TAG:-}' '$PY' '$ROOT/launcher/launch_agents.py' --agent-dir '$ROOT/agent' --domain hiddenbench --lang '$LANG_CODE' --condition '$cond' --server-url ws://127.0.0.1:$hbport/ws --num 4" >"$alog" 2>&1 &
      ag=$!
      res=$(wait_game "$hbrdir/$exp" "$slog" "$GAME_TIMEOUT" "$alog")
      killgrp "$ag" "$srv"; sleep 2
      if [ "$res" = ok ] && [ -f "$hbrdir/$exp" ]; then
        # collect ONLY the exact expected game_id file (no cross-game contamination / duplicates)
        cp "$hbrdir/$exp" "$RESULTS/hiddenbench/$cond/" 2>/dev/null||true
        cp "$hbrdir/$exp" "$RESULTS/hiddenbench_flat/${cond}__g${gi}_${exp}" 2>/dev/null||true
        done_hb=$((done_hb+1)); break
      fi
      log "w$w $cond HB g$gi attempt$att: $res (retry)"
    done
    [ "$res" = ok ] || log "w$w $cond HB g$gi: FAILED after $RETRIES attempts"
    sleep 1
  done
  log "w$w $cond: HB cell DONE ($done_hb/$hb_total)"

  # ---- aiwolf cell (one game per launch; AIWOLF_SEED = game_idx for cross-condition pairing) ----
  log "w$w $cond: aiwolf cell start (ports $(( ${AW_PORT_BASE:-8280} + w*8 ))-$(( ${AW_PORT_BASE:-8280} + w*8 + 7 )))"
  mkdir -p "$RESULTS/aiwolf/$cond"
  local done_aw=0 awok awrc aw_games; aw_games="${AW_GAMES:-$GAMES}"   # aiwolf eval seeds 1..AW_GAMES
  for gi in $(seq 1 "$aw_games"); do
    # idempotent: skip aiwolf games already collected
    ls "$RESULTS/aiwolf/$cond/g${gi}_"*.json >/dev/null 2>&1 && { done_aw=$((done_aw+1)); continue; }
    awok=0
    for att in $(seq 1 "$RETRIES"); do
      # fresh port per attempt + regenerated config (see rotation note at top of run_worker)
      awport=$(( ${AW_PORT_BASE:-8280} + w*8 + awrot % 8 )); awrot=$((awrot+1))
      sed -e "s/^    port: .*/    port: $awport/" -e "s/^  game_count: .*/  game_count: 1/" \
          "$ROOT/server/aiwolf/config/default_5_test.yml" > "$ROOT/server/aiwolf/$awcfg"
      wait_port_free "$awport" || { log "w$w $cond aiwolf g$gi attempt$att: port $awport busy, rotating"; continue; }
      mkdir -p "$awjdir"; rm -f "$awjdir"/*.json 2>/dev/null||true
      setsid bash -c "cd '$ROOT/server/aiwolf' && LOG_ROOT='$wlog' AIWOLF_SEED='$gi' ./aiwolf-server -c '$awcfg'" >"$LOGD/w${w}_aw_${cond}_g${gi}_a${att}_srv.log" 2>&1 &
      srv=$!; sleep 4
      setsid bash -c "DOMAIN=aiwolf CONDITIONS_FILE='${CONDITIONS_FILE:-}' LANG_CODE='$LANG_CODE' CONDITION='$cond' LOG_ROOT='$wlog' LLM_BASE_URL='$endpoint' DBAGENT_TMP_TAG='${RUN_TAG:-}' '$PY' '$ROOT/launcher/launch_agents.py' --agent-dir '$ROOT/agent' --domain aiwolf --lang '$LANG_CODE' --condition '$cond' --server-url ws://127.0.0.1:$awport/ws --num 5" >"$LOGD/w${w}_aw_${cond}_g${gi}_a${att}_ag.log" 2>&1 &
      ag=$!
      wait_one_aiwolf "$awjdir" "$AW_TIMEOUT"; awrc=$?
      if [ "$awrc" = 0 ]; then
        # collect ONLY the newest FINISHED game (win_side is a real team, not "NONE"=ongoing)
        "$PY" - "$awjdir" "$RESULTS/aiwolf/$cond" "$gi" <<'P' || true
import json,glob,os,sys,shutil
src,dst,gi=sys.argv[1],sys.argv[2],sys.argv[3]
cands=[]
for f in glob.glob(os.path.join(src,"*.json")):
    try:
        if json.load(open(f)).get("win_side") in ("VILLAGER","WEREWOLF"): cands.append((os.path.getmtime(f),f))
    except Exception: pass
if cands:
    f=max(cands)[1]
    # dup-safe: drop any existing collection for this gi before copying (parallel/relaunch race)
    for old in glob.glob(os.path.join(dst, f"g{gi}_*.json")):
        try: os.remove(old)
        except OSError: pass
    shutil.copy(f, os.path.join(dst, f"g{gi}_"+os.path.basename(f)))
P
        done_aw=$((done_aw+1)); awok=1; killgrp "$ag" "$srv"; wait_port_free "$awport" 10 || true; sleep 2; break
      fi
      killgrp "$ag" "$srv"; wait_port_free "$awport" 10 || true
      log "w$w $cond aiwolf g$gi attempt$att: $([ "$awrc" = 2 ] && echo stall || echo timeout) (retry)"; sleep 2
    done
    [ "$awok" = 1 ] || log "w$w $cond aiwolf g$gi: FAILED after $RETRIES attempts"
    sleep 1
  done
  log "w$w $cond: aiwolf cell DONE ($done_aw/$aw_games)"
}

log "=== PARALLEL MATRIX START lang=$LANG_CODE games=$GAMES endpoints=${#ENDPOINTS[@]} conds=${#CONDS[@]} nworkers=$NWORKERS ==="
pids=()
for w in $(seq 0 $((NWORKERS-1))); do
  [ "$w" -lt "${#CONDS[@]}" ] || break
  (
    ep="${ENDPOINTS[$((w % ${#ENDPOINTS[@]}))]}"
    for ci in $(seq "$w" "$NWORKERS" $((${#CONDS[@]}-1))); do
      run_worker "$w" "${CONDS[$ci]}" "$ep"
    done
  ) &
  pids+=("$!")
done
for p in "${pids[@]}"; do wait "$p"; done
log "=== ALL WORKERS DONE -> $RESULTS ==="

# ---- eval (HB + gold + plots + aiwolf + rankings) ----
log "=== EVAL ==="
PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/evaluate_exemplars.py" --lang "$LANG_CODE" --agent-dir "$ROOT/agent" --out "$RESULTS/hiddenbench_flat" >>"$LOGD/eval.log" 2>&1 || true
PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/evaluate_with_judge.py" "$RESULTS/hiddenbench_flat" -c "$ROOT/eval/config/judge.local.yml" $JUDGE_FLAG >>"$LOGD/eval.log" 2>&1 || true
"$EVAL_PY" "$ROOT/eval/src/plot_report.py" "$RESULTS/hiddenbench_flat/eval/metrics.json" >>"$LOGD/eval.log" 2>&1 || true
PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/evaluate_aiwolf.py" --src "$RESULTS/aiwolf" --out "$RESULTS/aiwolf_flat" >>"$LOGD/eval.log" 2>&1 || true
PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/evaluate_with_judge.py" "$RESULTS/aiwolf_flat" -c "$ROOT/eval/config/judge.local.yml" $JUDGE_FLAG >>"$LOGD/eval.log" 2>&1 || true
PYTHONPATH="$ROOT/eval/src" "$EVAL_PY" "$ROOT/eval/src/rankings.py" --hb "$RESULTS/hiddenbench_flat/eval/metrics.json" --aiwolf "$RESULTS/aiwolf_flat/eval/metrics.json" --out "$RESULTS/rankings.md" --report "$RESULTS/hiddenbench_flat/eval/report.md" --report "$RESULTS/aiwolf_flat/eval/report.md" >>"$LOGD/eval.log" 2>&1 \
  && log "rankings OK -> $RESULTS/rankings.md" || log "rankings FAILED"
log "=== ALL DONE ==="
touch "$ROOT/serving/MATRIX_DONE"
