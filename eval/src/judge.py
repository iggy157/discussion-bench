"""Subjective LLM-judge: rate the WHOLE discussion transcript on three items.

主観LLM-judge: 議論ログ全体を3項目で採点する.

Items (self-play setting; whole-log, no per-agent relative scoring):
  naturalness / coherence (non-contradiction) / topic development.
項目: 自然さ / 噛み合い・非矛盾 / 話題展開.

The judge model is managed in eval/config/judge.yml (provider/model/temperature/scale/lang),
and the API key is read from the root .env via the configured env var. A `mock` provider is
included for offline testing. The judge sees the full transcript (faithful to evaluating one
whole discussion log, which is what self-play produces).

NOTE on rubric provenance: AIWolfDial's A–F rubric is a RELATIVE (ranking) scheme intended
for cross-play and is intentionally NOT used here (self-play makes relative ranking
meaningless). These three absolute items are scored per game on a Likert scale.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("judge")

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "judge.yml"


def load_config(path: Path) -> dict[str, Any]:
    """Load the judge config / 判定設定を読み込む."""
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_transcript_text(result: dict[str, Any]) -> str:
    """Render the whole discussion transcript as plain text for the judge / ログ全体を整形."""
    lines: list[str] = []
    desc = (result.get("metadata") or {}).get("description") or result.get("description")
    if desc:
        lines.append(f"[Scenario] {desc}")
    for t in result.get("transcript") or []:
        rnd = t.get("day")
        agent = t.get("agent", "?")
        text = (t.get("text") or "").strip()
        if not text:
            continue
        prefix = f"(r{rnd}) " if rnd is not None else ""
        lines.append(f"{prefix}{agent}: {text}")
    return "\n".join(lines)


# The judge prompt skeleton is managed as a file (like the agent prompts):
# eval/prompts/judge.<lang>.txt with %%SCALE%% / %%ITEMS%% / %%TRANSCRIPT%% / %%SCHEMA%% tokens.
# 判定プロンプトの骨格もファイル管理: eval/prompts/judge.<lang>.txt（トークン差し替え）。
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _rubric_prompt(transcript: str, config: dict[str, Any]) -> str:
    """Build the judge prompt from the per-language template file / テンプレファイルから構築."""
    lang = str(config.get("lang", "en"))
    scale = int(config.get("scale", 5))
    items = config.get("items") or []
    items_block = "\n".join(f'- "{it["key"]}": {it.get(lang) or it.get("en") or it["key"]}' for it in items)
    keys = [it["key"] for it in items]
    schema = ", ".join(f'"{k}": <1-{scale}>' for k in keys)

    fname = "judge.ja.txt" if lang in ("ja", "jp") else "judge.en.txt"
    template_path = _PROMPTS_DIR / fname
    template = template_path.read_text(encoding="utf-8") if template_path.is_file() else _INLINE_TEMPLATE.get(
        "ja" if lang in ("ja", "jp") else "en", _INLINE_TEMPLATE["en"]
    )
    return (
        template.replace("%%SCALE%%", str(scale))
        .replace("%%ITEMS%%", items_block)
        .replace("%%TRANSCRIPT%%", transcript)
        .replace("%%SCHEMA%%", schema)
    )


# Inline fallback templates (used only if the prompt files are missing).
_INLINE_TEMPLATE = {
    "en": (
        "You are evaluating a multi-party discussion. Read the WHOLE transcript below and rate "
        "each item with an integer from 1 to %%SCALE%% (%%SCALE%% = best).\n\n"
        "## Items\n%%ITEMS%%\n\n## Transcript\n%%TRANSCRIPT%%\n\n"
        'Respond with ONLY this JSON (no prose):\n{"scores": {%%SCHEMA%%}, "rationale": {<each item key>: "brief reason"}}'
    ),
    "ja": (
        "あなたは多人数議論の評価者です。以下の議論ログ全体を読み、各項目を1〜%%SCALE%%の整数で"
        "採点してください（%%SCALE%%が最良）。\n\n"
        "## 評価項目\n%%ITEMS%%\n\n## 議論ログ\n%%TRANSCRIPT%%\n\n"
        '次のJSON形式のみで回答してください（説明文は不要）:\n{"scores": {%%SCHEMA%%}, "rationale": {<各項目キー>: "短い理由"}}'
    ),
}


# --- LLM providers ---------------------------------------------------------


def _call_openai(prompt: str, config: dict[str, Any]) -> str:
    """Call an OpenAI / OpenAI-compatible chat model / OpenAI互換モデルを呼ぶ."""
    from openai import OpenAI  # lazy import so `mock` works without the dep

    api_key = os.environ.get(str(config.get("api_key_env", "OPENAI_API_KEY")), "")
    base_url = config.get("base_url") or None
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=str(config.get("model", "gpt-4o")),
        temperature=float(config.get("temperature", 0.0)),
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


def _call_mock(prompt: str, config: dict[str, Any]) -> str:  # noqa: ARG001
    """Deterministic offline stand-in (for testing without an API) / テスト用モック."""
    scale = int(config.get("scale", 5))
    keys = [it["key"] for it in (config.get("items") or [])]
    mid = (scale + 1) // 2
    scores = {k: mid for k in keys}
    return json.dumps({"scores": scores, "rationale": {k: "mock" for k in keys}})


def _llm_call(prompt: str, config: dict[str, Any]) -> str:
    provider = str(config.get("provider", "openai")).lower()
    if provider == "mock":
        return _call_mock(prompt, config)
    if provider in ("openai", "vllm", "openai-compatible"):
        return _call_openai(prompt, config)
    msg = f"unsupported judge provider: {provider} (use openai | mock)"
    raise ValueError(msg)


def _parse_scores(raw: str, keys: list[str], scale: int) -> dict[str, Any]:
    """Leniently parse {scores, rationale} JSON from the model reply / 寛容にJSON抽出."""
    import re

    for m in re.finditer(r"\{.*\}", raw, flags=re.DOTALL):
        try:
            obj = json.loads(m.group(0))
        except (ValueError, TypeError):
            continue
        scores = obj.get("scores") if isinstance(obj, dict) else None
        if isinstance(scores, dict):
            clean = {}
            for k in keys:
                v = scores.get(k)
                try:
                    iv = int(round(float(v)))
                    clean[k] = max(1, min(scale, iv))
                except (TypeError, ValueError):
                    clean[k] = None
            return {"scores": clean, "rationale": obj.get("rationale", {})}
    return {"scores": {k: None for k in keys}, "rationale": {}}


def judge_game(result: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Score one game's whole transcript on the configured items / 1ゲームを採点する."""
    keys = [it["key"] for it in (config.get("items") or [])]
    scale = int(config.get("scale", 5))
    repeats = max(1, int(config.get("repeats", 1)))
    transcript = build_transcript_text(result)
    if not transcript.strip():
        return {"scores": {k: None for k in keys}, "rationale": {}, "n": 0}
    prompt = _rubric_prompt(transcript, config)
    sums: dict[str, list[int]] = {k: [] for k in keys}
    last_rationale: dict[str, Any] = {}
    for _ in range(repeats):
        parsed = _parse_scores(_llm_call(prompt, config), keys, scale)
        last_rationale = parsed.get("rationale", {})
        for k in keys:
            v = parsed["scores"].get(k)
            if isinstance(v, int):
                sums[k].append(v)
    scores = {k: (sum(v) / len(v) if v else None) for k, v in sums.items()}
    return {"scores": scores, "rationale": last_rationale, "n": repeats}


def main() -> None:
    """CLI: subjective-only scoring over a results dir / 主観採点のみのCLI."""
    parser = argparse.ArgumentParser(description="Subjective LLM-judge over game result JSONs")
    parser.add_argument("results_dir", type=str)
    parser.add_argument("-c", "--config", type=str, default=str(DEFAULT_CONFIG))
    parser.add_argument("-o", "--out", type=str, default=None)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    results_dir = Path(args.results_dir)
    out_dir = Path(args.out) if args.out else results_dir / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for fp in sorted(results_dir.glob("*.json")):
        with fp.open(encoding="utf-8") as f:
            result = json.load(f)
        sj = judge_game(result, config)
        rows.append({"game_id": result.get("game_id"), "condition": result.get("condition"), **sj})
        logger.info("judged %s -> %s", result.get("game_id"), sj["scores"])
    with (out_dir / "judge.json").open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    logger.info("wrote %s", out_dir / "judge.json")


if __name__ == "__main__":
    main()
