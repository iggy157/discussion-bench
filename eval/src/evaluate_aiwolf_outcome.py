"""aiwolf OUTCOME metrics (grounded, objective) — the aiwolf analog of HB collective-decision
accuracy. Did the discussion lead the VILLAGE to the right target?

- villager_vote_accuracy : of votes cast by the human team (VILLAGER/SEER/etc., excl. POSSESSED),
                           fraction targeting an actual WEREWOLF.
- execution_accuracy     : per vote day, the majority-voted (executed) player — fraction that are
                           actual WEREWOLF (collective decision correctness).
- vote_concentration     : per day, top-target share among village votes (coordination, SECONDARY/
                           process — high on a WRONG target is not good, so not an outcome).
Roles from union of all agents' INITIALIZE role_map; votes from VOTE entries (agent->response).
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import statistics as st
from pathlib import Path

WOLF = {"WEREWOLF"}
VILLAGE = {"VILLAGER", "SEER", "MEDIUM", "BODYGUARD", "HUNTER", "KNIGHT"}  # human team (excl POSSESSED)
CONDS = ["baseline", "analysis_only", "utterance_fewshot", "utterance_fewshot_analysis",
         "situation_fewshot", "situation_fewshot_analysis", "script_fewshot",
         "script_fewshot_analysis"]
SH = {"baseline": "①base", "analysis_only": "②anal", "utterance_fewshot": "③utt",
      "utterance_fewshot_analysis": "④utt+a", "situation_fewshot": "⑤situ",
      "situation_fewshot_analysis": "⑥situ+a", "script_fewshot": "⑦scr",
      "script_fewshot_analysis": "⑧scr+a"}


def game_outcome(d: dict) -> dict[str, float]:
    role: dict[str, str] = {}
    votes: dict[int, list[tuple[str, str]]] = collections.defaultdict(list)
    for x in d.get("entries", []):
        r = x.get("request")
        try:
            pkt = json.loads(r) if isinstance(r, str) else (r or {})
        except (ValueError, TypeError):
            continue
        rt = str(pkt.get("request", "")).upper()
        info = pkt.get("info") or {}
        if rt == "INITIALIZE":
            for k, v in (info.get("role_map") or {}).items():
                role[k] = v
        elif rt == "VOTE":
            voter = x.get("agent")
            target = (x.get("response") or "").strip()
            if voter and target:
                votes[int(info.get("day", 0))].append((voter, target))
    if not role or not votes:
        return {}
    vv = vt = 0
    exe_hit = exe_n = 0
    conc_all = []
    conc_vil = []
    for _day, vl in votes.items():
        vil_votes = [(v, t) for v, t in vl if role.get(v) in VILLAGE]
        for voter, target in vl:
            if role.get(voter) in VILLAGE:
                vt += 1
                if role.get(target) in WOLF:
                    vv += 1
        if vl:
            tally = collections.Counter(t for _, t in vl)
            top, cnt = tally.most_common(1)[0]
            exe_n += 1
            if role.get(top) in WOLF:
                exe_hit += 1
            conc_all.append(cnt / len(vl))
        if len(vil_votes) >= 2:  # village-only coordination (the discussion-quality signal)
            vt2 = collections.Counter(t for _, t in vil_votes)
            conc_vil.append(vt2.most_common(1)[0][1] / len(vil_votes))
    out = {}
    if vt:
        out["villager_vote_accuracy"] = vv / vt
    if exe_n:
        out["execution_accuracy"] = exe_hit / exe_n
    if conc_all:
        out["vote_concentration_all"] = st.mean(conc_all)
    if conc_vil:
        out["village_coordination"] = st.mean(conc_vil)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--src", action="append", required=True, help="aiwolf raw dir(s) with <cond>/*.json")
    p.add_argument("--out", required=True)
    p.add_argument("--label", default="run")
    p.add_argument("--conds", default=None, help="comma-sep condition subset (default: standard 8)")
    args = p.parse_args()
    global CONDS
    if args.conds:
        CONDS = args.conds.split(",")
        for c in CONDS:
            SH.setdefault(c, c)
    by: dict[str, dict[str, list[float]]] = {c: collections.defaultdict(list) for c in CONDS}
    for src in args.src:
        for c in CONDS:
            for f in glob.glob(f"{src}/{c}/*.json"):
                try:
                    d = json.load(open(f))
                except Exception:
                    continue
                m = game_outcome(d)
                for k, v in m.items():
                    by[c][k].append(v)
    def mean(c, k):
        return st.mean(by[c][k]) if by[c][k] else float("nan")
    out = [f"# aiwolf 議論プロセス/アウトカム (接地・客観) — {args.label}",
           "village_coordination=村陣営内の投票一致(議論で合意形成できたか, プロセス品質, ↑). "
           "vote/exec_acc=的中だが自己対戦で人狼上達と交絡→参考のみ。\n",
           "| 条件 | village_coordination | (vote_conc_all) | [vote_acc 交絡] | [exec_acc 交絡] | n |",
           "|---|---|---|---|---|---|"]
    for c in CONDS:
        n = len(by[c]["execution_accuracy"])
        out.append(f"| {SH[c]} | {mean(c,'village_coordination'):.3f} | {mean(c,'vote_concentration_all'):.3f} | "
                   f"{mean(c,'villager_vote_accuracy'):.3f} | {mean(c,'execution_accuracy'):.3f} | {n} |")
    order = sorted(CONDS, key=lambda c: -mean(c, "village_coordination"))
    out.append("\n## ランキング(village_coordination↓=議論プロセス品質)")
    out.append("| 順 | 条件 | village_coordination |")
    out.append("|---|---|---|")
    for i, c in enumerate(order, 1):
        out.append(f"| {i} | {SH[c]} | {mean(c,'village_coordination'):.3f} |")
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
