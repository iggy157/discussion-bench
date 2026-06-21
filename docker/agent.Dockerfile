# discussion-bench agent image (shared agent core + launcher) / 共有エージェント+ランチャ
# Build context = repo root (discussion-bench/). The same image drives both werewolf and HiddenBench;
# the launcher picks domain/condition/lang at run time from env.
FROM python:3.11-slim

WORKDIR /app
COPY agent/ /app/agent/
COPY launcher/ /app/launcher/
COPY config/ /app/config/
# Layout in the image mirrors the repo: /app/{agent,launcher,config}. The launcher reads
# the central /app/config/conditions.yml (= agent_dir.parent/config).

# Install the agent's runtime dependencies explicitly (no uv in the image).
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

ENV AGENT_DIR=/app/agent \
    PYTHONUNBUFFERED=1

# Defaults overridable by compose env / compose の環境変数で上書き可能.
ENV DOMAIN=hiddenbench \
    LANG_CODE=en \
    CONDITION=baseline \
    SERVER_URL=ws://hiddenbench-server:8090/ws \
    TEAM=discussion-bench-agent \
    NUM=4

CMD ["python", "/app/launcher/launch_agents.py"]
