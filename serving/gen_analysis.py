"""Generate EXEMPLAR-TYPE-SPECIFIC analysis (the general version of gen_script_analysis.py).

Each +analysis condition should get analysis DERIVED FROM its own exemplar type, not one shared
generic block. Mapping (K=5 condition-comparison):
  - script_fewshot_analysis   : analysis from scripts_k5     -> analysis_k5
  - situation_fewshot_analysis: analysis from situations     -> analysis_situ
  - utterance_fewshot_analysis: analysis from utterances_k5  -> analysis_utt
  - analysis_only             : NO exemplar -> POINTS checklist (kind=points, source=scripts_k5) -> analysis_points

Format by DOMAIN: aiwolf -> talk.md + action.md ; hb -> analysis.md.
Language by --analang: en (for the EN run; default) or ja. The EN run MUST use --analang en so the
injected analysis matches the English exemplars/discussion (the shipped analysis_common is English).
Model: OpenAI-compatible endpoint (local vLLM gemma-4-31b). No API key needed.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
from pathlib import Path

from openai import OpenAI

# System framing prepended to every analysis prompt: tells the analyzer HOW the analysis is used
# (multi-agent screenwriter system; you write only your own character's next move; server formats).
# Mirrors the original working prompt. Keyed by [analang][mode].
PREAMBLE = {
    "en": {
        "aiwolf": ("The following are 'good-game exemplar transcripts' of this werewolf (AIWolf) game, "
                   "given to you as background reference. In this system, multiple screenwriter-agents each "
                   "play ONE character and write their character's NEXT move (an utterance, or a single "
                   "decision), so the game itself is written up as a new transcript. You are one of those "
                   "screenwriters. The transcript is reference material for grasping the atmosphere, how the "
                   "discussion is carried, the tempo of utterances, the timing of topic shifts, and the "
                   "consistency of each character's voice. You will write ONLY your own character's one move "
                   "(or one target-agent name) — never other characters' lines, stage directions, or "
                   "inner-monologue narration, and never character-name/labelled script notation (the server "
                   "formats into the script form).\n\n"),
        "hb": ("The following are 'good-discussion exemplar transcripts' of this HiddenBench task, given as "
               "background reference. In this task several agents each hold a private fragment of information "
               "and contribute utterances to reach the correct collective answer through discussion. You are "
               "one of those agents. The transcript is reference for grasping how good discussions surface "
               "private information, integrate fragments, verify claims, and converge. You will write ONLY "
               "your own next utterance — not other agents' lines, stage directions, or narration (the server "
               "handles formatting).\n\n"),
    },
    "ja": {
        "aiwolf": ("以下は、この人狼ゲームの「お手本台本」です。実プレイログを、あなたへの下調べ用の参考資料として読んでもらいます。"
                   "このシステムでは、複数の脚本家エージェントがそれぞれ1名のキャラクターを担当し、自分の担当キャラの次の一手"
                   "(発話または判断)を書き継ぐことで、対局そのものが1本の新しい台本として書き上がっていきます。あなたはその脚本家"
                   "チームの一人です。台本は、これまでの台本全体を踏まえて担当キャラの次の一手を書くときの、雰囲気・議論の運び方・"
                   "発言のテンポ・話題転換の間合い・キャラクターの口調の一貫性を掴むための資料です。あなたが書くのは担当キャラの一手分"
                   "の本文(または対象エージェント名1件)のみで、他キャラのセリフ代弁・ト書き・心情ナレーションや、キャラ名・ラベル付き"
                   "の台本記法は書きません(台本フォーマットへの整形はサーバが行います)。\n\n"),
        "hb": ("以下は、このHiddenBenchタスクの「お手本台本」です。参考資料として読んでもらいます。このタスクでは、複数のエージェント"
               "がそれぞれ私的な断片情報を持ち寄り、議論を通じて正しい集団的回答に到達します。あなたはそのエージェントの一人です。"
               "台本は、良い議論が情報をどう開示(surfacing)し・断片をどう統合し・主張をどう検証し・どう収束するかを掴むための資料です。"
               "あなたが書くのは自分の次の一手の発話のみで、他エージェントの代弁・ト書き・ナレーションは書きません(整形はサーバが行います)。\n\n"),
    },
}

# ===================== JA prompts =====================
SRC_DESC_JA = {
    "scripts": "良い議論の台本（議論全体の流れ）",
    "situations": "良い議論で使われる、状況（シーン）別の言い回し例",
    "utterances": "良い議論から抜き出した個別の発話例（全体の流れは含まない）",
}
_EX_HEAD_JA = "以下は、良い議論のお手本（{src_desc}）です。\n--- お手本ここから ---\n{exemplars}\n--- お手本ここまで ---\n\n以上を読んだ上で、所見をまとめて返してください "
_TALK_JA = """(目安 800〜1100 字程度, 箇条書き可)。
あなたはこの後、**トーク (発言)** を担当します。観点は「どういう盤面状況がどういう議論を呼ぶか」の因果対応です。
- 盤面状況と議題の対応(3〜5件): 占いCO数(1-CO/2-CO以上),黒判定,襲撃結果,残り人数,役職分布が議題・トーン・テンポをどう変えるか。
- 議論展開パターン(2〜3件): どの状況で起きやすいか併せて。
- Dayフェーズ感: Day0=自己紹介・進行合意・印象 / Day1=朝CO・結果共有・検証質疑・投票宣言 / Day2以降=襲撃結果と前日整合性。
- Turn進行: Turn0〜3。最終Turnは全員@-mentionで投票宣言して締める(残り1発話は投票宣言用に温存)。
- 同議題への応答の散らばり: 簡潔賛同/賛同+補足/別観点・遅延/中立観察/スキップ。
- 主流から外れる位置取り: 非を認める・中立観察・整理役・保留がどの状況で出るか(攻める/攻められるの二元論にしない)。
- 発話の組み立て/口調: 「相手の一文+判断材料+短い結論」、キャラの一貫性。
観察された一例で別の流れも起こりうる前提。自分用の覚書(セリフ引用不要)。"""
_ACTION_JA = """(目安 600〜900 字程度, 箇条書き可)。
あなたはこの後、**投票・占い・襲撃 のアクション判断**のみを担当します(5人村=人狼1・狂人1・占い師1・村人2。霊媒・騎士なし)。状況→判断で。
- 占い: 盤面のどの情報から占い先を決めるか。
- 投票: 状況別に票が集まる位置。1-CO(結果を信じ進行)と2-CO(理由比較・Day0整合で真偽判定)の違いを含める。
- 襲撃(人狼): 真占い視を噛む/発言力ある村を削る/狂人の偽占いを生かす — 残り人数・占い構図でどう変わるか。
- 5人村特有: 一手のミスが致命傷、初日2CO=占い真贋戦、白サイドの薄さ。
各項目「この状況なら、こう動く」で。別判断も起こりうる前提。自分用の覚書。"""
_HB_JA = """(目安 800〜1100 字程度, 箇条書き可)。
あなたはこの後この議論に参加して発言します(HiddenBench=断片情報を持ち寄り議論で正解に到達する情報統合型)。観点は「どういう状況がどういう発言を呼ぶか」。
- 情報共有(surfacing): 自分だけの断片を、どのタイミング・粒度で出すと有効か(出し惜しみ/早すぎの弊害も)。
- 統合(integration): 他者の断片を拾い・つなぎ・全体像へ。
- 検証(verification): 結論を鵜呑みにせず既出事実と突き合わせ矛盾や抜けを詰める。
- 早すぎる収束の回避: 対立仮説・未統合情報を点検してから合意へ。
- フェーズ感: 序盤=情報出し / 中盤=突き合わせ・統合・検証 / 終盤=合意形成。
- 発話の組み立て/冗長回避: 「相手の一点+自分の情報や検証+短い結論」。同じ賛同の繰り返し(水増し)を避け各発話が新情報か検証か前進を担う。
別の流れも起こりうる前提。自分用の覚書。"""
_POINTS_HEAD_JA = "以下の良い議論のお手本（{src_desc}）を素材に、**良い議論の要点だけ**を簡潔なチェックリスト(箇条書き)として抽出してください。お手本そのものはエージェントに渡さず、この要点リストだけを渡す用途です。\n--- 素材ここから ---\n{exemplars}\n--- 素材ここまで ---\n"
_PT_JA = _POINTS_HEAD_JA + "観点=トーク。状況→議論の対応・フェーズ感・投票宣言フェーズ・応答の散らばり・口調を、抽象的な要点として10項目程度で。手本は引用しない。"
_PA_JA = _POINTS_HEAD_JA + "観点=アクション(投票/占い/襲撃)。状況→判断の要点を箇条書きで。1-CO/2-COの違い、5人村の手数感を含める。手本は引用しない。"
_PHB_JA = _POINTS_HEAD_JA + "観点=HiddenBench。情報共有/統合/検証/早すぎる収束の回避/フェーズ感/冗長回避を、抽象的な要点として10項目程度で。手本は引用しない。"

# ===================== EN prompts =====================
SRC_DESC_EN = {
    "scripts": "a transcript of a good discussion (the whole flow)",
    "situations": "scene-by-scene phrasing examples used in good discussions",
    "utterances": "individual utterances sliced from good discussions (no whole-flow)",
}
_EX_HEAD_EN = "Below is an exemplar of good discussion ({src_desc}).\n--- EXEMPLAR START ---\n{exemplars}\n--- EXEMPLAR END ---\n\nHaving read the above, write up your observations "
_TALK_EN = """(target ~800-1100 words, bullets OK).
You will next handle TALK (speaking). Focus on the CAUSAL mapping of "which board situation calls for which discussion" as situation-dependent judgment material, not memorized phrasing.
- Board situation -> agenda (3-5): how the number of seer COs (1-CO vs 2-CO+), a werewolf/"black" result, the night-attack result, players remaining, and the revealed-role distribution shift the agenda, tone, and tempo.
- Discussion patterns (2-3): each WITH the situation in which it tends to arise.
- Per-Day phases: Day0 = self-introductions / agreeing on process / light first impressions; Day1 = morning CO / sharing results / verification Q&A / vote declaration; Day2+ = attack result and consistency check against the previous day.
- Turn progression: roughly Turn 0-3; the FINAL turn = everyone declares their vote with an @-mention to close the day (reserve the last utterance for the vote declaration, do not spend it on deliberation).
- Spread of responses to one agenda: concise agreement / agreement + caveat / different angle or delayed view / neutral observation / skip — roles spread out rather than everyone echoing.
- Off-mainstream positioning (when someone is under attack): admitting fault / neutral observer / organizer who refocuses / holding back — and the situation each arises in (avoid an attacker-vs-attacked binary).
- Utterance construction & voice: "pick up one line from another speaker + add your own judgment material + a short conclusion"; keep persona/voice consistent.
These are one observed instance; other flows can occur depending on the situation. This is a personal memo (no need to quote lines verbatim)."""
_ACTION_EN = """(target ~600-900 words, bullets OK).
You will next handle ONLY the ACTIONS (vote / divine / attack). The 5-player game is werewolf x1, possessed x1, seer x1, villager x2 (no medium/bodyguard). Give situation -> decision mappings, not formal rules.
- Divine (seer): which board information drives the choice of target (e.g. an unconfirmed player who led the process; a quiet/low-content player; an off-feeling player).
- Vote: which position the votes converge on, by situation. Include the difference between 1-CO (trust the result and push the process) and 2-CO (compare reasons / Day0 consistency to judge which seer is real).
- Attack (werewolf): whether to kill the apparently-real seer, remove an influential villager, or keep the possessed's fake claim alive — and how this changes with players remaining and the CO structure.
- 5-player specifics: one mistake is often fatal (thin move budget); first-day 2-CO is essentially a seer-authenticity battle; the white side has very few players to spare.
Write each as "in this situation, do this". Other decisions can occur depending on the situation. This is a personal memo."""
_HB_EN = """(target ~800-1100 words, bullets OK).
You will next take part in this discussion and speak (HiddenBench = participants hold fragments of information and must reach the correct answer through discussion). Focus on "which situation calls for which utterance".
- Surfacing: when and at what granularity to put your private fragment on the table to be useful (and the harm of withholding or disclosing too early).
- Integration: how to pick up others' fragments, connect them, and build toward the whole picture.
- Verification: not taking conclusions at face value, cross-checking against established facts, pressing on contradictions or gaps.
- Avoiding premature convergence: check competing hypotheses and un-integrated info before agreeing.
- Phases: early = put information out; middle = cross-check / integrate / verify; late = build consensus.
- Utterance construction & anti-redundancy: "one point from another + your own info or verification + a short conclusion"; avoid everyone repeating the same agreement (padding) — each utterance should carry new info, verification, or progress.
Other flows can occur depending on the situation. This is a personal memo."""
_POINTS_HEAD_EN = "Using the good-discussion exemplar below ({src_desc}) as source material, extract ONLY the KEY POINTS of good discussion as a concise checklist (bullets). The exemplar itself is NOT given to the agent — only this checklist will be.\n--- SOURCE START ---\n{exemplars}\n--- SOURCE END ---\n"
_PT_EN = _POINTS_HEAD_EN + "Perspective = TALK. Give ~10 abstract key points covering situation->agenda mapping, per-Day phases, the vote-declaration turn, the spread of responses, and voice consistency. Do not quote the exemplar."
_PA_EN = _POINTS_HEAD_EN + "Perspective = ACTIONS (vote/divine/attack). Give the situation->decision key points as bullets, including the 1-CO vs 2-CO difference and the 5-player thin-move-budget feel. Do not quote the exemplar."
_PHB_EN = _POINTS_HEAD_EN + "Perspective = HiddenBench discussion. Give ~10 abstract key points covering surfacing / integration / verification / avoiding premature convergence / phases / anti-redundancy. Do not quote the exemplar."

LANGS = {
    "ja": dict(desc=SRC_DESC_JA, head=_EX_HEAD_JA, talk=_TALK_JA, action=_ACTION_JA, hb=_HB_JA,
               pt=_PT_JA, pa=_PA_JA, phb=_PHB_JA),
    "en": dict(desc=SRC_DESC_EN, head=_EX_HEAD_EN, talk=_TALK_EN, action=_ACTION_EN, hb=_HB_EN,
               pt=_PT_EN, pa=_PA_EN, phb=_PHB_EN),
}


def call(client: OpenAI, model: str, prompt: str) -> str:
    kwargs: dict = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if re.match(r"^(gpt-5|o1|o3|o4)", model):  # reasoning models: no temperature, max_completion_tokens
        kwargs["max_completion_tokens"] = 4096
    else:
        kwargs["temperature"] = 0.3
        kwargs["max_tokens"] = 2560
    r = client.chat.completions.create(**kwargs)
    return r.choices[0].message.content or ""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--provider", choices=["vllm", "openai"], default="vllm",
                   help="vllm=local gemma on --port; openai=real OpenAI (e.g. gpt-5.4) via OPENAI_API_KEY")
    p.add_argument("--model", default="gemma-4-31b")
    p.add_argument("--pack", required=True)
    p.add_argument("--lang", default="en", help="exemplar lang dir")
    p.add_argument("--analang", choices=["en", "ja"], default="en", help="analysis OUTPUT language")
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--mode", choices=["aiwolf", "hb"], required=True)
    p.add_argument("--kind", choices=["exemplar", "points"], default="exemplar")
    args = p.parse_args()

    L = LANGS[args.analang]
    pre = PREAMBLE[args.analang][args.mode]
    base = Path(args.pack) / "exemplars" / args.lang
    files = sorted(glob.glob(str(base / args.src / "*.md")))
    if not files:
        raise SystemExit(f"no exemplars in {base/args.src}")
    exemplars = "\n\n".join(Path(f).read_text(encoding="utf-8") for f in files)
    src_desc = L["desc"].get(re.sub(r"_k\d+$", "", args.src), args.src)
    outdir = base / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    if args.provider == "openai":
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    else:
        client = OpenAI(base_url=f"http://localhost:{args.port}/v1", api_key="EMPTY")

    def gen(tpl: str, *, points: bool) -> str:
        prompt = pre + (tpl if points else L["head"] + tpl).format(src_desc=src_desc, exemplars=exemplars)
        return call(client, args.model, prompt)

    pts = args.kind == "points"
    print(f"{args.pack} {args.src} -> {args.out} (mode={args.mode} kind={args.kind} analang={args.analang}, {len(files)} files)")
    if args.mode == "hb":
        a = gen(L["phb"] if pts else L["hb"], points=pts)
        (outdir / "analysis.md").write_text(f"# Analysis ({args.kind}, HB, from {args.src})\n\n{a}\n", encoding="utf-8")
        print(f"  wrote {outdir}/analysis.md ({len(a)} chars)")
    else:
        t = gen(L["pt"] if pts else L["talk"], points=pts)
        (outdir / "talk.md").write_text(f"# Analysis — talk ({args.kind}, from {args.src})\n\n{t}\n", encoding="utf-8")
        a = gen(L["pa"] if pts else L["action"], points=pts)
        (outdir / "action.md").write_text(f"# Analysis — action ({args.kind}, from {args.src})\n\n{a}\n", encoding="utf-8")
        print(f"  wrote {outdir}/talk.md ({len(t)}) + action.md ({len(a)})")


if __name__ == "__main__":
    main()
