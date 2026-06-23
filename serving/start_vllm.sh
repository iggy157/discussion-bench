#!/usr/bin/env bash
# Launch a local vLLM server (gemma-4-31B, TP=2). Parametrized for multi-server parallelism:
#   VLLM_GPUS (default 0,1)   GPUs for this server (TP size = number of GPUs)
#   VLLM_PORT (default 8000)  listen port
# Served under the name the agent configs expect (google/gemma-2-27b-it) + a gemma-4-31b alias.
# All servers use IDENTICAL model + decoding settings, so per-game quality is unchanged whichever
# endpoint a game is routed to.
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate

GPUS="${VLLM_GPUS:-0,1}"
PORT="${VLLM_PORT:-8000}"
TP="$(awk -F, '{print NF}' <<<"$GPUS")"
MAXLEN="${VLLM_MAXLEN:-40960}"

export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES="$GPUS"

# flashinfer JIT needs nvcc >= 12; the system PATH defaults to cuda-11.7. Point at cuda-12.2
# (driver supports CUDA 13, so 12.2 toolkit is fine).
export CUDA_HOME=/usr/local/cuda-12.2
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

exec vllm serve google/gemma-4-31B-it \
  --served-model-name google/gemma-2-27b-it gemma-4-31b \
  --tensor-parallel-size "$TP" \
  --port "$PORT" \
  --host 127.0.0.1 \
  --max-model-len "$MAXLEN" \
  --gpu-memory-utilization 0.90
