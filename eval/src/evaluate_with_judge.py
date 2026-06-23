"""Combined evaluation: objective metrics + subjective LLM-judge in one pass.

総合評価: 客観指標 + 主観LLM-judge を一括実行し、統合レポートを出す（make judge）。

For each game result it computes the objective failure-mode metrics (evaluate.py) AND the
three subjective items (judge.py), merges them, aggregates by condition, and writes a single
report.md + metrics.json. The subjective scores appear as subj_<item> columns.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from evaluate import aggregate, evaluate_game, render_markdown
from judge import DEFAULT_CONFIG as JUDGE_CONFIG
from judge import judge_game, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("evaluate_with_judge")


def main() -> None:
    """CLI: objective + subjective over a results dir / 客観+主観の一括CLI."""
    parser = argparse.ArgumentParser(description="Combined objective + subjective (LLM-judge) evaluation")
    parser.add_argument("results_dir", type=str, help="directory of per-game *.json")
    parser.add_argument("-o", "--out", type=str, default=None, help="output dir (default: <results_dir>/eval)")
    parser.add_argument("-c", "--judge-config", type=str, default=str(JUDGE_CONFIG))
    parser.add_argument("--threshold", type=float, default=0.5, help="surfacing token-overlap threshold")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM-judge (objective only)")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out) if args.out else results_dir / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    judge_cfg = load_config(Path(args.judge_config))

    per_game: list[dict[str, Any]] = []
    for fp in sorted(results_dir.glob("*.json")):
        try:
            with fp.open(encoding="utf-8") as f:
                result = json.load(f)
        except Exception:
            logger.exception("failed to read %s", fp)
            continue
        row = evaluate_game(result, threshold=args.threshold)
        if not args.no_judge:
            try:
                sj = judge_game(result, judge_cfg)
                for k, v in (sj.get("scores") or {}).items():
                    row[f"subj_{k}"] = v
            except Exception:
                logger.exception("judge failed on %s (objective kept)", result.get("game_id"))
        per_game.append(row)

    agg = aggregate(per_game)
    with (out_dir / "metrics.json").open("w", encoding="utf-8") as f:
        payload = {"per_game": per_game, "aggregate": agg, "judge": judge_cfg.get("model")}
        json.dump(payload, f, ensure_ascii=False, indent=2)
    (out_dir / "report.md").write_text(render_markdown(agg), encoding="utf-8")
    logger.info("evaluated %d game(s) (judge=%s) -> %s", len(per_game), not args.no_judge, out_dir)
    print(render_markdown(agg))


if __name__ == "__main__":
    main()
