<!-- Language: **English** | [日本語](PROMPTS.ja.md) -->

# Prompts — managed as files, split by system

Agent prompts live as files in three layers under `agent/`. Edit these files to change
prompts — they are loaded at runtime (no need to touch the config YAML).

## Layout

```
agent/
  base-prompts/<lang>/*.jinja                 # ① SHARED base parts (reusable blocks)
                                              #    history / identity / instruction / constraints /
                                              #    event / scenario* ...  (used via {{ block('name') }})
  aiwolf/prompts/<lang>/<mode>/*.jinja         # ② Werewolf prompt set (per request type)
                                              #    talk / whisper / vote / divine / guard / attack /
                                              #    initialize / daily_initialize / daily_finish
  hidden-bench/prompts/<lang>/<mode>/*.jinja   # ③ HiddenBench prompt set
                                              #    initialize / hb_pre / hb_discussion / hb_post
```

Both layers are made of Jinja blocks, but `base-prompts/` holds the **shared, reusable
parts** (referenced in code as `block('name')`), while each domain's `prompts/` **assembles**
those parts into a finished prompt per request type. So: base-prompts = the base, domain
prompts = the per-system compositions.

- `<lang>` = `jp` | `en`; `<mode>` = `multi_turn` (the mode the experiments / UI use).
- A file's stem is the request key: e.g. `talk.jinja` becomes `prompt.talk`. Domain files
  compose the base parts, e.g. `{{ block('history') }}` + `{{ block('instruction') }}`.

## How it loads

`agent/src/main.py` (`_apply_file_prompts`) and the launcher both overlay
`agent/<pack>/prompts/<lang>/<mode>/*.jinja` onto `config.prompt` at load time, where `pack`
= `aiwolf` | `hidden-bench` (from `config.domain`). File prompts override any inline
`config.prompt` entries; non-template flags (e.g. `narration_split`) stay in the config. If a
directory is absent, the inline config is used as a fallback.

## Notes

- `single_turn` mode keeps its prompts inline in the config (no file dir yet); add
  `agent/aiwolf/prompts/<lang>/single_turn/` if you want to externalize it too.
- The shared base parts (`base-prompts/<lang>/`) are cross-system by design (one definition
  of "history", "constraints", etc.); only the per-request compositions are split by system.
