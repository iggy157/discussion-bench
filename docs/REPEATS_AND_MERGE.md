# Repeats（反復）の増設と結果の統合

## 1. 反復の作り方（独立サンプルを増やす）
1反復 = 同じ条件×シード集合を **別の RESULTS ディレクトリ** にもう一度回すこと。

- **必ず RESULTS を分ける**（例: `run_en_cond_big_rep1`, `..._rep2`）。
  同一 RESULTS への再実行は **冪等**（既収集ゲームをスキップしてギャップを埋めるだけ）なので、
  独立サンプルは増えません。
- **並列で回すなら RUN_TAG / HB_PORT_BASE / AW_PORT_BASE を必ず変える**（ポート・一時config・
  ログ・aiwolf設定ファイルの衝突回避）。逐次なら同じ RUN_TAG で可。
  - 例: rep1 `RUN_TAG=cbig1 HB_PORT_BASE=8090 AW_PORT_BASE=8080`
        rep2 `RUN_TAG=cbig2 HB_PORT_BASE=8120 AW_PORT_BASE=8110`（≥10 離す）
- **決定性の注意**：シードは固定（HB=task_id、aiwolf=AIWOLF_SEED=game_idx）。同じシードの rep2 は
  **議論エージェントの temperature>0（サンプリング）だからこそ別の対局になる**。temperature=0 だと
  rep は同一になり無意味。reps を増やす前に議論側の温度が >0 か確認すること。

### 既存の自動反復ドライバ
`serving/driver_reps.sh`：締切まで back-to-back に `${RESULTS_PREFIX}_rep{N}` へ回す。
RUN_TAG/HB_PORT_BASE/AW_PORT_BASE で名前空間分離。CONDS/CONDITIONS_FILE を typed10 に差し替えれば流用可。
```bash
RESULTS_PREFIX=run_en_cond_big ENDPOINTS="http://127.0.0.1:8000/v1 http://127.0.0.1:8002/v1" \
  NWORKERS=6 RUN_TAG=cbig HB_PORT_BASE=8090 AW_PORT_BASE=8080 \
  DEADLINE_STR="2026-06-30 06:00" bash serving/driver_reps.sh
# ※driver_reps.sh 内の CONDS_ALL / CONDITIONS_FILE を typed10 に書き換えてから使う
```

## 2. 評価での統合（プールの仕方）

### 客観（discourse / aiwolf-outcome）= そのままプール可 ✅
`--flat`／`--src` を**複数渡す**と全ゲームを1つの大標本として集計（n が単純加算）。
```bash
# discourse（HB/aiwolf）: --flat を repの数だけ
python3 eval/src/evaluate_discourse.py \
  --flat results/run_en_cond_big_rep1/hiddenbench_flat \
  --flat results/run_en_cond_big_rep2/hiddenbench_flat \
  --conds "$K5" --out results/cond/big_hb_discourse_pooled.md --label "big HB K5 pooled"
# aiwolf-outcome: --src を repの数だけ
python3 eval/src/evaluate_aiwolf_outcome.py \
  --src results/run_en_cond_big_rep1/aiwolf --src results/run_en_cond_big_rep2/aiwolf \
  --conds "$K5" --out results/cond/big_aw_outcome_pooled.md --label "big K5 pooled"
```

### 主観（listwise / pairwise）= ⚠ 現状は単純プール不可
listwise/pairwise は **マッチド・シード（game index gN）をキー**にしており、`--flat` を複数渡しても
**同じ gN は最初の1件だけ採用**（rep2 の g1 は無視）＝ n が増えない。

統合する方法は2つ:
- **(A) rep ごとに実行して平均**（実装変更不要・推奨）:
  各 rep で listwise を回し、出力の「条件×criterion 平均順位」を rep 間で平均する。
  ```bash
  for r in rep1 rep2; do
    python3 eval/src/evaluate_listwise_subj.py --flat results/run_en_cond_big_$r/aiwolf_flat \
      --domain aiwolf --conds "$K5" --n-seeds 60 --out results/cond/big_aw_listwise_$r.md --label "big aw K5 $r"
  done
  # -> 2ファイルの平均順位表を手で（or小スクリプトで）平均
  ```
- **(B) コード改修でプール対応**（要望あれば対応）:
  `evaluate_listwise_subj.py` / `evaluate_pairwise_subj.py` のシードキーを `gN` →
  `repdir/gN`（dir も含める）に変えれば、rep2 の g1 が別シード扱いになり n が増える。
  ※マッチド・シード前提（同一シードで条件を横並び比較）は rep 内では保たれる。

## 3. 推奨運用
- まず **repeat=1** で K5(big) / K5+K1(small) を回し、結論の方向を確認。
- ブレが大きい指標だけ **rep2,3 を追加**（RESULTS 別・RUN_TAG別）→ 客観はプール、主観は (A) 平均。
- 反復を増やすのは「効果は見えるが n=1 で誤差内」のときに有効。HB accuracy 系は元々分離が大きいので
  少 rep で十分、aiwolf 系は分離が小さいので rep を増やす価値が相対的に高い。
