"""LLM backends for the exemplar generator.

手本ジェネレータの LLM バックエンド.

Any provider/model can be selected; Claude is the *principled default* (METHODOLOGY L3 —
script/analysis generation should come from a different model family than the Gemma discussion
agent and the GPT judge), but the pipeline runs on whatever is configured.

Backends:
- ``anthropic`` — Claude via the official ``anthropic`` SDK (adaptive thinking).
- ``openai`` / ``vllm`` / ``ollama`` — any OpenAI-compatible endpoint via the ``openai`` SDK.
  ``vllm``/``ollama`` default to local base URLs and a placeholder key. This is how you run a
  Gemma (or any) model served by vLLM or Ollama.
- ``google`` — Gemini / Gemma via the Google ``google-genai`` SDK.
- ``mock`` — offline, returns parseable canned scripts (no API budget).

Optional SDKs (``openai``, ``google-genai``) are imported lazily, so a missing one only fails
if you actually select that backend.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Default local endpoints for OpenAI-compatible servers (used when base_url is unset).
_VLLM_DEFAULT_BASE_URL = "http://localhost:8000/v1"
_OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"
# Placeholder key for local servers that don't authenticate.
_LOCAL_PLACEHOLDER_KEY = "EMPTY"
# OpenAI reasoning-model prefixes that reject ``temperature`` and use ``max_completion_tokens``.
_OPENAI_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")

# Models that REJECT sampling params (temperature/top_p/top_k) with a 400.
# Opus 4.7/4.8 and Fable/Mythos 5 — adaptive thinking only. (claude-api skill, 2026-06.)
_NO_SAMPLING_PREFIXES = (
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-fable-5",
    "claude-mythos-5",
)
# Floor for full-transcript generation; scripts truncate badly at the 4096 analysis cap.
_SCRIPT_MAX_TOKENS_FLOOR = 16000


def _drops_sampling(model: str) -> bool:
    """Return whether ``model`` rejects temperature/top_p/top_k.

    モデルがサンプリングパラメータを拒否する (400) かどうかを返す.
    """
    return any(model.startswith(p) for p in _NO_SAMPLING_PREFIXES)


class Provider(ABC):
    """Abstract text-generation backend.

    テキスト生成バックエンドの抽象基底.
    """

    @abstractmethod
    def generate(self, *, system: str, user: str, max_tokens: int, effort: str) -> str:
        """Generate a single completion.

        1 回の生成を実行して本文テキストを返す.

        Args:
            system: System prompt.
            user: User message body.
            max_tokens: Output token cap.
            effort: Reasoning effort (``low`` | ``medium`` | ``high`` | ``xhigh`` | ``max``).

        Returns:
            The concatenated text of the response.
        """


class AnthropicProvider(Provider):
    """Claude backend via the official ``anthropic`` SDK.

    公式 ``anthropic`` SDK 経由の Claude バックエンド.

    Notes:
        - Reads the key from ``api_key_env`` (default ``ANTHROPIC_API_KEY``, the SDK default).
        - Uses adaptive thinking + ``output_config.effort`` (the only supported thinking mode
          on Opus 4.7/4.8). ``temperature`` is omitted for models that reject it.
        - Streams the request (recommended for long / high-``max_tokens`` output) and returns
          the final accumulated message text.
    """

    def __init__(self, model: str, temperature: float, api_key_env: str) -> None:
        """Construct the Claude client.

        Claude クライアントを構築する.

        Args:
            model: Model id (e.g. ``claude-opus-4-8``).
            temperature: Requested temperature (ignored for no-sampling models).
            api_key_env: Env var holding the API key.
        """
        import anthropic  # noqa: PLC0415  (optional dep; only needed for the real backend)

        api_key = os.environ.get(api_key_env)
        if not api_key:
            msg = f"{api_key_env} is not set (copy ../.env.example to ../.env and fill it in)"
            raise RuntimeError(msg)
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._drops_sampling = _drops_sampling(model)
        if self._drops_sampling and temperature is not None:
            logger.info(
                "model %s rejects sampling params; ignoring temperature=%s",
                model,
                temperature,
            )

    def generate(self, *, system: str, user: str, max_tokens: int, effort: str) -> str:
        """See :meth:`Provider.generate`."""
        # We always use adaptive thinking, under which the Anthropic API requires temperature
        # to be unset (or exactly 1) — so temperature is never sent for this backend.
        kwargs: dict[str, object] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }

        with self._client.messages.stream(**kwargs) as stream:  # type: ignore[arg-type]
            message = stream.get_final_message()

        if message.stop_reason == "refusal":
            msg = "Claude refused the generation request (stop_reason=refusal)"
            raise RuntimeError(msg)

        # Log real token usage (output_tokens INCLUDES thinking) so cost can be measured.
        u = getattr(message, "usage", None)
        if u is not None:
            logging.getLogger("provider").info(
                "USAGE model=%s in=%s cache_read=%s cache_write=%s out=%s",
                self._model, getattr(u, "input_tokens", "?"),
                getattr(u, "cache_read_input_tokens", 0), getattr(u, "cache_creation_input_tokens", 0),
                getattr(u, "output_tokens", "?"))

        parts = [block.text for block in message.content if block.type == "text"]
        return "".join(parts).strip()


class OpenAICompatProvider(Provider):
    """OpenAI-compatible backend: OpenAI, vLLM, Ollama, or any local server.

    OpenAI 互換バックエンド: OpenAI / vLLM / Ollama / 任意のローカルサーバ.

    Notes:
        - ``base_url`` selects the endpoint (None = api.openai.com). vLLM/Ollama set their own.
        - For a custom ``base_url`` (local server) the API key is optional; a placeholder is
          used when the env var is unset, so unauthenticated local servers work.
        - For real OpenAI reasoning models (o1/o3/o4/gpt-5) ``temperature`` is dropped and
          ``max_completion_tokens`` is used; everything else uses ``temperature`` + ``max_tokens``
          (the form vLLM/Ollama expect).
    """

    def __init__(self, model: str, temperature: float, api_key: str | None, base_url: str | None) -> None:
        """Construct the OpenAI-compatible client.

        OpenAI 互換クライアントを構築する.

        Args:
            model: Model id (e.g. ``gpt-4o``, ``gemma2:27b``, a vLLM-served name).
            temperature: Sampling temperature.
            api_key: API key (placeholder allowed for local servers).
            base_url: Endpoint override, or None for api.openai.com.
        """
        from openai import OpenAI  # noqa: PLC0415  (optional dep; only for this backend)

        if not api_key:
            if base_url is None:
                msg = "OpenAI API key is missing (set the configured api_key_env, e.g. OPENAI_API_KEY)"
                raise RuntimeError(msg)
            api_key = _LOCAL_PLACEHOLDER_KEY  # local server without auth
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature
        self._is_reasoning = base_url is None and any(model.startswith(p) for p in _OPENAI_REASONING_PREFIXES)

    def generate(self, *, system: str, user: str, max_tokens: int, effort: str) -> str:  # noqa: ARG002
        """See :meth:`Provider.generate`. ``effort`` is ignored (OpenAI-compatible APIs)."""
        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self._is_reasoning:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = self._temperature

        resp = self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
        return (resp.choices[0].message.content or "").strip()


class GoogleProvider(Provider):
    """Gemini / Gemma backend via the Google ``google-genai`` SDK.

    Google ``google-genai`` SDK 経由の Gemini / Gemma バックエンド.
    """

    def __init__(self, model: str, temperature: float, api_key: str | None) -> None:
        """Construct the Google GenAI client.

        Google GenAI クライアントを構築する.

        Args:
            model: Model id (e.g. ``gemini-2.5-pro``, ``gemma-3-27b-it``).
            temperature: Sampling temperature.
            api_key: API key (e.g. from ``GOOGLE_API_KEY``).
        """
        from google import genai  # noqa: PLC0415  (optional dep; only for this backend)

        if not api_key:
            msg = "Google API key is missing (set the configured api_key_env, e.g. GOOGLE_API_KEY)"
            raise RuntimeError(msg)
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def generate(self, *, system: str, user: str, max_tokens: int, effort: str) -> str:  # noqa: ARG002
        """See :meth:`Provider.generate`. ``effort`` is ignored (Google API)."""
        resp = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config={
                "system_instruction": system,
                "temperature": self._temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return (resp.text or "").strip()


class MockProvider(Provider):
    """Offline backend that returns canned, parseable scripts.

    API を使わずに解析可能なダミー台本を返すオフラインバックエンド.

    Used to exercise the slice/write pipeline (``provider: mock`` in the config).
    """

    def generate(self, *, system: str, user: str, max_tokens: int, effort: str) -> str:  # noqa: ARG002
        """Return a canned script or analysis based on a marker in ``user``."""
        if "[[MOCK_KIND=aiwolf_script]]" in user:
            return _MOCK_AIWOLF_SCRIPT
        if "[[MOCK_KIND=hiddenbench_script]]" in user:
            return _MOCK_HIDDENBENCH_SCRIPT
        return _MOCK_ANALYSIS


def build_provider(
    provider: str,
    model: str,
    temperature: float,
    api_key_env: str,
    base_url: str | None,
) -> Provider:
    """Construct the configured provider.

    設定されたプロバイダを構築する.

    Args:
        provider: ``anthropic`` | ``openai`` | ``vllm`` | ``ollama`` | ``google`` | ``mock``.
        model: Model id.
        temperature: Requested temperature.
        api_key_env: Env var holding the API key.
        base_url: OpenAI-compatible endpoint override (or None).

    Returns:
        A :class:`Provider` instance.
    """
    if provider == "mock":
        return MockProvider()
    if provider == "anthropic":
        return AnthropicProvider(model=model, temperature=temperature, api_key_env=api_key_env)
    if provider == "google":
        return GoogleProvider(model=model, temperature=temperature, api_key=os.environ.get(api_key_env))
    # OpenAI-compatible family: openai (api.openai.com) / vllm / ollama (local defaults).
    if provider == "vllm":
        base_url = base_url or _VLLM_DEFAULT_BASE_URL
    elif provider == "ollama":
        base_url = base_url or _OLLAMA_DEFAULT_BASE_URL
    return OpenAICompatProvider(
        model=model,
        temperature=temperature,
        api_key=os.environ.get(api_key_env),
        base_url=base_url,
    )


def script_max_tokens(config_max_tokens: int) -> int:
    """Return the max_tokens floor for full-transcript generation.

    台本 (全文) 生成用の max_tokens 下限を返す. config 値が小さくても床を保証する.
    """
    return max(config_max_tokens, _SCRIPT_MAX_TOKENS_FLOOR)


_MOCK_AIWOLF_SCRIPT = """# サンプル対局 mock_5 (5人村)

## 役職配置
| ID | 名前 | 役職 |
|----|------|------|
| 1 | アオイ | VILLAGER |
| 2 | ハルト | WEREWOLF |
| 3 | ミナ | SEER |
| 4 | リク | POSSESSED |
| 5 | ソラ | VILLAGER |

## 0日目

### トーク
#### Turn 0
- **アオイ**: アオイです、よろしくお願いします。まず情報整理の方針を決めませんか。
- **ハルト**: ハルトです。落ち着いていきましょう。
- **ミナ**: ミナです。明日朝に占い結果を共有する前提で進めたいです。
- **リク**: リクです。賛成ですが、急ぎすぎないようにしたいですね。
- **ソラ**: ソラです。よろしくお願いします。

## 1日目

### トーク
#### Turn 0
- **ミナ**: 占い師COします。ハルトを占い、人狼判定が出ました。根拠も共有します。
- **リク**: 私も占い師です。ミナの結果には疑問があります。
- **アオイ**: 二者の占いCOですね。両者の根拠を順に比較しましょう、結論を急がずに。
- **ソラ**: 反対意見も残しておきたいです。リクの主張にも一理あります。
- **ハルト**: 私は人狼ではありません。投票前にもう一度整理させてください。
#### Turn 3
- **アオイ**: 比較の結果、私は @ハルト に投票します。
- **ソラ**: 私はまだ迷いがありますが @ハルト に投票します。
- **ミナ**: 結果通り @ハルト に投票します。
- **リク**: 私は @ミナ に投票します。
- **ハルト**: 私は @ミナ に投票します。
"""

_MOCK_HIDDENBENCH_SCRIPT = """# Mock HiddenBench Discussion

## Task
A four-person team must choose one option using distributed information.

## Pre-answers
- **Agent 1**: {"vote": "Option A", "rationale": "Based on my piece only."}
- **Agent 2**: {"vote": "Option B", "rationale": "Based on my piece only."}
- **Agent 3**: {"vote": "Option A", "rationale": "Based on my piece only."}
- **Agent 4**: {"vote": "Option C", "rationale": "Based on my piece only."}

## Round 1
- **Agent 1**: I hold a fact the others may not: the bridge route is currently closed.
- **Agent 2**: I did not know that. I have a different fact: the tunnel reopened today.
- **Agent 3**: Let me state my private detail before we converge on anything.
- **Agent 4**: I disagree with jumping to a conclusion; let us surface every fact first.

## Round 2
- **Agent 1**: Combining all four pieces, only one option remains consistent.
- **Agent 2**: I still want to double-check the minority view before agreeing.
- **Agent 3**: That check is fair; here is why the remaining option holds.
- **Agent 4**: Agreed, now that all hidden facts are on the table.

## Post-answers
- **Agent 1**: {"vote": "Option C", "rationale": "After pooling all hidden facts."}
- **Agent 2**: {"vote": "Option C", "rationale": "After pooling all hidden facts."}
- **Agent 3**: {"vote": "Option C", "rationale": "After pooling all hidden facts."}
- **Agent 4**: {"vote": "Option C", "rationale": "After pooling all hidden facts."}
"""

_MOCK_ANALYSIS = """# Analysis (where to look)

- A good discussion surfaces each participant's private information early, before any
  convergence happens.
- Multiple hypotheses are compared on their merits rather than the first proposal winning.
- Minority and dissenting views are voiced and acknowledged, not pressured into agreement.
- Phrasing varies across turns; speakers build on one prior point and add their own basis.
"""
