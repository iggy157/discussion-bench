"""LLM model builder shared between Agent and offline scripts (prewarm, etc).

Agent / オフラインスクリプト (prewarm 等) の両方から使える LLM モデル生成ユーティリティ.
config の provider セクション (openai / google / vertexai / ollama / anthropic) と
ロール別 overrides (llm.talk / llm.action) を受け取り, LangChain の Runnable インスタンスと
料金計算用メタ情報を返す.
"""

from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING, Any

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from utils.anthropic_cache import apply_cache_control

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage
    from langchain_core.runnables import Runnable

# llm.* / llm.talk.* / llm.action.* の中で「provider セクションを上書きする」設定.
# これ以外のキーはロール制御用 (provider/type, sleep_time, separate_langchain, talk, action) か
# 明示的に禁止するキー (api_key) のどちらか.
# api_key_env はキーそのものではなく「環境変数名」なので上書き対象として許可する.
LLM_OVERRIDE_KEYS: tuple[str, ...] = ("model", "temperature", "pricing_mode", "base_url", "api_key_env")

# Default endpoint for the vllm provider when ``base_url`` is not set (local OpenAI-compatible).
_VLLM_DEFAULT_BASE_URL = "http://localhost:8000/v1"
# Default env var holding the API key per provider. Overridable with ``api_key_env`` in the
# config (consistent with the generator / eval-judge configs). vertexai uses GCP ADC (no key);
# ollama is local (no key).
_DEFAULT_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "vllm": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def extract_llm_overrides(
    role_cfg: dict[str, Any],
    *,
    role_name: str,
) -> dict[str, Any]:
    """Extract override fields from an ``llm.*`` / ``llm.talk.*`` / ``llm.action.*`` block.

    config の該当ブロックから <provider> セクションを上書きする項目を抜き出す.
    セキュリティ上の事故防止のため, api_key がここに置かれたら明示的にエラーにする.

    Args:
        role_cfg (dict[str, Any]): llm.* / llm.talk.* / llm.action.* のブロック.
        role_name (str): エラーメッセージで使うロール名 ("talk" / "action" / "").

    Returns:
        dict[str, Any]: provider セクションを上書きする項目のみ抽出した辞書.

    Raises:
        ValueError: api_key が含まれている場合.
    """
    if "api_key" in role_cfg:
        msg = (
            f"api_key must not be set in llm.{role_name}; "
            "use environment variables (OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY) instead."
        )
        raise ValueError(msg)
    return {k: role_cfg[k] for k in LLM_OVERRIDE_KEYS if k in role_cfg}


def build_llm_model(  # noqa: C901, PLR0911  (one branch per LLM provider; N-way dispatch)
    provider: str,
    provider_section: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> tuple[Runnable[Any, BaseMessage], dict[str, str]]:
    """Create an LLM model instance + cost metadata.

    Args:
        provider (str): プロバイダタイプ (openai / google / vertexai / ollama / anthropic).
        provider_section (dict[str, Any]): config のトップレベル <provider>: ブロック.
        overrides (dict[str, Any] | None): llm.*.<provider override keys> で上書きする項目.

    Returns:
        tuple[Runnable[Any, BaseMessage], dict[str, str]]: (LLM インスタンスまたは
            ラップ済み Runnable, メタ辞書). メタは {provider_key, model_id, pricing_mode} を持つ.
            anthropic で ``cache: true`` (default) のときは ``apply_cache_control`` を
            前段に挟んだ ``RunnableSequence`` を返す.
    """
    section: dict[str, Any] = {**(provider_section or {}), **(overrides or {})}
    pricing_mode = str(section.get("pricing_mode", "standard"))
    model_id = str(section.get("model", ""))
    meta = {"provider_key": provider, "model_id": model_id, "pricing_mode": pricing_mode}
    match provider:
        case "openai":
            # base_url lets a vLLM / Ollama / any OpenAI-compatible server be used via the
            # openai provider. Local servers often need no key, so fall back to a placeholder
            # when base_url is set and the key env is unset.
            base_url = section.get("base_url")
            key_env = str(section.get("api_key_env") or _DEFAULT_KEY_ENV["openai"])
            api_key = os.environ.get(key_env) or ("EMPTY" if base_url else None)
            if api_key is None:
                msg = f"{key_env} is not set (required for provider 'openai' without base_url)"
                raise KeyError(msg)
            openai_kwargs: dict[str, Any] = {
                "model": model_id,
                "temperature": float(section["temperature"]),
                "api_key": SecretStr(api_key),
            }
            if base_url:
                openai_kwargs["base_url"] = str(base_url)
            return (ChatOpenAI(**openai_kwargs), meta)
        case "vllm":
            # vLLM speaks the OpenAI-compatible API. Default to the local vLLM endpoint and a
            # placeholder key (most local servers don't authenticate); OPENAI_API_KEY overrides
            # the key if your server requires one. `model` is the served model name (e.g.
            # google/gemma-2-27b-it); `base_url` overrides the endpoint.
            vllm_base_url = str(section.get("base_url") or _VLLM_DEFAULT_BASE_URL)
            vllm_key_env = str(section.get("api_key_env") or _DEFAULT_KEY_ENV["vllm"])
            vllm_api_key = os.environ.get(vllm_key_env) or "EMPTY"
            return (
                ChatOpenAI(
                    model=model_id,
                    temperature=float(section["temperature"]),
                    api_key=SecretStr(vllm_api_key),
                    base_url=vllm_base_url,
                ),
                meta,
            )
        case "google":
            google_key_env = str(section.get("api_key_env") or _DEFAULT_KEY_ENV["google"])
            return (
                ChatGoogleGenerativeAI(
                    model=model_id,
                    temperature=float(section["temperature"]),
                    api_key=SecretStr(os.environ[google_key_env]),
                ),
                meta,
            )
        case "vertexai":
            return (
                ChatGoogleGenerativeAI(
                    model=model_id,
                    temperature=float(section["temperature"]),
                    vertexai=True,
                ),
                meta,
            )
        case "ollama":
            return (
                ChatOllama(
                    model=model_id,
                    temperature=float(section["temperature"]),
                    base_url=str(section["base_url"]),
                ),
                meta,
            )
        case "anthropic":
            # Key env defaults to ANTHROPIC_API_KEY (the SDK default, consistent with
            # OPENAI_API_KEY / GOOGLE_API_KEY in the single root .env); overridable via api_key_env.
            anthropic_key_env = str(section.get("api_key_env") or _DEFAULT_KEY_ENV["anthropic"])
            anthropic_key = os.environ.get(anthropic_key_env)
            if not anthropic_key:
                msg = f"{anthropic_key_env} is not set for provider 'anthropic'"
                raise KeyError(msg)
            anthropic_model = ChatAnthropic(
                model_name=model_id,
                temperature=float(section["temperature"]),
                timeout=None,
                stop=None,
                api_key=SecretStr(anthropic_key),
            )
            cache_enabled = bool(provider_section.get("cache", True))
            cache_ttl = str(provider_section.get("cache_ttl", "5m"))
            if not cache_enabled:
                return (anthropic_model, meta)
            cache_injector = RunnableLambda(partial(apply_cache_control, ttl=cache_ttl))
            return (cache_injector | anthropic_model, meta)
        case _:
            raise ValueError(provider, "Unknown LLM type")
