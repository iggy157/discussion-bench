"""Load and validate the exemplar-generator config (``config/generator.yml``).

手本ジェネレータ設定 (``config/generator.yml``) を読み込み・検証する.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Supported provider backends / 対応プロバイダ.
# anthropic = Claude (the principled default, METHODOLOGY L3). openai/vllm/ollama all speak the
# OpenAI-compatible API (so any vLLM- or Ollama-served model works via base_url). google = Gemini
# / Gemma via the Google API. mock = offline pipeline test.
_PROVIDERS = {"anthropic", "openai", "vllm", "ollama", "google", "mock"}
# Supported generation languages / 生成対応言語.
_LANGS = {"en", "jp"}
# Supported domains / 生成対象ドメイン.
_DOMAINS = {"hiddenbench", "aiwolf"}


@dataclass
class HiddenBenchConfig:
    """HiddenBench-specific generation settings.

    HiddenBench 固有の生成設定.

    Attributes:
        benchmark: Path to ``benchmark.json`` (relative to the generator dir).
        eval_task_limit: Tasks ``[0:eval_task_limit)`` are the evaluation set; examples
            are built ONLY from the remainder (leakage control L1).
        total_rounds: Discussion length (mirrors the faithful T=15 protocol).
        num_agents: Number of agents in the script (canonical 4).
    """

    benchmark: Path
    eval_task_limit: int
    total_rounds: int
    num_agents: int


@dataclass
class GeneratorConfig:
    """Top-level generator configuration.

    ジェネレータの全体設定.

    Attributes:
        provider: ``anthropic`` (Claude) or ``mock`` (offline pipeline test).
        model: Model id (e.g. ``claude-opus-4-8``).
        max_tokens: Output cap for analysis calls; script calls use a higher floor.
        temperature: Requested temperature; IGNORED for models that reject sampling
            params (Opus 4.7/4.8, Fable/Mythos 5) — see provider.py.
        api_key_env: Env var holding the API key (e.g. ``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY``
            / ``GOOGLE_API_KEY``). Optional for local OpenAI-compatible servers (vllm/ollama).
        base_url: Optional OpenAI-compatible endpoint override (vLLM / Ollama / any local server).
            Ignored by ``anthropic`` / ``google``; ``vllm``/``ollama`` fall back to a sensible
            default when unset.
        lang: Generation language (``en`` | ``jp``).
        domains: Domains to generate for.
        num_scripts: Per-domain script count.
        token_match: ``approximate`` | ``off`` (③ utterance ↔ ⑤ script token matching).
        agent_dir: Path to the agent project root (exemplars are written under it).
        hiddenbench: HiddenBench-specific settings.
    """

    provider: str
    model: str
    max_tokens: int
    temperature: float
    api_key_env: str
    base_url: str | None
    lang: str
    domains: list[str]
    num_scripts: dict[str, int]
    token_match: str
    agent_dir: Path
    hiddenbench: HiddenBenchConfig
    config_dir: Path = field(default_factory=Path)


def _require(data: dict[str, Any], key: str) -> Any:  # noqa: ANN401
    """Return ``data[key]`` or raise a clear error.

    必須キーを取り出す. 欠けていれば明示的に失敗する.
    """
    if key not in data:
        msg = f"generator config missing required key: {key!r}"
        raise ValueError(msg)
    return data[key]


def load_config(config_path: Path) -> GeneratorConfig:
    """Parse and validate the generator YAML at ``config_path``.

    ``config_path`` の YAML を読み込み, 値を検証して :class:`GeneratorConfig` を返す.
    相対パス (benchmark / agent_dir) は config ファイルのあるディレクトリ基準で解決する.

    Args:
        config_path: Path to ``generator.yml``.

    Returns:
        A validated :class:`GeneratorConfig`.

    Raises:
        ValueError: On any missing key or out-of-domain value.
    """
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config_dir = config_path.resolve().parent.parent  # generator/ (config/ -> generator/)

    provider = str(_require(raw, "provider"))
    if provider not in _PROVIDERS:
        msg = f"provider must be one of {_PROVIDERS}, got {provider!r}"
        raise ValueError(msg)

    lang = str(_require(raw, "lang"))
    if lang not in _LANGS:
        msg = f"lang must be one of {_LANGS}, got {lang!r}"
        raise ValueError(msg)

    domains = [str(d) for d in _require(raw, "domains")]
    unknown = set(domains) - _DOMAINS
    if unknown:
        msg = f"unknown domains: {unknown} (allowed: {_DOMAINS})"
        raise ValueError(msg)

    num_scripts = {str(k): int(v) for k, v in _require(raw, "num_scripts").items()}

    token_match = str(raw.get("token_match", "approximate"))
    if token_match not in {"approximate", "off"}:
        msg = f"token_match must be 'approximate' or 'off', got {token_match!r}"
        raise ValueError(msg)

    agent_dir = (config_dir / str(_require(raw, "agent_dir"))).resolve()

    hb_raw: dict[str, Any] = dict(_require(raw, "hiddenbench"))
    hiddenbench = HiddenBenchConfig(
        benchmark=(config_dir / str(_require(hb_raw, "benchmark"))).resolve(),
        eval_task_limit=int(_require(hb_raw, "eval_task_limit")),
        total_rounds=int(hb_raw.get("total_rounds", 15)),
        num_agents=int(hb_raw.get("num_agents", 4)),
    )

    return GeneratorConfig(
        provider=provider,
        model=str(_require(raw, "model")),
        max_tokens=int(raw.get("max_tokens", 4096)),
        temperature=float(raw.get("temperature", 0.7)),
        api_key_env=str(raw.get("api_key_env", "ANTHROPIC_API_KEY")),
        base_url=(str(raw["base_url"]) if raw.get("base_url") else None),
        lang=lang,
        domains=domains,
        num_scripts=num_scripts,
        token_match=token_match,
        agent_dir=agent_dir,
        hiddenbench=hiddenbench,
        config_dir=config_dir,
    )
