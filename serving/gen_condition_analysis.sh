#!/usr/bin/env bash
# Build the ENGLISH analysis used by the K=5 condition comparison (conditions_v2_typed.yml),
# then save JA translations for human review.
#   PORT (default 8000)  gemma-4-31b endpoint
# Generates (both packs), in ENGLISH (--analang en):
#   analysis_situ   <- situations     (⑥ situation_fewshot_analysis)
#   analysis_utt    <- utterances_k5  (④ utterance_fewshot_analysis)
#   analysis_k5     <- scripts_k5     (⑧ script_fewshot_analysis)
#   analysis_points <- scripts_k5, POINTS checklist (② analysis_only)
# aiwolf -> talk.md+action.md ; hb -> analysis.md.
# Then translates every produced file to JA into results/analysis_review/<pack>/<dir>/.
set -uo pipefail
ROOT="/disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench"
cd "$ROOT"
PORT="${PORT:-8000}"
source eval/.venv/bin/activate
export OPENAI_API_KEY=EMPTY PYTHONPATH=eval/src
G(){ python3 serving/gen_analysis.py --port "$PORT" --model gemma-4-31b --analang en "$@"; }
T(){ python3 serving/translate_md.py --port "$PORT" --model gemma-4-31b --src "$1" --out "$2"; }

for spec in "agent/aiwolf:aiwolf" "agent/hidden-bench:hb"; do
  pack="${spec%%:*}"; mode="${spec##*:}"
  echo "===== GENERATE (EN) $pack ====="
  G --pack "$pack" --mode "$mode" --src situations    --out analysis_situ   --kind exemplar
  G --pack "$pack" --mode "$mode" --src utterances_k5 --out analysis_utt    --kind exemplar
  G --pack "$pack" --mode "$mode" --src scripts_k5    --out analysis_k5     --kind exemplar
  G --pack "$pack" --mode "$mode" --src scripts_k5    --out analysis_points --kind points
done

echo "===== TRANSLATE -> JA (review) ====="
for spec in "agent/aiwolf:aiwolf" "agent/hidden-bench:hb"; do
  pack="${spec%%:*}"; mode="${spec##*:}"
  files="analysis.md"; [ "$mode" = aiwolf ] && files="talk.md action.md"
  for d in analysis_situ analysis_utt analysis_k5 analysis_points; do
    for f in $files; do
      src="agent/$pack/exemplars/en/$d/$f"
      out="results/analysis_review/$pack/$d/$f"
      [ -f "$src" ] && T "$src" "$out"
    done
  done
done
echo "CONDITION_ANALYSIS_DONE"
