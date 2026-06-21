<script lang="ts">
  // HiddenBench human-play page. A human takes one of the 4 seats; the lobby fills the rest
  // with our condition-aware agents. The browser speaks the SAME wire protocol the agents
  // use (NAME / INITIALIZE / TALK / FINISH); HiddenBench context (phase / clues / options)
  // rides in info.profile as JSON. The full transcript is saved server-side.
  //
  // HiddenBench の人間プレイ画面。人間が4席のうち1席を担当し、残りはロビーが条件付きエージェントで埋める。
  // ブラウザはエージェントと同じプロトコルを話し、フェーズ等は info.profile のJSONで受け取る。
  import { base } from "$app/paths";

  type Phase = "init" | "pre" | "discussion" | "post";
  type HBPayload = {
    phase: Phase;
    description?: string;
    options?: string[];
    clues?: string[];
    round?: number;
    total_rounds?: number;
  };
  type Talk = { agent: string; text: string };

  let lobbyBase = "";

  // --- start screen state ---
  let conditionList = $state<string[]>(["baseline"]);
  let selectedCondition = $state<string>("baseline");
  let humans = $state(1); // 1 = solo (human + 3 AI); 2..4 = multi humans
  let phase = $state<"start" | "connecting" | "playing" | "finished" | "error">("start");
  let errorMsg = $state<string>("");

  // --- in-game state ---
  let name = $state<string>("");
  let payload = $state<HBPayload | null>(null);
  let transcript = $state<Talk[]>([]);
  let messageText = $state<string>("");
  let chosenOption = $state<string>("");
  let awaiting = $state(false); // true while it is our turn to answer/speak
  let socket: WebSocket | null = null;

  async function loadConditions() {
    try {
      const res = await fetch(`${lobbyBase}/api/conditions`);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data.conditions) && data.conditions.length) conditionList = data.conditions;
      if (data.default) selectedCondition = data.default;
    } catch (_e) {
      /* keep defaults */
    }
  }
  let _loaded = false;
  $effect(() => {
    if (!_loaded) {
      _loaded = true;
      loadConditions();
    }
  });

  async function start() {
    phase = "connecting";
    errorMsg = "";
    try {
      // human_slots>1 -> multi (several humans); here we use /api/join for solo and
      // /api/rooms for multi. For simplicity this page uses /api/join (solo) and, for
      // multi, the same endpoint per human (each browser joins the single HiddenBench table).
      const res = await fetch(`${lobbyBase}/api/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: "hiddenbench", condition: selectedCondition }),
      });
      if (!res.ok) throw new Error(`join failed: ${res.status}`);
      const data = await res.json();
      name = data.team ?? "you";
      connect(data.ws_url);
      pollUntilRunning(data.session_id);
    } catch (e) {
      phase = "error";
      errorMsg = e instanceof Error ? e.message : String(e);
    }
  }

  async function pollUntilRunning(sessionId: string) {
    // Best-effort: the AI seats are spawned by the lobby; we just keep our socket open.
    for (let i = 0; i < 60; i++) {
      try {
        const r = await fetch(`${lobbyBase}/api/session/${encodeURIComponent(sessionId)}`);
        if (r.ok) {
          const s = await r.json();
          if (s.status === "running" || s.status === "finished") return;
          if (s.status === "error") {
            phase = "error";
            errorMsg = s.error || "session error";
            return;
          }
        }
      } catch (_e) {
        /* ignore */
      }
      await new Promise((res) => setTimeout(res, 1000));
    }
  }

  function connect(url: string) {
    socket = new WebSocket(url);
    socket.onmessage = (ev) => handlePacket(JSON.parse(ev.data));
    socket.onclose = () => {
      if (phase === "playing" || phase === "connecting") phase = "finished";
    };
    socket.onerror = () => {
      phase = "error";
      errorMsg = "websocket error";
    };
  }

  function send(text: string) {
    socket?.send(text.endsWith("\n") ? text : text + "\n");
  }

  function parsePayload(profile: string | null | undefined): HBPayload | null {
    if (!profile) return null;
    try {
      const obj = JSON.parse(profile);
      return obj && obj.hb ? (obj as HBPayload) : null;
    } catch (_e) {
      return null;
    }
  }

  function handlePacket(pkt: any) {
    const req = pkt.request as string;
    const info = pkt.info ?? {};
    if (req === "NAME") {
      send(name);
      return;
    }
    if (req === "FINISH") {
      phase = "finished";
      socket?.close();
      return;
    }
    if (req === "INITIALIZE") {
      phase = "playing";
      payload = parsePayload(info.profile);
      send("Understood.");
      return;
    }
    if (req === "TALK") {
      payload = parsePayload(info.profile);
      transcript = (pkt.talk_history ?? []).map((t: any) => ({ agent: t.agent, text: t.text }));
      chosenOption = "";
      messageText = "";
      awaiting = true;
      return;
    }
  }

  function submit() {
    if (!payload || !awaiting) return;
    if (payload.phase === "pre" || payload.phase === "post") {
      if (!chosenOption) {
        errorMsg = "Pick an option / 選択肢を選んでください";
        return;
      }
      send(JSON.stringify({ vote: chosenOption, rationale: messageText }));
    } else {
      send(messageText);
    }
    awaiting = false;
    errorMsg = "";
  }
</script>

<main class="mx-auto max-w-2xl p-4">
  {#if phase === "start"}
    <h1 class="text-2xl font-bold">HiddenBench</h1>
    <p class="mt-1 text-sm opacity-70">
      隠れプロファイルの協調推論。4人で手がかりを出し合い、正解を導きます（あなたは1席を担当）。
    </p>
    <div class="mt-4 flex flex-col gap-3">
      <label class="flex items-center gap-2">
        <span class="w-28 text-sm">AI condition</span>
        <select class="select select-bordered select-sm" bind:value={selectedCondition}>
          {#each conditionList as c}
            <option value={c}>{c}</option>
          {/each}
        </select>
      </label>
      <button class="btn btn-primary" onclick={start}>ゲーム開始（人間1＋AI3）</button>
      <p class="text-xs opacity-50">
        人間同士で遊ぶ場合は、同じ画面を複数のブラウザで開いて各自「開始」してください（同一卓に入ります）。
      </p>
    </div>
  {:else if phase === "connecting"}
    <p class="p-8 text-center">接続中… AI席を起動しています。</p>
  {:else if phase === "error"}
    <p class="p-8 text-center text-error">エラー: {errorMsg}</p>
  {:else if phase === "finished"}
    <p class="p-8 text-center">ゲーム終了。ありがとうございました。（全ログはサーバ側に保存されます）</p>
  {:else}
    <!-- playing -->
    <div class="badge badge-neutral">{payload?.phase ?? "—"}</div>
    {#if payload?.description}
      <div class="card mt-3 bg-base-200 p-3 text-sm">
        <div class="font-bold opacity-70">状況</div>
        <div>{payload.description}</div>
      </div>
    {/if}
    {#if payload?.clues?.length}
      <div class="card mt-3 bg-base-200 p-3 text-sm">
        <div class="font-bold opacity-70">あなたの情報（順不同）</div>
        <ul class="list-disc pl-5">
          {#each payload.clues as c}<li>{c}</li>{/each}
        </ul>
      </div>
    {/if}
    {#if transcript.length}
      <div class="card mt-3 bg-base-200 p-3 text-sm">
        <div class="font-bold opacity-70">これまでの議論</div>
        {#each transcript as m}
          <div><span class="font-bold text-primary">{m.agent}</span>: {m.text}</div>
        {/each}
      </div>
    {/if}

    {#if awaiting}
      <div class="card mt-3 bg-base-100 p-3">
        {#if payload?.phase === "pre" || payload?.phase === "post"}
          <div class="text-sm opacity-70">
            {payload?.phase === "pre" ? "討論前の最初の判断。選択肢を1つ。" : "討論後の最終判断。選択肢を1つ。"}
          </div>
          <div class="mt-2 flex flex-wrap gap-2">
            {#each payload?.options ?? [] as o}
              <button
                class="btn btn-sm {chosenOption === o ? 'btn-primary' : 'btn-outline'}"
                onclick={() => (chosenOption = o)}>{o}</button>
            {/each}
          </div>
          <textarea class="textarea textarea-bordered mt-2 w-full" rows="2" placeholder="理由（任意）" bind:value={messageText}
          ></textarea>
        {:else}
          <div class="text-sm opacity-70">あなたの番です。1〜2文で議論に貢献してください。</div>
          <textarea class="textarea textarea-bordered mt-2 w-full" rows="2" placeholder="発言" bind:value={messageText}
          ></textarea>
        {/if}
        <button class="btn btn-primary mt-2" onclick={submit}>送信</button>
        {#if errorMsg}<p class="mt-1 text-xs text-error">{errorMsg}</p>{/if}
      </div>
    {:else}
      <p class="mt-3 text-center text-sm opacity-50">他の参加者の応答を待っています…</p>
    {/if}
  {/if}
</main>
