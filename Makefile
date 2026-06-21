# INLG system orchestration (run from repo root) / INLG統合システム (リポジトリ直下で実行)
# Usage / 使い方:
#   make hiddenbench     # HiddenBench only (server + 4 agents) via docker compose
#   make aiwolf          # Werewolf only
#   make both            # Both domains concurrently
#   make down            # Stop everything
#   make eval            # Run the metrics module over HiddenBench results
#   make local-hb        # Run HiddenBench locally (no docker; needs agent/.venv)

COMPOSE ?= docker compose
VENV ?= agent/.venv/bin/python
HB_RESULTS ?= server/hidden-bench/log/results

.PHONY: hiddenbench aiwolf both down logs eval local-hb local-aiwolf help

help:
	@echo "make hiddenbench | aiwolf | both | down | logs | eval | local-hb | local-aiwolf"

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

# Aggregate HiddenBench per-game results into failure-mode metrics + bilingual report.
eval:
	PYTHONPATH=eval/src $(VENV) eval/src/evaluate.py $(HB_RESULTS)

# Local (no-docker) runs for development.
local-hb:
	./run_local.sh hiddenbench

local-aiwolf:
	./run_local.sh aiwolf
