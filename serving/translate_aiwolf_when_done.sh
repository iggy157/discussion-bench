#!/usr/bin/env bash
# Wait for the new-prompt aiwolf matrix to finish, then render each game to English
# markdown and translate it to Japanese (faithful, via translate_md.py on :8000).
#
# Usage: setsid nohup serving/translate_aiwolf_when_done.sh > serving/aw_trans.log 2>&1 &
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
PY="$ROOT/agent/.venv/bin/python"
RUNLOG="$ROOT/serving/matrix_newprompt_aw.log"
SRC="$ROOT/results/run_newprompt_aw/aiwolf"
OUT="$ROOT/results/aiwolf_logs_ja"
PORT="${PORT:-8000}"
MODEL="${MODEL:-gemma-4-31b}"
EXPECT="${EXPECT:-24}"

log(){ echo "[$(date '+%F %H:%M:%S')] $*"; }

# ---- wait for the matrix run to finish (ALL DONE marker in its log, or expected game count) ----
log "waiting for matrix to finish (expect $EXPECT games)..."
while true; do
  grep -q "=== ALL DONE ===" "$RUNLOG" 2>/dev/null && { log "matrix log reports ALL DONE"; break; }
  n=$(find "$SRC" -name 'g*.json' 2>/dev/null | wc -l)
  [ "$n" -ge "$EXPECT" ] && { log "collected $n/$EXPECT games"; break; }
  sleep 30
done
sleep 5

# ---- render English markdown ----
log "rendering English markdown -> $OUT"
"$PY" "$ROOT/serving/render_aiwolf_md.py" --src "$SRC" --out "$OUT"

# ---- translate each .en.md to .ja.md ----
log "translating to Japanese (port $PORT, model $MODEL)..."
count=0
while IFS= read -r en; do
  ja="${en%.en.md}.ja.md"
  "$PY" "$ROOT/serving/translate_md.py" --port "$PORT" --model "$MODEL" \
        --src "$en" --out "$ja" --max-tokens 4096 || log "  FAILED: $en"
  count=$((count+1))
done < <(find "$OUT" -name '*.en.md' | sort)
log "=== AIWOLF TRANSLATION DONE: $count files -> $OUT ==="
touch "$ROOT/serving/AW_TRANS_DONE"
