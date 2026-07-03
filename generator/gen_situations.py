"""Generate situation-keyed few-shot exemplars via gemma (vLLM, OpenAI-compatible API).

中立な「場面ラベル」ごとに、話題非依存の良い発話例を gemma に生成させ、
agent/<pack>/exemplars/<lang>/situations/ に書き出す。状況キーは"処方箋"でなく中立な場面のみ
（分析は別因子=共通analysisに分離）。L2維持のため特定話題・固有名詞・正解に触れさせない。

Usage:
    python generator/gen_situations.py --lang en [--n 4] [--model gemma-4-31b] \
        [--endpoint http://127.0.0.1:8000/v1]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Neutral scene labels per language (NOT prescriptive — the principle/analysis is a separate factor).
SITUATIONS = {
    "jp": {
        "hidden-bench": [
            ("01", "自分だけが持っている情報を場に出す時"),
            ("02", "結論が早くまとまりかけている時"),
            ("03", "多数派と違う考えを持っている時"),
            ("04", "前提が崩れた／情報が食い違った時"),
            ("05", "結論を出す直前に全体を整理する時"),
        ],
        "aiwolf": [
            ("01", "役職や手がかりなど私的情報を開示する時"),
            ("02", "誰かの主張に矛盾を感じた時"),
            ("03", "多数派の流れに疑問を持った時"),
            ("04", "少数意見・反論が出た時"),
            ("05", "投票や結論の直前に状況を整理する時"),
        ],
    },
    "en": {
        "hidden-bench": [
            ("01", "When you hold information no one else has"),
            ("02", "When the group is converging on an answer too quickly"),
            ("03", "When you disagree with the majority"),
            ("04", "When an assumption breaks or information conflicts"),
            ("05", "When summarizing the whole picture before concluding"),
            ("06", "When eliminating options against the constraints (process of elimination)"),
            ("07", "When raising an alternative hypothesis to test"),
            ("08", "When reconciling two pieces of conflicting evidence"),
            ("09", "When asking a clarifying or probing question"),
            ("10", "When acknowledging and building on someone else's point"),
        ],
        "aiwolf": [
            ("01", "When disclosing private information (your role or a clue)"),
            ("02", "When you sense a contradiction in someone's claim"),
            ("03", "When you doubt the direction the majority is taking"),
            ("04", "When a minority opinion or rebuttal is raised"),
            ("05", "When organizing the situation just before a vote or conclusion"),
            ("06", "When checking a claim against someone's earlier statements (consistency)"),
            ("07", "When weighing an emotional appeal against objective evidence"),
            ("08", "When asking someone to give grounds for their claim"),
            ("09", "When weighing probabilistic plausibility against logical possibility"),
            ("10", "When proposing who to investigate or vote for, with reasoning"),
        ],
    },
}


def _prompt(lang: str, scene: str, n: int) -> str:
    if lang == "jp":
        return (
            "あなたは多人数の議論の良い手本データを作成しています。\n"
            f"次の『場面』で、良い参加者が言いそうな短い発言例を{n}個、日本語で挙げてください。\n\n"
            f"場面: {scene}\n\n制約:\n"
            "- 特定の話題・固有名詞・正解・タスク内容には一切触れない（どんな議題でも通用する一般的な言い回し）。\n"
            "- 各発言は1〜2文で簡潔に。説明や前置きは不要、発言そのものだけ。\n"
            "- 箇条書き（- ）で発言だけを出力する。"
        )
    return (
        "You are creating reference data of GOOD multi-party discussion.\n"
        f"For the scene below, list {n} short example utterances a good participant might say, in English.\n\n"
        f"Scene: {scene}\n\nConstraints:\n"
        "- Do NOT mention any specific topic, proper nouns, answers, or task content "
        "(use general phrasings usable in ANY discussion).\n"
        "- Each utterance is 1-2 sentences, concise. No preamble or explanation — just the utterances.\n"
        "- Output ONLY the utterances as a bullet list (- )."
    )


def gen(endpoint: str, model: str, lang: str, scene: str, n: int) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": _prompt(lang, scene, n)}],
        "temperature": 0.7,
        "max_tokens": 400,
    }).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer x"})
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--lang", default="en", choices=["en", "jp"])
    p.add_argument("--n", type=int, default=4)
    p.add_argument("--model", default="gemma-4-31b")
    p.add_argument("--endpoint", default="http://127.0.0.1:8000/v1")
    args = p.parse_args()
    label = "## 場面: " if args.lang == "jp" else "## Scene: "
    for pack, scenes in SITUATIONS[args.lang].items():
        out_dir = ROOT / "agent" / pack / "exemplars" / args.lang / "situations"
        out_dir.mkdir(parents=True, exist_ok=True)
        for sid, scene in scenes:
            body = gen(args.endpoint, args.model, args.lang, scene, args.n)
            (out_dir / f"situation_{sid}.md").write_text(f"{label}{scene}\n\n{body}\n", encoding="utf-8")
            print(f"[{args.lang}/{pack}] situation_{sid}: {scene} ({len(body)} chars)")
    print("DONE")


if __name__ == "__main__":
    main()
