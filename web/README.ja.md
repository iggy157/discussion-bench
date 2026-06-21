<!-- 言語: [English](README.md) | **日本語** -->

# web（人間用ロビー）

人間がブラウザで**HiddenBenchの1席をプレイ**できる最小Webロビー。LLMエージェントと**同一の忠実
プロトコル**で、人間（および人間↔LLM）の議論データを集める。ロビーは `hidden-bench` サーバへの
単なるエージェントクライアントなので、サーバ改変は不要。（より豪華な `ui/` に置き換え済み。最小の
参照用として残している。）

## 仕組み

```
ブラウザ  <--FastAPI WS-->  web  <--WS-->  hidden-bench サーバ
```
ロビーは1エージェントとしてサーバに接続し、NAMEハンドシェイクを行い、各パケットをブラウザへ中継する：
INITIALIZE で手がかり＋選択肢を表示、TALK(pre/post) で選択肢＋理由を要求、TALK(discussion) で
1〜2文の発言を要求、FINISH で終了。各人間セッションのトランスクリプトは `log/human/` に保存される。

## 実行

```bash
uv sync
# 1) HiddenBenchサーバ（4席）と、そこへ接続するLLMエージェント3体を起動
# 2) ロビーを起動（人間が4席目に入る）：
HB_URL=ws://127.0.0.1:8090/ws uv run uvicorn --app-dir src app:app --host 0.0.0.0 --port 8000
# http://localhost:8000 を開く（LAN内ならスマホでも可。遠隔はトンネルで公開）
```

環境変数：`HB_URL`（HiddenBenchサーバのWS URL）、`HUMAN_LOG_DIR`（既定 `log/human`）。

## 注意

- 人間だけのゲームにするには、ロビーを4つのブラウザで開き、サーバの `agent_count: 4` にする
  （ブラウザ1つにつき1席を埋める）。
- UIは二言語（EN/JPラベル併記）。タスク内容の言語はサーバの `lang` に従う（日本語タスクは
  サーバに `benchmark.ja.json` を置く）。
- これは意図的に最小構成（1ページ、認証なし、キューなし）。マッチング・ビューア・人狼対応つきの
  本格UIは `../ui/`（../docs/SYSTEM.ja.md 参照）。

## 構成

```
src/app.py            -- FastAPIブリッジ（ブラウザWS <-> hidden-bench サーバWS）+ セッションログ
src/static/index.html -- 1ページの二言語UI
```
