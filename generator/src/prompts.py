"""Render the generator's prompts (system + user) from per-language Jinja templates.

言語別の Jinja テンプレートから, 生成用プロンプト (system + user) を組み立てる.

Bilingual handling matches the other components (agent ``base-prompts/<lang>/`` and eval
``prompts/<lang>/``): prompts are **split per language** under ``prompts/<lang>/*.jinja`` and
each language version is **authored natively** (the Japanese files are written in idiomatic
Japanese, not translated from English). The same single mechanism — pick ``prompts/<lang>/`` —
is used everywhere; nothing here interpolates a "write in <language>" flag.

Three prompt families, matching the three Claude calls in the pipeline:
- ``aiwolf_script`` / ``hiddenbench_script`` — generate a full transcript (⑤), prompt-tuned so
  the transcript demonstrates resolution of the four target failure modes, without leaking
  task answers (L2 is enforced separately on the analysis call).
- ``analysis`` — extract topic-independent "where to look" notes (②) from a script, with the
  strict L2 no-leakage rule baked into the system prompt.

The ③ utterance few-shot slot is NOT generated here — it is sliced from the script (see
slicing.py), which is what keeps ③ and ⑤ fair to compare.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from leakage import HiddenBenchTask

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_ENV = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    undefined=StrictUndefined,
    autoescape=False,  # noqa: S701  (rendering prompts, not HTML)
    keep_trailing_newline=True,
)

# Domain label used inside the (per-language) analysis prompt, authored per language.
_DOMAIN_LABEL = {
    "en": {"aiwolf": "werewolf (AIWolfDial)", "hiddenbench": "HiddenBench"},
    "jp": {"aiwolf": "人狼（AIWolfDial）", "hiddenbench": "HiddenBench"},
}


@dataclass
class Prompt:
    """A rendered system + user prompt pair.

    レンダリング済みの system + user プロンプト対.
    """

    system: str
    user: str


def _render(lang: str, name: str, /, **ctx: object) -> str:
    """Render ``prompts/<lang>/<name>`` with ``ctx``.

    言語別テンプレート ``prompts/<lang>/<name>`` をコンテキスト付きでレンダリングする.
    """
    return _ENV.get_template(f"{lang}/{name}").render(**ctx)


def aiwolf_script_prompt(lang: str, seed: int) -> Prompt:
    """Build the prompt for a full 5-player werewolf transcript (⑤).

    5 人村の全文台本 (⑤) を生成するプロンプトを組み立てる.

    Args:
        lang: ``en`` | ``jp``.
        seed: Generation seed/index (varies the scenario; L1 disjoint from eval seeds).

    Returns:
        A :class:`Prompt`.
    """
    return Prompt(
        system=_render(lang, "system_script.jinja"),
        user=_render(lang, "aiwolf_script.jinja", seed=seed),
    )


def hiddenbench_script_prompt(
    lang: str,
    task: HiddenBenchTask,
    total_rounds: int,
    num_agents: int,
) -> Prompt:
    """Build the prompt for a full HiddenBench transcript (⑤) from a disjoint task (L1).

    評価セットと重複しないタスク (L1) から HiddenBench 全文台本 (⑤) を生成するプロンプトを組み立てる.

    Args:
        lang: ``en`` | ``jp``.
        task: The source task (drawn from beyond the evaluation slice).
        total_rounds: Discussion rounds (faithful T=15).
        num_agents: Number of agents (canonical 4).

    Returns:
        A :class:`Prompt`.
    """
    return Prompt(
        system=_render(lang, "system_script.jinja"),
        user=_render(
            lang,
            "hiddenbench_script.jinja",
            task=task,
            total_rounds=total_rounds,
            num_agents=num_agents,
        ),
    )


def analysis_prompt(lang: str, domain: str, script_md: str) -> Prompt:
    """Build the prompt for topic-independent analysis notes (②), with L2 enforced.

    トピック非依存の分析ノート (②) を生成するプロンプトを組み立てる. L2 (漏洩対策) を system で強制.

    Args:
        lang: ``en`` | ``jp``.
        domain: ``aiwolf`` | ``hiddenbench``.
        script_md: The script to analyze.

    Returns:
        A :class:`Prompt`.
    """
    return Prompt(
        system=_render(lang, "system_analysis.jinja"),
        user=_render(
            lang,
            "analysis.jinja",
            domain_label=_DOMAIN_LABEL[lang][domain],
            script_md=script_md,
        ),
    )
