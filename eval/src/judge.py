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
    rows = result.get("transcript")
    if not rows and result.get("entries"):
        # aiwolf raw server log ({agents, entries, ...}): extract TALK utterances into transcript rows.
        rows = []
        for e in result.get("entries", []):
            resp = (e.get("response") or "").strip()
            if not resp or resp.lower() in ("over", "skip"):
                continue
            req = e.get("request")
            try:
                pkt = json.loads(req) if isinstance(req, str) else (req or {})
                if str(pkt.get("request", "")).upper() != "TALK":
                    continue
                day = int((pkt.get("info") or {}).get("day", 0))
            except (ValueError, TypeError):
                continue
            rows.append({"day": day, "agent": e.get("agent", "?"), "text": resp})
    for t in rows or []:
        rnd = t.get("day")
        agent = t.get("agent", "?")
        text = (t.get("text") or "").strip()
        if not text:
            continue
        prefix = f"(r{rnd}) " if rnd is not None else ""
        lines.append(f"{prefix}{agent}: {text}")
    return "\n".join(lines)


# The judge prompt skeleton is managed as per-language files (same convention as the agent and
# the generator): eval/prompts/<lang>/judge.txt with %%SCALE%% / %%ITEMS%% / %%TRANSCRIPT%% /
# %%SCHEMA%% tokens. Language dirs are en / jp; `ja` is accepted as an alias for jp.
# 判定プロンプトも言語別ファイルで管理: eval/prompts/<lang>/judge.txt（en/jp。ja は jp の別名）。
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _lang_dir(config: dict[str, Any]) -> str:
    """Normalize the configured language to a prompt dir name (en | jp) / 言語をディレクトリ名へ正規化."""
    return "jp" if str(config.get("lang", "en")).lower() in ("ja", "jp") else "en"


def _rubric_prompt(transcript: str, config: dict[str, Any]) -> str:
    """Build the judge prompt from the per-language template file / テンプレファイルから構築."""
    lang = str(config.get("lang", "en")).lower()
    lang_dir = _lang_dir(config)
    scale = int(config.get("scale", 5))
    items = config.get("items") or []
    # Item labels may be keyed by the configured lang, jp, ja, or en — fall back through all.
    items_block = "\n".join(
        f'- "{it["key"]}": {it.get(lang) or it.get("jp") or it.get("ja") or it.get("en") or it["key"]}'
        for it in items
    )
    keys = [it["key"] for it in items]
    schema = ", ".join(f'"{k}": <1-{scale}>' for k in keys)

    template_path = _PROMPTS_DIR / lang_dir / "judge.txt"
    template = (
        template_path.read_text(encoding="utf-8") if template_path.is_file() else _INLINE_TEMPLATE[lang_dir]
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
        "Respond with ONLY this JSON (no prose):\n"
        '{"scores": {%%SCHEMA%%}, "rationale": {<each item key>: "brief reason"}}'
    ),
    "jp": (
        "あなたは多人数議論の評価者です。以下の議論ログ全体を読み、各項目を1〜%%SCALE%%の整数で"
        "採点してください（%%SCALE%%が最良）。\n\n"
        "## 評価項目\n%%ITEMS%%\n\n## 議論ログ\n%%TRANSCRIPT%%\n\n"
        "次のJSON形式のみで回答してください（説明文は不要）:\n"
        '{"scores": {%%SCHEMA%%}, "rationale": {<各項目キー>: "短い理由"}}'
    ),
}


# --- LLM providers ---------------------------------------------------------


# Default local endpoints for OpenAI-compatible servers (used when base_url is unset).
_VLLM_DEFAULT_BASE_URL = "http://localhost:8000/v1"
_OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"
# Models that REJECT sampling params (temperature) with a 400 (drop temperature for these).
_NO_SAMPLING_PREFIXES = (
    "claude-opus-4-8", "claude-opus-4-7", "claude-fable-5", "claude-mythos-5",
    "o1", "o3", "o4", "gpt-5",
)
# max_tokens for the (short) JSON judge reply; anthropic requires it explicitly.
_JUDGE_MAX_TOKENS = 1024


def _drops_sampling(model: str) -> bool:
    """Return whether ``model`` rejects sampling params / サンプリング拒否モデルか."""
    return any(model.startswith(p) for p in _NO_SAMPLING_PREFIXES)


def _call_openai(prompt: str, config: dict[str, Any], base_url: str | None) -> str:
    """Call an OpenAI / OpenAI-compatible chat model (OpenAI / vLLM / Ollama / local)."""
    from openai import OpenAI  # lazy import so `mock` works without the dep

    api_key = os.environ.get(str(config.get("api_key_env", "OPENAI_API_KEY"))) or (
        "EMPTY" if base_url else ""
    )
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    model = str(config.get("model", "gpt-4o"))
    kwargs: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if not _drops_sampling(model):
        kwargs["temperature"] = float(config.get("temperature", 0.0))
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _call_anthropic(prompt: str, config: dict[str, Any]) -> str:
    """Call a Claude model via the anthropic SDK / Claude を呼ぶ."""
    import anthropic  # lazy import

    api_key = os.environ.get(str(config.get("api_key_env", "ANTHROPIC_API_KEY")), "")
    client = anthropic.Anthropic(api_key=api_key)
    model = str(config.get("model", "claude-opus-4-8"))
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": int(config.get("max_tokens", _JUDGE_MAX_TOKENS)),
        "messages": [{"role": "user", "content": prompt}],
    }
    if not _drops_sampling(model):
        kwargs["temperature"] = float(config.get("temperature", 0.0))
    msg = client.messages.create(**kwargs)
    return "".join(b.text for b in msg.content if b.type == "text")


def _call_google(prompt: str, config: dict[str, Any]) -> str:
    """Call a Gemini / Gemma model via google-genai / Gemini・Gemma を呼ぶ."""
    from google import genai  # lazy import

    api_key = os.environ.get(str(config.get("api_key_env", "GOOGLE_API_KEY")), "")
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=str(config.get("model", "gemini-2.5-pro")),
        contents=prompt,
        config={
            "temperature": float(config.get("temperature", 0.0)),
            "max_output_tokens": int(config.get("max_tokens", _JUDGE_MAX_TOKENS)),
        },
    )
    return resp.text or ""


def _call_mock(prompt: str, config: dict[str, Any]) -> str:  # noqa: ARG001
    """Deterministic offline stand-in (for testing without an API) / テスト用モック."""
    scale = int(config.get("scale", 5))
    keys = [it["key"] for it in (config.get("items") or [])]
    mid = (scale + 1) // 2
    scores = dict.fromkeys(keys, mid)
    return json.dumps({"scores": scores, "rationale": dict.fromkeys(keys, "mock")})


def _llm_call(prompt: str, config: dict[str, Any]) -> str:
    """Dispatch to the configured judge provider / 設定された judge プロバイダに振り分け.

    Any provider/model works (kept consistent with the generator). GPT is the default judge
    family (METHODOLOGY L3 — separate from the Claude generator and Gemma discussion agent).
    どのプロバイダでも可。既定は GPT（生成器Claude・議論Gemma と系列分離）。
    """
    provider = str(config.get("provider", "openai")).lower()
    base_url = config.get("base_url") or None
    if provider == "mock":
        return _call_mock(prompt, config)
    if provider == "anthropic":
        return _call_anthropic(prompt, config)
    if provider == "google":
        return _call_google(prompt, config)
    if provider in ("openai", "openai-compatible"):
        return _call_openai(prompt, config, base_url)
    if provider == "vllm":
        return _call_openai(prompt, config, base_url or _VLLM_DEFAULT_BASE_URL)
    if provider == "ollama":
        return _call_openai(prompt, config, base_url or _OLLAMA_DEFAULT_BASE_URL)
    msg = f"unsupported judge provider: {provider} (use anthropic | openai | vllm | ollama | google | mock)"
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
                    iv = round(float(v))
                    clean[k] = max(1, min(scale, iv))
                except (TypeError, ValueError):
                    clean[k] = None
            return {"scores": clean, "rationale": obj.get("rationale", {})}
    return {"scores": dict.fromkeys(keys), "rationale": {}}


def judge_game(result: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Score one game's whole transcript on the configured items / 1ゲームを採点する."""
    keys = [it["key"] for it in (config.get("items") or [])]
    scale = int(config.get("scale", 5))
    repeats = max(1, int(config.get("repeats", 1)))
    transcript = build_transcript_text(result)
    if not transcript.strip():
        return {"scores": dict.fromkeys(keys), "rationale": {}, "n": 0}
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
