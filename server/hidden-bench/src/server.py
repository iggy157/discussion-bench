"""HiddenBench WebSocket game server.

HiddenBench WebSocketゲームサーバ.

Hosts the faithful HiddenBench protocol (see game.py) for agent clients that speak the
aiwolf-nlp-common wire protocol. For each task it waits for ``agent_count`` connections
(a table), runs one game, sends FINISH, then closes — agents reconnect for the next task
(mirroring how the werewolf server cycles games).

aiwolf-nlp-commonのワイヤプロトコルを話すエージェント向けに, HiddenBenchを忠実にホストする.
タスクごとに agent_count 接続を待ち, 1ゲーム実行 → FINISH → 切断. エージェントは次タスクで再接続する.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import websockets
import yaml

from game import AgentConn, run_game
from task import load_tasks, resolve_benchmark_path, select_tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("hiddenbench.server")

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "hiddenbench.yml"


def load_config(path: Path) -> dict[str, Any]:
    """Load the server YAML config, then apply root-.env overrides / YAML読込+env上書き.

    The central root .env (via compose / run_local) can steer the server so "one config
    controls everything": HB_LANG -> lang, CONDITION -> condition, HB_TASK_LIMIT -> task_limit,
    HB_TOTAL_ROUNDS -> total_rounds. Unset env vars leave the YAML value untouched.
    中央 .env で lang/condition/task_limit/total_rounds を上書きできる (未設定ならYAML値).
    """
    with Path(path).open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    _env_override(config, "lang", "HB_LANG", str)
    _env_override(config, "condition", "CONDITION", str)
    _env_override(config, "task_limit", "HB_TASK_LIMIT", int)
    _env_override(config, "total_rounds", "HB_TOTAL_ROUNDS", int)
    _env_override(config, "port", "HB_PORT", int)  # per-worker port for parallel runs
    # Per-action wait limits. The densest tasks (long per-agent info) generate slowly at high
    # rounds; under load a single talk can exceed the default 120s reply window and the server
    # drops the game. Raising these only lets slow generations finish (model/decoding unchanged,
    # so per-game quality is identical) — important for long-context production runs.
    _env_override(config, "response_timeout_ms", "HB_RESP_TIMEOUT_MS", int)
    _env_override(config, "action_timeout_ms", "HB_ACTION_TIMEOUT_MS", int)
    # HB_TASK_IDS: comma-separated explicit task ids (e.g. "1,2,3"). Takes precedence over
    # task_limit. Lets an orchestrator run one specific task per server launch.
    task_ids_env = os.environ.get("HB_TASK_IDS")
    if task_ids_env:
        config["task_ids"] = [int(x) for x in task_ids_env.split(",") if x.strip()]
    _apply_log_root(config)
    return config


def _apply_log_root(config: dict[str, Any]) -> None:
    """Centralize results under one tree when LOG_ROOT is set by the orchestrator.

    LOG_ROOT が設定されていれば結果の出力先を一元化する。
    Layout: ``<LOG_ROOT>/hidden-bench[/<LOG_SCOPE>]/results`` — LOG_SCOPE is empty for
    local/docker and ``web`` for the browser-UI stack, so local and Docker share one location
    while web games go into a sub-folder.
    """
    log_root = os.environ.get("LOG_ROOT")
    if not log_root:
        return
    scope = os.environ.get("LOG_SCOPE", "")
    config["output_dir"] = str(Path(log_root) / "hidden-bench" / scope / "results")


def _env_override(config: dict[str, Any], key: str, env: str, cast: Any) -> None:
    """Override config[key] from os.environ[env] if set / 環境変数があれば上書き."""
    val = os.environ.get(env)
    if val is not None and val != "":
        config[key] = cast(val)


class Matchmaker:
    """Collects connections into fixed-size tables / 接続を固定人数の卓に集める."""

    def __init__(self, agent_count: int) -> None:
        self.agent_count = agent_count
        self.queue: asyncio.Queue[tuple[str, Any, asyncio.Event]] = asyncio.Queue()

    async def add(self, name: str, ws: Any, done: asyncio.Event) -> None:
        await self.queue.put((name, ws, done))

    async def next_table(self) -> list[tuple[str, Any, asyncio.Event]]:
        members: list[tuple[str, Any, asyncio.Event]] = []
        while len(members) < self.agent_count:
            members.append(await self.queue.get())
        return members


async def _ws_send_recv(ws: Any, response_timeout_s: float, packet: str) -> str:
    """Send one packet and await one text reply (newline-trimmed) / 1送信1受信."""
    await ws.send(packet)
    reply = await asyncio.wait_for(ws.recv(), timeout=response_timeout_s)
    if isinstance(reply, (bytes, bytearray)):
        reply = bytes(reply).decode("utf-8")
    return str(reply).strip()


async def handler(ws: Any, matchmaker: Matchmaker, response_timeout_s: float) -> None:
    """Per-connection handler: NAME handshake, then park until the game finishes.

    接続ごとのハンドラ: NAMEハンドシェイク後, ゲーム終了までブロックして接続を保持する.
    """
    try:
        name = await _ws_send_recv(ws, response_timeout_s, json.dumps({"request": "NAME"}))
    except (TimeoutError, websockets.exceptions.WebSocketException):
        logger.warning("NAME handshake failed; dropping connection")
        return
    name = name or f"agent-{id(ws) % 10000}"
    done = asyncio.Event()
    await matchmaker.add(name, ws, done)
    logger.info("agent %s connected and queued", name)
    # Keep the websocket coroutine alive while the game loop drives this socket.
    await done.wait()


def _write_result(out_dir: Path, result: Any) -> Path:
    """Persist a GameResult as JSON for the metrics module / 結果をJSON保存."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.game_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(result.__dict__, f, ensure_ascii=False, indent=2)
    return path


async def game_loop(config: dict[str, Any], matchmaker: Matchmaker) -> None:
    """Drive tasks sequentially, one table per game / タスクを逐次に1卓ずつ実行する."""
    base = Path(__file__).resolve().parent.parent
    data_dir = base / str(config.get("data_dir", "data"))
    lang = str(config.get("lang", "en"))
    total_rounds = int(config.get("total_rounds", 15))
    agent_count = int(config.get("agent_count", 4))
    condition = str(config.get("condition", "baseline"))
    seed = int(config.get("seed", 42))
    action_timeout_ms = int(config.get("action_timeout_ms", 60000))
    response_timeout_ms = int(config.get("response_timeout_ms", 120000))
    response_timeout_s = response_timeout_ms / 1000.0
    out_dir = base / str(config.get("output_dir", "log/results"))
    game_count = config.get("game_count")
    repeats = int(config.get("repeats_per_task", 1))

    tasks = load_tasks(resolve_benchmark_path(data_dir, lang))
    tasks = select_tasks(tasks, config.get("task_ids"), config.get("task_limit"))
    if game_count is not None:
        tasks = tasks[: int(game_count)]
    logger.info("loaded %d task(s), lang=%s, condition=%s, rounds=%d", len(tasks), lang, condition, total_rounds)

    game_no = 0
    for task in tasks:
        for rep in range(repeats):
            members = await matchmaker.next_table()
            names = [m[0] for m in members]
            game_id = f"hb-{task.id:03d}-r{rep}-{game_no:04d}"
            logger.info("starting game %s task=%s agents=%s", game_id, task.id, names)
            conns = [
                AgentConn(
                    name=name,
                    index=i,
                    send_recv=_bind_send_recv(ws, response_timeout_s),
                    send=_bind_send(ws),
                )
                for i, (name, ws, _done) in enumerate(members)
            ]
            try:
                result = await run_game(
                    task=task,
                    conns=conns,
                    game_id=game_id,
                    total_rounds=total_rounds,
                    lang=lang,
                    condition=condition,
                    seed=seed + rep,
                    action_timeout_ms=action_timeout_ms,
                    response_timeout_ms=response_timeout_ms,
                )
                path = _write_result(out_dir, result)
                logger.info(
                    "game %s done: pre=%.2f post=%.2f gain=%+.2f -> %s",
                    game_id,
                    result.pre_accuracy,
                    result.post_accuracy,
                    result.integration_gain,
                    path,
                )
            except Exception:
                logger.exception("game %s failed", game_id)
            finally:
                for _name, ws, done in members:
                    done.set()
                    with _suppress():
                        await ws.close()
            game_no += 1
    logger.info("all games complete (%d)", game_no)


def _bind_send_recv(ws: Any, response_timeout_s: float):
    """Return a coroutine fn bound to one websocket / 1socketに束縛した送受信関数を返す."""

    async def _fn(packet: str) -> str:
        return await _ws_send_recv(ws, response_timeout_s, packet)

    return _fn


def _bind_send(ws: Any):
    """Return a fire-and-forget send coroutine bound to one websocket / 送信専用関数."""

    async def _fn(packet: str) -> None:
        await ws.send(packet)

    return _fn


class _suppress:
    """Tiny async context manager that swallows exceptions / 例外を握り潰す簡易CM."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return True


async def main_async(config: dict[str, Any]) -> None:
    """Start the server and the game loop / サーバとゲームループを起動する."""
    host = str(config.get("host", "0.0.0.0"))
    port = int(config.get("port", 8090))
    agent_count = int(config.get("agent_count", 4))
    response_timeout_s = int(config.get("response_timeout_ms", 120000)) / 1000.0
    matchmaker = Matchmaker(agent_count)

    async def _handler(ws: Any) -> None:
        await handler(ws, matchmaker, response_timeout_s)

    logger.info("HiddenBench server listening on ws://%s:%d/ws (agent_count=%d)", host, port, agent_count)
    async with websockets.serve(_handler, host, port, max_size=None, ping_interval=None):
        await game_loop(config, matchmaker)


def main() -> None:
    """CLI entry point / CLIエントリポイント."""
    parser = argparse.ArgumentParser(description="HiddenBench WebSocket game server")
    parser.add_argument("-c", "--config", type=str, default=str(DEFAULT_CONFIG), help="server config YAML")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    asyncio.run(main_async(config))


if __name__ == "__main__":
    main()
