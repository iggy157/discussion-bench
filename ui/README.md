# ui/ — Web UI（aiwolf-nlp-demo ベース）

ブラウザで遊べるUI層です。`aiwolf-nlp-demo` の豪華な人狼UI（SvelteKitビューア＋FastAPIロビー＋Caddy）を
取り込み、**エージェント起動だけを本リポジトリの `launcher` に差し替え**てあります。これにより、AI席は
実験と同じ共有エージェントで動き、**UIから実験条件（台本あり/なし等）を選んで起動**できます。

> ⚠️ このUIは**フェーズ開発中**です。バックエンド（ロビーのエージェント起動・設定生成）は差し替え済み・
> 動作確認済みですが、**フロント（ナビ・条件セレクタ・HiddenBenchページ）と実ブラウザ検証は未完了**です。
> 現状を下にまとめます。

## いまの状態

| 項目 | 状態 |
|---|---|
| demoのUI層を取り込み（viewer / lobby / Caddy / configs） | ✅ |
| ロビーのAI起動を本リポジトリの `launcher` に差し替え（人狼・条件対応） | ✅ コードレベル検証済み |
| ソロ/マルチ・卓マッチング・離脱時takeover（demo由来） | ✅ そのまま流用 |
| 人間も同じ `server/aiwolf` + 同じ設定で対戦 | ✅ 設計どおり |
| `/api/conditions` で条件一覧を返す | ✅ |
| フロントに条件セレクタUI | ⬜ 未（次フェーズ） |
| 上部ナビ（AIWolf / HiddenBench 切替） | ⬜ 未 |
| HiddenBenchページ | ⬜ 未 |
| lobby Dockerイメージに本リポジトリのagent同梱 | ⬜ 未（今はローカル実行向け） |
| 実ブラウザでの通し動作確認 | ⬜ 未（要・実機） |

## 仕組み（差し替えのポイント）

- `lobby/main.py` の `_build_agent_config()` は、`launcher/launch_agents.py` の `build_config()` を呼び、
  `domain=aiwolf` ＋ 選択された `condition` ＋ 言語で**本リポジトリのエージェント設定**を生成します。
- AI席のプロセスは demo と同じ Popen 機構で起動されますが、起動先は `agent/`（本リポジトリの共有エージェント）です。
- 起動先・ランチャ・条件は環境変数で差し替え可能：
  - `AGENT_LLM_DIR`（既定 `../agent`）, `INLG_LAUNCHER_DIR`（既定 `../launcher`）,
    `INLG_CONDITIONS`（既定 `../config/conditions.yml`）, `CONDITION`（既定 `baseline`）,
    `AGENT_LLM_PYTHON` / `INLG_PYTHON`（エージェント用のPython）。
- LLMのモデル・プロバイダは**エージェント設定（`agent/aiwolf/config`）側**が決めます（実験と同一設定で人間も対戦するため、
  demoの `LLM_PROVIDER/LLM_MODEL` は適用しません）。

## ローカルで動かす（暫定）

```bash
# 1) 人狼サーバを起動（別ターミナル）
cd ../server/aiwolf && go run . -c ./config/default_5.yml

# 2) ロビーを起動（要 fastapi/uvicorn。agentのPythonを使う）
cd lobby
AGENT_LLM_PYTHON=../../agent/.venv/bin/python \
GAME_WS_INTERNAL_URL=ws://127.0.0.1:8080/ws \
GAME_WS_PUBLIC_URL=ws://127.0.0.1:8080/ws \
CONDITION=baseline \
  uvicorn main:app --port 8002

# 3) ビューアを起動（SvelteKit。要 node/pnpm）
cd ../viewer && pnpm install && pnpm dev
# ブラウザで開発サーバを開き、/demo へ。AI席は CONDITION の条件で起動される。
```

> compose 一発起動（lobby イメージに agent 同梱）と HiddenBench ページ、ナビ、条件セレクタは次フェーズで整備します。

## 取り込み元

`aiwolf-nlp-demo`（lobby / viewer / Caddy / configs / scripts）。`repos/aiwolf-nlp-server` と
`repos/aiwolf-nlp-agent-llm` は取り込まず、本リポジトリの `server/aiwolf` と `agent/` を使います。
