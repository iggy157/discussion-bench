"""Translate a markdown file to Japanese (for human review) via a local gemma endpoint.

Used to produce JA review copies of the ENGLISH analysis that is actually injected at run time.
Faithful translation only — no summarizing, no commentary.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from openai import OpenAI

PROMPT = ("以下の英語のテキストを、意味を変えず・要約せず・省略せず、自然な日本語に翻訳してください。"
          "見出しや箇条書きの構造はそのまま保ち、翻訳した本文だけを返してください（前置き不要）。\n\n"
          "--- 原文ここから ---\n{text}\n--- 原文ここまで ---")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--model", default="gemma-4-31b")
    p.add_argument("--src", required=True, help="English .md file")
    p.add_argument("--out", required=True, help="Japanese .md output")
    p.add_argument("--max-tokens", type=int, default=2560, help="raise for long scripts to avoid truncation")
    args = p.parse_args()
    text = Path(args.src).read_text(encoding="utf-8")
    client = OpenAI(base_url=f"http://localhost:{args.port}/v1", api_key="EMPTY")
    r = client.chat.completions.create(model=args.model,
                                       messages=[{"role": "user", "content": PROMPT.format(text=text)}],
                                       temperature=0.0, max_tokens=args.max_tokens)
    ja = r.choices[0].message.content or ""
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(ja + "\n", encoding="utf-8")
    print(f"  translated {args.src} -> {args.out} ({len(ja)} chars)")


if __name__ == "__main__":
    main()
