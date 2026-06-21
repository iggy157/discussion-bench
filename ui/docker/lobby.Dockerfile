# Lobby backend (FastAPI) + THIS repo's shared agent + launcher.
# ロビーbackend(FastAPI) ＋ 本リポジトリの共有エージェント＋ランチャを同梱。
# Build context = repo root (discussion-bench/). The lobby spawns AI seats by calling our launcher,
# which builds the shared agent's config (domain=aiwolf + selected condition).
FROM python:3.11-slim

WORKDIR /app

# --- our shared agent + launcher + central config ---
COPY agent/ /app/agent/
COPY launcher/ /app/launcher/
COPY config/ /app/config/

# --- agent runtime deps (no uv in the image) ---
RUN pip install --no-cache-dir \
    "aiwolf-nlp-common==0.7.0" \
    "langchain-openai>=0.3.9" \
    "langchain-google-genai>=2.1.0" \
    "langchain-anthropic>=1.3.0" \
    "langchain-ollama>=0.3.0" \
    "jinja2>=3.1.6" \
    "pyyaml>=6.0.2" \
    "python-dotenv>=1.1.0" \
    "python-ulid>=3.0.0" \
    "websocket-client>=1.7.0"

# --- lobby deps + app + demo configs (server configs / i18n) ---
COPY ui/lobby/requirements.txt /app/lobby/requirements.txt
RUN pip install --no-cache-dir -r /app/lobby/requirements.txt
COPY ui/lobby/ /app/lobby/
COPY ui/configs/ /app/configs/

ENV AGENT_LLM_DIR=/app/agent \
    LAUNCHER_DIR=/app/launcher \
    CONDITIONS_FILE=/app/config/conditions.yml \
    AGENT_LLM_PYTHON=python \
    AGENTS_DIR=/app/configs/agents \
    DEFAULT_LANGUAGE=ja \
    CONDITION=baseline \
    GENERATED_CONFIG_DIR=/app/lobby/.generated

WORKDIR /app/lobby
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
