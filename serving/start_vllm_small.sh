#!/usr/bin/env bash
# Launch a vLLM server for a LIGHTWEIGHT model, served under the SAME alias the agent configs
# expect (google/gemma-2-27b-it) so NO config change is needed — just point ENDPOINTS at this port.
#   MODEL      (default unsloth/gemma-3-4b-it)  HF repo (ungated mirror, no token needed)
#   VLLM_GPUS  (default 3)                      GPU(s); TP = number of GPUs
#   VLLM_PORT  (default 8004)                   listen port
#   VLLM_MAXLEN(default 65536)                  match the big-model run for fair comparison
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate

MODEL="${MODEL:-unsloth/gemma-3-4b-it}"
GPUS="${VLLM_GPUS:-3}"
PORT="${VLLM_PORT:-8004}"
TP="$(awk -F, '{print NF}' <<<"$GPUS")"
MAXLEN="${VLLM_MAXLEN:-65536}"

export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES="$GPUS"
export CUDA_HOME=/usr/local/cuda-12.2
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

exec vllm serve "$MODEL" \
  --served-model-name google/gemma-2-27b-it gemma-4-31b \
  --tensor-parallel-size "$TP" \
  --port "$PORT" \
  --host 127.0.0.1 \
  --max-model-len "$MAXLEN" \
  --gpu-memory-utilization 0.90
