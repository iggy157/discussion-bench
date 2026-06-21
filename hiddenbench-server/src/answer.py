"""Answer extraction and scoring for HiddenBench.

HiddenBenchの回答抽出と採点.

The pre/post elicitation asks agents for JSON ``{"vote": <option>, "rationale": ...}``
(faithful to the upstream ``prompts.py``). Real LLMs wrap or paraphrase, so we extract
leniently: (1) parse the first JSON object with a ``vote`` field; (2) else match an
option string mentioned in the text. The matched option is canonicalised to the exact
option in ``possible_answers``.

事前/事後回答は JSON {"vote","rationale"} を要求する (上流prompts.pyに忠実). 実LLMは
体裁が崩れるため寛容に抽出する: まずvote付きJSON, 無ければ選択肢文字列の一致で判定.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class Decision:
    """A single agent decision / 1エージェントの判断.

    Attributes:
        raw: The raw agent response text / 生の応答テキスト.
        option: The canonical matched option, or None if unparseable / 正規化済み選択肢.
        rationale: Extracted rationale if present / 抽出された理由.
    """

    raw: str
    option: str | None
    rationale: str

    def is_correct(self, correct_answer: str) -> bool:
        """Whether this decision matches the correct option / 正解と一致するか."""
        return self.option is not None and self.option == correct_answer


def _canonicalise(value: str, options: list[str]) -> str | None:
    """Map a free string to the exact option it best denotes / 文字列を正規選択肢へ写像."""
    v = value.strip().lower()
    # Exact / containment match against options.
    for opt in options:
        if v == opt.strip().lower():
            return opt
    for opt in options:
        ol = opt.strip().lower()
        if ol and (ol in v or v in ol):
            return opt
    return None


def _first_json_vote(text: str) -> tuple[str | None, str]:
    """Find the first ``{...}`` block carrying a ``vote`` field / vote付きJSONを探す."""
    for match in re.finditer(r"\{[^{}]*\}", text, flags=re.DOTALL):
        try:
            obj = json.loads(match.group(0))
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and "vote" in obj:
            return str(obj["vote"]), str(obj.get("rationale", ""))
    return None, ""


def extract_decision(text: str, options: list[str]) -> Decision:
    """Extract a Decision from an agent response / 応答からDecisionを抽出する."""
    text = (text or "").strip()
    vote, rationale = _first_json_vote(text)
    if vote is not None:
        canon = _canonicalise(vote, options)
        if canon is not None:
            return Decision(raw=text, option=canon, rationale=rationale)
    # Fallback: scan the whole text for an option mention (last mention wins,
    # approximating the agent's concluding choice).
    chosen: str | None = None
    low = text.lower()
    best_pos = -1
    for opt in options:
        pos = low.rfind(opt.strip().lower())
        if pos > best_pos:
            best_pos = pos
            chosen = opt
    return Decision(raw=text, option=chosen, rationale=rationale)


def average_accuracy(decisions: list[Decision], correct_answer: str) -> float:
    """Average rule: fraction of agents choosing the correct option / 平均ルール正答率."""
    if not decisions:
        return 0.0
    return sum(1 for d in decisions if d.is_correct(correct_answer)) / len(decisions)


def majority_correct(decisions: list[Decision], correct_answer: str) -> bool:
    """Majority rule: >50% of agents chose the correct option / 多数決ルール (>50%)."""
    if not decisions:
        return False
    correct = sum(1 for d in decisions if d.is_correct(correct_answer))
    return correct > len(decisions) / 2
