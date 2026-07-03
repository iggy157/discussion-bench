#!/usr/bin/env bash
# chain_reps.sh — ROUND1_DONE を待って rep2 → 評価 → rep3 → 評価 を無人実行。
#   各rep = HB60問(65−台本出典{4,8,12,14,30}) + aiwolf シード1..60、big(8条件)+small(10条件)並走。
#   結果: results/run_r{2,3}_{big,small}/ 、主観 subj60_*.md、自動サマリ results/run_r{2,3}_report_auto.md
#   マーカー: serving/REP2_DONE / serving/REP3_DONE
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
set -a; [ -f ./.env ] && . ./.env; set +a
EV="$ROOT/eval/.venv/bin/python"
LOG="$ROOT/serving/chain_reps.log"
log(){ echo "[$(date '+%F %H:%M:%S')] $*" >>"$LOG"; }

HB60="1 2 3 5 6 7 9 10 11 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65"
C8="baseline analysis_only utterance_fewshot utterance_fewshot_analysis situation_fewshot situation_fewshot_analysis script_fewshot_k5 script_fewshot_analysis_k5"
C10="$C8 script_fewshot_k1 script_fewshot_analysis_k1"
CC8="baseline,analysis_only,utterance_fewshot,utterance_fewshot_analysis,situation_fewshot,situation_fewshot_analysis,script_fewshot_k5,script_fewshot_analysis_k5"
CC10="$CC8,script_fewshot_k1,script_fewshot_analysis_k1"

wait_done(){ # log1 log2 max_sec
  local t=0
  while [ "$t" -lt "$3" ]; do
    grep -q "ALL DONE" "$1" 2>/dev/null && grep -q "ALL DONE" "$2" 2>/dev/null && return 0
    sleep 300; t=$((t+300))
  done
  return 1
}

run_subj(){ # flat domain conds out label
  log ">> $5 (n=60)"
  PYTHONPATH="$ROOT/eval/src" "$EV" "$ROOT/eval/src/evaluate_listwise_subj.py" \
    --flat "$1" --domain "$2" --conds "$3" --n-seeds 60 --out "$4" --label "$5" >>"$LOG" 2>&1 \
    && log "<< $5 OK -> $4" || log "!! $5 FAILED"
}

auto_report(){ # rep_no big_dir small_dir out
  "$EV" - "$2" "$3" "$4" "rep$1" <<'PYEOF' >>"$LOG" 2>&1 || true
import json, re, sys, pathlib
bigd, smalld, out, tag = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
parts = [f"# {tag} 自動レポート (n=60)\n\n自動生成サマリ。客観=HB事後正答率 / 主観=listwise総合表の転載。\n"]
for R, lab in [(bigd, "big (gemma-4-31b)"), (smalld, "small (gemma-3-4b)")]:
    parts.append(f"\n## {lab}\n")
    try:
        agg = json.load(open(f"{R}/hiddenbench_flat/eval/metrics.json"))["aggregate"]
        rows = sorted(((c, v) for c, v in agg.items() if c not in ("gold_script", "human")),
                      key=lambda x: -x[1]["post_accuracy"])
        parts.append("\n### HB 客観（事後正答率）\n\n| 条件 | post | pre | gain | n |\n|---|---|---|---|---|\n")
        for c, v in rows:
            parts.append(f"| {c} | {v['post_accuracy']:.2f} | {v['pre_accuracy']:.2f} | {v['integration_gain']:+.2f} | {v['n_games']} |\n")
    except Exception as e:
        parts.append(f"(HB metrics 読み込み失敗: {e})\n")
    for dom in ("hb", "aiwolf"):
        f = pathlib.Path(f"{R}/subj60_{dom}.md")
        if f.exists():
            m = re.search(r"## 総合ランキング.*", f.read_text(), re.S)
            if m:
                parts.append(f"\n### {dom} 主観 listwise (n=60)\n\n" + m.group(0) + "\n")
        else:
            parts.append(f"\n### {dom} 主観: ファイルなし\n")
pathlib.Path(out).write_text("".join(parts))
print("auto report ->", out)
PYEOF
}

run_rep(){ # rep_no
  local N="$1" BIGR="$ROOT/results/run_r$1_big" SMLR="$ROOT/results/run_r$1_small"
  local BLOG="serving/matrix_r$1_big.log" SLOG="serving/matrix_r$1_small.log"
  log "=== rep$N: launching big+small (HB 60 ids, aiwolf g1..60) ==="
  setsid nohup env \
    LANG_CODE=en GAMES=60 AW_GAMES=60 NWORKERS=4 RETRIES=3 \
    HB_TASK_LIST="$HB60" \
    ENDPOINTS="http://127.0.0.1:8000/v1 http://127.0.0.1:8002/v1" \
    CONDS="$C8" CONDITIONS_FILE="config/conditions_v2_typed10.yml" \
    RESULTS="$BIGR" RUN_TAG="r$1_big" \
    bash serving/run_matrix_parallel.sh > "$BLOG" 2>&1 &
  setsid nohup env \
    LANG_CODE=en GAMES=60 AW_GAMES=60 NWORKERS=4 RETRIES=3 AW_TIMEOUT=720 \
    HB_TASK_LIST="$HB60" \
    ENDPOINTS="http://127.0.0.1:8004/v1 http://127.0.0.1:8014/v1" \
    CONDS="$C10" CONDITIONS_FILE="config/conditions_v2_typed10.yml" \
    RESULTS="$SMLR" RUN_TAG="r$1_small" \
    HB_PORT_BASE=8110 AW_PORT_BASE=8360 \
    bash serving/run_matrix_parallel.sh > "$SLOG" 2>&1 &
  sleep 10
  log "rep$N: waiting for matrices (max 26h)"
  wait_done "$BLOG" "$SLOG" 93600 || { log "!! rep$N matrices timeout"; return 1; }
  log "rep$N matrices done — listwise subjective n=60"
  run_subj "$BIGR/hiddenbench_flat" hb     "$CC8"  "$BIGR/subj60_hb.md"     "r$1_big_hb"
  run_subj "$BIGR/aiwolf_flat"      aiwolf "$CC8"  "$BIGR/subj60_aiwolf.md" "r$1_big_aiwolf"
  run_subj "$SMLR/hiddenbench_flat" hb     "$CC10" "$SMLR/subj60_hb.md"     "r$1_small_hb"
  run_subj "$SMLR/aiwolf_flat"      aiwolf "$CC10" "$SMLR/subj60_aiwolf.md" "r$1_small_aiwolf"
  auto_report "$N" "$BIGR" "$SMLR" "$ROOT/results/run_r$1_report_auto.md"
  touch "$ROOT/serving/REP$1_DONE"
  log "=== rep$N DONE ==="
}

log "=== chain_reps: waiting for ROUND1_DONE (max 16h) ==="
t=0
while [ "$t" -lt 57600 ]; do
  [ -f "$ROOT/serving/ROUND1_DONE" ] && break
  sleep 300; t=$((t+300))
done
[ -f "$ROOT/serving/ROUND1_DONE" ] || { log "!! timeout waiting ROUND1_DONE"; exit 1; }

run_rep 2 || exit 1
run_rep 3 || exit 1
log "=== chain_reps: ALL REPS DONE ==="
