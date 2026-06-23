# 引き継ぎ: freccia での英語本ラン (HANDOFF)

このドキュメントは、別サーバ **freccia**（7× RTX PRO 6000 Blackwell Max-Q, 96GB/枚）で
**英語の本実行**を回す Claude Code への引き継ぎです。検証は thalys（A100 80GB×2）で完了済み。
まずこの全文と、`README.md` / `docs/METHODOLOGY.ja.md` / `docs/METRICS.ja.md` / `results/INDEX.md` を読んでください。

## 0. この研究の目的（1行）
「良い議論の手本（台本・発話例・状況別例）＋分析」を文脈内で与えると、LLM多人数議論
（HiddenBench＝分散情報統合 / aiwolf＝人狼）が改善するかを、**example型 × analysis の要因計画**で検証する。

## 1. 条件設計（本実行）
example型 {none, utterance, situation, script} × analysis {無,有} = **8条件**。
- 6条件レジストリ: `config/conditions.yml`（旧3本analysis）
- **8条件レジストリ: `config/conditions_v2.yml`（共通analysis `analysis_common/` を使用）← 本実行はこれ**
- launcherは `CONDITIONS_FILE=config/conditions_v2.yml` 環境変数で切替（`launcher/launch_agents.py`）。
- 抽象度の階段: none→analysis→utterance→situation→script。situationキーは中立な場面ラベル（処方箋でない）。

## 2. thalys検証で分かったこと（本実行に効く確定事項）
- **⑧script+analysis が両ドメインで最良**（HB P(1位)73% / 総合69%）。①baseline・②analysis_only が下位。中位（utt+a/situ+a/scr/utt）は統計的に同点。`results/run_jp_8cond_v1plus/rankings_stability.md` 参照。
- **HBはgemmaには易しく二極化**（baselineで85%がpost=1.0、残りはpost=0）。正答率は飽和して条件弁別しない → **process指標（多様性/同調/主観）が主弁別**。だから評価は「妥当タスク全部」を使い、難易度で選抜しない（cherry-pick批判回避）。
- gemma judgeは主観を天井（〜5.0）にして弁別力が低い → **本実行はjudgeをGPT等の別系統強モデルに**（測定器として）。

## 3. モデル方針（本実行）
- **システム（議論agent＋台本/分析/situation生成）＝ 単一モデル gemma-4-31B-it、bf16固定**。
  - 理由: 単一変数の綺麗な実験／「なぜこのモデル」論争回避。**FP8等で量子化しない**（質がthalysと変わる＝交絡）。96GBあるのでbf16で余裕。
- **judge ＝ 別系統の強モデル（GPT想定）**。`eval/config/judge.yml`（本番）/`judge.local.yml`（検証=gemma）。temperatureは judge=0.0、agent=0.7（変更不要）。

## 4. freccia セットアップ
```bash
# venv（各プロジェクト個別。.venv は git管理外）
cd agent && uv sync && cd ..
cd eval  && uv sync && cd ..
# vLLM (serving)。Blackwell(sm_120)は CUDA 12.8+ と対応vLLM/flashinferが必要。
cd serving && uv venv && source .venv/bin/activate && uv pip install -U vllm flashinfer-python && cd ..
# aiwolf Goサーバはバイナリ非追跡 → 再ビルド
cd server/aiwolf && go build -o aiwolf-server . && cd ../..
# APIキー（.env は git管理外。example からコピーして記入）
cp config/.env.example config/.env   # + agent/*/config/.env も同様に
# モデル: google/gemma-4-31B-it を HF からDL（初回vLLM起動で自動 or huggingface-cli）
```

### vLLM 起動（Blackwell = 1枚1エンドポイント）
gemma-4-31B-it は重み約62GB → **96GB 1枚に載る → TP=1**。`serving/start_vllm.sh` を **GPUごとに**起動して
最大7エンドポイント。**max-model-len は 65536 以上**（HB文脈は最大~41kまで伸びる。native 131072）。
```bash
# 例: 7枚それぞれにTP=1で起動（ポート8000..8006）
for g in 0 1 2 3 4 5 6; do
  VLLM_GPUS=$g VLLM_PORT=$((8000+g)) VLLM_MAXLEN=65536 nohup bash serving/start_vllm.sh > serving/vllm_$g.log 2>&1 &
done
```
※ `start_vllm.sh` は `--served-model-name google/gemma-2-27b-it gemma-4-31b` の別名で出す（agent configを変えずに済む）。
※ `--tensor-parallel-size` は VLLM_GPUS の枚数で自動。1枚指定ならTP=1。

## 5. 実行（オーケストレーション）
- **HB難易度プロファイリング**: `serving/profile_hb.sh`（`REPS`対応）。
  英語65問×5反復のbaseline → `eval/src/select_hb_tasks.py` で **評価セット＋台本ソース（妥当性フィルタ＋種別層化＋固定seed）** を `config/hb_task_split.yml` に出力。baselineデータは本実行に再利用可。
  - thalysで英語プロファイリング実行中。完了後 `config/hb_task_split.yml`(EN版) を commit すれば freccia はそれを使うだけでよい（再プロファイル不要。ただし freccia は速いので再実行も可）。
- **本実行**: `serving/run_matrix_parallel.sh`。
  - `ENDPOINTS="http://127.0.0.1:8000/v1 ... :8006/v1"` を**ラウンドロビン**（7エンドポイント並列）。
  - `CONDS="baseline analysis_only utterance_fewshot utterance_fewshot_analysis situation_fewshot situation_fewshot_analysis script_fewshot script_fewshot_analysis"`、`CONDITIONS_FILE=config/conditions_v2.yml`、`LANG_CODE=en`、`HB_RESP_TIMEOUT_MS=600000`。
  - **TODO（要対応）**: 現状の `run_matrix_parallel.sh` はタスクあたり1ゲーム。**反復(REPS)対応が未実装**。`profile_hb.sh` のrepループを移植するか、HB側は `HB_TASK_IDS` を評価タスク集合にして×5回まわす設計に拡張すること。
- **評価**: `make` 系 or `eval/src/` 直接。`evaluate_with_judge.py`（judge=GPTに設定）→ `plot_report.py` → `rankings.py` → `rankings_stability.py`（ブートストラップ信頼性）。

## 6. ハマりどころ（thalysで踏んで修正済み。freccia でも再発しうる）
1. **aiwolf `win_side`**: 進行中は文字列 `"NONE"`（真値!）、決着で `"VILLAGER"`/`"WEREWOLF"`。完了判定は
   **`win_side in (VILLAGER,WEREWOLF)` 必須**（`run_matrix_parallel.sh` 修正済み）。"NONE"を完了扱いすると
   day0 数発話で収集→全ゲーム破壊。
2. **HB文脈オーバーフロー**: round14付近で 40960 超過→agentが400→無言death。**max-model-len≥65536**で回避。
   `wait_game` は "maximum context length" を fast-fail 検知（修正済み）。
3. **エージェント起動バースト**: 1マシンで多ゲーム同時起動すると4×N個のPython spawnでCPU thrash→接続失敗→
   ゲーム未開始。`profile_hb.sh` に stagger＋watchdog（150秒未開始でfast-fail）導入済み。
   **freccia は7エンドポイント＝GPU分離なのでGPU競合は無いが、CPUコア数に注意**（7×4=28 agent spawn）。
   コアが足りなければ同時ストリーム数を絞る。
4. **HBサーバは1ゲーム/起動**（multi-gameサイクル不安定）→ orchestratorは `HB_TASK_IDS` で1ゲームずつ起動。
5. **温度**: agent=0.7 / judge=0.0（適切、変更不要）。
6. **gemmaは judge も生成も同一で検証したが、本番は judge=GPT**（自己選好でなく弁別力＝天井解消のため）。

## 7. freccia でやることの順序（推奨）
1. セットアップ（§4）＋ vLLM 1枚疎通テスト（gemma-4-31bがTP=1で起動するか）。
2. （thalysのEN `hb_task_split.yml` を使う or）英語プロファイリングを freccia で実行（7並列で速い）。
3. **英語exemplar生成**（まだ無い）: 台本ソースから EN の scripts/utterances/analysis_common/situations を生成
   （`generator/` 参照。本番の台本生成は別系統強モデル＝Claude推奨だが、システム単一モデル方針なら gemma でも可。要相談）。
4. `run_matrix_parallel.sh`（REPS拡張後）で 8条件 × 評価タスク × 5反復、ENDPOINTS=7並列、LANG_CODE=en。
5. judge=GPT で評価 → rankings / rankings_stability / plot。

## 8. 参照
- 研究設計: `docs/METHODOLOGY.ja.md` / 指標の読み方: `docs/METRICS.ja.md`
- 結果の置き場: `results/INDEX.md`（命名規則も）
- thalys検証結果: `results/run_jp_8cond_v1plus/`（8条件・rankings_stability あり）
