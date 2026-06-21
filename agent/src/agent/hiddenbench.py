"""HiddenBench domain adapter agent.

HiddenBench (協調熟議) ドメイン用エージェントアダプタ.

The same shared agent core (prompt building, script/analysis injection, LLM call, cost
tracking) drives both werewolf and HiddenBench — only the I/O seam differs. This subclass:

- parses the HiddenBench per-turn context (phase / clues / options / round) that the
  HiddenBench server packs into ``info.profile`` as JSON, and
- routes the single standard TALK request to a phase-specific prompt
  (``hb_pre`` / ``hb_discussion`` / ``hb_post``).

INITIALIZE still runs the shared ``initialize()`` (so the script+analysis injection layer
is IDENTICAL to werewolf — see METHODOLOGY.md P2), priming the agent's clues into
history. No werewolf action handlers (vote/divine/guard/attack) are ever invoked.

人狼と同じ共有コア (プロンプト構築・台本/分析注入・LLM呼出・コスト計上) で両ドメインを駆動し,
入出力の継ぎ目だけが異なる. 本サブクラスは info.profile のJSON文脈を解析し, 標準TALKを
フェーズ別プロンプト (hb_pre / hb_discussion / hb_post) に振り分ける.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from aiwolf_nlp_common.packet import Request

from agent.agent import Agent

if TYPE_CHECKING:
    from aiwolf_nlp_common.packet import Packet, Role

logger = logging.getLogger(__name__)

_VALID_PHASES = {"init", "pre", "discussion", "post"}


class HiddenBenchAgent(Agent):
    """Agent for the HiddenBench collaborative-reasoning domain / HiddenBench用エージェント."""

    def __init__(self, config: dict[str, Any], name: str, game_id: str, role: Role) -> None:
        """Initialize, with an empty HiddenBench context / 空のHiddenBench文脈で初期化."""
        super().__init__(config, name, game_id, role)
        # Per-turn context parsed from info.profile / info.profileから解析するターン文脈.
        self.hb_context: dict[str, Any] | None = None

    def set_packet(self, packet: Packet) -> None:
        """Set packet, then parse the HiddenBench context from info.profile.

        パケットをセットし, info.profileからHiddenBench文脈を解析する.
        """
        super().set_packet(packet)
        if packet.info is not None and packet.info.profile:
            parsed = _parse_hb_profile(packet.info.profile)
            if parsed is not None:
                self.hb_context = parsed

    def _phase(self) -> str:
        """Current HiddenBench phase / 現在のHiddenBenchフェーズ."""
        phase = (self.hb_context or {}).get("phase", "discussion")
        return phase if phase in _VALID_PHASES else "discussion"

    def talk(self) -> str:
        """Respond to a TALK request, routing by HiddenBench phase.

        TALKリクエストに対し, HiddenBenchフェーズで分岐して応答する.
        ``pre`` / ``post`` は JSON 回答 (整形しない), ``discussion`` は発話 (通常整形).
        """
        phase = self._phase()
        prompt_key = f"hb_{phase}" if phase in {"pre", "discussion", "post"} else "hb_discussion"
        response = self._send_message_to_llm(Request.TALK, prompt_key_override=prompt_key)
        self.sent_talk_count = len(self.talk_history)
        if phase in {"pre", "post"}:
            # Answer phases must return the raw JSON decision untouched (the server parses it).
            # 回答フェーズは生のJSON判断をそのまま返す (サーバが解析する).
            return response or ""
        return self._postprocess_utterance(response, "talk")


def _parse_hb_profile(profile: str) -> dict[str, Any] | None:
    """Parse the JSON HiddenBench payload carried in info.profile / profileのJSONを解析."""
    try:
        obj = json.loads(profile)
    except (ValueError, TypeError):
        return None
    if isinstance(obj, dict) and obj.get("hb") is True:
        return obj
    return None
