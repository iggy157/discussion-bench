"""Minimal canned-response agent for integration testing the HiddenBench server.

HiddenBenchサーバ結合テスト用の最小スタブエージェント (LLM不要・定型応答).
Uses the real aiwolf-nlp-common Client so it exercises the actual wire framing.
"""

from __future__ import annotations

import json
import sys

from aiwolf_nlp_common.client import Client
from aiwolf_nlp_common.packet import Request


def run(url: str, name: str) -> None:
    """Connect and respond to the HiddenBench protocol with canned answers."""
    client = Client(url=url, token=None)
    client.connect()
    while True:
        packet = client.receive()
        if packet.request == Request.NAME:
            client.send(name)
            continue
        if packet.request == Request.FINISH:
            break
        if packet.request == Request.INITIALIZE:
            client.send("Understood.")
            continue
        if packet.request == Request.TALK:
            payload = json.loads(packet.info.profile) if packet.info and packet.info.profile else {}
            phase = payload.get("phase", "discussion")
            options = payload.get("options", ["?"])
            if phase in ("pre", "post"):
                client.send(json.dumps({"vote": options[0], "rationale": "stub"}))
            else:
                client.send(f"{name}: I lean towards {options[0]}.")
            continue
    client.close()


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
