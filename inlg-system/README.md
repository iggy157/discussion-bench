# inlg-system

Orchestration for the INLG study: **one config selects what runs**, and werewolf +
HiddenBench can run **concurrently**. Mirrors the aiwolf-nlp-demo pattern of running
multiple game servers side by side.

INLG研究のオーケストレーション。**設定ひとつで実行内容を選択**し、人狼とHiddenBenchを
**同時起動**できる（aiwolf-nlp-demo方式）。

## The single knob / 単一の操作点

`.env` (copy from `.env.example`) + compose **profiles**:

```bash
cp .env.example .env     # set LANG_CODE, CONDITION, API keys, ports
docker compose --profile hiddenbench up --build              # HiddenBench only
docker compose --profile aiwolf up --build                   # werewolf only
docker compose --profile aiwolf --profile hiddenbench up --build   # BOTH concurrently
```

`.env` keys: `LANG_CODE` (jp|en), `CONDITION` (one of the six), per-domain ports/teams,
and `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `CLAUDE_API_KEY` (passed to agents).

## Services / サービス

| Service | Profile | Port | Notes |
|---------|---------|------|-------|
| `aiwolf-server` | aiwolf | 8080 | Go werewolf server (unmodified), config mounted RO |
| `aiwolf-agents` | aiwolf | – | 5 manyshot agents → werewolf server |
| `hiddenbench-server` | hiddenbench | 8090 | faithful HiddenBench server |
| `hiddenbench-agents` | hiddenbench | – | 4 manyshot agents → HiddenBench server |

Both domains are independent server+agent pairs on different ports, so they coexist.

## The launcher / ランチャ (`launcher/launch_agents.py`)

Makes "one config selects what runs" real for the agents. For a chosen
`(domain, lang, condition)` it:
1. resolves the agent main config, 2. merges the mode child (like manyshot `load_config`),
3. overlays the condition's `scenario` block from
   `aiwolf-jsai-manyshot_ver0/config/conditions/conditions.yml` (paths formatted with
   `{domain}/{lang}`) and stamps the `condition` label, 4. overrides
   `web_socket.url` / `agent.team` / `agent.num`, 5. writes a flat config and runs
   `src/main.py`.

**Safety**: a non-baseline condition whose exemplar directory is empty auto-falls back to
baseline behaviour (so runs never break before you author exemplars).

```bash
# inspect the merged config without launching:
python launcher/launch_agents.py --agent-dir ../aiwolf-jsai-manyshot_ver0 \
  --domain hiddenbench --lang en --condition script_fewshot_analysis --dry-run
```

## Local (no docker) / ローカル

```bash
LANG_CODE=en CONDITION=baseline ./run_local.sh hiddenbench   # server + 4 agents
LANG_CODE=jp CONDITION=baseline ./run_local.sh aiwolf        # go server + 5 agents
```
(uses the manyshot project's `.venv`; HiddenBench results land in
`../hiddenbench-server/log/results`.)

## Makefile / 便利ターゲット

`make hiddenbench | aiwolf | both | down | logs | eval | local-hb`

## Layout / 構成

```
docker-compose.yml             -- both domains, profile-gated
docker/aiwolf-server.Dockerfile        (Go build)
docker/hiddenbench-server.Dockerfile   (Python)
docker/agent.Dockerfile                (shared agent + launcher)
launcher/launch_agents.py      -- domain/condition/lang -> merged config -> run agents
run_local.sh                   -- no-docker dev runner
.env.example                   -- the single knob
Makefile
```
