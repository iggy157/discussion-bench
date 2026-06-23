<!-- 言語: [English](SYSTEM.md) | **日本語** -->

# システム全体像

このドキュメントは、本システムが「何を・どういう作りで実現しているか」を上から順に追える地図です。
個々の使い方は [README](../README.ja.md) に、研究上の設計判断は
[METHODOLOGY.md](METHODOLOGY.ja.md) と [VERIFICATION.md](VERIFICATION.ja.md) に
それぞれ譲り、ここでは全体のかたちを掴むことに集中します。

## 一言でいうと

複数のLLMエージェントに議論をさせ、その様子を評価するためのプラットフォームです。議論の場は
2種類用意してあります。ひとつは社会的推理の対話ゲームである**人狼**（AIWolfDialプロトコル、5人）、
もうひとつは手がかりを分担して持ち寄り正解を導く**HiddenBench**（協調推論、4人）です。重要なのは、
この2つをまったく同じ1つのエージェントがプレイするという点です。操作はすべてリポジトリ直下に
集約されており、片方だけでも両方同時でも起動できます。

## なぜこういう作りなのか

人狼とHiddenBenchは、議論のルールも進め方もまるで違うゲームです。素朴に考えると環境ごとに別々の
エージェントを用意したくなりますが、それでは「同じ条件で比べた」と言えなくなります。そこで本システムは、
**エージェントの中身（プロンプトの組み立て・手本の注入・LLM呼び出し）は2環境で完全に共有し、
ゲームの進行ルールだけを環境ごとに分ける**という方針を取っています。

言い換えると、公平性は「2つのゲームの仕組みを無理やり揃えること」ではなく、「介入する部分（エージェント側）と
評価する部分（トランスクリプトの指標）を揃えること」で担保しています。各ゲームは、それぞれのコミュニティで
標準とされる進め方に忠実に従います。この考え方の詳細は方法論ドキュメントにまとめてあります。

## 構成要素

リポジトリ直下が操作の起点（制御面）で、`.env`・`config/`・`docker-compose.yml`・`Makefile`・
`launcher/` がここに置かれています。その下に、役割ごとの部品がぶら下がります。

| パス | 役割 |
|------|------|
| [../agent/](../agent/) | 両環境をプレイする**共有エージェント**。`src/` が頭脳本体（HiddenBench対応の `src/agent/hiddenbench.py` を含む）、`aiwolf/`・`hidden-bench/` が環境ごとの設定と手本スロット。 |
| [../server/aiwolf/](../server/aiwolf/) | 人狼（AIWolfDial）ゲームサーバ（Go）。外部リポジトリを**無改造**で取り込み。 |
| [../server/hidden-bench/](../server/hidden-bench/) | HiddenBenchサーバ（Python）。4エージェント・T=15ラウンド固定・事前/事後回答・採点までを忠実に実装。 |
| [../eval/](../eval/) | トランスクリプトから失敗様態の指標を計算し、日英レポートを出力。 |
| [../ui/](../ui/) | ブラウザUI（aiwolf-nlp-demo 由来）。人狼・HiddenBench の人間プレイ。AI席は launcher 経由で起動。 |
| [../archive/](../archive/) | 廃止済み・参考用コンポーネント（例: 旧 `web/` ロビー。`ui/` に置換）。orchestration からは未参照。 |
| [../launcher/](../launcher/) | 環境・条件・言語を受け取り、エージェント設定を組み立てて起動する。 |
| [../docker-compose.yml](../docker-compose.yml) | 2環境を profiles（`aiwolf` / `hiddenbench`）として定義。片方でも両方でも起動できる。 |

## 1つのエージェントが両環境を動かせる理由

鍵になるのは、HiddenBenchサーバが**新しい通信規約を一切持ち込んでいない**点です。共有パケット
ライブラリ `aiwolf-nlp-common`（0.7.0）に元からある NAME / INITIALIZE / TALK / FINISH の4種類だけで
やり取りします。HiddenBench固有の文脈（いまが事前回答か議論か事後回答か、手がかり、選択肢、ラウンド番号）は、
パケットの `info.profile` フィールドにJSONとして同梱して運びます。

エージェント側の `HiddenBenchAgent` はこのJSONを読み取り、標準のTALKリクエストを場面ごとのプロンプト
（`hb_pre` / `hb_discussion` / `hb_post`）に振り分けます。逐次のターン順は、サーバが1体ずつ順番に発話を
引き出し、それまでの全発言を渡していくことで自然に守られます（HiddenBench論文 §4.2 に忠実）。そして
手本（台本・分析）の注入は、人狼のときと**まったく同じコード経路**（`_feed_scenario_chunk()`）を通ります。
これが「同じエージェントで両環境」を成立させている仕組みです。

## 動かし方（リポジトリ直下で実行）

```bash
cp .env.example .env          # OPENAI_API_KEY 等・LANG_CODE・CONDITION を設定

# Docker — 両環境同時
docker compose --profile aiwolf --profile hiddenbench up --build
#   make both | make hiddenbench | make aiwolf でも可

# ローカル（Dockerなし）
cd agent && uv sync && cd ..
make local-hb                 # HiddenBenchサーバ + 4エージェント

# 評価
make eval                     # -> log/hidden-bench/results/eval/report.md

# 人間によるデータ収集（ブラウザUI）
cd ui && make up
# その後 http://localhost/hidden-bench を開いて人間が1席を担当（人狼は /demo）
```

## 各コンポーネントを単体で動かす

各コンポーネントは単体でも動かせます（以前は各ディレクトリのREADMEにあった内容）：

- **HiddenBenchサーバ**（`server/hidden-bench`）：`uv run src/server.py -c config/hiddenbench.yml`。
  エージェントは `ws://<host>:8090/ws` に接続。設定項目（`agent_count`・`total_rounds`・
  `task_ids`/`task_limit`・`seed`・`output_dir`）は `config/hiddenbench.yml` にコメントで記載。
  LLM不要のスモークテスト：サーバ起動後に `python tests/stub_agent.py ws://127.0.0.1:8090/ws P1` を×4。
- **評価**（`eval`）：`make eval`（客観のみ・API不要）/ `make judge`（客観＋主観LLM-judge）。判定モデルは
  `eval/config/judge.yml`、判定プロンプトは `eval/prompts/judge.{en,ja}.txt`。人狼は先に
  `eval/src/werewolf_adapter.py` でログ変換。指標の出典は [METHODOLOGY.ja.md](METHODOLOGY.ja.md) §客観評価。
- **UI**（`ui`）：`cd ui && docker compose up --build` → `/demo` と `/hidden-bench`。composeを使わない
  ローカル開発では `server/aiwolf`（`go run .`）・ロビー（`uvicorn main:app`）・ビューア（`pnpm dev`）を個別に起動。
  SvelteKitフロントは本リポジトリではブラウザ未検証。
- **archive**（`archive/web`）：旧・最小のHiddenBenchロビー。`ui/` に置き換え済みで `archive/` に退避（参照用。orchestration からは未参照）。

## いまの状態

サーバ・エージェントのHiddenBench対応・指標計算・ランチャ・compose・ブラウザUIは、いずれも構築済みで
スモークテストも通っています（サーバと実クライアントの結合、忠実なトランスクリプト生成、採点、評価レポート
までを確認済み）。

一方で、手本スロット（`agent/<環境>/exemplars/`）は**意図的に空**のままにしてあります。台本・発話例・分析を
あとから置く前提で、それまでは `baseline` 以外の条件を選んでも自動的に `baseline` と同じ挙動になります。実際に
LLMエージェントを動かすにはプロバイダのAPIキー（またはローカルの vLLM / Ollama 配信の Gemma）が必要です。実験設計として
残っている検討事項（人狼の本番プロトコル、主観評価の尺度、Gemmaのサイズ）は方法論ドキュメントの末尾に
まとめてあります。
