#!/usr/bin/env bash
ROOT=/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench; cd "$ROOT"
EVAL="$ROOT/eval/.venv/bin/python"
C8="baseline,analysis_only,utterance_fewshot,utterance_fewshot_analysis,situation_fewshot,situation_fewshot_analysis,script_fewshot_k5,script_fewshot_analysis_k5"
rm -f serving/AIWOLF_SUBJ_DONE
t=0
while :; do
  b=$(ls results/verify_big/aiwolf/*/*.json 2>/dev/null|wc -l)
  s=$(ls results/verify_small/aiwolf/*/*.json 2>/dev/null|wc -l)
  echo "[$(date +%H:%M:%S)] waiting: big_aw=$b/80 small_aw=$s/80"
  { [ "$b" -ge 80 ] && [ "$s" -ge 80 ]; } && { echo "both complete"; break; }
  [ "$t" -ge 10800 ] && { echo "timeout, proceeding with what exists"; break; }
  sleep 30; t=$((t+30))
done
for tag in big small; do
  fd="results/verify_$tag/aiwolf_flat_lw"; rm -rf "$fd"; mkdir -p "$fd"
  for cond in ${C8//,/ }; do
    for f in results/verify_$tag/aiwolf/$cond/g*.json; do
      [ -f "$f" ] || continue
      cp "$f" "$fd/${cond}__$(basename "$f")"
    done
  done
  echo "[$tag] flat files: $(ls "$fd" | wc -l)"
  PYTHONPATH=eval/src "$EVAL" eval/src/evaluate_listwise_subj.py \
    --flat "$fd" --domain aiwolf --n-seeds 10 --conds "$C8" \
    --judge-config eval/config/judge.listwise.yml \
    --out "results/verify_$tag/subj_aiwolf_listwise.md" --label "v${tag}_aw" 2>&1 | tail -3
done
touch serving/AIWOLF_SUBJ_DONE
echo "=== AIWOLF SUBJ DONE ==="
