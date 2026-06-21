# Prompts — managed as files, split by system / プロンプトのファイル管理（システム別）

Agent prompts live as files in three layers. Edit these files to change prompts — they are
loaded at runtime (no need to touch the config YAML).

エージェントのプロンプトは3層のファイルで管理する。プロンプトを変えるにはこれらのファイルを編集
すればよい（config YAML を触る必要はない。実行時に読み込まれる）。

## Layout / 構成

```
agent/
  prompts/<lang>/*.jinja                     # ① SHARED blocks used by both systems
                                             #    両システム共通のブロック
                                             #    history / identity / instruction / constraints /
                                             #    event / scenario* ...  (referenced via {{ block('name') }})
  aiwolf/prompts/<lang>/<mode>/*.jinja        # ② Werewolf prompt set (per request type)
                                             #    人狼のプロンプト一式（リクエスト種別ごと）
                                             #    talk / whisper / vote / divine / guard / attack /
                                             #    initialize / daily_initialize / daily_finish
  hidden-bench/prompts/<lang>/<mode>/*.jinja  # ③ HiddenBench prompt set
                                             #    initialize / hb_pre / hb_discussion / hb_post
```

- `<lang>` = `jp` | `en`; `<mode>` = `multi_turn` (the mode the experiments/UI use).
- A file's stem is the request key: e.g. `talk.jinja` becomes `prompt.talk`. Domain files
  compose the shared blocks, e.g. `{{ block('history') }}` + `{{ block('instruction') }}`.
  / ファイル名(stem)がリクエストキー。ドメインのファイルが共通ブロックを組み合わせる。

## How it loads / 読み込みの仕組み

`src/main.py` (`_apply_file_prompts`) and the launcher both overlay
`agent/<pack>/prompts/<lang>/<mode>/*.jinja` onto `config.prompt` at load time, where
`pack` = `aiwolf` | `hidden-bench` (from `config.domain`). File prompts override any inline
`config.prompt` entries; non-template flags (e.g. `narration_split`) stay in the config.
If a directory is absent, the inline config is used as a fallback.

`src/main.py` とランチャが、ロード時に `agent/<pack>/prompts/<lang>/<mode>/*.jinja` を
`config.prompt` に重ねる。ファイルが優先。`narration_split` 等の非テンプレ設定は config に残す。
ディレクトリが無ければ従来のインライン config にフォールバックする。

## Notes / 注意

- `single_turn` mode keeps its prompts inline in the config (no file dir yet); add
  `agent/aiwolf/prompts/<lang>/single_turn/` if you want to externalize it too.
- The shared blocks (`prompts/<lang>/`) are cross-system by design (one definition of
  "history", "constraints", etc.); only the per-request compositions are split by system.
