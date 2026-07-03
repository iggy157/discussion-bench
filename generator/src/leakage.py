"""Leakage control (L1): pick generation instances disjoint from the evaluation set.

漏洩対策 (L1): 評価セットと重複しないインスタンスから手本を生成する.

For HiddenBench, the evaluation runs the first ``eval_task_limit`` tasks; examples are built
ONLY from the remainder, so task-id disjointness is guaranteed mechanically. For werewolf
there is no shared task set — disjointness is by using different game seeds from evaluation,
so we simply hand out distinct seed indices.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HiddenBenchTask:
    """One HiddenBench benchmark task (the fields the script prompt needs).

    HiddenBench のタスク 1 件 (台本プロンプトが使うフィールド).
    """

    id: int
    name: str
    description: str
    shared_information: list[str]
    hidden_information: list[str]
    possible_answers: list[str]
    correct_answer: str


def load_hiddenbench_tasks_by_ids(benchmark_path: Path, ids: list[int]) -> list[HiddenBenchTask]:
    """Load explicit task ids (a curated, validity-/difficulty-selected script source).

    明示したタスクIDを読み込む（妥当性・難易度で選定した台本ソース用）。L1は呼び出し側が保証
    （eval_ids と素集合であること）。指定順を保持する。
    """
    raw = json.loads(benchmark_path.read_text(encoding="utf-8"))
    by_id = {int(t["id"]): t for t in raw}
    missing = [i for i in ids if i not in by_id]
    if missing:
        msg = f"benchmark missing requested script ids: {missing}"
        raise ValueError(msg)
    return [
        HiddenBenchTask(
            id=int(by_id[i]["id"]),
            name=str(by_id[i]["name"]),
            description=str(by_id[i]["description"]),
            shared_information=[str(x) for x in by_id[i].get("shared_information", [])],
            hidden_information=[str(x) for x in by_id[i].get("hidden_information", [])],
            possible_answers=[str(x) for x in by_id[i].get("possible_answers", [])],
            correct_answer=str(by_id[i].get("correct_answer", "")),
        )
        for i in ids
    ]


def select_hiddenbench_tasks(
    benchmark_path: Path,
    eval_task_limit: int,
    count: int,
) -> list[HiddenBenchTask]:
    """Return ``count`` tasks drawn from beyond the evaluation slice (L1).

    評価スライス (先頭 ``eval_task_limit`` 件) の外から ``count`` 件のタスクを返す.

    Args:
        benchmark_path: Path to ``benchmark.json``.
        eval_task_limit: Size of the evaluation slice (tasks ``[0:eval_task_limit)``).
        count: How many generation tasks to return.

    Returns:
        Up to ``count`` tasks taken in order from index ``eval_task_limit`` onward.

    Raises:
        ValueError: If the remainder has fewer than ``count`` tasks.
    """
    raw = json.loads(benchmark_path.read_text(encoding="utf-8"))
    pool = raw[eval_task_limit:]
    if len(pool) < count:
        msg = (
            f"benchmark has {len(raw)} tasks; eval reserves {eval_task_limit}, "
            f"leaving {len(pool)} for generation, but {count} requested"
        )
        raise ValueError(msg)
    return [
        HiddenBenchTask(
            id=int(t["id"]),
            name=str(t["name"]),
            description=str(t["description"]),
            shared_information=[str(x) for x in t.get("shared_information", [])],
            hidden_information=[str(x) for x in t.get("hidden_information", [])],
            possible_answers=[str(x) for x in t.get("possible_answers", [])],
            correct_answer=str(t.get("correct_answer", "")),
        )
        for t in pool[:count]
    ]


def aiwolf_seeds(count: int, eval_seed_base: int = 0, gen_seed_base: int = 10_000) -> list[int]:
    """Return ``count`` werewolf generation seeds disjoint from evaluation seeds (L1).

    評価用シード (``eval_seed_base`` 起点) と重複しない生成用シードを ``count`` 個返す.
    生成側は ``gen_seed_base`` 起点の連番を使うため, 評価側と機械的に分離される.

    Args:
        count: Number of seeds to return.
        eval_seed_base: Reserved base for evaluation seeds (documented, not used here).
        gen_seed_base: Base for generation seeds; must be far above the eval range.

    Returns:
        ``[gen_seed_base, gen_seed_base + 1, ...]`` of length ``count``.
    """
    _ = eval_seed_base  # documented for symmetry with the HiddenBench split
    return [gen_seed_base + i for i in range(count)]
