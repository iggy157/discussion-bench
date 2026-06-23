#!/usr/bin/env bash
# Validate the aiwolf-completion fix: run ONE full aiwolf game (no load) and report whether it
# finishes with a real win_side and a realistic number of utterances.
set +e
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
PY="$ROOT/agent/.venv/bin/python"
EVAL_PY="$ROOT/eval/.venv/bin/python"
ENDPOINT="http://127.0.0.1:8000/v1"
PORT=8085
COND="baseline"
WLOG="$ROOT/serving/test_aw_one_log"
JDIR="$WLOG/aiwolf/json"
OUT="$ROOT/serving/test_aiwolf_one.result"
rm -rf "$WLOG" "$OUT"; mkdir -p "$JDIR"

# per-test config (own port, single game)
CFG="config/aiwolf_test_one.yml"
sed -e "s/^    port: .*/    port: $PORT/" -e "s/^  game_count: .*/  game_count: 1/" \
    "$ROOT/server/aiwolf/config/default_5_test.yml" > "$ROOT/server/aiwolf/$CFG"

setsid bash -c "cd '$ROOT/server/aiwolf' && LOG_ROOT='$WLOG' AIWOLF_SEED='1' ./aiwolf-server -c '$CFG'" >"$WLOG/srv.log" 2>&1 &
srv=$!
sleep 5
setsid bash -c "DOMAIN=aiwolf LANG_CODE='jp' CONDITION='$COND' LOG_ROOT='$WLOG' LLM_BASE_URL='$ENDPOINT' '$PY' '$ROOT/launcher/launch_agents.py' --agent-dir '$ROOT/agent' --domain aiwolf --lang jp --condition '$COND' --server-url ws://127.0.0.1:$PORT/ws --num 5" >"$WLOG/ag.log" 2>&1 &
ag=$!

# poll up to 360s for a FINISHED game (win_side is a real team)
res="timeout"; t=0
while [ "$t" -lt 360 ]; do
  ws=$("$PY" - "$JDIR" <<'P'
import json,glob,sys,os
for f in glob.glob(os.path.join(sys.argv[1],"*.json")):
    try:
        w=json.load(open(f)).get("win_side")
        if w in ("VILLAGER","WEREWOLF"): print(w); break
    except Exception: pass
P
)
  [ -n "$ws" ] && { res="$ws"; break; }
  sleep 5; t=$((t+5))
done

# summarize the newest json
"$PY" - "$JDIR" "$res" <<'P' > "$OUT" 2>&1
import json,glob,os,sys
jdir,res=sys.argv[1],sys.argv[2]
fs=sorted(glob.glob(os.path.join(jdir,"*.json")),key=os.path.getmtime)
print("result_wait:",res)
print("json_files:",len(fs))
if fs:
    d=json.load(open(fs[-1]))
    e=d.get("entries",[])
    talk=sum(1 for x in e if isinstance(x,dict) and x.get("response") and '"TALK"' in str(x.get("request","")))
    days=[]
    for x in e:
        try: days.append(json.loads(x.get("request","{}")).get("info",{}).get("day"))
        except: pass
    days=[d for d in days if d is not None]
    print("win_side:",d.get("win_side"))
    print("entries:",len(e),"TALK_responses:",talk,"max_day:",max(days) if days else None)
P
for pg in "$srv" "$ag"; do kill -TERM -"$pg" 2>/dev/null; done; sleep 2
for pg in "$srv" "$ag"; do kill -KILL -"$pg" 2>/dev/null; done
bash "$ROOT/serving/cleanup_runs.sh" >/dev/null 2>&1
echo "=== TEST COMPLETE ===" >> "$OUT"
