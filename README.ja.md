<!-- 言語: [English](README.md) | **日本語** -->

# マルチエージェントLLM議論プラットフォーム

**複数のLLMエージェントによる議論**を2つの環境で実行・評価するためのプラットフォームです。

- **人狼（Werewolf）** — 社会的推理の対話ゲーム（AIWolfDialプロトコル、5人）。
- **HiddenBench** — 隠れプロファイル型の協調推論タスク（4エージェントが情報を分担して持ち、
  議論して正解に到達する）。

1つの設定可能なLLMエージェントが両方をプレイします。制御はすべてリポジトリ直下
（`.env` と `config/`）から行い、Docker かローカルで片方／両方の環境を起動し、得られた
トランスクリプトを同梱の評価ツールで採点します。小さなWebロビーを使えば、人間が
HiddenBenchの1席に参加できます（人間の議論データ収集などに利用）。

## 何ができるか

- いずれかの環境で1ゲーム／タスクを通しで実行し、ゲームごとのトランスクリプトと結果を出力。
- 両環境で同一のエージェントコードを使用。LLMプロバイダ（OpenAI / Google / Anthropic /
  Ollama）とプロンプトは設定で指定。
- エージェントのプロンプトに手本（完全トランスクリプト／単一発話例／分析メモ）を注入できる。
  どれを注入するかは名前付きの **condition（条件）** で選択。既定の `baseline` は何も注入しない。
- トランスクリプトから失敗様態の指標（情報の表面化、早期収束、語彙多様性、同調）を計算し、
  日英レポートを出力。

## ディレクトリ構成

リポジトリの**直下が制御面**で、その他は部品です。

| パス | 役割 |
|------|------|
| `.env` / `.env.example` | 唯一の設定ファイル。言語・条件・ポート・LLM APIキー。Docker Compose／ローカル実行／エージェントが参照。 |
| `config/inlg.yml` | 実行設定の可読マップ（どの環境・言語・環境別パラメータ）。 |
| `config/conditions.yml` | 手本注入の **condition** プリセット（エージェントのプロンプトに何を入れるか）。 |
| `docker-compose.yml` | 両環境を Compose の **profiles**（`aiwolf` / `hiddenbench`）として定義。片方／両方を起動。 |
| `docker/` | Dockerfile群：エージェント用と2つのサーバ用。 |
| `launcher/` | （環境・言語・条件）を受け取り、エージェント設定を組み立ててエージェントを起動。 |
| `Makefile`, `run_local.sh` | Docker／ローカル実行のエントリポイント。 |
| `agent/` | 両環境をプレイするLLMエージェント。`src/` がエンジン本体、`aiwolf/`・`hidden-bench/` は各環境の設定と手本スロット、`prompts/`・`data/` は共有。 |
| `server/aiwolf/` | 人狼ゲームサーバ（Go）。 |
| `server/hidden-bench/` | HiddenBenchサーバ（Python）。 |
| `eval/` | トランスクリプトから指標を計算しレポート出力。 |
| `web/` | 人間がHiddenBenchの1席に参加するためのブラウザロビー（データ収集）。 |
| `docs/` | 設計・手法メモ（背景資料。実行には不要）。 |

## 必要なもの

- Docker + Docker Compose、**または**ローカル実行用に
  [`uv`](https://docs.astral.sh/uv/)・Python 3.11+・Go 1.24+（人狼サーバ用のみ）。
- LLMプロバイダのAPIキー（OpenAI / Google / Anthropic）、**または**ローカルの Ollama。

## 設定

```bash
cp .env.example .env
# その後 .env を編集:
#   LANG_CODE=en|jp           両環境の言語
#   CONDITION=baseline        手本注入プリセット（config/conditions.yml 参照）
#   OPENAI_API_KEY=...         （および/または GOOGLE_API_KEY / CLAUDE_API_KEY）
```

LLMプロバイダとモデルはエージェントの環境別設定
（`agent/aiwolf/config/…` と `agent/hidden-bench/config/…`）で指定します。既定は OpenAI。

## Dockerで実行

```bash
docker compose --profile hiddenbench up --build              # HiddenBenchのみ
docker compose --profile aiwolf up --build                   # 人狼のみ
docker compose --profile aiwolf --profile hiddenbench up --build   # 両方同時

# 同等の Make ターゲット:
make hiddenbench   |   make aiwolf   |   make both   |   make down   |   make logs
```

2環境は別ポート（人狼8080、HiddenBench8090）を使うので並走できます。

## ローカルで実行（Dockerなし）

```bash
cd agent && uv sync && cd ..      # エージェントの仮想環境を一度だけ作成
make local-hb                     # HiddenBenchサーバ + 4エージェント
make local-aiwolf                 # 人狼サーバ(Go) + 5エージェント
# 直接実行する場合:  ./run_local.sh hiddenbench
```

## 評価

```bash
make eval        # server/hidden-bench/log/results/ を読み、.../eval/report.md と metrics.json を出力
```

レポートは condition 別に集計されるので、複数条件を回すと1つの比較表になります。

## 人間の参加（HiddenBench）

```bash
cd web && uv sync
HB_URL=ws://127.0.0.1:8090/ws uv run uvicorn --app-dir src app:app --port 8000
# HiddenBenchサーバ + 3エージェントを起動し、http://localhost:8000 を開いて4席目に入る
```

人間のセッションは `web/log/human/` に保存され、後で分析できます。

## 実行の流れ

1. サーバ（人狼またはHiddenBench）が起動し、必要人数のエージェント接続を待つ。
2. ランチャが選択した環境／言語／条件のエージェント設定を組み立て、エージェントを起動。
   エージェントはWebSocketでサーバに接続する。
3. サーバがゲーム／タスクを進行し、エージェントは各リクエストに設定済みのLLMで応答する。
4. サーバがゲームごとの結果を書き出し、`eval/` がトランスクリプトを指標に変換する。

## 補足

- `server/aiwolf/` と `agent/` はベンダリングしたスナップショット。共有パケットライブラリ
  `aiwolf-nlp-common` は PyPI（`==0.7.0`）から導入し、同梱はしない。
- 手本スロット（`agent/<env>/exemplars/`）は**空**で同梱。ファイルを追加するまで、`baseline`
  以外の条件は自動的に `baseline` と同じ挙動になる。
- `.env`・仮想環境・`log/` は git 管理外。実APIキーは絶対にコミットしないこと。
