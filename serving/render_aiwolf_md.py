"""Render raw aiwolf game JSONs into human-readable English markdown transcripts.

Reads each per-condition game JSON (results/<run>/aiwolf/<cond>/g*.json), extracts the
role reveal (agents), the win side, and the TALK transcript (same extraction as
eval/src/evaluate_aiwolf.py::parse_game), and writes one .en.md per game.

役職(agents)・勝敗(win_side)・発話ログを1試合1ファイルの英語markdownに描画する
（後段で translate_md.py により日本語訳する）。

    python serving/render_aiwolf_md.py --src results/run_newprompt_aw/aiwolf \
        --out results/aiwolf_logs_ja
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_SKIP = {"", "Over", "Skip", "ForceSkip"}


def parse_game(path: Path) -> dict[str, Any] | None:
    """Extract roles (by persona name), win_side, and the TALK transcript from one game JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    transcript: list[dict[str, Any]] = []
    # persona -> role: each agent's own INITIALIZE carries info.role_map = {persona: ROLE}
    # (an agent only sees its own role there), so the union across all INITIALIZE entries
    # recovers the full persona->role mapping the internal "agents" list can't (it uses IDs).
    roles: dict[str, str] = {}
    for e in entries:
        try:
            req = json.loads(e["request"])
        except (KeyError, ValueError, TypeError):
            continue
        rtype = req.get("request")
        info = req.get("info") or {}
        if rtype == "INITIALIZE":
            roles.update((info.get("role_map") or {}))
            continue
        if rtype != "TALK":
            continue
        text = (e.get("response") or "").strip()
        if text in _SKIP:
            continue
        agent = str(e.get("agent", "?"))
        day = int(info.get("day", 0))
        transcript.append({"day": day, "agent": agent, "text": text})
    if not transcript:
        return None
    return {
        "game_id": data.get("game_id", path.stem),
        "win_side": data.get("win_side"),
        "roles": roles,
        "transcript": transcript,
    }


def render_md(game: dict[str, Any], cond: str, label: str) -> str:
    """Render a parsed game into readable English markdown."""
    lines: list[str] = []
    lines.append(f"# aiwolf log — condition={cond} — {label}")
    lines.append(f"- game_id: {game['game_id']}")
    lines.append(f"- win_side: {game['win_side']}")
    lines.append("")
    lines.append("## Roles")
    for persona, role in game["roles"].items():
        lines.append(f"- {persona}: {role}")
    lines.append("")
    lines.append("## Discussion")
    cur_day = None
    for t in game["transcript"]:
        if t["day"] != cur_day:
            cur_day = t["day"]
            lines.append("")
            lines.append(f"### Day {cur_day}")
        lines.append(f"- **{t['agent']}**: {t['text']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, help="dir with per-condition subdirs of game JSONs")
    p.add_argument("--out", required=True, help="output dir; writes <cond>/<label>.en.md")
    args = p.parse_args()
    src = Path(args.src)
    out = Path(args.out)
    n = 0
    for cond_dir in sorted(src.iterdir()):
        if not cond_dir.is_dir():
            continue
        cond = cond_dir.name
        games = sorted(cond_dir.glob("g*.json"))
        for gi, gpath in enumerate(games, 1):
            game = parse_game(gpath)
            if game is None:
                print(f"  SKIP (no transcript): {gpath}")
                continue
            label = gpath.name.split("_")[0]  # e.g. "g3"
            md = render_md(game, cond, label)
            dst = out / cond / f"{label}.en.md"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(md, encoding="utf-8")
            n += 1
            print(f"  rendered {gpath.name} -> {dst} ({len(md)} chars, win={game['win_side']})")
    print(f"DONE: rendered {n} games")


if __name__ == "__main__":
    main()
