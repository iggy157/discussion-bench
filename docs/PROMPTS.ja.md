<!-- 言語: [English](PROMPTS.md) | **日本語** -->

# プロンプト — ファイルで管理し、システム別に分割

エージェントのプロンプトは `agent/` 配下の3層のファイルで管理します。プロンプトを変えるには
これらのファイルを編集すればよく、実行時に読み込まれます（config YAML を触る必要はありません）。

## 構成

```
agent/
  base-prompts/<lang>/*.jinja                 # ① 共有の「土台」部品（再利用ブロック）
                                              #    history / identity / instruction / constraints /
                                              #    event / scenario* ...（code内 {{ block('name') }} で使用）
  aiwolf/prompts/<lang>/<mode>/*.jinja         # ② 人狼のプロンプト一式（リクエスト種別ごと）
                                              #    talk / whisper / vote / divine / guard / attack /
                                              #    initialize / daily_initialize / daily_finish
  hidden-bench/prompts/<lang>/<mode>/*.jinja   # ③ HiddenBench のプロンプト一式
                                              #    initialize / hb_pre / hb_discussion / hb_post
```

どちらの層も Jinja のブロックでできていますが、`base-prompts/` は**共有の再利用部品**
（code内では `block('name')` で参照）、各ドメインの `prompts/` はそれらを**組み立てた**
リクエスト種別ごとの完成プロンプト、という役割分担です。つまり base-prompts＝土台、
ドメインの prompts＝システム別の組み立て、です。

- `<lang>` = `jp` | `en`、`<mode>` = `multi_turn`（実験・UIで使うモード）。
- ファイル名(stem)がリクエストキー：例 `talk.jinja` は `prompt.talk` になる。ドメインの
  ファイルが土台部品を組み合わせる（例 `{{ block('history') }}` + `{{ block('instruction') }}`）。

## 読み込みの仕組み

`agent/src/main.py`（`_apply_file_prompts`）とランチャが、ロード時に
`agent/<pack>/prompts/<lang>/<mode>/*.jinja` を `config.prompt` に重ねます（`pack` は
`config.domain` から `aiwolf` | `hidden-bench`）。ファイルのプロンプトがインライン config を
上書きし、`narration_split` 等の非テンプレ設定は config に残ります。ディレクトリが無ければ
インライン config にフォールバックします。

## 注意

- `single_turn` モードは現状プロンプトを config にインラインで持ちます（ファイル化したい場合は
  `agent/aiwolf/prompts/<lang>/single_turn/` を追加）。
- 共有の土台部品（`base-prompts/<lang>/`）はシステム横断で1つだけ定義（"history" や
  "constraints" など）。システム別に分かれるのはリクエスト種別ごとの組み立てだけです。

## コンポーネント共通の規約

プロンプトを持つコンポーネントは、すべて**同じ言語別分割** — `prompts/<lang>/`（`en` / `jp`）— を
使い、日英対応の仕組みを統一しています。

| コンポーネント | プロンプトファイル |
|-----------|--------------|
| agent | `agent/base-prompts/<lang>/*.jinja`、`agent/<pack>/prompts/<lang>/<mode>/*.jinja` |
| generator | `generator/prompts/<lang>/*.jinja`（system / 台本 / 分析） |
| eval（judge） | `eval/prompts/<lang>/judge.txt`（`ja` は `jp` の別名として受理） |

各言語ファイルは**その言語でネイティブに書き起こし**ています。日本語版は英語からの逐語訳ではなく、
自然な日本語で書いています（逆も同様）。「この言語で書け」という1つのプロンプト＋言語フラグ、という
やり方はとっていません。言語ディレクトリで選びます。
