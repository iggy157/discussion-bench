#!/usr/bin/env bash
ROOT=/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench; cd "$ROOT"
EVAL="$ROOT/eval/.venv/bin/python"
C8="baseline,analysis_only,utterance_fewshot,utterance_fewshot_analysis,situation_fewshot,situation_fewshot_analysis,script_fewshot_k5,script_fewshot_analysis_k5"
rm -f serving/EVAL20_DONE
t=0
while :; do
  ba=$(ls results/verify_big/aiwolf/*/*.json 2>/dev/null|wc -l); sa=$(ls results/verify_small/aiwolf/*/*.json 2>/dev/null|wc -l)
  bh=$(ls results/verify_big/hiddenbench_flat/*.json 2>/dev/null|grep -v gold|wc -l); sh=$(ls results/verify_small/hiddenbench_flat/*.json 2>/dev/null|grep -v gold|wc -l)
  echo "[$(date +%H:%M)] big aw=$ba hb=$bh | small aw=$sa hb=$sh (target 160 each)"
  { [ "$ba" -ge 160 ] && [ "$sa" -ge 160 ] && [ "$bh" -ge 160 ] && [ "$sh" -ge 160 ]; } && break
  [ "$t" -ge 14400 ] && { echo "timeout"; break; }
  sleep 60; t=$((t+60))
done
for tag in big small; do
  # HB listwise (20 seeds)
  PYTHONPATH=eval/src "$EVAL" eval/src/evaluate_listwise_subj.py --flat results/verify_$tag/hiddenbench_flat \
    --domain hb --n-seeds 20 --conds "$C8" --judge-config eval/config/judge.listwise.yml \
    --out results/verify_$tag/subj_hb_listwise_n20.md --label ${tag}_hb20 2>&1 | tail -2
  # aiwolf flat (rebuild for 20) + listwise
  fd="results/verify_$tag/aiwolf_flat_lw"; rm -rf "$fd"; mkdir -p "$fd"
  for cond in ${C8//,/ }; do for f in results/verify_$tag/aiwolf/$cond/g*.json; do [ -f "$f" ] && cp "$f" "$fd/${cond}__$(basename "$f")"; done; done
  PYTHONPATH=eval/src "$EVAL" eval/src/evaluate_listwise_subj.py --flat "$fd" \
    --domain aiwolf --n-seeds 20 --conds "$C8" --judge-config eval/config/judge.listwise.yml \
    --out results/verify_$tag/subj_aiwolf_listwise_n20.md --label ${tag}_aw20 2>&1 | tail -2
  # objective rankings refresh (20)
  [ -f results/verify_$tag/aiwolf_flat/eval/metrics.json ] || PYTHONPATH=eval/src "$EVAL" eval/src/evaluate_aiwolf.py --src results/verify_$tag/aiwolf --out results/verify_$tag/aiwolf_flat >/dev/null 2>&1
  PYTHONPATH=eval/src "$EVAL" eval/src/rankings.py --hb results/verify_$tag/hiddenbench_flat/eval/metrics.json --aiwolf results/verify_$tag/aiwolf_flat/eval/metrics.json --out results/verify_$tag/rankings_n20.md >/dev/null 2>&1
done
touch serving/EVAL20_DONE
echo "=== EVAL20 DONE ==="
