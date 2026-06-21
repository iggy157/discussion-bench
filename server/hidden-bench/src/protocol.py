"""Wire-protocol packet builders for the HiddenBench server.

HiddenBenchサーバのワイヤプロトコル・パケット生成.

The HiddenBench server reuses the EXACT packet envelope that the aiwolf-nlp-common
``Client`` parses (``Packet.from_dict``), so that an unmodified agent client can drive
both werewolf and HiddenBench games. We only use request types that already exist in
aiwolf-nlp-common 0.7.0 (NAME / INITIALIZE / TALK / FINISH) — no library changes.

HiddenBench-specific context (phase, clues, options, round) is carried inside the one
free-form string field that survives ``Info.from_dict``: ``info.profile``, as a JSON
string. The agent's HiddenBench adapter parses it.

人狼用エージェントクライアントを無改造で流用するため, aiwolf-nlp-common 0.7.0 に既存の
リクエスト型 (NAME / INITIALIZE / TALK / FINISH) だけを使う. HiddenBench固有の文脈
(フェーズ・手がかり・選択肢・ラウンド) は ``info.profile`` にJSON文字列として載せる.
"""

from __future__ import annotations

import json
from typing import Any


def _setting(agent_count: int, action_timeout_ms: int, response_timeout_ms: int) -> dict[str, Any]:
    """Build a minimal but schema-complete Setting payload / 最小の完全なSettingを構築.

    ``Setting.from_dict`` requires role_num_map + talk/whisper/vote/attack_vote/timeout
    to be present, so we fill them with neutral values. They are unused by HiddenBench.
    """
    return {
        "agent_count": agent_count,
        "max_day": None,
        "role_num_map": {"VILLAGER": agent_count},
        "vote_visibility": True,
        "talk": {
            "max_count": {"per_agent": 1, "per_day": agent_count},
            "max_length": {
                "count_in_word": False,
                "count_spaces": False,
                "per_talk": -1,
                "mention_length": 0,
                "per_agent": -1,
                "base_length": -1,
            },
            "max_skip": 0,
        },
        "whisper": {
            "max_count": {"per_agent": 0, "per_day": 0},
            "max_length": {
                "count_in_word": False,
                "count_spaces": False,
                "per_talk": -1,
                "mention_length": 0,
                "per_agent": -1,
                "base_length": -1,
            },
            "max_skip": 0,
        },
        "vote": {"max_count": 1, "allow_self_vote": True},
        "attack_vote": {"max_count": 0, "allow_self_vote": False, "allow_no_target": True},
        "timeout": {"action": action_timeout_ms, "response": response_timeout_ms},
    }


def _info(
    *,
    game_id: str,
    day: int,
    agent: str,
    agent_names: list[str],
    profile_payload: dict[str, Any] | None,
    remain_count: int | None,
) -> dict[str, Any]:
    """Build an Info payload compatible with ``Info.from_dict``.

    ``Info.from_dict`` requires status_map and role_map; we mark everyone ALIVE/VILLAGER
    (roles are meaningless in HiddenBench). HiddenBench context rides in ``profile``.
    """
    return {
        "game_id": game_id,
        "day": day,
        "agent": agent,
        "profile": json.dumps(profile_payload, ensure_ascii=False) if profile_payload is not None else None,
        "medium_result": None,
        "divine_result": None,
        "executed_agent": None,
        "attacked_agent": None,
        "vote_list": None,
        "attack_vote_list": None,
        "status_map": {n: "ALIVE" for n in agent_names},
        "role_map": {n: "VILLAGER" for n in agent_names},
        "remain_count": remain_count,
        "remain_length": None,
        "remain_skip": 0,
    }


def name_request() -> str:
    """NAME request (server asks the agent for its name) / 名前リクエスト."""
    return json.dumps({"request": "NAME"}, ensure_ascii=False)


def initialize_packet(
    *,
    game_id: str,
    agent: str,
    agent_names: list[str],
    payload: dict[str, Any],
    agent_count: int,
    action_timeout_ms: int,
    response_timeout_ms: int,
) -> str:
    """INITIALIZE packet delivering the agent's clues + task framing.

    エージェントの手がかり + タスク文脈を渡すINITIALIZEパケット.
    """
    return json.dumps(
        {
            "request": "INITIALIZE",
            "info": _info(
                game_id=game_id,
                day=0,
                agent=agent,
                agent_names=agent_names,
                profile_payload=payload,
                remain_count=None,
            ),
            "setting": _setting(agent_count, action_timeout_ms, response_timeout_ms),
            "talk_history": [],
            "whisper_history": [],
        },
        ensure_ascii=False,
    )


def talk_packet(
    *,
    game_id: str,
    day: int,
    agent: str,
    agent_names: list[str],
    payload: dict[str, Any],
    talk_history: list[dict[str, Any]],
    remain_count: int,
    agent_count: int,
    action_timeout_ms: int,
    response_timeout_ms: int,
) -> str:
    """TALK packet used for pre-answer, each discussion turn, and post-answer.

    事前回答・各議論ターン・事後回答で使うTALKパケット. フェーズは payload['phase'] で区別.
    """
    return json.dumps(
        {
            "request": "TALK",
            "info": _info(
                game_id=game_id,
                day=day,
                agent=agent,
                agent_names=agent_names,
                profile_payload=payload,
                remain_count=remain_count,
            ),
            "setting": _setting(agent_count, action_timeout_ms, response_timeout_ms),
            "talk_history": talk_history,
            "whisper_history": [],
        },
        ensure_ascii=False,
    )


def finish_packet(*, game_id: str, agent: str, agent_names: list[str]) -> str:
    """FINISH packet (ends the agent's game session) / ゲーム終了パケット."""
    return json.dumps(
        {
            "request": "FINISH",
            "info": _info(
                game_id=game_id,
                day=0,
                agent=agent,
                agent_names=agent_names,
                profile_payload=None,
                remain_count=None,
            ),
            "setting": None,
            "talk_history": None,
            "whisper_history": None,
        },
        ensure_ascii=False,
    )


def make_talk(idx: int, day: int, turn: int, agent: str, text: str) -> dict[str, Any]:
    """Build a Talk history entry / トーク履歴エントリを構築."""
    return {"idx": idx, "day": day, "turn": turn, "agent": agent, "text": text, "skip": False, "over": False}
