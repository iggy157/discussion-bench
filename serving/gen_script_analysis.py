"""Generate SCRIPT-DERIVED analysis (talk + action) for the aiwolf script exemplars.

Motivation: the shipped analysis is GENERIC ("where to look" rubric) and not anchored to the
actual script's structure, so the script's strengths (self-intro -> role CO -> seer-reveal timing
-> behaviour reading -> vote-declaration phase) never transfer. This re-derives the analysis FROM
the scripts themselves, using the two prompts that previously worked (one for TALK, one for ACTION).

For each K in --ks, reads {pack}/exemplars/{lang}/scripts_k{K}/*.md, feeds the concatenated scripts
to the judge/generator model, and writes:
    {pack}/exemplars/{lang}/analysis_k{K}/talk.md
    {pack}/exemplars/{lang}/analysis_k{K}/action.md
Both files land in the same dir so the launcher injects both (analysis_dir = analysis_k{K}).

Model: OpenAI-compatible endpoint (local vLLM gemma-4-31b by default). No API key needed.
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

from openai import OpenAI

TALK_PROMPT = """以下は、もともと効果があったシステムで議論エージェントに添付していた台本です。
--- 台本ここから ---
{scripts}
--- 台本ここまで ---

以上を読んだ上で、所見をまとめて返してください (目安 800〜1100 字程度, 箇条書き可)。
あなたはこの後、**トーク (発言)** を担当します。観点は **「どういう盤面状況がどういう議論を呼ぶか」**
の因果対応です。形式パターンの暗記ではなく、状況依存の判断材料として書いてください。

- **盤面状況と議題の対応** (主要なもの 3〜5 件): 占い CO の数 (1-CO / 2-CO 以上), 黒判定の有無,
  襲撃結果, 残り人数, 公開役職分布などの状況が、その時間帯の議題・トーン・テンポをどう変えているか。
- **観察される議論展開のパターン** (主要なもの 2〜3 件): それぞれ「どの状況で起きやすいか」を併せて。
- **Day ごとのフェーズ感**: Day0=自己紹介・進行方針合意・軽い印象表明 / Day1=朝CO・結果共有・検証質疑・
  投票宣言 / Day2 以降=襲撃結果と前日からの整合性確認、のような自然な節目を観察ベースで。
- **Day 内の Turn 進行と投票宣言フェーズ**: 各日のトークは概ね Turn 0〜3。最終 Turn は全員が
  ``@-mention`` 付きで投票先を明確に宣言して締めるのが典型。発話回数の残り 1 回は投票宣言用に温存する。
- **同じ議題への応答の散らばり方**: 賛同(簡潔)/賛同+補足/別観点・遅延/中立観察/スキップ のように役割が散る。
  担当キャラの口調・性格に沿って自分の役割を選び取る感覚で。
- **議論の主流から外れる位置取り** (誰かが攻められている局面): 非を認める・中立観察・整理役・保留 など、
  それぞれが発生する状況条件を抜き出す。攻める vs 攻められるの 2 元論にしない。
- **発話の組み立て**: 1 発話の長さ感、「相手の一文を拾う + 自分の判断材料 + 短い結論」の応酬リズム。
- **沈黙・短文・転換 / 口調の一貫性**: 本筋へ戻す入り方、終盤の短文使い、担当キャラの一人称・語尾・テンションの軸。
これらは台本に観察された一例で、状況が変われば別の流れも起こりうる前提で書いてください。
このまとめは自分自身の覚書として使います。台本のセリフをそのまま引用する必要はありません。"""

ACTION_PROMPT = """以下は、もともと効果があったシステムで議論エージェントに添付していた台本です。
--- 台本ここから ---
{scripts}
--- 台本ここまで ---

以上を読んだ上で、所見をまとめて返してください (目安 600〜900 字程度, 箇条書き可)。
あなたはこの後、**投票・占い・襲撃 などのアクション判断**のみを担当します
(5人村は「人狼1・狂人1・占い師1・村人2」の構成のため、霊媒・騎士は登場しません)。
形式的なルールではなく、**状況 → 判断** の対応を台本から抜き出してください。

- **占い (占い師)**: 盤面のどの情報を読んで占い先を決めているか、状況 → 判断で。
- **投票**: 状況別に票が集まる位置の選ばれ方。占い 1-CO と 2-CO で投票の意味の違い
  (1-CO は結果を信じて進行、2-CO は理由比較・Day0 整合性で真偽判定) を含める。
- **襲撃 (人狼)**: 真占い視を噛むか、発言力のある村を削るか、狂人の偽占いを生かすか — 残り人数/占い結果の構図で。
- **5人村特有の状況対応**: 一手のミスが致命傷の手数感、初日 2 占い CO で確定する 1-1 構図の処理、
  白サイドが残せる人数の薄さ、など局面の手数の薄さが判断にどう影響するか。
各項目は「この状況なら、こう動く」の条件付きで。台本に観察された一例で、状況が変われば別判断も起こりうる前提。
このまとめは自分自身の覚書として使います。台本のセリフをそのまま引用する必要はありません。"""

# HiddenBench has no roles / votes / actions — it is pure information-integration discussion.
# So analysis is SINGLE (combined), not split into talk/action.
HB_PROMPT = """以下は、もともと効果があったシステムで議論エージェントに添付していた、HiddenBench
（各参加者が断片情報を持ち寄り、議論して正解に到達する情報統合型タスク）の良い議論の台本です。
--- 台本ここから ---
{scripts}
--- 台本ここまで ---

以上を読んだ上で、所見をまとめて返してください (目安 800〜1100 字程度, 箇条書き可)。
あなたはこの後、この議論に参加して発言します。観点は **「どういう状況がどういう発言を呼ぶか」** の
因果対応です。形式の暗記ではなく、状況依存の判断材料として書いてください。

- **情報共有(surfacing)**: 自分だけが持つ断片情報を、どのタイミングで・どの粒度で場に出すと有効か。
  出し惜しみ／早すぎる開示の弊害も含めて、台本から読み取れる「出し方」を抽出する。
- **統合(integration)**: 他者の断片をどう拾い、つなぎ、全体像へ組み上げているか。誰かの情報に
  自分の情報を接続して前進させる発話の作り方。
- **検証(verification)**: 主張・結論を鵜呑みにせず、既出の事実と突き合わせて整合性を確認する動き。
  矛盾や抜けを指摘して詰める発話がどの状況で出るか。
- **早すぎる収束を避ける**: 一つの仮説に飛びつかず、対立仮説や未統合の情報を点検してから合意へ向かう。
  どの状況で「待った」をかけ、どの状況で収束させているか。
- **フェーズ感**: 序盤=情報出し合い / 中盤=突き合わせ・統合・検証 / 終盤=合意形成、のような自然な節目を観察ベースで。
- **発話の組み立て / 冗長回避**: 「相手の一点を拾う + 自分の情報や判断材料を足す + 短い結論」の応酬リズム。
  同じ賛同の言い回しを全員が繰り返す水増しを避け、各発話が新しい情報か検証か前進を担うようにする。
これらは台本に観察された一例で、状況が変われば別の流れも起こりうる前提で書いてください。
このまとめは自分自身の覚書として使います。台本のセリフをそのまま引用する必要はありません。"""


def call(client: OpenAI, model: str, prompt: str) -> str:
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )
    return r.choices[0].message.content or ""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--model", default="gemma-4-31b")
    p.add_argument("--pack", default="agent/aiwolf", help="exemplar pack dir (contains exemplars/<lang>)")
    p.add_argument("--lang", default="en")
    p.add_argument("--ks", default="1,3,5,10", help="comma-sep script counts")
    p.add_argument("--mode", choices=["aiwolf", "hb"], default="aiwolf",
                   help="aiwolf=talk+action split; hb=single combined analysis")
    args = p.parse_args()

    client = OpenAI(base_url=f"http://localhost:{args.port}/v1", api_key="EMPTY")
    base = Path(args.pack) / "exemplars" / args.lang
    for k in [s.strip() for s in args.ks.split(",") if s.strip()]:
        sdir = base / f"scripts_k{k}"
        files = sorted(glob.glob(str(sdir / "*.md")))
        if not files:
            print(f"[skip] no scripts in {sdir}")
            continue
        scripts = "\n\n".join(Path(f).read_text(encoding="utf-8") for f in files)
        outdir = base / f"analysis_k{k}"
        outdir.mkdir(parents=True, exist_ok=True)
        if args.mode == "hb":
            print(f"K={k}: {len(files)} scripts -> generating combined HB analysis ...")
            a = call(client, args.model, HB_PROMPT.format(scripts=scripts))
            (outdir / "analysis.md").write_text("# Analysis (script-derived, HB)\n\n" + a + "\n", encoding="utf-8")
            print(f"  wrote {outdir}/analysis.md  ({len(a)} chars)")
        else:
            print(f"K={k}: {len(files)} scripts -> generating talk+action analysis ...")
            talk = call(client, args.model, TALK_PROMPT.format(scripts=scripts))
            (outdir / "talk.md").write_text("# Analysis — talk (script-derived)\n\n" + talk + "\n", encoding="utf-8")
            action = call(client, args.model, ACTION_PROMPT.format(scripts=scripts))
            (outdir / "action.md").write_text("# Analysis — action (script-derived)\n\n" + action + "\n", encoding="utf-8")
            print(f"  wrote {outdir}/talk.md  ({len(talk)} chars) + action.md ({len(action)} chars)")


if __name__ == "__main__":
    main()
