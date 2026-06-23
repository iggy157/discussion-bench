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
