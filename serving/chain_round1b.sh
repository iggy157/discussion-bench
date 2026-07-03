#!/usr/bin/env bash
# chain_round1b.sh — 1周目完成チェーン (n=30主観+自動レポート挟み込み版)。
#   1. fx_big2/fx_small2 の ALL DONE を待つ
#   2. リークid(8,12,14,30)のHBゲームを退避 → HB客観をクリーンデータで再評価
#   3. listwise 主観 n=30 ×4本 → subj30_*.md → 自動サマリ results/run_fix30_report_auto.md
#      → マーカー serving/SUBJ30_DONE
#   4. 完成フィル起動: HB残り28問 + aiwolf g31..60 (big/small 並走)
#   5. 両完了後 listwise 主観 n=60 ×4本 → subj60_*.md → 自動サマリ → ROUND1_DONE
# ログ: serving/chain_round1.log (旧チェーンと共用追記)
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

reeval_hb(){ # results_dir — HB客観のみ再評価(リーク退避後) + rankings再生成
  local R="$1"
  PYTHONPATH="$ROOT/eval/src" "$EV" "$ROOT/eval/src/evaluate_exemplars.py" --lang en \
    --agent-dir "$ROOT/agent" --out "$R/hiddenbench_flat" >>"$LOG" 2>&1 || true
  PYTHONPATH="$ROOT/eval/src" "$EV" "$ROOT/eval/src/evaluate_with_judge.py" "$R/hiddenbench_flat" \
    -c "$ROOT/eval/config/judge.local.yml" --no-judge >>"$LOG" 2>&1 || true
  PYTHONPATH="$ROOT/eval/src" "$EV" "$ROOT/eval/src/rankings.py" \
    --hb "$R/hiddenbench_flat/eval/metrics.json" --aiwolf "$R/aiwolf_flat/eval/metrics.json" \
    --out "$R/rankings.md" --report "$R/hiddenbench_flat/eval/report.md" \
    --report "$R/aiwolf_flat/eval/report.md" >>"$LOG" 2>&1 || true
}

run_subj(){ # flat domain conds out label nseeds
  log ">> $5 (n=$6)"
  PYTHONPATH="$ROOT/eval/src" "$EV" "$ROOT/eval/src/evaluate_listwise_subj.py" \
    --flat "$1" --domain "$2" --conds "$3" --n-seeds "$6" --out "$4" --label "$5" >>"$LOG" 2>&1 \
    && log "<< $5 OK -> $4" || log "!! $5 FAILED"
}

auto_report(){ # out_md title suffix
  "$EV" - "$1" "$2" "$3" <<'PYEOF' >>"$LOG" 2>&1 || true
import json, re, sys, pathlib
out, title, sfx = sys.argv[1], sys.argv[2], sys.argv[3]
root = pathlib.Path(".")
parts = [f"# {title}\n\n自動生成サマリ（客観=クリーンHB再評価後 / 主観=listwise 総合表の転載）。詳細は各ファイル参照。\n"]
for R, lab in [("results/run_fix10_big", "big (gemma-4-31b)"), ("results/run_fix10_small", "small (gemma-3-4b)")]:
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
        f = pathlib.Path(f"{R}/subj{sfx}_{dom}.md")
        if f.exists():
            m = re.search(r"## 総合ランキング.*", f.read_text(), re.S)
            if m:
                parts.append(f"\n### {dom} 主観 listwise (n={sfx})\n\n" + m.group(0) + "\n")
        else:
            parts.append(f"\n### {dom} 主観 (n={sfx}): ファイルなし\n")
pathlib.Path(out).write_text("".join(parts))
print("auto report ->", out)
PYEOF
}

C8="baseline analysis_only utterance_fewshot utterance_fewshot_analysis situation_fewshot situation_fewshot_analysis script_fewshot_k5 script_fewshot_analysis_k5"
C10="$C8 script_fewshot_k1 script_fewshot_analysis_k1"
CC8="baseline,analysis_only,utterance_fewshot,utterance_fewshot_analysis,situation_fewshot,situation_fewshot_analysis,script_fewshot_k5,script_fewshot_analysis_k5"
CC10="$CC8,script_fewshot_k1,script_fewshot_analysis_k1"

log "=== chain_round1b: waiting for fx_big2/fx_small2 (max 14h) ==="
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

log "re-evaluating HB objective on clean flats"
reeval_hb "$ROOT/results/run_fix10_big"
reeval_hb "$ROOT/results/run_fix10_small"

log "n=30 listwise subjective (judge on :8000, phase 2 not yet started)"
run_subj "results/run_fix10_big/hiddenbench_flat"   hb     "$CC8"  "results/run_fix10_big/subj30_hb.md"      r1n30_big_hb      30
run_subj "results/run_fix10_big/aiwolf_flat"        aiwolf "$CC8"  "results/run_fix10_big/subj30_aiwolf.md"  r1n30_big_aiwolf  30
run_subj "results/run_fix10_small/hiddenbench_flat" hb     "$CC10" "results/run_fix10_small/subj30_hb.md"     r1n30_small_hb    30
run_subj "results/run_fix10_small/aiwolf_flat"      aiwolf "$CC10" "results/run_fix10_small/subj30_aiwolf.md" r1n30_small_aiwolf 30
auto_report "results/run_fix30_report_auto.md" "n=30 中間レポート (1周目前半, 2026-07-03)" 30
touch "$ROOT/serving/SUBJ30_DONE"
log "n=30 milestone complete -> results/run_fix30_report_auto.md"

HB_REST="13 22 23 24 31 37 40 41 42 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65"
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

log "round-1 complete — listwise subjective n=60"
run_subj "results/run_fix10_big/hiddenbench_flat"   hb     "$CC8"  "results/run_fix10_big/subj60_hb.md"      r1_big_hb      60
run_subj "results/run_fix10_big/aiwolf_flat"        aiwolf "$CC8"  "results/run_fix10_big/subj60_aiwolf.md"  r1_big_aiwolf  60
run_subj "results/run_fix10_small/hiddenbench_flat" hb     "$CC10" "results/run_fix10_small/subj60_hb.md"     r1_small_hb    60
run_subj "results/run_fix10_small/aiwolf_flat"      aiwolf "$CC10" "results/run_fix10_small/subj60_aiwolf.md" r1_small_aiwolf 60
auto_report "results/run_round1_report_auto.md" "1周目(n=60)レポート (2026-07-03)" 60

log "=== chain_round1b: ALL DONE ==="
touch "$ROOT/serving/ROUND1_DONE"
