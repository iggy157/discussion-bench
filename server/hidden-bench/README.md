# hidden-bench server

Faithful **HiddenBench** (hidden-profile collaborative reasoning) WebSocket game server
for the INLG study. Hosts the exact protocol of Li, Naito & Shirado
([arXiv:2505.11556](https://arxiv.org/abs/2505.11556)) so the shared manyshot agent can
play HiddenBench the same way it plays werewolf.

INLG研究のための **HiddenBench**（隠れプロファイル協調推論）WebSocketゲームサーバ。
論文 (2505.11556) のプロトコルを忠実にホストし、共有エージェントが人狼と同じ要領で
HiddenBenchをプレイできるようにする。

## Faithfulness / 忠実性

| Item | Value | Source |
|------|-------|--------|
| Agents / エージェント | 4 | paper §4.2 |
| Discussion rounds | **fixed T=15**, no early stop | paper §4.2 (the jonradoff repo's consensus early-stop is an implementation extra, **off** here) |
| Turn order | round 1 sequential; later rounds each sees the full prior transcript | paper §4.2 (enforced by eliciting agents strictly in order with growing `talk_history`) |
| Pre/post elicitation | individual `{"vote","rationale"}` JSON | repo `prompts.py` |
| Scoring | average-rule & majority-rule accuracy; integration gain = post−pre | paper §3 |
| Data | HuggingFace `YuxuanLi1225/HiddenBench` (`data/benchmark.json`, 65 tasks) | dataset card |

Cite the **paper** (Li et al.) for the paradigm/metrics and the **repo** (Radoff) only for
prompt strings. See `../INLG_METHODOLOGY.md` §2.

## Protocol on the wire / ワイヤプロトコル

Reuses only aiwolf-nlp-common 0.7.0 request types (NAME / INITIALIZE / TALK / FINISH).
HiddenBench context (phase / clues / options / round) is carried as JSON in `info.profile`.
The discussion uses **traditional TALK request/response**, which gives the server exact
sequential turn control. Pre-answer / each discussion turn / post-answer are all TALK,
distinguished by `payload.phase` (`pre` / `discussion` / `post`).

## Run / 実行

```bash
uv sync                                   # or: pip install websockets pyyaml
uv run src/server.py -c config/hiddenbench.yml
# agents then connect to ws://<host>:8090/ws
```

Smoke test with canned-response stubs (no LLM):
```bash
uv run src/server.py -c config/hiddenbench.yml &
python tests/stub_agent.py ws://127.0.0.1:8090/ws P1   # x4 (in 4 shells / background)
```

## Config / 設定 (`config/hiddenbench.yml`)

Key knobs: `agent_count` (4), `total_rounds` (15), `lang` (en/ja), `condition` label,
`task_ids` / `task_limit` (which tasks; keep **disjoint** from exemplar tasks —
leakage control), `repeats_per_task`, `seed`, `output_dir`.

Per-game result JSON (transcript, clue distribution, pre/post decisions, scores) is written
to `output_dir` and consumed by `../eval`.

## Bilingual data / 二言語データ

`lang: en` reads `data/benchmark.json` (upstream English). `lang: ja` reads
`data/benchmark.ja.json` if you drop in a Japanese translation, else falls back to English.
The agent-side framing (system/options wording) is bilingual via the agent's JP/EN configs.

## Layout / 構成

```
src/
  task.py      -- benchmark loading, round-robin hidden-info distribution, per-agent clues
  protocol.py  -- packet builders (Info/Setting JSON compatible with the agent client)
  answer.py    -- lenient JSON/option extraction + average/majority scoring
  game.py      -- the faithful 3-phase protocol + GameResult
  server.py    -- websockets server, matchmaking, sequential game loop
config/hiddenbench.yml
data/benchmark.json   -- 65 official tasks
tests/stub_agent.py   -- canned-response agent for integration testing
```
