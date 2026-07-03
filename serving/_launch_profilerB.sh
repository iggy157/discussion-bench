#!/usr/bin/env bash
cd /disk/ssd14ta/yharada/aiwolf/inlg/2026/develop/discussion-bench
t=0
while [ $t -lt 1800 ]; do
  curl -s -m5 http://127.0.0.1:8002/v1/models 2>/dev/null | grep -q gemma && break
  sleep 20; t=$((t+20))
done
curl -s -m5 http://127.0.0.1:8002/v1/models 2>/dev/null | grep -q gemma || { echo "8002 NOT READY"; exit 1; }
echo "8002 READY $(date '+%H:%M:%S') -> profiler B (tasks 40-65)"
LANG_CODE=en NWORKERS=1 NTASKS=65 REPS=5 TIMEOUT=900 RETRIES=3 TASK_START=40 TASK_END=65 \
  PROFILE_OUT="$PWD/results/hb_profiling_en_5rep" ENDPOINT="http://127.0.0.1:8002/v1" \
  bash serving/profile_hb.sh > serving/profile_hb_en_B.out 2>&1 &
echo "profiler B pid=$!"
