# discussion-bench orchestration (run from repo root) / discussion-bench 統合システム (リポジトリ直下で実行)
# Pipeline / パイプライン:  generate (exemplars) -> run (server + agents) -> eval (metrics + judge)
# Usage / 使い方:
#   make generate        # Build example slots via the generator (generator/.venv)
#   make hiddenbench     # HiddenBench only (server + 4 agents) via docker compose
#   make aiwolf          # Werewolf only
#   make both            # Both domains concurrently
#   make down            # Stop everything
#   make eval            # Objective metrics over HiddenBench results (eval/.venv)
#   make judge           # Objective + subjective LLM-judge in one pass
#   make local-hb        # Run HiddenBench locally (no docker; needs agent/.venv)

COMPOSE ?= docker compose
# Per-component virtualenvs (each component has its own pyproject; sync once with `uv sync`).
# コンポーネントごとの venv（各々 pyproject を持つ。`uv sync` で一度同期）。
GEN_VENV  ?= generator/.venv/bin/python
EVAL_VENV ?= eval/.venv/bin/python
# Unified log tree (repo root). Servers/agents write here (local & Docker alike); eval reads
# the HiddenBench results from the same place and writes its report into results/eval/.
LOG_ROOT ?= $(CURDIR)/log
HB_RESULTS ?= log/hidden-bench/results
LANG_CODE ?= jp
# Subjective LLM-judge config (override for local gemma: JUDGE_CFG=eval/config/judge.local.yml).
JUDGE_CFG ?= eval/config/judge.yml

.PHONY: generate hiddenbench aiwolf both down logs eval judge plots local-hb local-aiwolf help

help:
	@echo "make generate | hiddenbench | aiwolf | both | down | logs | eval | judge | local-hb | local-aiwolf"

# Build the example-injection slots (scripts/utterances/analysis) via the generator.
# Needs: (cd generator && uv sync). Reads generator/config/generator.yml + root .env.
generate:
	PYTHONPATH=generator/src $(GEN_VENV) generator/src/main.py -c generator/config/generator.yml

hiddenbench:
	$(COMPOSE) --profile hiddenbench up --build

aiwolf:
	$(COMPOSE) --profile aiwolf up --build

both:
	$(COMPOSE) --profile aiwolf --profile hiddenbench up --build

down:
	$(COMPOSE) --profile aiwolf --profile hiddenbench down

logs:
	$(COMPOSE) logs -f

# Objective failure-mode metrics only (no API needed) -> bilingual report + plots.
# Needs: (cd eval && uv sync).
eval:
	PYTHONPATH=eval/src $(EVAL_VENV) eval/src/evaluate.py $(HB_RESULTS)
	$(EVAL_VENV) eval/src/plot_report.py $(HB_RESULTS)/eval/metrics.json

# Objective + subjective LLM-judge in one pass (judge model = eval/config/judge.yml) + plots.
# 客観 + 主観LLM-judge を一括 -> 統合レポート + 可視化。判定モデルは eval/config/judge.yml。
judge:
	PYTHONPATH=eval/src $(EVAL_VENV) eval/src/evaluate_with_judge.py $(HB_RESULTS) -c $(JUDGE_CFG)
	$(EVAL_VENV) eval/src/plot_report.py $(HB_RESULTS)/eval/metrics.json

# Local (no-docker) runs for development.
local-hb:
	./run_local.sh hiddenbench

local-aiwolf:
	./run_local.sh aiwolf

# Render the eval metrics into a single PNG (results/local_run/hiddenbench_flat/eval/plots.png).
plots:
	$(EVAL_VENV) eval/src/plot_report.py $(HB_RESULTS)/eval/metrics.json

# Evaluate the generated exemplar scripts themselves as a "gold_script" reference group:
# writes gold result JSONs into the flat results dir, then re-runs judge+plots so the final
# plot includes the gold reference. (Human-vs-human logs, if present as condition=human result
# JSONs in the same dir, are likewise picked up by judge/plots automatically.)
exemplars:
	PYTHONPATH=eval/src $(EVAL_VENV) eval/src/evaluate_exemplars.py --lang $(LANG_CODE) --agent-dir agent --out $(HB_RESULTS)
	$(MAKE) judge HB_RESULTS=$(HB_RESULTS) JUDGE_CFG=$(JUDGE_CFG)

# Per-domain + overall condition rankings (HiddenBench / aiwolf / overall) into rankings.md.
# Converts aiwolf game JSONs, evaluates them (domain-general metrics + judge), then ranks.
rankings:
	PYTHONPATH=eval/src $(EVAL_VENV) eval/src/evaluate_aiwolf.py --src results/local_run/aiwolf --out results/local_run/aiwolf_flat
	PYTHONPATH=eval/src $(EVAL_VENV) eval/src/evaluate_with_judge.py results/local_run/aiwolf_flat -c $(JUDGE_CFG)
	PYTHONPATH=eval/src $(EVAL_VENV) eval/src/rankings.py --hb $(HB_RESULTS)/eval/metrics.json --aiwolf results/local_run/aiwolf_flat/eval/metrics.json --out results/local_run/rankings.md

# =====================================================================
# OPS one-liners (vLLM serve / runs / listwise+pairwise eval). `make ops-help`.
# FLAT / SRC accept multiple space-separated dirs. Override any VAR= on the CLI.
# =====================================================================
GPUS    ?= 0,1
PORT    ?= 8000
MAXLEN  ?= 49152
SMODEL  ?= unsloth/gemma-3-4b-it
SGPUS   ?= 3
SPORT   ?= 8004
SMAXLEN ?= 65536
DOMAIN  ?= aiwolf
SEEDS   ?= 60
PWSEEDS ?= 8
OPSLABEL?= run
CONDS   ?=
JUDGECFG?= eval/config/judge.listwise.yml
MODELPORT ?= 8000
ENDPOINTS ?= http://127.0.0.1:8000/v1
RESULTS   ?= $(CURDIR)/results/run_en_kexp_big
AWG       ?= 30
HBLIST    ?= $(shell python3 -c "print(' '.join(str(i) for i in range(1,46) if i not in (4,8,12,14,30,32,34)))")
# eval wrapper: eval venv + PYTHONPATH(judge import) + dummy key for local vLLM
EVAL = cd $(CURDIR) && . eval/.venv/bin/activate && PYTHONPATH=eval/src OPENAI_API_KEY=EMPTY

.PHONY: ops-help serve-big serve-small wait models gpu stop-big stop-small freegpu \
        status cleanup scriptcount gen-analysis gen-typed-analysis kexp kexp-big kexp-small \
        listwise pairwise discourse aiwolf-outcome

ops-help:
	@echo "SERVE:  make serve-big [GPUS=0,1 PORT=8000] | serve-small [SGPUS=3 SPORT=8004]"
	@echo "        make wait PORT=8000 | models PORT=8000 | gpu | stop-big | stop-small | freegpu GPU=0"
	@echo "RUN:    make status | cleanup | scriptcount"
	@echo "        make gen-analysis [MODELPORT=8000]      # script-derived talk+action analysis K=1,3,5,10"
	@echo "        make kexp-big | kexp-small [AWG=30]     # K+analysis sweep (script_k{1,3,5,10}_a)"
	@echo "EVAL:   make listwise FLAT='d1 d2' DOMAIN=aiwolf SEEDS=60 [CONDS=c1,c2] OUT=x.md OPSLABEL='..'"
	@echo "        make pairwise FLAT='d1 d2' DOMAIN=hb PWSEEDS=8 [CONDS=..] OUT=x.md"
	@echo "        make discourse FLAT='d1 d2' OUT=x.md | aiwolf-outcome SRC='d1 d2' OUT=x.md"

serve-big:
	cd $(CURDIR)/serving && VLLM_GPUS=$(GPUS) VLLM_PORT=$(PORT) VLLM_MAXLEN=$(MAXLEN) \
	  nohup bash start_vllm.sh > vllm_$(PORT).log 2>&1 & echo "big vLLM :$(PORT) GPUs $(GPUS) -> serving/vllm_$(PORT).log"

serve-small:
	cd $(CURDIR)/serving && MODEL=$(SMODEL) VLLM_GPUS=$(SGPUS) VLLM_PORT=$(SPORT) VLLM_MAXLEN=$(SMAXLEN) \
	  nohup bash start_vllm_small.sh > vllm_small_$(SPORT).log 2>&1 & echo "small vLLM :$(SPORT) GPUs $(SGPUS) -> serving/vllm_small_$(SPORT).log"

wait:
	@echo "waiting for :$(PORT) ..."; until curl -s -m3 http://localhost:$(PORT)/v1/models 2>/dev/null | grep -q gemma; do sleep 8; done; echo "READY :$(PORT)"

models:
	@curl -s http://localhost:$(PORT)/v1/models | python3 -c "import sys,json;print([m['id'] for m in json.load(sys.stdin)['data']])"

gpu:
	@nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader

stop-big:
	-pkill -f 'vllm serve google/gemma-4-31B' || true ; echo stopped-big

stop-small:
	-pkill -f 'vllm serve $(SMODEL)' || true ; echo stopped-small

# kills EVERY compute proc on GPU $(GPU) — only use on GPUs running YOUR jobs
freegpu:
	@nvidia-smi -i $(GPU) --query-compute-apps=pid --format=csv,noheader | xargs -r kill -9 ; echo "freed GPU $(GPU)"

status:
	@bash serving/status.sh
cleanup:
	@bash serving/cleanup_runs.sh
scriptcount:
	@bash serving/launch_scriptcount.sh

gen-analysis:
	$(EVAL) python3 serving/gen_script_analysis.py --port $(MODELPORT) --pack agent/aiwolf --lang en --ks 1,3,5,10

# exemplar-TYPE-specific analysis for the 8-cond comparison (situ/utt/scr + points). Run AFTER sweep.
gen-typed-analysis:
	PORT=$(MODELPORT) bash serving/gen_typed_analysis.sh

kexp:
	setsid nohup env \
	  CONDS="script_k1_a script_k3_a script_k5_a script_k10_a" \
	  CONDITIONS_FILE="config/conditions_scriptcount_analysis.yml" \
	  ENDPOINTS="$(ENDPOINTS)" NWORKERS=4 LANG_CODE=en \
	  HB_TASK_LIST="$(HBLIST)" AW_GAMES=$(AWG) \
	  GAME_TIMEOUT=1200 AW_TIMEOUT=600 RETRIES=5 \
	  HB_RESP_TIMEOUT_MS=600000 HB_ACTION_TIMEOUT_MS=300000 \
	  RESULTS="$(RESULTS)" \
	  bash serving/run_matrix_parallel.sh > serving/kexp_$(notdir $(RESULTS)).log 2>&1 & \
	  echo "kexp launched -> $(RESULTS)  (log serving/kexp_$(notdir $(RESULTS)).log)"
kexp-big:
	$(MAKE) kexp ENDPOINTS="http://127.0.0.1:8000/v1" RESULTS="$(CURDIR)/results/run_en_kexp_big"
kexp-small:
	$(MAKE) kexp ENDPOINTS="http://127.0.0.1:8004/v1" RESULTS="$(CURDIR)/results/run_en_kexp_small"

listwise:
	$(EVAL) python3 eval/src/evaluate_listwise_subj.py $(foreach d,$(FLAT),--flat $(d)) \
	  --domain $(DOMAIN) --judge-config $(JUDGECFG) --n-seeds $(SEEDS) $(if $(CONDS),--conds $(CONDS),) --out $(OUT) --label "$(OPSLABEL)"
pairwise:
	$(EVAL) python3 eval/src/evaluate_pairwise_subj.py $(foreach d,$(FLAT),--flat $(d)) \
	  --domain $(DOMAIN) --judge-config $(JUDGECFG) --n-seeds $(PWSEEDS) $(if $(CONDS),--conds $(CONDS),) --out $(OUT) --label "$(OPSLABEL)"
discourse:
	$(EVAL) python3 eval/src/evaluate_discourse.py $(foreach d,$(FLAT),--flat $(d)) --out $(OUT) --label "$(OPSLABEL)"
aiwolf-outcome:
	$(EVAL) python3 eval/src/evaluate_aiwolf_outcome.py $(foreach d,$(SRC),--src $(d)) --out $(OUT) --label "$(OPSLABEL)"
