<!-- 言語: [English](README.md) | **日本語** -->

# マルチエージェントLLM議論プラットフォーム

複数のLLMエージェントに議論をさせ、その結果を評価するためのプラットフォームです。対象は次の2つの環境です。

- **人狼（Werewolf）** — 5人で行う社会的推理の対話ゲーム（AIWolfDialプロトコル）。
- **HiddenBench** — 4体のエージェントが手がかりを分担して持ち、議論を通じて正解にたどり着く協調推論タスク。

どちらの環境も、同じ1つのエージェントがプレイします。操作はリポジトリ直下の `.env` と `config/` に集約されており、Docker でもローカルでも、片方だけでも両方同時でも起動できます。実行後はトランスクリプトを同梱の評価ツールで採点でき、Webロビーを使えば人間がHiddenBenchに1人分のプレイヤーとして参加することもできます（人間の議論データを集めたいときに便利です）。

## できること

- 人狼・HiddenBenchのいずれかを1ゲーム通しで実行し、トランスクリプトと結果を保存する。
- エージェントのコードは両環境で共通。使用するLLM（OpenAI / Google / Anthropic / Ollama）やプロンプトは設定で切り替える。
- エージェントのプロンプトに「手本」を注入できる。注入する手本（完全なトランスクリプト・単一発話の例・分析メモ）は **condition（条件）** という名前付きプリセットで選ぶ。既定の `baseline` では何も注入しない。
- トランスクリプトから議論の失敗様態（情報の表面化、早期収束、語彙の多様性、同調など）を指標化し、日英併記のレポートを出力する。

## ディレクトリ構成

リポジトリ直下が操作の起点で、その下に各部品がぶら下がる形です。

| パス | 役割 |
|------|------|
| `.env` / `.env.example` | 設定の一元管理ファイル。言語・条件・ポート・LLMのAPIキーをここに書く。Docker Compose・ローカル実行・エージェントのすべてが参照する。 |
| `config/inlg.yml` | 実行設定を一覧できる読み物（どの環境を・どの言語で・どんなパラメータで動かすか）。 |
| `config/conditions.yml` | 手本注入の condition プリセット定義。 |
| `docker-compose.yml` | 2つの環境を Compose の profiles（`aiwolf` / `hiddenbench`）として定義。片方でも両方でも起動できる。 |
| `docker/` | エージェント用と各サーバ用の Dockerfile。 |
| `launcher/` | 環境・言語・条件を受け取り、エージェント設定を組み立てて起動する。 |
| `Makefile` / `run_local.sh` | Docker 実行・ローカル実行の入り口。 |
| `agent/` | 両環境をプレイするLLMエージェント。`src/` が本体、`aiwolf/`・`hidden-bench/` に各環境の設定と手本スロット、`prompts/`・`data/` は共通部分。 |
| `server/aiwolf/` | 人狼ゲームサーバ（Go）。 |
| `server/hidden-bench/` | HiddenBenchサーバ（Python）。 |
| `eval/` | トランスクリプトから指標を計算し、レポートを書き出す。 |
| `web/` | 人間がHiddenBenchに参加するためのブラウザ用ロビー。 |
| `docs/` | 設計・手法の補足資料（背景情報。動かすだけなら不要）。 |

## 用意するもの

- Docker と Docker Compose。ローカルで動かす場合は [`uv`](https://docs.astral.sh/uv/) と Python 3.11以上、人狼サーバを使うなら Go 1.24以上。
- LLMプロバイダのAPIキー（OpenAI / Google / Anthropic）。または手元の Ollama。

## 設定

```bash
cp .env.example .env
```

`.env` を開いて、最低限つぎの3つを設定します。

- `LANG_CODE` — 言語（`en` または `jp`）。両環境に適用される。
- `CONDITION` — 手本注入のプリセット（`baseline` ほか。詳細は `config/conditions.yml`）。
- `OPENAI_API_KEY` など — 使うプロバイダのAPIキー。

LLMのプロバイダとモデル自体は、エージェントの環境別設定（`agent/aiwolf/config/…`・`agent/hidden-bench/config/…`）で指定します。既定は OpenAI です。

## Docker で動かす

```bash
docker compose --profile hiddenbench up --build                    # HiddenBench だけ
docker compose --profile aiwolf up --build                         # 人狼だけ
docker compose --profile aiwolf --profile hiddenbench up --build   # 両方同時
```

同じことが Make でもできます。

```bash
make hiddenbench   |   make aiwolf   |   make both   |   make down   |   make logs
```

2つの環境はポートが別（人狼が8080、HiddenBenchが8090）なので、同時に動かしても干渉しません。

## ローカルで動かす（Dockerなし）

```bash
cd agent && uv sync && cd ..      # エージェントの仮想環境を最初に一度だけ作る
make local-hb                     # HiddenBenchサーバ + エージェント4体
make local-aiwolf                 # 人狼サーバ(Go) + エージェント5体
```

`./run_local.sh hiddenbench` のように直接呼んでも構いません。

## 評価する

```bash
make eval
```

`server/hidden-bench/log/results/` の結果を読み込み、同じ場所の `eval/report.md` と `metrics.json` を生成します。レポートは condition ごとに集計されるので、複数の条件で回せばそのまま比較表になります。

## 人間が参加する（HiddenBench）

```bash
cd web && uv sync
HB_URL=ws://127.0.0.1:8090/ws uv run uvicorn --app-dir src app:app --port 8000
```

HiddenBenchサーバとエージェント3体を起動したうえで `http://localhost:8000` を開くと、残り1席に人間として参加できます。各セッションの記録は `web/log/human/` に保存されます。

## 動作の流れ

1. サーバ（人狼またはHiddenBench）が起動し、必要な人数のエージェントが揃うのを待つ。
2. ランチャが、選んだ環境・言語・条件に合わせてエージェント設定を組み立て、エージェントを起動する。エージェントはWebSocketでサーバにつなぐ。
3. サーバがゲーム／タスクを進め、エージェントは各リクエストに対し設定したLLMで応答する。
4. サーバがゲームごとの結果を書き出し、`eval/` がそれを指標へ変換する。

## 補足

- `server/aiwolf/` と `agent/` は外部リポジトリのスナップショットを取り込んだものです。共通パケットライブラリ `aiwolf-nlp-common` は同梱せず、PyPI（`==0.7.0`）から入れます。
- 手本スロット（`agent/<環境>/exemplars/`）は空の状態で同梱しています。ファイルを置くまでは、`baseline` 以外の条件を選んでも自動的に `baseline` と同じ挙動になります。
- `.env`・仮想環境・`log/` は Git の管理対象外です。実際のAPIキーは絶対にコミットしないでください。
