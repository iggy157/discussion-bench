<!-- 言語: [English](README.md) | **日本語** -->

# eval（指標 + LLM-judge）

議論ログ全体（自己対戦では1ゲーム＝1ログ）に対する評価。**客観的な失敗様態指標**（ルールベース）
＋**主観LLM-judge**（3項目）を計算し、条件別の日英レポートを出す。

## 客観指標（出典は一次資料で検証済み）

| 指標 | 位置づけ | 忠実な出典（../docs/METHODOLOGY.ja.md §客観評価 参照） |
|------|----------|------------------------------------------------|
| 事前/事後/Full 正答率・統合ゲイン・多数決 | HiddenBenchネイティブ | Li, Naito & Shirado 2025 (arXiv:2505.11556) |
| **情報表面化率**（＝information coverage） | **適応** | Lu, Yuan & McLeod 2012 / Stasser & Titus 1985 — **HiddenBenchではない** |
| 収束ラウンド | 公式repoの `consensus_round` に一致 | jonradoff/hiddenbench（論文は固定T=15・早期終了なし） |
| 尚早合意・終端合意 | **自作** | cf. Smit et al. ICML2024 / Wu et al. 2511.07784 |
| distinct-1 / distinct-2（÷総トークン） | 公表どおり | Li et al. NAACL2016 (1510.03055) — **DMADではない** |
| 語彙的自己反復（1 − Self-BLEU、自分の履歴に対して） | **適応** | Self-BLEU = Zhu et al. 2018 (Texygen) / 100−Self-BLEU枠 = Liang et al. 2024 |
| 同調率/独立率の代理 | **適応** | BenchForm ICLR2025 (2501.13381)。我々のIR=1−CR（BenchFormのIRはTrust∩Doubtの連言で≠1−CR） |

帰属は一次資料で確認のうえ修正済み：表面化率はHiddenBenchの指標**ではなく** Lu/Stasser の
information coverage、distinct-n/Self-BLEU は **DMAD/DoT ではない**、「自己反復」は**語彙的**
（表層n-gram）であって意味的ではない。適応/自作の指標はレポート上でフラグ表示（`*self-defined`・`*adapted`）。

## 主観LLM-judge

議論ログ全体を3項目で採点：**自然さ／噛み合い・非矛盾／話題展開**。（AIWolfDial の A〜F は他者対戦前提の
相対評価なので、自己対戦の本研究では不採用。）判定モデルは `config/judge.yml`（英）/ `config/judge.ja.yml`
（日本語参照）で一元管理：provider/model/temperature/scale/lang。APIキーはルートの `.env` から読む。
オフラインテスト用に `mock` プロバイダ同梱。

## 実行（リポジトリ直下から Make）

```bash
make eval     # 客観のみ（API不要）   -> server/hidden-bench/log/results/eval/report.md
make judge    # 客観 + 主観LLM-judge -> 同じレポートに subj_* 列を追加
```

直接実行：
```bash
PYTHONPATH=src python src/evaluate.py <results_dir>                 # 客観のみ
PYTHONPATH=src python src/evaluate_all.py <results_dir> -c config/judge.yml   # + LLM-judge
PYTHONPATH=src python src/evaluate_all.py <results_dir> --no-judge  # 客観のみ
```

### 人狼ログ
eval は HiddenBench の結果JSONを直接読む。人狼はサーバのJSONゲームログを先に変換する（HB固有指標はN/A、
distinct-n / 自己反復 / LLM-judge は適用可）：
```bash
PYTHONPATH=src python src/werewolf_adapter.py <server-json-log-dir> -o <out> --condition baseline --lang jp
make judge HB_RESULTS=<out>
```

## 注意
- **トークン化**：英＝単語トークン、日＝文字トークン（MeCab不要）。distinct-n は総トークンで割る。
- 収束/同調の**立場抽出はルールベース**（選択肢の最後の言及。BenchFormも同様にルールベース。HiddenBenchは
  選択肢が既知）。LLM抽出にしたい場合は `src/stance.py` が継ぎ目。
- 集計は `condition` 単位 → 6条件を回すと1つの比較表になる。

## 構成
```
config/judge.yml (.ja.yml)  -- 判定モデル設定（provider/model/scale/items）
prompts/judge.en.txt judge.ja.txt  -- 判定プロンプト骨格（ファイル管理。%%ITEMS%%/%%TRANSCRIPT%%/%%SCALE%%/%%SCHEMA%%）
src/
  tokenize_text.py  stance.py
  surfacing.py      -- information coverage（Lu/Stasser、適応と明記）
  convergence.py    -- 収束ラウンド / 尚早合意
  diversity.py      -- distinct-n（Li 2016）、語彙的自己反復（Zhu 2018 / Liang 2024）
  conformity.py     -- 同調/独立（BenchForm適応。IR = 1−CR）
  evaluate.py       -- 客観指標 + レポート
  judge.py          -- 主観LLM-judge（provider: openai | mock）
  evaluate_all.py   -- 客観+主観の統合（make judge）
  werewolf_adapter.py -- aiwolf-nlp-server のJSONログ -> transcript 形へ
```
