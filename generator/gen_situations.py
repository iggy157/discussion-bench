"""Generate situation-keyed few-shot exemplars via gemma (vLLM, OpenAI-compatible API).

中立な「場面ラベル」ごとに、話題非依存の良い発話例を gemma に生成させ、
agent/<pack>/exemplars/jp/situations/ に書き出す。状況キーは"処方箋"でなく中立な場面のみ
（分析は別因子=共通analysisに分離）。L2維持のため特定話題・固有名詞・正解に触れさせない。

Usage:
    python generator/gen_situations.py [--n 4] [--model google/gemma-2-27b-it] \
        [--endpoint http://127.0.0.1:8000/v1]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Neutral scene labels (NOT prescriptive — the principle/analysis is a separate factor).
SITUATIONS = {
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
}


def gen(endpoint: str, model: str, scene: str, n: int) -> str:
    """Ask gemma for N topic-independent example utterances for one scene / 1場面のn発話例."""
    prompt = (
        "あなたは多人数の議論の良い手本データを作成しています。\n"
        f"次の『場面』で、良い参加者が言いそうな短い発言例を{n}個、日本語で挙げてください。\n\n"
        f"場面: {scene}\n\n"
        "制約:\n"
        "- 特定の話題・固有名詞・正解・タスク内容には一切触れない（どんな議題でも通用する一般的な言い回しにする）。\n"
        "- 各発言は1〜2文で簡潔に。説明や前置きは不要、発言そのものだけ。\n"
        "- 箇条書き（- ）で発言だけを出力する。"
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 400,
    }).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer x"})
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"].strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=4)
    p.add_argument("--model", default="google/gemma-2-27b-it")
    p.add_argument("--endpoint", default="http://127.0.0.1:8000/v1")
    args = p.parse_args()
    for pack, scenes in SITUATIONS.items():
        out_dir = ROOT / "agent" / pack / "exemplars" / "jp" / "situations"
        out_dir.mkdir(parents=True, exist_ok=True)
        for sid, scene in scenes:
            body = gen(args.endpoint, args.model, scene, args.n)
            text = f"## 場面: {scene}\n\n{body}\n"
            (out_dir / f"situation_{sid}.md").write_text(text, encoding="utf-8")
            print(f"[{pack}] situation_{sid}: {scene} ({len(body)} chars)")
    print("DONE")


if __name__ == "__main__":
    main()
