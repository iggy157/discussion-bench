"""Convert aiwolf (werewolf) game JSONs into the shared result schema for the eval pipeline.

aiwolfの対局JSON（リクエスト/レスポンスのパケットログ）を、HiddenBenchと共通の result スキーマ
（transcript[{day,agent,text}] + metadata.options）へ変換する。これにより evaluate_with_judge.py
が aiwolf にも **ドメイン汎用な指標**（distinct-n / 自己反復多様性 / 同調・独立 / 収束 / 主観judge）を
計算できる。正答率・surfacing は aiwolf に無いので欠損（ランキングからは除外する）。

vote 先（＝立場）の検出には、発話に登場するゲーム内プレイヤー名を options として用いる。

Usage:
    python eval/src/evaluate_aiwolf.py --src results/local_run/aiwolf --out results/local_run/aiwolf_flat
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_SKIP = {"", "Over", "Skip", "ForceSkip"}


def parse_game(path: Path) -> dict[str, Any] | None:
    """Parse one aiwolf game JSON into a result dict (transcript + options + win_side)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    transcript: list[dict[str, Any]] = []
    speakers: set[str] = set()
    idx = 0
    for e in entries:
        try:
            req = json.loads(e["request"])
        except (KeyError, ValueError, TypeError):
            continue
        if req.get("request") != "TALK":
            continue
        text = (e.get("response") or "").strip()
        if text in _SKIP:
            continue
        agent = str(e.get("agent", "?"))
        day = int((req.get("info") or {}).get("day", 0))
        transcript.append({"idx": idx, "day": day, "turn": 0, "agent": agent, "text": text})
        speakers.add(agent)
        idx += 1
    if not transcript:
        return None
    return {
        "game_id": data.get("game_id", path.stem),
        "lang": "jp",
        "transcript": transcript,
        # options = in-game player names (vote/suspicion targets) for stance-based metrics.
        "metadata": {"options": sorted(speakers), "hidden_information": []},
        "win_side": data.get("win_side"),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Convert aiwolf game JSONs to the shared eval schema")
    p.add_argument("--src", default="results/local_run/aiwolf", help="dir with per-condition subdirs of game JSONs")
    p.add_argument("--out", default="results/local_run/aiwolf_flat", help="flat output dir")
    args = p.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for cond_dir in sorted(d for d in src.iterdir() if d.is_dir()):
        cond = cond_dir.name
        for gp in sorted(cond_dir.glob("*.json")):
            res = parse_game(gp)
            if res is None:
                continue
            res["condition"] = cond
            res["game_id"] = f"{cond}-{res['game_id']}"
            (out / f"{cond}__{gp.stem[:40]}.json").write_text(
                json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            n += 1
    print(f"converted {n} aiwolf game(s) -> {out}")


if __name__ == "__main__":
    main()
