<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import { Capacitor } from "@capacitor/core";
  import { Keyboard } from "@capacitor/keyboard";
  import {
    actOnAction,
    currentPeriod,
    fetchActionWindow,
    fetchActions,
    fold,
    type Action,
  } from "./api";
  import { centroid, inset, jitteredGrid, type Point } from "./homeLayout";
  import { keyFeedback, primeAudio } from "./dtmf";
  import { bumpLogs, bumpUser, setBackHandler } from "./store";

  /** Back to the tile home. */
  export let onHome: () => void;

  // The screen, top to bottom: the display (messages, and what is being typed),
  // the actions as cells — or, once one is chosen, its tiers — and the bar with
  // two blank buttons: the centre one turns the page, the right one goes home.
  const COLS = 2;
  const ROWS = 4;
  const PER_PAGE = COLS * ROWS;
  const GAP = 5;

  let actions: Action[] = [];
  let loading = true;
  let page = 0;
  let query = "";
  let typing = false;
  // a soft keyboard is up: the window shrank under it. With a physical keyboard
  // nothing shrinks, and the cells stay, filtering as you type.
  let keyboardUp = false;
  let selected: Action | null = null;
  let windowMarks: number | null = null;
  let acting = false;
  // what the display says when nobody is typing: the last act, or an error
  let message: string[] = [];
  let input: HTMLInputElement;
  let width = 0;
  let height = 0;

  // ---- what is typed picks the action ----
  $: q = fold(query.trim());
  $: matches = !q
    ? []
    : /^\d+$/.test(q)
      ? actions.filter((a) => a.id.startsWith(q))
      : actions.filter((a) => fold(a.name).includes(q));
  // one match left: it is the one, no need to confirm
  $: if (typing && matches.length === 1 && !selected) choose(matches[0]);

  // ---- the cells of the current page: everything, or what the typing matches ----
  $: shown = q ? matches : actions;
  $: pages = Math.max(1, Math.ceil(shown.length / PER_PAGE));
  $: if (page >= pages) page = 0;
  $: onPage = shown.slice(page * PER_PAGE, (page + 1) * PER_PAGE);
  $: cells = layout(onPage, page, width, height);

  function layout(list: Action[], seed: number, w: number, h: number) {
    if (!list.length || !w || !h) return [];
    const rows = Math.ceil(list.length / COLS);
    let polys = jitteredGrid(COLS, rows, seed + 1);
    // an odd count: the last cell spans the last row
    if (list.length % COLS === 1) {
      const a = polys[polys.length - 2];
      const b = polys[polys.length - 1];
      polys = [...polys.slice(0, -2), [a[0], b[1], b[2], a[3]]];
    }
    return list.map((action, i) => {
      const shape = inset(polys[i].map(([x, y]) => [x * w, y * h] as Point), GAP);
      const [cx, cy] = centroid(shape);
      const xs = shape.map((p) => p[0]);
      const cellW = Math.max(...xs) - Math.min(...xs);
      return { action, points: shape.map((p) => p.join(",")).join(" "), cx, cy, lines: wrap(action.name, cellW) };
    });
  }

  /** Breaks a name into lines that fit a cell, at most three. */
  function wrap(name: string, cellW: number): string[] {
    const perLine = Math.max(6, Math.floor((cellW - 16) / 8.4));
    const lines: string[] = [];
    let line = "";
    for (const word of name.split(/\s+/)) {
      if (line && (line + " " + word).length > perLine) {
        lines.push(line);
        line = word;
      } else line = line ? `${line} ${word}` : word;
    }
    if (line) lines.push(line);
    return lines.slice(0, 3);
  }

  // ---- the keyboard ----
  // Focusing a field from code does not raise Android's soft keyboard, so on the
  // phone it is asked for explicitly.
  function raiseKeyboard() {
    input?.focus();
    if (Capacitor.isNativePlatform()) Keyboard.show().catch(() => {});
  }

  function openKeyboard() {
    selected = null;
    raiseKeyboard();
  }

  function onFocus() {
    typing = true;
  }

  function onBlur() {
    typing = false;
    if (!selected) query = "";
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "Enter" && matches.length > 0) {
      e.preventDefault();
      choose(matches[0]);
    } else if (e.key === "Escape") {
      input.blur();
    }
  }

  // Android's back key closes the soft keyboard without blurring the field; when
  // the window grows back to its full height, the keyboard is gone.
  let fullHeight = 0;
  function onResize() {
    const h = window.innerHeight;
    if (h > fullHeight) fullHeight = h;
    const wasUp = keyboardUp;
    keyboardUp = h < fullHeight * 0.85;
    if (wasUp && !keyboardUp && typing) input?.blur();
  }

  // ---- choosing, then acting ----
  function choose(action: Action) {
    primeAudio();
    keyFeedback("#");
    selected = action;
    windowMarks = null;
    query = "";
    input?.blur();
    fetchActionWindow(action.id)
      .then((w) => {
        if (selected?.id === action.id) windowMarks = w.window_marks;
      })
      .catch(() => {});
  }

  async function act(option: number) {
    if (!selected || acting) return;
    const action = selected;
    primeAudio();
    keyFeedback(String((option % 9) + 1));
    acting = true;
    try {
      const r = await actOnAction(action.id, { option, period: currentPeriod() });
      message = [
        `+${r.marks} ${r.marks === 1 ? "marca" : "marcas"}`,
        r.name,
        `${r.window_marks}/${r.window_limit} na janela`,
      ];
      if (r.energy_penalty) message.push(`−${r.energy_penalty} energia`);
      if (r.journey_reset) message.push("a energia acabou · jornada no estágio 1");
      bumpLogs();
      bumpUser();
      selected = null;
    } catch (e: any) {
      message = [e?.message ?? "erro ao agir"];
    } finally {
      acting = false;
    }
  }

  function cancel() {
    selected = null;
  }

  // ---- the bar ----
  function nextPage() {
    primeAudio();
    keyFeedback("0");
    if (selected) return cancel();
    page = (page + 1) % pages;
  }

  function home() {
    primeAudio();
    keyFeedback("*");
    onHome();
  }

  onMount(async () => {
    fullHeight = window.innerHeight;
    window.addEventListener("resize", onResize);
    // a chosen action is undone by back before the page is left
    setBackHandler(() => {
      if (selected) {
        cancel();
        return true;
      }
      return false;
    });
    // the keyboard opens on arrival: typing is the fastest way to an action
    await tick();
    raiseKeyboard();
    try {
      actions = await fetchActions();
      if (!actions.length) message = ["nenhuma ação ainda", "adquira uma no shop"];
    } catch (e: any) {
      message = [e?.message ?? "erro ao carregar"];
    } finally {
      loading = false;
    }
  });

  onDestroy(() => {
    window.removeEventListener("resize", onResize);
    setBackHandler(null);
  });
</script>

<div class="act" class:typing={typing && keyboardUp} class:choosing={!!selected}>
  <!-- the display: messages, what is typed, what was chosen -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="display" on:click={openKeyboard}>
    <input
      bind:this={input}
      bind:value={query}
      class="field"
      type="text"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      enterkeyhint="go"
      aria-label="ação"
      on:focus={onFocus}
      on:blur={onBlur}
      on:keydown={onKey}
    />
    {#if selected}
      <p class="big">{selected.name}</p>
      <p class="small">{windowMarks === null ? "…" : `${windowMarks}/5 marcas nas últimas 6h`}</p>
    {:else if typing}
      <p class="big">{query || "▍"}</p>
      {#if q}
        <p class="small">
          {#if matches.length}{matches[0].name}{#if matches.length > 1} · +{matches.length - 1}{/if}{:else}nada{/if}
        </p>
      {/if}
    {:else if loading}
      <p class="small">…</p>
    {:else}
      {#each message as line, i}<p class={i === 0 ? "big" : "small"}>{line}</p>{/each}
    {/if}
  </div>

  {#if selected}
    <!-- the margin rises: the tiers of the chosen action -->
    <div class="tiers">
      {#each selected.tiers ?? [] as t (t.index)}
        <button class="tier" disabled={acting} on:click={() => act(t.index)}>
          <span class="tier-label">{t.label}</span>
          <span class="tier-marks">{t.marks}</span>
        </button>
      {/each}
    </div>
  {:else}
    <div class="cells" bind:clientWidth={width} bind:clientHeight={height}>
      {#if width && height}
        <svg viewBox="0 0 {width} {height}" width={width} height={height}>
          {#each cells as c (c.action.id)}
            <g class="cell" role="button" tabindex="0" aria-label={c.action.name}
              on:click={() => choose(c.action)}
              on:keydown={(e) => e.key === "Enter" && choose(c.action)}>
              <polygon points={c.points} />
              <text x={c.cx} y={c.cy - ((c.lines.length - 1) * 16) / 2}>
                {#each c.lines as line, i}<tspan x={c.cx} dy={i === 0 ? 0 : 16}>{line}</tspan>{/each}
              </text>
            </g>
          {/each}
        </svg>
      {/if}
    </div>
  {/if}

  <!-- two blank buttons: the page, and home -->
  <div class="bar">
    <span class="pages" aria-hidden="true">{#if pages > 1}{#each Array(pages) as _, i}<i class:on={i === page}></i>{/each}{/if}</span>
    <button class="page-btn" aria-label={selected ? "cancelar" : "próxima página"} on:click={nextPage}></button>
    <button class="home-btn" aria-label="início" on:click={home}></button>
  </div>
</div>

<style>
  .act {
    --ink: #ffd23f;
    position: absolute;
    inset: 0;
    padding: 10px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: #000000;
    user-select: none;
    -webkit-user-select: none;
  }

  .display {
    position: relative;
    flex: 0 0 32%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    gap: 0.4rem;
    padding: 0.5rem 0.4rem;
    overflow: hidden;
    cursor: text;
  }
  /* with the keyboard up, the display is all there is above it */
  .act.typing .display { flex: 1; }
  .field {
    position: absolute;
    opacity: 0;
    width: 1px;
    height: 1px;
    border: 0;
    padding: 0;
    pointer-events: none;
  }
  .big, .small {
    margin: 0;
    font-family: var(--font-mono);
    color: var(--ink);
    overflow-wrap: anywhere;
  }
  .big { font-size: 1.6rem; line-height: 1.15; text-transform: uppercase; }
  .small { font-size: 0.85rem; opacity: 0.7; }

  .cells { flex: 1; min-height: 0; }
  .act.typing .cells { display: none; }
  svg { display: block; width: 100%; height: 100%; }
  .cell { cursor: pointer; outline: none; }
  polygon {
    fill: #000000;
    stroke: var(--ink);
    stroke-opacity: 0.55;
    stroke-width: 1.5;
  }
  text {
    fill: var(--ink);
    font-family: var(--font-mono);
    font-size: 13px;
    text-anchor: middle;
    dominant-baseline: middle;
    text-transform: uppercase;
  }
  .cell:hover polygon, .cell:focus-visible polygon, .cell:active polygon { stroke: #ffffff; stroke-opacity: 1; }
  .cell:hover text, .cell:focus-visible text, .cell:active text { fill: #ffffff; }

  .tiers {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-auto-rows: 1fr;
    gap: 8px;
    align-content: end;
  }
  .tier {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.3rem;
    min-height: 4.5rem;
    background: #000000;
    border: 1.5px solid var(--ink);
    color: var(--ink);
    font-family: var(--font-mono);
    cursor: pointer;
  }
  .tier:active:not(:disabled), .tier:hover:not(:disabled) { border-color: #ffffff; color: #ffffff; }
  .tier:disabled { opacity: 0.4; }
  .tier-label { font-size: 0.85rem; }
  .tier-marks { font-size: 1.3rem; }

  .bar {
    position: relative;
    flex: 0 0 56px;
    display: flex;
    align-items: stretch;
    justify-content: center;
  }
  .act.typing .bar { display: none; }
  .page-btn, .home-btn {
    background: #000000;
    border: 1.5px solid var(--ink);
    cursor: pointer;
  }
  .page-btn { width: 34%; }
  .home-btn { position: absolute; right: 0; top: 0; bottom: 0; width: 18%; }
  .page-btn:active, .home-btn:active, .page-btn:hover, .home-btn:hover { border-color: #ffffff; }
  .pages {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    gap: 5px;
  }
  .pages i {
    width: 6px;
    height: 6px;
    border: 1px solid var(--ink);
    opacity: 0.6;
  }
  .pages i.on { background: var(--ink); opacity: 1; }
</style>
