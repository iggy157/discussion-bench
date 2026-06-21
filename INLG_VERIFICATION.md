# INLG構想 — サーバ流用検証メモ

調査日: 2026-06-21

## 目的
INLG構想（同一エージェントが「台本＋分析」の6条件で **人狼** と **HiddenBench(協調熟議)** の
2ドメインを戦い、同一評価する）を実装するにあたり、
HiddenBenchを既存 `aiwolf-nlp-server`（特に `config/playground.yml`）でホストできるか検証する。

## HiddenBench の実際の仕組み
- 出典: 論文 arXiv 2505.11556 / 公式実装 https://github.com/jonradoff/hiddenbench /
  データ https://huggingface.co/datasets/YuxuanLi1225/HiddenBench (`benchmark.json`, 65タスク)
- **4エージェント/タスク**。
- タスクJSON: `shared_information`(全員共有) + `hidden_information`(1エージェント1事実ずつ配分) +
  `possible_answers`(選択肢) + `correct_answer`。
  共有情報だけだとダミー選択肢に誘導され、全員の隠し事実を統合して初めて正解が出る設計。
- 3フェーズ:
  1. 事前: 各エージェント個別に「選択肢＋理由」をJSON回答 → 事前正答率
  2. 議論: T=15ラウンド逐次発話（1巡目は順、以降は全員の最新発言＋全履歴を見て応答）。
     モデレータ無し。合意で早期終了。発話は1-2文程度に制約。
  3. 事後: 各エージェント再回答（選択肢＋理由） → 主指標(事後正答率)
- 採点: 選択肢に対する正答率(平均/多数決) + 情報統合ゲイン(post-pre)。
  協調〜対立の5プロンプト条件。
- タスク妥当性: Full Profile精度≥80% かつ Hidden Profile精度≤20%。

## playground.yml の正体
`狼0 / 全員VILLAGER 5 / day_phases=daily_talkのみ / night_phases無し` の純議論設定。
ただしGoエンジン自体は人狼専用にハードコードされている。

## 写像検証（HiddenBench要件 × aiwolf-nlp-server）
| HiddenBench要件 | Goサーバ | 判定 |
|---|---|---|
| 議論ラウンド(多巡・全履歴) | daily_talk / freeform talk phase | ✅ ここだけ合う |
| 1エージェントずつ非対称な手がかり配布 | info.profileは人狼ペルソナ1本。配布機構無し | ❌ 強引 |
| 事前/事後の個別回答(選択肢+理由) | request型が無い。VOTEはエージェント対象で選択肢を選べない | ❌ 不可 |
| 選択肢への正誤採点 | 勝敗はチーム(村/狼)ベース。正解選択肢の概念無し | ❌ 不可 |
| 終了条件 | util/game_util.go:28 CalcWinSideTeam: 狼0なら即village勝利。狼人口駆動 | ❌ N巡後回答収集と別物 |

決め手: HiddenBenchの核(非対称配布・選択肢への事前/事後回答・選択肢採点)は人狼プロトコルに
対応物が無い。VOTEで「選択肢B」は原理的に選べない。終了条件も狼人口ベース。

## 結論
- **Goサーバ(playground.yml含む)はHiddenBench実験に不適。** 大改造も人狼を壊すため不適。
- 推奨: **人狼=既存Goサーバ(無改造) / HiddenBench=新規の軽量Python "bench-server"**。
  同一WebSocketプロトコルで manyshot エージェントを両ドメインに流用する。
  - 議論フェーズは既存 TALK_PHASE_START/END・TALK_BROADCAST を再利用(freeform実装そのまま)。
  - INITIALIZEの手がかり配布と事前/事後の選択肢回答だけ最小拡張。
    進行ロジックは公式 hiddenbench/benchmark.py を移植。
  - 本物の benchmark.json を直接読む。
- docker compose は aiwolf-nlp-demo の「同一プロトコルのサーバを service名で複数同時起動」
  パターンに乗せ、yaml一つで aiwolf / hiddenbench 選択＋両方同時起動。
