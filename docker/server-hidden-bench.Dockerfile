# HiddenBench server image / HiddenBenchサーバ・イメージ
# Build context = repo root (inlg/).
FROM python:3.11-slim

WORKDIR /app
COPY server/hidden-bench/ /app/
RUN pip install --no-cache-dir "websockets>=12.0" "pyyaml>=6.0.2"

EXPOSE 8090
CMD ["python", "src/server.py", "-c", "config/hiddenbench.yml"]
