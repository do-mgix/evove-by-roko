<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import { Capacitor } from "@capacitor/core";
  import { Keyboard } from "@capacitor/keyboard";
  import {
    actOnAction,
    currentPeriod,
    fetchActionWindow,
    fetchActions,
    fetchAttributes,
    type AttrNode,
    fold,
    type Action,
  } from "./api";
  import { GRID_COLS, SHRINK, drawBoxes, pack, polyPath, seeded, type Size } from "./homeLayout";
  import { primeAudio } from "./dtmf";
  import { powerOn, tap } from "./sfx";
  import { bumpLogs, bumpUser, setBackHandler } from "./store";
  import GainsScreen, { type Gain } from "./GainsScreen.svelte";

  /** Back to the tile home. */
  export let onHome: () => void;

  // The screen, top to bottom: the display (messages, and what is being typed),
  // the actions as cells — or, once one is chosen, its tiers — and the bar with
  // two blank buttons: the centre one turns the page, the right one goes home.
  // On the grid of three squares across: rows of a rectangle and a square, or
  // three squares, at most four rows.
  const ROWS = 4;
  const PER_PAGE = 8;
  const GAP = 9;
  // a new page comes on cell by cell, like the home, at uneven moments
  const DELAY = [0, 110, 60, 170, 30, 220, 140, 90];

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
  // the leaves as they stood when the action was chosen, to tell what the act moved
  let before: Map<string, AttrNode> | null = null;
  // after an act, everything gives way to what it paid
  let gains: { title: string; tokens: number; marks: number; list: Gain[]; roko?: string } | null = null;
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

  /** The sizes of a page's cells, row by row: a rectangle and a square either
   *  way round, or three squares — the same for the same page every time. */
  function sizes(n: number, rand: () => number): Size[] {
    const out: Size[] = [];
    while (out.length < n) {
      const left = n - out.length;
      const rows: Size[][] =
        left === 1 ? [["rect"]]
        : left === 2 ? [["rect", "square"], ["square", "rect"]]
        : [["rect", "square"], ["square", "rect"], ["square", "square", "square"]];
      out.push(...rows[Math.floor((rand() + 0.5) * rows.length) % rows.length]);
    }
    return out;
  }

  function layout(list: Action[], seed: number, w: number, h: number) {
    if (!list.length || !w || !h) return [];
    const rand = seeded(seed + 1);
    const { boxes, rows } = pack(sizes(list.length, rand));
    // the squares keep their size from page to page
    const side = Math.min((w * SHRINK) / GRID_COLS, h / ROWS);
    return drawBoxes(boxes, rows, w, h, side, GAP, rand).map((c, i) => ({
      action: list[i],
      d: polyPath(c.shape),
      cx: c.cx,
      cy: c.cy,
      lines: wrap(list[i].name, c.w),
    }));
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
    tap(9);
    selected = action;
    windowMarks = null;
    query = "";
    input?.blur();
    fetchActionWindow(action.id)
      .then((w) => {
        if (selected?.id === action.id) windowMarks = w.window_marks;
      })
      .catch(() => {});
    before = null;
    fetchAttributes()
      .then((list) => {
        if (selected?.id === action.id) before = new Map(list.map((a) => [a.key, a]));
      })
      .catch(() => {});
  }

  /** The leaves whose marks grew since `before`, with where each bar stood. */
  function diff(prev: Map<string, AttrNode> | null, now: AttrNode[]): Gain[] {
    if (!prev) return [];
    return now
      .filter((a) => a.total_marks > (prev.get(a.key)?.total_marks ?? 0))
      .map((a) => {
        const was = prev.get(a.key);
        const rankBefore = was?.rank ?? "A";
        // Still on the same rank: the bar grew from where it was. A rank crossed:
        // the old rank's bar, filled to the end from where it stood — that is the
        // growth worth seeing; a fresh rank at 0/n would show nothing.
        if (was && was.rank_index === a.rank_index) {
          return { key: a.key, name: a.name, rankBefore, rank: a.rank, from: was.marks, marks: a.max ? a.need : a.marks, need: a.need };
        }
        const need = was?.need ?? 3;
        return { key: a.key, name: a.name, rankBefore, rank: a.rank, from: was?.marks ?? 0, marks: need, need };
      })
      .sort((x, y) => y.marks - y.from - (x.marks - x.from));
  }

  async function act(option: number) {
    if (!selected || acting) return;
    const action = selected;
    primeAudio();
    tap(option + 1);
    acting = true;
    try {
      const tier = (action.tiers ?? []).find((t) => t.index === option);
      const prev = before;
      const r = await actOnAction(action.id, { option, period: currentPeriod() });
      const now = r.log_only ? [] : await fetchAttributes().catch(() => []);
      gains = {
        title: tier ? `${r.name} · ${tier.label}` : r.name,
        tokens: r.token_gain - r.tokens_wasted - r.token_cost,
        marks: r.marks,
        list: diff(prev, now),
        roko: r.journey_reset ? "a energia acabou. a jornada recomeçou do primeiro estágio." : undefined,
      };
      message = [];
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
    if (selected) {
      tap(0);
      return cancel();
    }
    page = (page + 1) % pages;
    // the new page comes on, with the sound of it
    powerOn();
  }

  function home() {
    primeAudio();
    tap(0);
    onHome();
  }

  onMount(async () => {
    fullHeight = window.innerHeight;
    window.addEventListener("resize", onResize);
    // a chosen action is undone by back before the page is left
    setBackHandler(() => {
      if (gains) {
        gains = null;
        return true;
      }
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
      if (actions.length) powerOn();
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

{#if gains}
  <GainsScreen
    title={gains.title}
    tokens={gains.tokens}
    marks={gains.marks}
    gains={gains.list}
    roko={gains.roko}
    onDone={() => (gains = null)}
  />
{:else}
<div class="act" class:typing={typing && keyboardUp} class:choosing={!!selected} style="--shrink: {SHRINK}">
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
          {#each cells as c, i (c.action.id)}
            <g class="cell" role="button" tabindex="0" aria-label={c.action.name}
              style="--delay: {DELAY[i % DELAY.length]}ms"
              on:click={() => choose(c.action)}
              on:keydown={(e) => e.key === "Enter" && choose(c.action)}>
              <path class="shape" d={c.d} />
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
{/if}

<style>
  .act {
    --ink: #00f0ff;
    /* text on the dark backdrop */
    --deep: #ffffff;
    position: absolute;
    inset: 0;
    padding: 10px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: transparent;
    user-select: none;
    -webkit-user-select: none;
  }

  .display {
    position: relative;
    flex: 0 0 32%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: flex-end;
    text-align: right;
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
    color: var(--deep);
    overflow-wrap: anywhere;
  }
  .big { font-size: 1.6rem; line-height: 1.15; text-transform: uppercase; }
  .small { font-size: 0.85rem; opacity: 0.7; }

  .cells { flex: 1; min-height: 0; }
  .act.typing .cells { display: none; }
  svg { display: block; width: 100%; height: 100%; }
  .cell {
    cursor: pointer;
    outline: none;
    transform-box: fill-box;
    transform-origin: 50% 50%;
    /* each page comes on like the home does (keyframes in app.css) */
    animation:
      tube-on 0.45s cubic-bezier(0.2, 0.8, 0.3, 1) var(--delay) both,
      settle 0.35s steps(1) calc(var(--delay) + 0.45s) 1;
  }
  @media (prefers-reduced-motion: reduce) {
    .cell { animation: none; }
  }
  .shape {
    /* see-through: a faint wash of jornada's cyan, and its outline */
    fill: var(--ink);
    fill-opacity: 0.1;
    stroke: var(--ink);
    stroke-width: 1.5;
    stroke-linejoin: miter;
  }
  text {
    fill: var(--ink);
    font-family: var(--font-mono);
    font-size: 13px;
    text-anchor: middle;
    dominant-baseline: middle;
    text-transform: uppercase;
  }
  /* pressed, the wash fills in;
     hover only with a real pointer: on touch it sticks to the last cell tapped */
  .cell:focus-visible .shape, .cell:active .shape {
    fill-opacity: 0.3;
  }
  @media (hover: hover) {
    .cell:hover .shape { fill-opacity: 0.3; }
  }

  .tiers {
    flex: 1;
    min-height: 0;
    align-self: flex-end;
    width: calc(var(--shrink) * 100%);
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
    min-height: 3.6rem;
    color: var(--ink);
    font-family: var(--font-mono);
  }
  .tier:disabled { opacity: 0.4; }
  .tier-label { font-size: 0.85rem; }
  .tier-marks { font-size: 1.3rem; }

  /* the bar shrinks into the corner with the cells */
  .bar {
    position: relative;
    flex: 0 0 44px;
    align-self: flex-end;
    width: calc(var(--shrink) * 100%);
    display: flex;
    align-items: stretch;
    justify-content: center;
  }
  .act.typing .bar { display: none; }
  /* see-through, square-cornered, outlined in cyan */
  .tier, .page-btn, .home-btn {
    background: transparent;
    border: 1.5px solid var(--ink);
    border-radius: 0;
    cursor: pointer;
    transition: background 0.06s;
  }
  .page-btn { width: 30%; margin: 4px 0; }
  .home-btn { position: absolute; right: 0; top: 4px; bottom: 4px; width: 16%; }
  /* pressed, a wash of the cyan */
  .tier:active:not(:disabled), .page-btn:active, .home-btn:active {
    background: rgba(0, 240, 255, 0.25);
  }
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
    border: 1px solid var(--deep);
    opacity: 0.6;
  }
  .pages i.on { background: var(--deep); opacity: 1; }
</style>
