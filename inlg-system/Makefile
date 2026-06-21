# INLG system orchestration / INLG統合システムのオーケストレーション
# Usage / 使い方:
#   make hiddenbench     # HiddenBench only (server + 4 agents) via docker compose
#   make aiwolf          # Werewolf only
#   make both            # Both domains concurrently
#   make down            # Stop everything
#   make eval            # Run the metrics module over HiddenBench results
#   make local-hb        # Run HiddenBench locally (no docker; needs the manyshot .venv)

COMPOSE ?= docker compose
VENV ?= ../aiwolf-jsai-manyshot_ver0/.venv/bin/python

.PHONY: hiddenbench aiwolf both down logs eval local-hb help

help:
	@echo "make hiddenbench | aiwolf | both | down | logs | eval | local-hb"

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
	$(VENV) ../inlg-eval/src/evaluate.py ../hiddenbench-server/log/results || \
	  PYTHONPATH=../inlg-eval/src $(VENV) ../inlg-eval/src/evaluate.py ../hiddenbench-server/log/results

# Local (no-docker) HiddenBench run for development.
local-hb:
	./run_local.sh hiddenbench
