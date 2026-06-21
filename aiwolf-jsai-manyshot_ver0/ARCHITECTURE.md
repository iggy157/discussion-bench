# アーキテクチャ: プロンプトと `llm_message_history` の流れ

このドキュメントでは、エージェントが LLM とどうやり取りしているかを「**プロンプトの組み立て方**」と「**`llm_message_history` の構造**」の 2 軸で説明します。発表資料・新規参加者向け onboarding を想定。

実装の細部は [doc/](doc/) 以下の機能別ドキュメントを参照。

---

## 1. 全体像: 2 本の独立した履歴

`config.multi_turn.jp.yml` の `llm.separate_langchain: true` のとき、各エージェントは **2 つの独立した会話履歴** を保持します。

```
┌─ Agent (1 process per agent, multiprocessing.spawn) ─────────────┐
│                                                                  │
│   self.llm_message_history_talk    ← talk 系 LLM (例: gpt-5.2)   │
│   self.llm_message_history_action  ← action 系 LLM (例: gpt-4o)  │
│                                                                  │
│   self.talk_history     ← サーバから受信した Talk[] (ランタイム) │
│   self.whisper_history  ← サーバから受信した Whisper[]           │
│   self.info / self.setting  ← 直近の Info / Setting              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

> **重要**: `self.talk_history` と `self.llm_message_history_*` は別物。
> - 前者は**サーバから broadcast された全 Talk オブジェクト**を蓄積したリスト
> - 後者は**LangChain に渡す会話履歴** (HumanMessage / AIMessage が交互に積まれる)
>
> 後者の中の HumanMessage に、`history.jinja` ブロックが前者をレンダしたテキストとして埋め込まれます。

リクエスト種別による振り分け:

| リクエスト | talk 側に追記 | action 側に追記 |
|---|:-:|:-:|
| `INITIALIZE` (共通) | ✓ | ✓ |
| `DAILY_INITIALIZE` (共通) | ✓ | ✓ |
| `DAILY_FINISH` (共通) | ✓ | ✓ |
| `TALK` / `WHISPER` | ✓ | — |
| `VOTE` / `DIVINE` / `GUARD` / `ATTACK` | — | ✓ |

これにより:
- **talk 系 LLM** は会話の自然さに必要な情報 (発話履歴・キャラクター・台本) のみを見る
- **action 系 LLM** は判断に必要な情報 (発話履歴は要約済みで, 各リクエストは対象選択のみ) を見る
- 両者ともキャラクター identity と日次イベントは共有 (共通リクエストで同期)

---

## 2. ゲーム開始前: scenario priming (manyshot)

`Agent.initialize()` の冒頭で `_feed_sample_games()` が走り、両 history に**台本コンテキスト**を焼き込みます。これがこのプロジェクトのコア。

> 補足: `data/sample_games_md/` の **台本そのものは Claude Opus 4.7 で生成** したもの。
> このプロジェクトは「LLM が書いた人狼の対局例 → LLM 自身に分析させて要約 → LLM の世界モデルとして使う」
> という 3 段階の LLM 連携が特徴。詳しくは [doc/system_overview.md](doc/system_overview.md)。

```
両 history の状態 (scenario priming 直後):

  [0] SystemMessage   ← prompts/<lang>/scenario_system.jinja をレンダ
                        target_role 別の出力ルール
                        ("発話本文のみ出力" / "対象名のみ出力" 等)

  [1] HumanMessage    ← prompts/<lang>/scenario.jinja をレンダ
                        - 10 本の manyshot 台本本文 (data/sample_games_md/)
                        - 分析観点指示 (状況→議論の因果 / 応答散らばり / 投票宣言フェーズ等)
                        サイズ: ~37,000 chars (5人村, full delivery)

  [3] AIMessage       ← data/scenario_cache/<dir>/<hash>.json から読み込んだ要約
                        prewarm_scenario.py で事前生成済み
                        サイズ: ~1,500 chars
```

talk 側と action 側で同じ scenario.jinja を target_role 違いでレンダするため、**観点が違う 2 種類の AIMessage 要約**が cache に格納されている。

> **Anthropic の場合**: ここに `cache_control` が `apply_cache_control` 経由で自動注入され、prompt cache の対象になる ([doc/anthropic_cache.md](doc/anthropic_cache.md))。OpenAI は自動キャッシュなので何もしなくても効く。

---

## 3. INITIALIZE 受信時

サーバから INITIALIZE パケット (役職・プロフィール・初期状態) が届くと、`_send_message_to_llm(Request.INITIALIZE)` が両 history に追記:

```
両 history に共通で追加:

  [3] HumanMessage    ← config.prompt.initialize テンプレートをレンダ
                        - block('identity'): キャラクター名・役職・プロフィール
                        - block('instruction'): 「ゲーム開始です」
                        - 末尾: 「これはセットアップメッセージです。役のセリフを生成せず,
                                『了解しました』とだけ返してください」

  [4] AIMessage       ← LLM の応答: 「了解しました」
```

**「了解しました」固定指示の意義**: ここで LLM が自由応答すると "in-character" のセリフを生成し、それが AIMessage として履歴に残る。後続の TALK_PHASE で LLM が「自分が前のターンで言ったこと」と誤認して、まだ誰も発言していないのに「賛成です」のような脈絡無い応答を生む原因になる (= 自己 priming feedback loop)。これを防ぐためのルール。

---

## 4. DAILY_INITIALIZE (Day 開始)

```
両 history に共通で追加:

  [5] HumanMessage    ← config.prompt.daily_initialize テンプレート
                        - block('instruction'): 「N日目が始まりました」
                        - block('event'): その日の出来事 (前日の処刑・襲撃・自分の占い結果等)

  [6] AIMessage       ← 「了解しました」
```

これで **両系統が同期** (= 何が起きているかについて同じ事実を持つ)。

---

## 5. Talk フェーズ (talk 側のみ更新)

サーバから TALK リクエスト (request/response 仕様) または TALK_PHASE_START (freeform 仕様) が届くと、talk 系 LLM が呼ばれる。

```
talk 側 history (TALK 1 回目後):

  [0]-[6] 上記まで ...
  [7] HumanMessage    ← config.prompt.talk テンプレート
                        - block('history'): self.talk_history 全件をテキスト化
                          (例: "ダイスケ: あ、えと…ダイスケです。よろしく")
                        - block('instruction'): 「N日目のトークです」
                        - block('constraints'):
                            * 文字数制限 (50 文字以内 + @-mention で +50 等)
                            * 本日のあなたの発話状況: 既に 2 回発話済み, 残り 2 回
                            * (freeform時) [PASS] 指示 + remain_talk_map 表示
                            * (narration_split時)「」必須・ト書き許可

  [8] AIMessage       ← LLM の生成した発話 (例: 「占い理由を整理します。サクラさんを占ったのは…」)

(以降、TALK 2 回目, 3 回目 ... と同様に [HumanMessage, AIMessage] が積まれる)
```

action 側 history はこの間まったく不変。

> 注意: HumanMessage 内の `block('history')` は **`self.talk_history` (Agent attribute)** をレンダする。`llm_message_history_talk` 自体ではない。両者は独立したデータ構造。

---

## 6. Action リクエスト (action 側のみ更新)

VOTE / DIVINE / GUARD / ATTACK は対象選択 1 件出力。

```
action 側 history (VOTE 1 回目後):

  [0]-[6] 上記まで ...
  [7] HumanMessage    ← config.prompt.vote テンプレート
                        - block('instruction'): 「投票対象を1名選んで...」
                        - 対象一覧: 生存エージェント名のリスト
                        - block('constraints'): 「対象エージェント名のみを出力」

  [8] AIMessage       ← LLM の応答 (例: "サクラ")
```

talk 側 history は不変。action 側は talk 側よりずっと薄い (1 ゲームで ~10〜15 回程度)。

---

## 7. DAILY_FINISH (Day 終了)

```
両 history に共通で追加:

  [n]   HumanMessage  ← config.prompt.daily_finish テンプレート
                        - block('instruction'): 「N日目が終了しました」
                        - block('event'): 投票結果・処刑者
                        - block('history'): その日の talk_history 全件
                        - 末尾: 「役のセリフ・感想を生成せず, 『了解しました』」

  [n+1] AIMessage     ← 「了解しました」
```

これも自己 priming 防止の固定応答。

---

## 8. ゲーム終盤の history イメージ

3 日間対局・5 人村の talk 側 history は最終的にこんな構造になる:

```
[0]   SystemMessage    scenario rules                          (~700 chars)
[1]   HumanMessage     manyshot 台本 + 分析指示               (~37,000 chars)  ←─┐
[2]   AIMessage        scenario cache 要約                    (~1,500 chars)    │ Anthropic
                                                                                │ cache 対象
[3]   HumanMessage     INITIALIZE (identity + 了解指示)                         │ (ほぼ
[4]   AIMessage        了解しました                                             │  不変)
[5]   HumanMessage     Day 0 DAILY_INITIALIZE                                   │
[6]   AIMessage        了解しました                                             │
[7]   HumanMessage     Day 0 TALK #1 (history は空)                             │
[8]   AIMessage        Day 0 自分の発話 #1                                      │
[9]   HumanMessage     Day 0 TALK #2 (history は 1〜数件)                       │
[10]  AIMessage        Day 0 自分の発話 #2                                      │
... Day 0 TALK × 2〜4 回 ...                                                    │
[15]  HumanMessage     Day 0 DAILY_FINISH (投票結果込み)                        │
[16]  AIMessage        了解しました                                             │
[17]  HumanMessage     Day 1 DAILY_INITIALIZE (占い結果込み)                    │
[18]  AIMessage        了解しました                                             │
... Day 1 TALK × ~4 回 ...                                                      │
[27]  HumanMessage     Day 1 DAILY_FINISH                                       │
[28]  AIMessage        了解しました                                             │
... Day 2 cycle (TALK × ~4 + DAILY_FINISH) ...                                  │
[40]  HumanMessage     直近の TALK request                                     ─┘ ← cache breakpoint
[41]  AIMessage        現ターンの発話 (← 今まさに生成された)
```

サイズの目安:
- 全体トークン数: ~50,000-80,000 (うち scenario 部分が圧倒的)
- `cache_control` で大半を cached_input にすれば、毎ターンのコストは数十円〜数百円台に抑えられる ([doc/cost.md](doc/cost.md))。

---

## 9. 新規 HumanMessage の組み立て (Jinja2 テンプレート 3 層構造)

各リクエストで生成される HumanMessage は config の `prompt.<request>` テンプレートが起点だが、その中で `{{ block('...') }}` 経由で複数の prompt block をレンダして合成する:

```
config.prompt.talk:        ← config/config.multi_turn.jp.yml で定義
  |
  ├─ {{ block('history') }}      → prompts/jp/history.jinja
  │                                 (self.talk_history を見出し付きで列挙)
  │
  ├─ {{ block('instruction') }}  → prompts/jp/instruction.jinja
  │                                 (request_key で分岐: 「N日目のトークです」等)
  │
  └─ {{ block('constraints') }}  → prompts/jp/constraints.jinja
                                    (request_key で分岐, 文字数制限・talk_state・
                                     freeform時 [PASS] / remain_talk_map・
                                     narration_split時「」必須等)
```

`block()` グローバルは `src/utils/jinja_env.py` で定義。`headings.enabled: true` のとき各ブロック冒頭に見出し (`### 履歴` 等, `prompts/<lang>/_labels.yml` で定義) を自動付与する。

### 各 block の主な変数

| Block | 主な変数 |
|---|---|
| `identity` | `info.agent` / `role.value` / `info.profile` / `local_profile` (`profile.source: local` 時) |
| `history` | `history_source` (`talk_history` or `whisper_history`) / `history_start` (差分送信用 offset) / `info` |
| `event` | `day_events` (single-turn で蓄積) / `info` (multi-turn で直接) |
| `instruction` | `request_key` |
| `constraints` | `request_key` / `setting` / `info.remain_length` / `talk_state` / `remain_talk_map` / `narration_split` / `freeform` |

---

## 10. モード別の差分

| モード | history の違い |
|---|---|
| **multi-turn** (現在の既定) | 上記の通り `llm_message_history_*` を蓄積。`scenario priming` が活きる |
| **single-turn** | `llm_message_history` を **使わない**。毎リクエストで必要な全コンテキスト (identity + event + history + instruction + constraints) を 1 個の HumanMessage に詰めて単発送信。INITIALIZE/DAILY_INITIALIZE/DAILY_FINISH は LLM に送らず agent 内 `day_events` に保存 |
| **separate_langchain: true** (現在の既定) | talk / action で別 LLM 履歴。共通リクエストは両方に積む |
| **separate_langchain: false** | 単一 LLM 履歴 (`llm_message_history`)。target_role は `default` |
| **scenario.delivery: full** (現在の既定) | scenario priming は INITIALIZE 時 1 回だけ |
| **scenario.delivery: by_day** | scenario priming が Day ごと。Day 0 は INITIALIZE 時、Day 1+ は DAILY_INITIALIZE 時に該当 day の章節 chunk が追加される (`scenario_daily.jinja`) |
| **agent.freeform: true** | `[PASS]` 制御トークン + `remain_talk_map` がプロンプトに表示。`handle_talk_phase` が初回 stagger (0〜3秒) と `[PASS]` 検出を行う ([doc/freeform.md](doc/freeform.md)) |
| **prompt.narration_split: true** | LLM の応答が `「セリフ」 + ト書き` 形式。サーバ送信前に「」内側のみ抽出 ([doc/narration_split.md](doc/narration_split.md)) |
| **anthropic.cache: true** (Claude のみ・既定 true) | 最後の AIMessage に `cache_control` を自動注入し、prompt cache 対象化 ([doc/anthropic_cache.md](doc/anthropic_cache.md)) |

---

## 11. なぜこういう設計か

| 設計判断 | 理由 |
|---|---|
| **scenario priming を history 先頭に置く** | LLM が常に参照する "世界モデル" として機能。Anthropic cache_control もここを対象にできる |
| **prewarm + cache 機構** | scenario summary を毎ゲーム生成すると INITIALIZE タイムアウト (60s) を超える。事前生成して cache 読みすれば LLM 呼び出しゼロで起動可能 |
| **separate_langchain で talk/action 分離** | talk = 自然さ重視 (高品質モデル + 大量履歴)、action = 判断精度重視 (軽量モデル可・履歴薄)。同じモデルで両方やると talk 側のノイズが action に漏れる |
| **共通リクエストは両 history に同期** | identity と日次イベントは両方で必要。分離しすぎると整合性が崩壊する |
| **共通リクエストの応答を「了解しました」固定** | LLM の自由応答が AIMessage に残ると、後続の TALK で「自分が前ターンで言ったこと」と誤参照される (履歴ありき発言の原因) |
| **runtime に self.talk_history を別途持つ** | サーバ broadcast されたすべての Talk を蓄積し、各 talk リクエストで `history.jinja` ブロックが整形して HumanMessage 内に埋め込む。LangChain 履歴とは独立 |
| **Jinja2 ブロックで prompt を合成** | block 単位で再利用・switch (lang / mode / freeform / narration_split 等の axis を直交させやすい) |
| **mechanics flag (5p/9p/13p)** | 5 人村では囁き・護衛・霊媒が起きないので、prompt 内でこれらの語を出さない (誤誘導防止) |

---

## 12. 確認・デバッグ手段

| やりたいこと | 手段 |
|---|---|
| 各リクエストでどんな HumanMessage がレンダされるか確認 | `uv run python scripts/preview_prompt.py` → `preview.md` を見る |
| scenario cache の中身を確認 | `data/scenario_cache_readable/<dir>/*.md` を見る |
| 実ゲーム中の LLM やり取り | `log/<game>/<agent>.log` の `LLM` 行 (prompt + response 完全記録) |
| コスト集計 | `log/<game>/cost_summary.md` (finish 時生成) |

---

## 13. 関連ドキュメント

- [README.md](README.md) — システム全体概要・クイックスタート
- [doc/scenario_cache.md](doc/scenario_cache.md) — manyshot priming のキャッシュ詳細
- [doc/freeform.md](doc/freeform.md) — グループチャット仕様向け挙動
- [doc/narration_split.md](doc/narration_split.md) — 「」抽出モード
- [doc/anthropic_cache.md](doc/anthropic_cache.md) — Claude prompt cache 自動注入
- [doc/cost.md](doc/cost.md) — コストトレース仕組み
- [doc/config_reference.md](doc/config_reference.md) — 全フラグ一覧
- [preview.md](preview.md) — (生成物) jp/en × multi_turn/single_turn の全プロンプト実例
