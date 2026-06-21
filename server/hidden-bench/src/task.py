"""HiddenBench task loading and information distribution.

HiddenBenchタスクの読み込みと情報配分.

Faithful to the Hidden Profile paradigm of Li, Naito & Shirado (arXiv:2505.11556):
- ``shared_information`` is given to every agent.
- ``hidden_information`` is a flat list distributed round-robin so each agent
  receives a disjoint slice (each unshared fact held by exactly one agent).
- Per-agent information order is shuffled (the canonical protocol tells agents the
  order is randomly shuffled and carries no meaning).

論文 (Li et al., 2505.11556) の隠れプロファイル設定に忠実:
共有情報は全員へ, 隠し情報はラウンドロビンで重複なく配分し, 各エージェント内の順序はシャッフルする.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Task:
    """A single HiddenBench task / 単一のHiddenBenchタスク.

    Attributes:
        id: Task id / タスクID.
        name: Task short name / タスク名.
        description: Scenario description shown to all agents / 全員に提示する状況説明.
        shared_information: Facts given to every agent / 全員共有の事実.
        hidden_information: Flat list of unshared facts distributed across agents /
            各エージェントへ配分する未共有事実のフラットなリスト.
        possible_answers: The fixed option set / 選択肢集合.
        correct_answer: The single correct option / 唯一の正解選択肢.
    """

    id: int
    name: str
    description: str
    shared_information: list[str]
    hidden_information: list[str]
    possible_answers: list[str]
    correct_answer: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> Task:
        """Build a Task from a benchmark.json record / benchmark.jsonの1件から生成."""
        return Task(
            id=int(obj["id"]),
            name=str(obj.get("name", obj["id"])),
            description=str(obj["description"]),
            shared_information=list(obj.get("shared_information", [])),
            hidden_information=list(obj.get("hidden_information", [])),
            possible_answers=list(obj["possible_answers"]),
            correct_answer=str(obj["correct_answer"]),
            metadata={k: v for k, v in obj.items() if k not in _CORE_KEYS},
        )

    def distribute(self, num_agents: int, seed: int) -> list[list[str]]:
        """Assign hidden facts round-robin to ``num_agents`` agents.

        隠し情報をラウンドロビンで各エージェントへ重複なく配分する.

        Returns:
            list[list[str]]: ``unshared[i]`` = the hidden facts held only by agent i /
                エージェントiだけが持つ隠し事実.
        """
        rng = random.Random(seed)
        pool = list(self.hidden_information)
        rng.shuffle(pool)
        unshared: list[list[str]] = [[] for _ in range(num_agents)]
        for idx, fact in enumerate(pool):
            unshared[idx % num_agents].append(fact)
        return unshared

    def agent_clues(self, agent_index: int, num_agents: int, seed: int) -> list[str]:
        """Return the shuffled clue list (shared + this agent's hidden) for one agent.

        1エージェント分の手がかり (共有 + 自分の隠し) をシャッフルして返す.
        """
        unshared = self.distribute(num_agents, seed)
        clues = list(self.shared_information) + list(unshared[agent_index])
        # Per-agent order shuffle, deterministic per (task, agent, seed).
        rng = random.Random(f"{seed}-{agent_index}-{self.id}")
        rng.shuffle(clues)
        return clues

    def full_information(self) -> list[str]:
        """All facts (shared + every hidden) for the Full-Profile ceiling condition.

        Full-Profile条件 (上限) 用の全事実 (共有 + 全隠し).
        """
        return list(self.shared_information) + list(self.hidden_information)


_CORE_KEYS = {
    "id",
    "name",
    "description",
    "shared_information",
    "hidden_information",
    "possible_answers",
    "correct_answer",
}


def load_tasks(path: Path) -> list[Task]:
    """Load all tasks from a benchmark.json file / benchmark.jsonから全タスクを読み込む."""
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        msg = f"benchmark.json must be a JSON list of tasks, got {type(data).__name__}"
        raise TypeError(msg)
    return [Task.from_dict(o) for o in data]


def resolve_benchmark_path(data_dir: Path, lang: str) -> Path:
    """Resolve the benchmark file for a language, falling back to English.

    言語に対応する benchmark ファイルを解決する. 翻訳が無ければ英語にフォールバック.

    Looks for ``benchmark.<lang>.json`` first (e.g. a Japanese translation dropped in
    by the user), otherwise uses ``benchmark.json`` (the upstream English set).
    """
    localized = data_dir / f"benchmark.{lang}.json"
    if localized.is_file():
        return localized
    return data_dir / "benchmark.json"


def select_tasks(tasks: list[Task], ids: list[int] | None, limit: int | None) -> list[Task]:
    """Select a subset of tasks by explicit ids or a leading limit.

    明示IDまたは先頭limit件でタスク部分集合を選ぶ.
    Held-out exemplar leakage control (see METHODOLOGY.md L1) is the caller's
    responsibility: evaluation ids and exemplar ids must be disjoint.
    """
    if ids:
        by_id = {t.id: t for t in tasks}
        return [by_id[i] for i in ids if i in by_id]
    if limit is not None:
        return tasks[:limit]
    return tasks
