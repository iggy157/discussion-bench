# web (human lobby)

Minimal web lobby so a **human can play one HiddenBench seat in the browser** — to collect
human (and human↔LLM) discussion data using the **same faithful protocol** the LLM agents
use. The lobby is just another agent client to `hidden-bench server`, so the server needs no
changes.

人間がブラウザで**HiddenBenchの1席をプレイ**できる最小Webロビー。LLMエージェントと
**同一の忠実プロトコル**で人間の議論データを集める。サーバ改変は不要。

## How it works / 仕組み

```
browser  <--FastAPI WS-->  web  <--WS-->  hidden-bench server
```
The lobby connects to the server as one agent, does the NAME handshake, and relays each
packet to the browser: INITIALIZE shows the human their clues+options; TALK(pre/post) asks
for an option + rationale; TALK(discussion) asks for a 1–2 sentence message; FINISH ends.
Each human session transcript is saved under `log/human/` for data collection.

## Run / 実行

```bash
uv sync
# 1) start the HiddenBench server (4 seats) and 3 LLM agents pointing at it
# 2) start the lobby (the human takes the 4th seat):
HB_URL=ws://127.0.0.1:8090/ws uv run uvicorn --app-dir src app:app --host 0.0.0.0 --port 8000
# open http://localhost:8000  (works on a phone over LAN; expose via a tunnel for remote)
```

Env: `HB_URL` (HiddenBench server WS URL), `HUMAN_LOG_DIR` (default `log/human`).

## Notes / 注意

- For an all-human game, open the lobby in 4 browsers and set the server `agent_count: 4`
  (the lobby fills one seat per browser).
- The UI is bilingual (EN/JP labels inline). Task content language follows the server's
  `lang` (drop a `benchmark.ja.json` into the server for Japanese tasks).
- This is intentionally minimal (single page, no auth, no queue). For a public,
  multi-table, QR-code deployment, fold it into the aiwolf-nlp-demo lobby/Caddy stack
  later (see ../SYSTEM.md).

## Layout / 構成

```
src/app.py            -- FastAPI bridge (browser WS <-> hidden-bench server WS) + session logging
src/static/index.html -- single-page bilingual UI
```
