"""Evaluate the GENERATED exemplar scripts themselves, as a reference ("gold") condition.

生成した手本台本そのものを、同じ指標で評価して参照（gold）条件として比較に加える。

The HiddenBench exemplar scripts (agent/hidden-bench/exemplars/<lang>/scripts/script_NN.md)
are parsed into the same per-game result schema the server emits, stamped with
``condition: "gold_script"``, and written next to the experiment's flat results so that
``evaluate_with_judge.py`` + ``plot_report.py`` pick them up as one extra group. The task's
correct answer / hidden information are recovered from benchmark.json by matching the script's
vote option set (robust to the script paraphrasing the task description).

aiwolf exemplar scripts have no HiddenBench-style pre/post answers, so only the domain-general
diversity metrics are reported for them (printed, not merged into the HB plot).

Usage:
    python eval/src/evaluate_exemplars.py --lang jp \
        --agent-dir agent --benchmark server/hidden-bench/data/benchmark.json \
        --out results/local_run/hiddenbench_flat
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from diversity import distinct_n

_UTT_RE = re.compile(r"^- \*\*(?P<agent>.+?)\*\*:\s*(?P<text>.+)$")
_HEADER_RE = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")


def _section(title: str) -> str:
    t = title.lower()
    if "事前回答" in title or "pre" in t:
        return "pre"
    if "事後回答" in title or "post" in t:
        return "post"
    if title.startswith("ラウンド") or t.startswith("round"):
        return "round"
    return "other"


def parse_hb_script(md: str) -> dict[str, Any]:
    """Parse an HB exemplar script into pre/post votes + a round transcript."""
    pre: dict[str, str] = {}
    post: dict[str, str] = {}
    transcript: list[dict[str, Any]] = []
    section = "other"
    round_no = 0
    idx = 0
    for line in md.splitlines():
        h = _HEADER_RE.match(line)
        if h:
            section = _section(h.group("title"))
            if section == "round":
                round_no += 1
            continue
        m = _UTT_RE.match(line)
        if not m:
            continue
        agent = m.group("agent").strip()
        text = m.group("text").strip()
        if section in ("pre", "post"):
            vote = _extract_vote(text)
            if vote is not None:
                (pre if section == "pre" else post)[agent] = vote
        elif section == "round":
            transcript.append({"idx": idx, "day": round_no, "turn": 0, "agent": agent, "text": text})
            idx += 1
    return {"pre": pre, "post": post, "transcript": transcript}


def _extract_vote(text: str) -> str | None:
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return None
    v = obj.get("vote") if isinstance(obj, dict) else None
    return str(v) if v else None


def _match_task(votes: list[str], benchmark: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the benchmark task whose possible_answers best cover the script's votes."""
    best, best_score = None, -1
    vset = {v for v in votes if v}
    for t in benchmark:
        opts = set(t.get("possible_answers") or [])
        score = len(vset & opts)
        if score > best_score:
            best, best_score = t, score
    return best if best_score > 0 else None


def _accuracy(votes: dict[str, str], correct: str) -> float:
    if not votes:
        return 0.0
    return sum(1.0 for v in votes.values() if v == correct) / len(votes)


def eval_hb_exemplars(agent_dir: Path, lang: str, benchmark: list[dict[str, Any]], out_dir: Path) -> int:
    scripts = sorted((agent_dir / "hidden-bench" / "exemplars" / lang / "scripts").glob("*.md"))
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for i, sp in enumerate(scripts, 1):
        parsed = parse_hb_script(sp.read_text(encoding="utf-8"))
        votes = list(parsed["pre"].values()) + list(parsed["post"].values())
        task = _match_task(votes, benchmark)
        if task is None:
            continue
        correct = task["correct_answer"]
        pre_acc = _accuracy(parsed["pre"], correct)
        post_acc = _accuracy(parsed["post"], correct)
        n_post = len(parsed["post"]) or 1
        result = {
            "game_id": f"gold-hb-{i:03d}",
            "task_id": task["id"],
            "task_name": task.get("name"),
            "correct_answer": correct,
            "lang": lang,
            "condition": "gold_script",
            "num_agents": len(parsed["post"]) or len(parsed["pre"]),
            "total_rounds": max((t["day"] for t in parsed["transcript"]), default=0),
            "pre_decisions": {a: {"option": v} for a, v in parsed["pre"].items()},
            "post_decisions": {a: {"option": v} for a, v in parsed["post"].items()},
            "transcript": parsed["transcript"],
            "pre_accuracy": pre_acc,
            "post_accuracy": post_acc,
            "integration_gain": post_acc - pre_acc,
            "post_majority_correct": sum(1 for v in parsed["post"].values() if v == correct) / n_post > 0.5,
            "metadata": {
                "options": task.get("possible_answers"),
                "hidden_information": task.get("hidden_information"),
                "shared_information": task.get("shared_information"),
            },
        }
        (out_dir / f"gold_script__{result['game_id']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        n += 1
    return n


def report_aiwolf_diversity(agent_dir: Path, lang: str) -> None:
    """aiwolf scripts: report domain-general diversity only (no HB accuracy pipeline)."""
    scripts = sorted((agent_dir / "aiwolf" / "exemplars" / lang / "scripts").glob("*.md"))
    for sp in scripts:
        utts = [m.group("text").strip() for line in sp.read_text(encoding="utf-8").splitlines()
                if (m := _UTT_RE.match(line))]
        if utts:
            print(f"  aiwolf {sp.name}: utt={len(utts)} distinct-1={distinct_n(utts, 1, lang):.3f} "
                  f"distinct-2={distinct_n(utts, 2, lang):.3f}")


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate generated exemplar scripts as a gold reference")
    p.add_argument("--lang", default="jp")
    p.add_argument("--agent-dir", default="agent")
    p.add_argument("--benchmark", default="server/hidden-bench/data/benchmark.json")
    p.add_argument("--out", default="results/local_run/hiddenbench_flat",
                   help="dir to write gold_script result JSONs (the experiment's flat dir)")
    args = p.parse_args()

    benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    n = eval_hb_exemplars(Path(args.agent_dir), args.lang, benchmark, Path(args.out))
    print(f"wrote {n} HB gold_script result(s) into {args.out}")
    print("aiwolf exemplar diversity (domain-general, not in the HB plot):")
    report_aiwolf_diversity(Path(args.agent_dir), args.lang)


if __name__ == "__main__":
    main()
