# discussion-bench — operations runbook (one-liners)

All via `make <target>` from repo root. `make ops-help` lists everything.
Local vLLM serves gemma under names `google/gemma-2-27b-it` + `gemma-4-31b` (agents need no config
change — just point ENDPOINTS at the port). Eval needs no real API key (`OPENAI_API_KEY=EMPTY`).

GPU topology: NVLink pairs (0,1)(3,4)(5,6)(2,7). TP=2 needs an NVLink pair. TP=1 (single GPU) is
fine for 31b too (no NCCL hang). Don't touch other users' GPUs (e.g. GPU4 if in use).

---

## 0. Serve models
```
make serve-big GPUS=0,1 PORT=8000     # gemma-4-31b (TP=2 on NVLink pair); ~2-3 min to load
make wait PORT=8000                    # block until ready
make serve-small SGPUS=3 SPORT=8004    # gemma-3-4b (single GPU)
make wait PORT=8004
make models PORT=8000                  # sanity: lists served model ids
make gpu                               # memory/util snapshot
```
Stop: `make stop-big` / `make stop-small`. If procs survive (EngineCore/Worker_TP): `make freegpu GPU=0`
(kills ALL compute procs on that GPU — only your own jobs).

---

## 1. Generate script-DERIVED analysis (the fix)
Re-derives talk+action analysis FROM each K-script set (K=1,3,5,10) using gemma on :8000.
Writes `agent/aiwolf/exemplars/en/analysis_k{K}/{talk,action}.md`.
```
make gen-analysis MODELPORT=8000
```
Inspect: `cat agent/aiwolf/exemplars/en/analysis_k5/talk.md`. Re-run to regenerate.

---

## 2. Script-count sweep WITH derived analysis (30 seeds × 4 conditions, both models)
Conditions: `script_k1_a script_k3_a script_k5_a script_k10_a` (config/conditions_scriptcount_analysis.yml).
Big on :8000, small on :8004 (serve both first). Runs detached.
```
make kexp-big  AWG=30                  # -> results/run_en_kexp_big   (log serving/kexp_run_en_kexp_big.log)
make kexp-small AWG=30                 # -> results/run_en_kexp_small  (log serving/kexp_run_en_kexp_small.log)
make status                            # progress; counts collected games
```
Idempotent (re-run fills gaps). `make cleanup` kills stray run procs (NOT vLLM).
Each run auto-evals (HB metrics + aiwolf flat + rankings) at the end; aiwolf raw -> `<RESULTS>/aiwolf`,
flat -> `<RESULTS>/aiwolf_flat`, HB flat -> `<RESULTS>/hiddenbench_flat`.

---

## 3. Compare K levels (pick the best K)
```
# objective discourse (padding/opening-diversity) per K — aiwolf + HB
make discourse FLAT='results/run_en_kexp_big/hiddenbench_flat' OUT=results/kexp_big_hb_discourse.md OPSLABEL='kexp big HB'
# aiwolf outcome (village_coordination) per K
make aiwolf-outcome SRC='results/run_en_kexp_big/aiwolf' OUT=results/kexp_big_aiwolf_outcome.md OPSLABEL='kexp big'
# subjective listwise ranking across the 4 K conditions (forced-ranking, discriminating)
make listwise FLAT='results/run_en_kexp_big/aiwolf_flat' DOMAIN=aiwolf SEEDS=30 \
  CONDS=script_k1_a,script_k3_a,script_k5_a,script_k10_a OUT=results/kexp_big_aiwolf_listwise.md OPSLABEL='kexp big'
# pairwise cross-check
make pairwise FLAT='results/run_en_kexp_big/aiwolf_flat' DOMAIN=aiwolf PWSEEDS=8 \
  CONDS=script_k1_a,script_k3_a,script_k5_a,script_k10_a OUT=results/kexp_big_aiwolf_pairwise.md
```
Repeat with `run_en_kexp_small` for the 4b model. Hypothesis: more scripts (tokens) helps big but
may hurt small (inverse correlation across the two models).

---

## 4. Eval one-liners (general; FLAT/SRC accept multiple space-separated dirs to pool reps)
```
make listwise FLAT='dirA dirB' DOMAIN=aiwolf|hb SEEDS=60 [CONDS=c1,c2,..] OUT=x.md OPSLABEL='..'
make pairwise FLAT='dirA dirB' DOMAIN=aiwolf|hb PWSEEDS=8 [CONDS=..] OUT=x.md
make discourse FLAT='dirA dirB' OUT=x.md
make aiwolf-outcome SRC='rawDirA rawDirB' OUT=x.md
```
- listwise/pairwise judge config: `eval/config/judge.listwise.yml` (4 criteria: natural_expression /
  contextual_dialogue / logical_consistency / speaker_individuality; HB uses the first 3, override
  with `JUDGECFG=`).
- listwise = rank all conds of a matched seed in one call (forces discrimination). pairwise =
  per-pair win-rate (independent cross-check). Agreement = robust; disagreement = low 分解能.

---

## Notes / gotchas
- aiwolf flat transcript ~556 tok, HB ~1215 → 8 logs fit one judge call easily.
- matched seed: game index gN = same HB task / same aiwolf role assignment across conditions.
- conditions auto-fall-back to baseline if an exemplar dir is empty (so run gen-analysis first).
- run_matrix_parallel.sh env: CONDS, CONDITIONS_FILE, ENDPOINTS, NWORKERS, LANG_CODE, HB_TASK_LIST,
  AW_GAMES, RESULTS, RUN_TAG/HB_PORT_BASE/AW_PORT_BASE (namespacing for parallel drivers).
