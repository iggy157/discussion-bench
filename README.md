# INLG 2026 — Scripts + Analysis for Multi-Party Discourse

One self-contained system for the INLG study: giving an LLM agent **full LLM-generated
discussion scripts + analysis** (as topic-independent examples) to fix multi-party
discourse failures, evaluated across **two domains** — werewolf (AIWolfDial) and
**HiddenBench** (hidden-profile collaborative reasoning) — with **one shared agent**.

INLG研究の自己完結システム。**LLM生成の完全議論台本＋分析**を話題非依存の手本として与え、
多人数談話の失敗を改善する。**人狼(AIWolfDial)** と **HiddenBench**(隠れプロファイル協調推論)の
**2ドメイン**を**1つの共有エージェント**で戦い、同一評価する。

## Read first / まず読む
- [INLG_SYSTEM.md](INLG_SYSTEM.md) — the map of the whole system / 全体図
- [INLG_METHODOLOGY.md](INLG_METHODOLOGY.md) — the defensible 6-condition design + citations / 防御的手法設計
- [INLG_VERIFICATION.md](INLG_VERIFICATION.md) — why the Go server can't host HiddenBench / 検証

## Repository layout / 構成

| Dir | What |
|-----|------|
| `hiddenbench-server/` | Faithful HiddenBench WebSocket server (Python): 4 agents, fixed T=15 sequential, pre/post elicitation, scoring. |
| `aiwolf-jsai-manyshot_ver0/` | The **shared agent** (manyshot). Has the HiddenBench adapter + JP/EN prompts + the 6-condition exemplar slots. Drives both domains. |
| `aiwolf-nlp-server/` | Werewolf (AIWolfDial) game server (Go). Vendored snapshot, unmodified. |
| `inlg-eval/` | Transcript failure-mode metrics → bilingual report. |
| `inlg-system/` | Orchestration: docker compose (both domains concurrent) + launcher (one config selects domain/condition/lang). |
| `inlg-web/` | Minimal web lobby: a human plays one HiddenBench seat (human-data collection). |

`aiwolf-nlp-server/` and `aiwolf-jsai-manyshot_ver0/` are **vendored snapshots** (this is a
self-contained monorepo). `aiwolf-nlp-common` is NOT vendored — it is installed from PyPI
(`==0.7.0`). / この2つは**ベンダリングしたスナップショット**。common は PyPI から導入。

## Quick start / クイックスタート

### Docker — both domains at once / 両ドメイン同時
```bash
cd inlg-system
cp .env.example .env        # set OPENAI_API_KEY / CLAUDE_API_KEY / GOOGLE_API_KEY, LANG_CODE, CONDITION
docker compose --profile aiwolf --profile hiddenbench up --build
#   HiddenBench only:  docker compose --profile hiddenbench up --build
#   Werewolf only:     docker compose --profile aiwolf up --build
```

### Local (no docker) / ローカル
```bash
cd hiddenbench-server && uv sync && cd ..
cd aiwolf-jsai-manyshot_ver0 && uv sync && cd ..     # recreates the agent venv
cd inlg-system && LANG_CODE=en CONDITION=baseline ./run_local.sh hiddenbench
```

### Evaluate / 評価
```bash
cd inlg-eval && uv run src/evaluate.py ../hiddenbench-server/log/results
```

### Human data collection / 人間データ収集
```bash
cd inlg-web && uv sync
HB_URL=ws://127.0.0.1:8090/ws uv run uvicorn --app-dir src app:app --port 8000
# start the HiddenBench server + 3 LLM agents, then open http://localhost:8000 for the 4th seat
```

## Status / 現状
- All components built and smoke-tested (server↔agent integration, faithful transcript,
  scoring, eval report). / 全コンポーネント構築・スモークテスト済み。
- **Exemplars are intentionally empty** (`aiwolf-jsai-manyshot_ver0/data/exemplars/`). Add
  scripts / utterance-fewshot / analysis later; non-baseline conditions fall back to
  baseline until populated. / 手本は意図的に空。後から追加する。
- Running real agents needs LLM provider API keys (or local Ollama/Gemma). / 実行にはAPIキー。

## License / provenance note
This monorepo vendors snapshots of `aiwolf-nlp-server` (aiwolfdial) and the manyshot agent
(derived from iggy157/aiwolf-jsai-manyshot). Respect their upstream licenses. The INLG glue
(`hiddenbench-server`, `inlg-eval`, `inlg-system`, `inlg-web`) and the agent's HiddenBench
adapter are the new contributions of this study.
