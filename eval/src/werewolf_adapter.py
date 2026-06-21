"""Convert an aiwolf-nlp-server JSON game log into the transcript shape eval/judge consume.

aiwolf-nlp-server のJSONゲームログを、eval/judge が読む transcript 形へ変換する。

The werewolf server writes per-game JSON (json_logger): {agents, entries, game_id, win_side},
where each entry has {agent, request, response, ...} and `request` is a packet JSON string.
We extract the TALK utterances (the agent's `response` to a TALK request) into a transcript.

Werewolf has no hidden_information / option set, so the HiddenBench-native metrics (surfacing,
accuracy, convergence, conformity) are N/A and come out empty; the domain-general metrics
(distinct-n, lexical self-repetition) and the subjective LLM-judge apply to the whole log.
Pass --condition to tag games for per-condition aggregation.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("werewolf_adapter")

# Responses that are control tokens / skips, not real utterances.
_SKIP = {"", "over", "skip", "[pass]", "了解しました", "understood."}


def convert(log: dict[str, Any], *, condition: str, lang: str) -> dict[str, Any]:
    """Convert one werewolf game log into a transcript-shaped result dict / 1ログを変換."""
    transcript: list[dict[str, Any]] = []
    idx = 0
    for entry in log.get("entries", []):
        response = (entry.get("response") or "").strip()
        if not response or response.lower() in _SKIP:
            continue
        # Parse the request packet to keep only TALK utterances and recover the day.
        req_raw = entry.get("request")
        day = 0
        is_talk = False
        try:
            pkt = json.loads(req_raw) if isinstance(req_raw, str) else (req_raw or {})
            is_talk = str(pkt.get("request", "")).upper() == "TALK"
            day = int((pkt.get("info") or {}).get("day", 0))
        except (ValueError, TypeError):
            continue
        if not is_talk:
            continue
        transcript.append(
            {"idx": idx, "day": day, "turn": idx, "agent": entry.get("agent", "?"), "text": response}
        )
        idx += 1

    return {
        "game_id": log.get("game_id", "werewolf"),
        "task_id": log.get("game_id", "werewolf"),
        "domain": "aiwolf",
        "condition": condition,
        "lang": lang,
        "win_side": log.get("win_side"),
        "agents": log.get("agents"),
        "transcript": transcript,
        # No hidden-profile structure in werewolf -> HB-native metrics will be empty.
        "metadata": {"options": [], "hidden_information": []},
    }


def main() -> None:
    """CLI: convert a dir of werewolf JSON logs into transcript-shaped result JSONs."""
    parser = argparse.ArgumentParser(description="Convert werewolf server JSON logs for eval/judge")
    parser.add_argument("logs_dir", type=str, help="dir of aiwolf-nlp-server json logs")
    parser.add_argument("-o", "--out", type=str, required=True, help="output dir for transcript-shaped results")
    parser.add_argument("--condition", type=str, default="unknown", help="condition label to tag these games")
    parser.add_argument("--lang", type=str, default="jp")
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for fp in sorted(logs_dir.glob("*.json")):
        try:
            with fp.open(encoding="utf-8") as f:
                log = json.load(f)
            if "entries" not in log:
                continue
            result = convert(log, condition=args.condition, lang=args.lang)
            with (out_dir / f"{fp.stem}.json").open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            n += 1
        except Exception:
            logger.exception("failed to convert %s", fp)
    logger.info("converted %d werewolf log(s) -> %s", n, out_dir)


if __name__ == "__main__":
    main()
