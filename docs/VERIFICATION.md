<!-- Language: **English** | [日本語](VERIFICATION.ja.md) -->

# Verification: can the existing werewolf server host HiddenBench?

Investigated 2026-06-21.

Before writing a HiddenBench server from scratch, we checked whether the werewolf server we
already have (`aiwolf-nlp-server`, in particular its zero-werewolf "pure discussion" config
`playground.yml`) could be reused. The conclusion: **it is not suitable**, and here is why.

## How HiddenBench actually works

HiddenBench is a "hidden profile" task (paper arXiv:2505.11556 by Li, Naito & Shirado;
reference implementation github.com/jonradoff/hiddenbench; data on HuggingFace
`YuxuanLi1225/HiddenBench`, `benchmark.json`, 65 tasks). Each task is solved by **4 agents**.

A task defines information shared with everyone (`shared_information`), one secret clue handed
to each agent (`hidden_information`), the options (`possible_answers`), and the single correct
answer (`correct_answer`). The key design: looking only at the shared information leads to a
decoy option; only by pooling everyone's secret clues can the group reach the correct answer.

Progress has three phases. **Pre**: each agent privately answers `{vote, rationale}` in JSON
before discussion (pre-accuracy). **Discussion**: T=15 sequential rounds (round 1 in order;
later rounds each responds after seeing all others' latest messages and the full history).
**Post**: each agent answers again after discussion (this is the primary post-accuracy).
Scoring is the proportion choosing the correct option, plus integration gain (post − pre).

## Mapping it onto the werewolf server

`playground.yml` is "0 werewolves / 5 villagers / daytime talk only / no night", i.e. almost
pure discussion. It looks suitable, but the Go engine is built specifically for werewolf, so
mapping the HiddenBench requirements one by one runs aground:

| HiddenBench requirement | Werewolf server | Verdict |
|---|---|---|
| Multi-round discussion with full history | the daytime talk phase can do this | ✅ this part fits |
| Per-agent asymmetric clue distribution | `info.profile` is a single werewolf persona; no distribution mechanism | ❌ forced |
| Pre/post individual answer (option + rationale) | no such request type; a vote targets an *agent*, not an option | ❌ impossible |
| Scoring against a correct option | win/lose is by team (village/werewolf); no "correct option" concept | ❌ impossible |
| Termination | `util/game_util.go:28` returns village-win immediately if werewolves=0; werewolf-population driven | ❌ unlike "collect answers after N rounds" |

The decisive rows are the bottom three. HiddenBench's core — asymmetric clue distribution,
pre/post answers over a fixed option set, and option-based scoring — has no counterpart in the
werewolf protocol. A vote cannot express "option B", and termination is driven by the werewolf
population, which is unlike "discuss for N rounds, then collect answers".

## Conclusion

Therefore the werewolf server (including `playground.yml`) is unsuitable for HiddenBench.
Heavily refactoring the Go engine is also undesirable (it risks breaking working werewolf).

The chosen approach: **keep the werewolf server unmodified for werewolf, and add a small new
Python server for HiddenBench**. Both speak the same WebSocket protocol, so the agent (the
brain) is reused for both. The HiddenBench server reproduces the official protocol faithfully
and reads the real `benchmark.json` directly. Docker Compose runs both servers concurrently,
selectable by config.
