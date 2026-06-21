"""Faithful HiddenBench discussion protocol over the WebSocket connections.

WebSocket接続上で動くHiddenBench議論プロトコルの忠実実装.

Protocol (Li, Naito & Shirado, arXiv:2505.11556 §4.2):
  1. Pre-discussion: each agent individually returns {"vote","rationale"} (Y^pre).
  2. Discussion: fixed T rounds (default 15), sequential turn order; every agent always
     sees the full prior transcript (round 1 is sequential; later rounds each respond
     after seeing all others) — guaranteed here because we pass the growing talk_history
     and elicit agents strictly in order.  NO early stopping (paper runs fixed T; the
     consensus early-stop in the jonradoff repo is an implementation extra and is NOT
     enabled by default here).
  3. Post-discussion: each agent returns {"vote","rationale"} (Y^post).
Scoring: average-rule and majority-rule accuracy, integration gain = post - pre.

プロトコルは論文§4.2に忠実: 事前個別回答 → 固定Tラウンド逐次議論 (早期終了なし) → 事後個別回答.
採点は平均/多数決正答率と統合ゲイン (post-pre).
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable

from answer import Decision, average_accuracy, extract_decision, majority_correct
from protocol import finish_packet, initialize_packet, make_talk, talk_packet
from task import Task

logger = logging.getLogger("hiddenbench.game")

# A connection abstraction: send a JSON string, await the agent's text reply.
# 接続の抽象: JSON文字列を送り, エージェントのテキスト応答を待つ.
SendRecv = Callable[[str], Awaitable[str]]


SendOnly = Callable[[str], Awaitable[None]]


@dataclass
class AgentConn:
    """One connected agent / 接続済みエージェント1体.

    Attributes:
        name: Agent name returned at the NAME handshake / NAMEで返された名前.
        index: 0-based seat index / 0始まりの席インデックス.
        send_recv: Coroutine to send a packet and await the reply / 送受信コルーチン.
        send: Fire-and-forget send (used for FINISH, which gets no reply) /
            応答を待たない送信 (FINISH用; FINISHには返信が来ない).
    """

    name: str
    index: int
    send_recv: SendRecv
    send: SendOnly | None = None


@dataclass
class GameResult:
    """The full record of one HiddenBench game / 1ゲームの完全な記録."""

    game_id: str
    task_id: int
    task_name: str
    correct_answer: str
    lang: str
    condition: str
    num_agents: int
    total_rounds: int
    agent_names: list[str]
    clues_by_agent: dict[str, list[str]]
    pre_decisions: dict[str, dict[str, Any]]
    post_decisions: dict[str, dict[str, Any]]
    transcript: list[dict[str, Any]]
    pre_accuracy: float
    post_accuracy: float
    pre_majority_correct: bool
    post_majority_correct: bool
    integration_gain: float
    metadata: dict[str, Any] = field(default_factory=dict)


def _base_payload(task: Task, conn: AgentConn, *, num_agents: int, total_rounds: int, lang: str, seed: int) -> dict[str, Any]:
    """Static per-agent HiddenBench context carried in info.profile.

    info.profileに載せる各エージェント静的文脈 (手がかり・選択肢・説明).
    """
    return {
        "hb": True,
        "lang": lang,
        "task_id": task.id,
        "description": task.description,
        "options": task.possible_answers,
        "clues": task.agent_clues(conn.index, num_agents, seed),
        "agent_index": conn.index,
        "num_agents": num_agents,
        "total_rounds": total_rounds,
    }


async def run_game(
    *,
    task: Task,
    conns: list[AgentConn],
    game_id: str,
    total_rounds: int,
    lang: str,
    condition: str,
    seed: int,
    action_timeout_ms: int,
    response_timeout_ms: int,
) -> GameResult:
    """Run one faithful HiddenBench game and return its full record.

    1ゲームを忠実に実行し, 完全な記録を返す.
    """
    num_agents = len(conns)
    agent_names = [c.name for c in conns]
    payloads = {
        c.name: _base_payload(task, c, num_agents=num_agents, total_rounds=total_rounds, lang=lang, seed=seed)
        for c in conns
    }
    clues_by_agent = {c.name: payloads[c.name]["clues"] for c in conns}

    def _talk(conn: AgentConn, payload: dict[str, Any], history: list[dict[str, Any]], remain: int) -> str:
        return talk_packet(
            game_id=game_id,
            day=int(payload.get("round", 0)),
            agent=conn.name,
            agent_names=agent_names,
            payload=payload,
            talk_history=history,
            remain_count=remain,
            agent_count=num_agents,
            action_timeout_ms=action_timeout_ms,
            response_timeout_ms=response_timeout_ms,
        )

    # ---- INITIALIZE: deliver clues; agents acknowledge (reply discarded) ----
    for conn in conns:
        pkt = initialize_packet(
            game_id=game_id,
            agent=conn.name,
            agent_names=agent_names,
            payload={**payloads[conn.name], "phase": "init"},
            agent_count=num_agents,
            action_timeout_ms=action_timeout_ms,
            response_timeout_ms=response_timeout_ms,
        )
        await conn.send_recv(pkt)

    # ---- PRE-DISCUSSION: individual decision (Y^pre) ----
    pre_decisions: dict[str, Decision] = {}
    for conn in conns:
        payload = {**payloads[conn.name], "phase": "pre"}
        reply = await conn.send_recv(_talk(conn, payload, [], remain=0))
        pre_decisions[conn.name] = extract_decision(reply, task.possible_answers)
        logger.info("[pre] %s -> %s", conn.name, pre_decisions[conn.name].option)

    # ---- DISCUSSION: fixed T rounds, sequential, full history, no early stop ----
    transcript: list[dict[str, Any]] = []
    idx = 0
    for rnd in range(total_rounds):
        for turn, conn in enumerate(conns):
            payload = {**payloads[conn.name], "phase": "discussion", "round": rnd}
            remain = (total_rounds - rnd) * num_agents - turn
            reply = await conn.send_recv(_talk(conn, payload, list(transcript), remain=remain))
            text = (reply or "").strip()
            entry = make_talk(idx=idx, day=rnd, turn=turn, agent=conn.name, text=text)
            transcript.append(entry)
            idx += 1
        logger.info("[round %d/%d] complete", rnd + 1, total_rounds)

    # ---- POST-DISCUSSION: individual final decision (Y^post) ----
    post_decisions: dict[str, Decision] = {}
    for conn in conns:
        payload = {**payloads[conn.name], "phase": "post"}
        reply = await conn.send_recv(_talk(conn, payload, list(transcript), remain=0))
        post_decisions[conn.name] = extract_decision(reply, task.possible_answers)
        logger.info("[post] %s -> %s", conn.name, post_decisions[conn.name].option)

    # ---- FINISH (send-only: agents close on FINISH and do not reply) ----
    for conn in conns:
        pkt = finish_packet(game_id=game_id, agent=conn.name, agent_names=agent_names)
        if conn.send is not None:
            await conn.send(pkt)
        else:  # pragma: no cover - mock conns without a send-only path
            with contextlib.suppress(Exception):
                await conn.send_recv(pkt)

    pre_list = [pre_decisions[c.name] for c in conns]
    post_list = [post_decisions[c.name] for c in conns]
    pre_acc = average_accuracy(pre_list, task.correct_answer)
    post_acc = average_accuracy(post_list, task.correct_answer)

    return GameResult(
        game_id=game_id,
        task_id=task.id,
        task_name=task.name,
        correct_answer=task.correct_answer,
        lang=lang,
        condition=condition,
        num_agents=num_agents,
        total_rounds=total_rounds,
        agent_names=agent_names,
        clues_by_agent=clues_by_agent,
        pre_decisions={n: asdict(d) for n, d in pre_decisions.items()},
        post_decisions={n: asdict(d) for n, d in post_decisions.items()},
        transcript=transcript,
        pre_accuracy=pre_acc,
        post_accuracy=post_acc,
        pre_majority_correct=majority_correct(pre_list, task.correct_answer),
        post_majority_correct=majority_correct(post_list, task.correct_answer),
        integration_gain=post_acc - pre_acc,
        metadata={
            "shared_information": task.shared_information,
            "hidden_information": task.hidden_information,
            "options": task.possible_answers,
        },
    )
