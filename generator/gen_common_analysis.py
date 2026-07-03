"""Generate the COMMON analysis from the failure-mode taxonomy (NOT from any script), via gemma.

共通analysisを「失敗様態タクソノミー」から直接生成する（台本・発話例を一切入力しない）。
→ analysis_only / utterance+analysis / situation+analysis / script+analysis の全条件に公平
（どの提示形式とも独立な一般原則）。出力: agent/<pack>/exemplars/<lang>/analysis_common/analysis.md

Usage:
    python generator/gen_common_analysis.py --lang en [--model gemma-4-31b] [--endpoint ...:8000/v1]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Failure modes the study targets (the inverse of the eval metrics) — the ONLY input to the analysis.
TAXONOMY = {
    "hidden-bench": (
        "collaborative reasoning where each participant holds different private clues and the group "
        "must pool them to reach one correct answer",
        [
            "Information withholding: participants fail to surface the private facts only they know.",
            "Premature convergence: the group locks onto an early answer before evidence is in.",
            "Reflexive conformity: minority members cave to the majority without scrutiny.",
            "Stagnation / low diversity: repeating the same points instead of advancing.",
            "Weak integration: not synthesizing pooled facts or confirming shared understanding.",
        ],
    ),
    "aiwolf": (
        "a social-deduction discussion (werewolf) where participants hold private information/roles "
        "and must reason about who is deceiving",
        [
            "Withholding private information or disclosing it at a poor time.",
            "Premature convergence: rushing to execute/conclude before checking the evidence.",
            "Reflexive conformity: following the majority without independent scrutiny.",
            "Stagnation / low diversity: repetitive talk that does not advance the deduction.",
            "Weak verification: not checking claims for consistency or asking for grounds.",
        ],
    ),
}


def gen(endpoint: str, model: str, lang: str, domain: str) -> str:
    setting, modes = TAXONOMY[domain]
    modes_txt = "\n".join(f"- {m}" for m in modes)
    if lang == "jp":
        instr = (
            "あなたは「良い多人数議論の進め方」を一般原則としてまとめます。\n"
            f"対象は、{setting}です。\n\n"
            "次の既知の失敗様態を回避・克服するために、良い議論が共通して取る進め方を、"
            "**特定の話題・事例・台本・発話例に一切依存しない一般原則**として書いてください:\n"
            f"{modes_txt}\n\n"
            "制約:\n- 特定タスクの正解語・固有名詞・具体例には触れない（話題非依存・L2）。\n"
            "- 失敗様態ごとに見出しを立て、各2〜3個の箇条書き原則。\n"
            "- 命令でなく『良い議論はこうしている』という観察の形。\n"
            "- 見出しは `# 分析（着眼点・共通）` で始め、Markdownで出力。前置き・後書きなし。"
        )
    else:
        instr = (
            "You are writing GENERAL principles for how good multi-party discussion proceeds.\n"
            f"The setting is {setting}.\n\n"
            "Write the recurring moves that GOOD discussions use to avoid/overcome the known failure "
            "modes below, as **general principles that do NOT depend on any specific topic, example, "
            "script, or utterance**:\n"
            f"{modes_txt}\n\n"
            "Constraints:\n- Never mention specific answers, proper nouns, or concrete examples "
            "(topic-independent, L2).\n- One heading per failure mode, each with 2-3 bullet principles.\n"
            "- Observational ('good discussions do X'), not commands.\n"
            "- Start with `# Analysis (where to look)` and output Markdown only. No preamble/closing."
        )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": instr}],
        "temperature": 0.7,
        "max_tokens": 900,
    }).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer x"})
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--lang", default="en", choices=["en", "jp"])
    p.add_argument("--model", default="gemma-4-31b")
    p.add_argument("--endpoint", default="http://127.0.0.1:8000/v1")
    args = p.parse_args()
    for pack in ("hidden-bench", "aiwolf"):
        out_dir = ROOT / "agent" / pack / "exemplars" / args.lang / "analysis_common"
        out_dir.mkdir(parents=True, exist_ok=True)
        text = gen(args.endpoint, args.model, args.lang, pack)
        (out_dir / "analysis.md").write_text(text + "\n", encoding="utf-8")
        print(f"[{args.lang}/{pack}] common analysis: {len(text)} chars")
    print("DONE")


if __name__ == "__main__":
    main()
