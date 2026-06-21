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
| ロビーをHiddenBenchにも対応（domain切替・4人固定・HB URL） | ✅ コードレベル検証済み |
| ソロ/マルチ・卓マッチング・離脱時takeover（demo由来） | ✅ そのまま流用 |
| 人間も同じ `server/aiwolf` + 同じ設定で対戦 | ✅ 設計どおり |
| `/api/conditions` で条件一覧を返す | ✅ |
| 人狼ページに条件セレクタUI | ✅ 実装（要ブラウザ検証） |
| 上部ナビ（AIWolf / HiddenBench 切替、`+layout.svelte`） | ✅ 実装（要ブラウザ検証） |
| HiddenBenchページ（`/hidden-bench`、条件選択＋議論UI） | ✅ 実装（要ブラウザ検証） |
| docker compose 一発起動（game-server=server/aiwolf、lobby=本agent、caddy=viewer、HBサーバ） | ✅ 構成済み（要ビルド検証） |
| lobby Dockerイメージに本リポジトリのagent同梱 | ✅ Dockerfile済み |
| 実ブラウザ／SvelteKitビルドでの通し動作確認 | ⬜ 未（要・実機） |

> Python側（ロビーの起動・設定生成）は `py_compile` ＋ `build_config` の実呼び出しで検証済みです。
> フロント（SvelteKit）は当環境に pnpm/Node22 が無くビルド検証できていないため、**実機での確認が必要**です。

## 仕組み（差し替えのポイント）

- `lobby/main.py` の `_build_agent_config()` は、`launcher/launch_agents.py` の `build_config()` を呼び、
  `domain=aiwolf` ＋ 選択された `condition` ＋ 言語で**本リポジトリのエージェント設定**を生成します。
- AI席のプロセスは demo と同じ Popen 機構で起動されますが、起動先は `agent/`（本リポジトリの共有エージェント）です。
- 起動先・ランチャ・条件は環境変数で差し替え可能：
  - `AGENT_LLM_DIR`（既定 `../agent`）, `LAUNCHER_DIR`（既定 `../launcher`）,
    `CONDITIONS_FILE`（既定 `../config/conditions.yml`）, `CONDITION`（既定 `baseline`）,
    `AGENT_LLM_PYTHON` / `AGENT_LLM_PYTHON`（エージェント用のPython）。
- LLMのモデル・プロバイダは**エージェント設定（`agent/aiwolf/config`）側**が決めます（実験と同一設定で人間も対戦するため、
  demoの `LLM_PROVIDER/LLM_MODEL` は適用しません）。

## docker compose で起動（推奨）

```bash
# リポジトリ直下の .env を用意（APIキー・CONDITION・LANG_CODE）
cp ../.env.example ../.env   # まだなら

cd .   # discussion-bench/ui
docker compose up --build
# ブラウザで:
#   http://localhost/demo          … 人狼（AIWolf）
#   http://localhost/hidden-bench   … HiddenBench
# 上部ナビで両者を切替。AI席は画面の condition セレクタで選んだ条件で起動。
```

compose は game-server（=`server/aiwolf`）・hidden-bench-server（=`server/hidden-bench`）・
lobby（本リポジトリの `agent`＋`launcher` 同梱）・caddy（viewer配信＋WSリバプロ）を立ち上げます。

## ローカルで動かす（compose を使わない暫定）

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
