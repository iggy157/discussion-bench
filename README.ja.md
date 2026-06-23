<!-- 言語: [English](README.md) | **日本語** -->

# マルチエージェントLLM議論プラットフォーム

複数のLLMエージェントに議論をさせ、その結果を評価するためのプラットフォームです。対象は次の2つの環境です。

- **人狼（Werewolf）** — 5人で行う社会的推理の対話ゲーム（AIWolfDialプロトコル）。
- **HiddenBench** — 4体のエージェントが手がかりを分担して持ち、議論を通じて正解にたどり着く協調推論タスク。

どちらの環境も、同じ1つのエージェントがプレイします。操作はリポジトリ直下の `.env` と `config/` に集約されており、Docker でもローカルでも、片方だけでも両方同時でも起動できます。実行後はトランスクリプトを同梱の評価ツールで採点でき、ブラウザUI（`ui/`）を使えば人間が1席を担当してプレイすることもできます（人間の議論データを集めたいときに便利です）。

## できること

- 人狼・HiddenBenchのいずれかを1ゲーム通しで実行し、トランスクリプトと結果を保存する。
- エージェントのコードは両環境で共通。使用するLLM（vLLM / OpenAI / Ollama / Google / Anthropic）やプロンプトは設定で切り替える。
- エージェントのプロンプトに「手本」を注入できる。注入する手本（完全なトランスクリプト・単一発話の例・分析メモ）は **condition（条件）** という名前付きプリセットで選ぶ。既定の `baseline` では何も注入しない。
- トランスクリプトから議論の失敗様態（情報の表面化、早期収束、語彙の多様性、同調など）を指標化し、日英併記のレポートを出力する。

## ディレクトリ構成

リポジトリ直下が操作の起点で、その下に各部品がぶら下がる形です。

| パス | 役割 |
|------|------|
| `.env` / `.env.example` | 設定の一元管理ファイル。言語・条件・ポート・LLMのAPIキーをここに書く。Docker Compose・ローカル実行・エージェントのすべてが参照する。 |
| `config/system.yml` | 実行設定を一覧できる読み物（どの環境を・どの言語で・どんなパラメータで動かすか）。 |
| `config/conditions.yml` | 手本注入の condition プリセット定義。 |
| `docker-compose.yml` | 2つの環境を Compose の profiles（`aiwolf` / `hiddenbench`）として定義。片方でも両方でも起動できる。 |
| `docker/` | エージェント用と各サーバ用の Dockerfile。 |
| `launcher/` | 環境・言語・条件を受け取り、エージェント設定を組み立てて起動する。 |
| `Makefile` / `run_local.sh` | Docker 実行・ローカル実行の入り口。 |
| `agent/` | 両環境をプレイするLLMエージェント。`src/` が本体、`aiwolf/`・`hidden-bench/` に各環境の設定と手本スロット、`prompts/`・`data/` は共通部分。 |
| `server/aiwolf/` | 人狼ゲームサーバ（Go）。 |
| `server/hidden-bench/` | HiddenBenchサーバ（Python）。 |
| `generator/` | 手本注入スロット（`scripts`/`utterances`/`analysis`）を Claude（既定の生成器系列。任意のプロバイダ/モデルに変更可）で生成し、`agent/<env>/exemplars/` に下書きを書き出す。 |
| `eval/` | トランスクリプトから指標を計算し、レポートを書き出す。 |
| `ui/` | ブラウザUI（aiwolf-nlp-demo 由来）。人狼・HiddenBench の人間プレイ。AI席は launcher 経由で起動。 |
| `docs/` | 設計・手法の補足資料（背景情報。動かすだけなら不要）。 |
| `archive/` | 廃止済み・参考用コンポーネント（例: 旧 `web/` ロビー。`ui/` に置換）。orchestration からは未参照。 |

## ドキュメント

詳しい資料は `docs/` 配下にあります（各ファイルは英語 `.md` と日本語 `.ja.md` の対）：

- [docs/SYSTEM.ja.md](docs/SYSTEM.ja.md) — 全体図 + 各コンポーネントの動かし方
- [docs/METHODOLOGY.ja.md](docs/METHODOLOGY.ja.md) — 研究設計（6条件）+ 検証済みの引用
- [docs/VERIFICATION.ja.md](docs/VERIFICATION.ja.md) — なぜ人狼サーバでHiddenBenchを動かせないか
- [docs/EXEMPLARS.ja.md](docs/EXEMPLARS.ja.md) — 手本スロットの作り方
- [docs/PROMPTS.ja.md](docs/PROMPTS.ja.md) — エージェントのプロンプトのファイル管理

`docs/` は**システム全体**を扱います。vendored スナップショットに同梱されるコンポーネント内部の
ドキュメントは各コンポーネント直下に置かれます（例: `agent/doc/`・`agent/ARCHITECTURE.md` は
agent 内部、`server/*/doc/`）。迷ったら `docs/` から。

## 用意するもの

- Docker と Docker Compose。ローカルで動かす場合は [`uv`](https://docs.astral.sh/uv/) と Python 3.11以上、人狼サーバを使うなら Go 1.24以上。
- LLMプロバイダのAPIキー（OpenAI / Anthropic / Google）。および/または手元の **vLLM** か Ollama サーバ。既定の議論モデルは vLLM 配信の Gemma（キー不要）、生成は既定 Claude・judge は既定 GPT（こちらはキーが必要）。

## 設定

```bash
cp .env.example .env
```

`.env` を開いて、最低限つぎの3つを設定します。

- `LANG_CODE` — 言語（`en` または `jp`）。両環境に適用される。
- `CONDITION` — 手本注入のプリセット（`baseline` ほか。詳細は `config/conditions.yml`）。
- `OPENAI_API_KEY` など — 使うプロバイダのAPIキー。

### モデル — どのプロバイダでも可。既定は3系列分離

各コンポーネントは独立に LLM を選べ、**どのプロバイダ/モデルでも動きます**（Anthropic / OpenAI /
Google、または **vLLM・Ollama が OpenAI 互換エンドポイントで配信する任意のモデル**）。同梱の既定値は
`docs/METHODOLOGY.md` の3系列分離（L3）に従います。

| 役割 | 既定 | 設定場所 | 差し替え |
|------|------|----------|----------|
| 手本生成 | **Claude**（`claude-opus-4-8`） | `generator/config/generator.yml` | `provider:`（＋`base_url:`） |
| 議論エージェント | **vLLM 配信の Gemma 上位**（`google/gemma-2-27b-it` @ `localhost:8000/v1`） | `agent/<env>/config/config.multi_turn.<lang>.yml` の `llm.type` ＋ `vllm:` セクション | `llm.type:` ＋ 対応する provider セクション |
| LLM judge | **GPT**（`gpt-4o`） | `eval/config/judge.yml` | `provider:`（＋`base_url:`） |

3コンポーネントとも**設定方法は共通**です。バックエンドは **`provider`** で選び、**`model` /
`temperature` / `base_url` / `api_key_env`** で設定します（どのキーも全コンポーネントで同じ意味）。
provider 語彙も共通: **`vllm` / `openai` / `ollama` / `google` / `anthropic`**（generator・judge は
`mock` も）。generator と judge はこれらをトップレベルに、agent は `llm:` 直下に書きます（agent は加えて
`vllm:`/`openai:` などのプロバイダ別セクションや `llm.talk`/`llm.action` のロール別指定という拡張を
持ちます）。議論エージェントの既定は `llm.provider: vllm`（モデル名とエンドポイントは `vllm:` セクション）。
`llm.provider` を変えるだけで別バックエンドへ切替。vLLM/Ollama は APIキー不要（プレースホルダ使用）、
それ以外は `api_key_env` がプロバイダ既定（`OPENAI_API_KEY` / `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`）に
なります。

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

## 手本スロットを生成する

6つの条件（`docs/METHODOLOGY.md` 参照）が注入する手本は**空の状態**で同梱されています。
`generator/` は Claude（既定の生成器系列。`config/generator.yml` で任意のプロバイダ/モデルに変更可）を呼び出してこれを生成し、人手レビュー前提の下書きとして
`agent/<env>/exemplars/<lang>/{scripts,utterances,analysis}/` に書き出します。

```bash
cd generator && uv sync
uv run src/main.py --dry-run          # プロンプトのレンダリングのみ（API呼び出し・書き込みなし）
uv run src/main.py                    # 生成（config/generator.yml とルートの .env を読む）
```

1例につき Claude を**2回**呼びます。1回は全文台本（⑤）、もう1回はトピック非依存の分析（②）。
単発発話 few-shot（③）は別プロンプトで生成せず、同じ台本から**スライス**します。これにより③と⑤の
違いは「提示形式」だけになり、中身は同一ソース由来のため「不公平」と言われません。漏洩対策(L1)は機械的に
担保します（HiddenBench は評価スライス外のタスクから生成、人狼は生成専用シードを使用）。分析プロンプトは
L2（トピック非依存・答え・選択肢名・固有名詞の除去）を強制します。`config/generator.yml` の
`provider: mock` にすると、API予算を使わずにパイプラインをオフライン検証できます。

## 評価する

```bash
cd eval && uv sync && cd ..    # eval 用 venv を一度だけ作成
make eval        # 客観指標: log/hidden-bench/results/ を読み results/eval/report.md と metrics.json を生成
make judge       # 客観 + 主観LLM-judge を一括（判定モデルは eval/config/judge.yml）
```

レポートは condition ごとに集計されるので、複数の条件で回せばそのまま比較表になります。judge の既定は GPT ですが、任意のプロバイダ/モデルに変更可（上のモデル表・`eval/config/judge.yml` 参照）。

## ログ

実行ログはすべて**リポジトリ直下の単一 `log/` ツリー**に集約されます（**ローカルでも Docker でも同じ場所**）。ブラウザUI（`ui/`）で実行したゲームだけ `web/` サブフォルダに分かれます。

```
log/
  aiwolf/
    json/  game/  realtime/  match_optimizer.json   # 人狼のゲーム記録（サーバ）
    agents/<タイムスタンプ>/                          # エージェントログ + cost_summary.json/.md
    web/                                             # ブラウザUI実行分のみ
      json/  game/  realtime/   agents/<タイムスタンプ>/
  hidden-bench/
    results/*.json                                   # HiddenBench のゲーム結果（サーバ）
    results/eval/{report.md,metrics.json}            # 評価出力
    agents/<タイムスタンプ>/
    web/
      results/*.json   agents/<タイムスタンプ>/
```

出力先は2つの環境変数で決まり、オーケストレータが自動設定します：`LOG_ROOT`（リポジト直下 `log/`。`run_local.sh`・Docker Compose・UI が設定）と `LOG_SCOPE`（通常は空、UI は `web`）。`LOG_ROOT` を変えればツリー全体を移設できます。`log/` は git 管理外です。

## 人間が参加する（ブラウザUI）

`ui/` を使います。人狼・HiddenBench の人間プレイ用フルブラウザUIで、AI席は launcher 経由で自動起動し、人間が1席を担当できます。

```bash
cd ui && make up        # サーバ・エージェント・ロビーをまとめてビルド＆起動
# その後 http://localhost/hidden-bench （人狼は /demo）を開く
```

設定は `ui/` 側（`ui/.env`・`ui/Makefile`）を参照。旧 `web/` ロビーは `archive/web/` に退避済み。

## 動作の流れ

1. サーバ（人狼またはHiddenBench）が起動し、必要な人数のエージェントが揃うのを待つ。
2. ランチャが、選んだ環境・言語・条件に合わせてエージェント設定を組み立て、エージェントを起動する。エージェントはWebSocketでサーバにつなぐ。
3. サーバがゲーム／タスクを進め、エージェントは各リクエストに対し設定したLLMで応答する。
4. サーバがゲームごとの結果を書き出し、`eval/` がそれを指標へ変換する。

## 補足

- `server/aiwolf/` と `agent/` は外部リポジトリのスナップショットを取り込んだものです。共通パケットライブラリ `aiwolf-nlp-common` は同梱せず、PyPI（`==0.7.0`）から入れます。
- 手本スロット（`agent/<環境>/exemplars/`）は空の状態で同梱しています。ファイルを置くまでは、`baseline` 以外の条件を選んでも自動的に `baseline` と同じ挙動になります。
- `.env`・仮想環境・`log/` は Git の管理対象外です。実際のAPIキーは絶対にコミットしないでください。
