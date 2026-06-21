<!-- 言語: [English](README.md) | **日本語** -->

# hidden-bench サーバ

**HiddenBench**（隠れプロファイル協調推論）を忠実に再現した WebSocket ゲームサーバ。
論文 Li, Naito & Shirado（[arXiv:2505.11556](https://arxiv.org/abs/2505.11556)）のプロトコルを
忠実にホストし、共有エージェントが人狼と同じ要領で HiddenBench をプレイできるようにする。

## 忠実性

| 項目 | 値 | 出典 |
|------|----|------|
| エージェント数 | 4 | 論文 §4.2 |
| 議論ラウンド | **固定 T=15**・早期終了なし | 論文 §4.2（jonradoff repo の合意による早期終了は実装独自で、ここでは**無効**） |
| ターン順 | 1巡目は順番、以降は全員の全履歴を見て応答 | 論文 §4.2（`talk_history` を伸ばしつつ順番に発話を引き出して担保） |
| 事前/事後回答 | 各自の `{"vote","rationale"}` JSON | repo `prompts.py` |
| 採点 | 平均/多数決の正答率、統合ゲイン = post−pre | 論文 §3 |
| データ | HuggingFace `YuxuanLi1225/HiddenBench`（`data/benchmark.json`、65タスク） | データカード |

パラダイム・指標は**論文**（Li et al.）、プロンプト文字列のみ**repo**（Radoff）を引く。
`../../docs/METHODOLOGY.ja.md` 参照。

## ワイヤプロトコル

aiwolf-nlp-common 0.7.0 既存のリクエスト型（NAME / INITIALIZE / TALK / FINISH）だけを使う。
HiddenBench の文脈（フェーズ / 手がかり / 選択肢 / ラウンド）は `info.profile` にJSONで載せる。
議論は**従来のTALK request/response**で進めるため、サーバが厳密に逐次ターンを制御できる。
事前回答・各議論ターン・事後回答はすべてTALKで、`payload.phase`（`pre` / `discussion` / `post`）で区別する。

## 実行

```bash
uv sync                                   # または: pip install websockets pyyaml
uv run src/server.py -c config/hiddenbench.yml
# エージェントは ws://<host>:8090/ws へ接続する
```

定型応答スタブでのスモークテスト（LLM不要）：
```bash
uv run src/server.py -c config/hiddenbench.yml &
python tests/stub_agent.py ws://127.0.0.1:8090/ws P1   # ×4（4つのシェル/バックグラウンドで）
```

## 設定（`config/hiddenbench.yml`）

主な項目：`agent_count`（4）、`total_rounds`（15）、`lang`（en/ja）、`condition` ラベル、
`task_ids` / `task_limit`（どのタスクか。手本タスクと**重複させない**＝漏洩対策）、
`repeats_per_task`、`seed`、`output_dir`。

ゲームごとの結果JSON（トランスクリプト・手がかり配分・事前/事後判断・スコア）が `output_dir` に
書き出され、`../../eval` が読み込む。

## 二言語データ

`lang: en` は `data/benchmark.json`（上流の英語）を読む。`lang: ja` は `data/benchmark.ja.json`
があればそれを、無ければ英語にフォールバック。エージェント側の枠組み（system/選択肢の文言）は
エージェントの日英 config で二言語対応。

## 構成

```
src/
  task.py      -- benchmark読込、隠し情報のラウンドロビン配分、各エージェントの手がかり
  protocol.py  -- パケット生成（エージェントクライアント互換の Info/Setting JSON）
  answer.py    -- 寛容なJSON/選択肢抽出 + 平均/多数決採点
  game.py      -- 忠実な3フェーズ進行 + GameResult
  server.py    -- websockets サーバ、卓マッチング、逐次ゲームループ
config/hiddenbench.yml
data/benchmark.json   -- 公式65タスク
tests/stub_agent.py   -- 結合テスト用の定型応答エージェント
```
