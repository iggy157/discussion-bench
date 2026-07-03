#!/usr/bin/env bash
# Generate exemplar-type-specific analysis for ALL +analysis conditions, both domains.
# Run AFTER the K-sweep finishes (shares the gemma judge on :PORT). gemma-4-31b by default.
#   PORT (default 8000)   OpenAI-compatible gemma endpoint
# Produces (per domain pack):
#   analysis_situ   <- situations exemplars   (situation_fewshot_analysis)
#   analysis_utt    <- utterances exemplars   (utterance_fewshot_analysis)
#   analysis_scr    <- scripts exemplars      (script_fewshot_analysis)
#   analysis_points <- scripts as source, POINTS checklist (analysis_only; no exemplar shown)
# aiwolf -> talk.md+action.md ; hb -> analysis.md
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
PORT="${PORT:-8000}"
source eval/.venv/bin/activate
export OPENAI_API_KEY=EMPTY PYTHONPATH=eval/src
G(){ python3 serving/gen_analysis.py --port "$PORT" --model gemma-4-31b "$@"; }

for spec in "agent/aiwolf:aiwolf" "agent/hidden-bench:hb"; do
  pack="${spec%%:*}"; mode="${spec##*:}"
  echo "===== $pack (mode=$mode) ====="
  G --pack "$pack" --mode "$mode" --src situations --out analysis_situ  --kind exemplar
  G --pack "$pack" --mode "$mode" --src utterances --out analysis_utt   --kind exemplar
  G --pack "$pack" --mode "$mode" --src scripts    --out analysis_scr   --kind exemplar
  G --pack "$pack" --mode "$mode" --src scripts    --out analysis_points --kind points
done
echo "ALL TYPED ANALYSIS DONE"
