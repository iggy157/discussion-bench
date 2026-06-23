# archive/

Deprecated components kept for reference only. Not part of the active system, not wired into
`docker-compose.yml`, the `Makefile`, or `run_local.sh`.

廃止済み・参考用に残しているコンポーネント。現行システムの一部ではなく、orchestration からは参照されません。

- **`web/`** — the original minimal HiddenBench human-play lobby. **Superseded by `ui/`**
  (the full browser UI: werewolf + HiddenBench human play). For human participation use `ui/`
  (`cd ui && make up`, then open `http://localhost/hidden-bench`).
