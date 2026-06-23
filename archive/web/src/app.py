"""Minimal web lobby: a human plays one HiddenBench seat in the browser.

最小Webロビー: 人間がブラウザでHiddenBenchの1席をプレイする.

Purpose: collect human (and human↔LLM) discussion data with the SAME faithful protocol
the LLM agents use — the lobby is just another agent client to hiddenbench-server, so the
server needs no changes. Fill the other seats with LLM agents (run the agent launcher
pointing at the same server) or with more human browsers.

目的: LLMエージェントと同一の忠実プロトコルで人間の議論データを集める. ロビーは
hiddenbench-server への単なるエージェントクライアントなので, サーバ改変は不要.

Flow per browser session:
  browser --{join,name}--> lobby --WS--> hiddenbench-server
  server --NAME-->        lobby sends the name
  server --INITIALIZE-->  lobby shows clues+options; human clicks ready; lobby acks
  server --TALK(pre)-->   lobby shows options; human picks; lobby sends JSON vote
  server --TALK(disc)-->  lobby shows transcript; human types; lobby sends text
  server --TALK(post)-->  lobby shows options+transcript; human picks; lobby sends JSON
  server --FINISH-->      lobby shows done; logs the human transcript
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("web")

HB_URL = os.environ.get("HB_URL", "ws://127.0.0.1:8090/ws")
LOG_DIR = Path(os.environ.get("HUMAN_LOG_DIR", str(Path(__file__).resolve().parent.parent / "log" / "human")))
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="discussion-bench HiddenBench human lobby")


@app.get("/")
async def index() -> HTMLResponse:
    """Serve the single-page bilingual UI / 日英1ページUIを返す."""
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


async def _browser_recv(ws: WebSocket, queue: asyncio.Queue[dict[str, Any]]) -> None:
    """Pump browser messages into a queue / ブラウザのメッセージをキューへ流す."""
    try:
        while True:
            data = await ws.receive_text()
            await queue.put(json.loads(data))
    except WebSocketDisconnect:
        await queue.put({"type": "_disconnect"})


async def _await_reply(queue: asyncio.Queue[dict[str, Any]], want: str) -> dict[str, Any]:
    """Wait for a browser message of a given type / 指定typeのブラウザ応答を待つ."""
    while True:
        msg = await queue.get()
        if msg.get("type") == "_disconnect":
            raise WebSocketDisconnect(code=1000)
        if msg.get("type") == want:
            return msg


@app.websocket("/play")
async def play(ws: WebSocket) -> None:
    """Bridge one browser human to one hiddenbench-server seat / 1席分の橋渡し."""
    await ws.accept()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    pump = asyncio.create_task(_browser_recv(ws, queue))
    transcript_log: list[dict[str, Any]] = []
    name = "human"
    try:
        join = await _await_reply(queue, "join")
        name = str(join.get("name") or "human")
        async with websockets.connect(HB_URL, max_size=None, ping_interval=None) as server:
            while True:
                raw = await server.recv()
                pkt = json.loads(raw if isinstance(raw, str) else bytes(raw).decode("utf-8"))
                req = pkt.get("request")
                info = pkt.get("info") or {}
                payload = json.loads(info["profile"]) if info.get("profile") else {}

                if req == "NAME":
                    await server.send(name)
                    continue
                if req == "FINISH":
                    await ws.send_text(json.dumps({"type": "finish"}))
                    break
                if req == "INITIALIZE":
                    await ws.send_text(json.dumps({"type": "init", "name": name, "payload": payload}))
                    await _await_reply(queue, "ready")
                    await server.send("Understood.")
                    continue
                if req == "TALK":
                    phase = payload.get("phase", "discussion")
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "prompt",
                                "phase": phase,
                                "payload": payload,
                                "transcript": pkt.get("talk_history") or [],
                            },
                        ),
                    )
                    reply = await _await_reply(queue, "reply")
                    value = str(reply.get("value", ""))
                    if phase in ("pre", "post"):
                        option = str(reply.get("option", value))
                        out = json.dumps({"vote": option, "rationale": value})
                        transcript_log.append({"phase": phase, "option": option, "rationale": value})
                        await server.send(out)
                    else:
                        transcript_log.append({"phase": "discussion", "text": value})
                        await server.send(value)
                    continue
    except (WebSocketDisconnect, websockets.exceptions.WebSocketException) as exc:
        logger.info("session ended (%s): %s", name, exc)
    finally:
        pump.cancel()
        _persist(name, transcript_log)


def _persist(name: str, transcript: list[dict[str, Any]]) -> None:
    """Persist a human session transcript for data collection / 人間ログを保存."""
    if not transcript:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    idx = len(list(LOG_DIR.glob("*.json")))
    path = LOG_DIR / f"human-{name}-{idx:04d}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump({"name": name, "transcript": transcript}, f, ensure_ascii=False, indent=2)
    logger.info("saved human transcript -> %s", path)


# Optional static mount (favicon etc.) / 任意の静的マウント.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
