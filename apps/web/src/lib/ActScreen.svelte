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
  import { GRID_COLS, GRID_GAP, SLANT, drawBoxes, formsFor, gridUnit, packFree, polyPath, seeded } from "./homeLayout";
  import Icon from "./Icon.svelte";
  import { primeAudio } from "./dtmf";
  import { powerOn, tap } from "./sfx";
  import { bumpLogs, bumpUser, setBackHandler } from "./store";
  import GainsScreen, { type Gain } from "./GainsScreen.svelte";

  /** Back to the tile home. */
  export let onHome: () => void;

  // The screen, top to bottom: the display (messages, and what is being typed),
  // the actions as cells — or, once one is chosen, its tiers — and the bar with
  // two buttons: the arrow turns the page, the circle goes home.
  // On the grid every screen shares; a button here takes SCALE × SCALE of its
  // squares, or sizes between, like 2×3.
  const SCALE = 2;
  const PER_PAGE = 8;
  const GAP = GRID_GAP;
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
  // the grid's squares, and how many rows of them fit; the bar, the tiers and
  // the panels are as wide as a row of them
  $: unit = gridUnit(width);
  $: fit = unit ? Math.floor(height / unit) : 0;
  $: cells = layout(onPage, page, width, height, unit, fit);

  // the sizes a button may take, in its own squares: one, two side by side, or
  // one and a half tall — times SCALE, in the grid's
  const SIZES: [number, number][] = [[1, 1], [2, 1], [1, 1.5]];

  /** The sizes of a page's cells, in the grid's squares — the same for the same
   *  page every time. When they would not fit `fit` rows, the last large ones
   *  give way to plain squares. */
  function sizes(n: number, rand: () => number, fit: number): [number, number][] {
    const out = Array.from({ length: n }, () => {
      const v = rand() + 0.5;
      const [w, h] = SIZES[v < 0.4 ? 1 : v < 0.75 ? 0 : 2];
      return [Math.round(w * SCALE), Math.round(h * SCALE)] as [number, number];
    });
    for (let i = n - 1; i >= 0 && packFree(out, GRID_COLS).rows > fit; i--) out[i] = [SCALE, SCALE];
    return out;
  }

  function layout(list: Action[], seed: number, w: number, h: number, unit: number, fit: number) {
    if (!list.length || !w || !h || !fit) return [];
    const rand = seeded(seed + 1);
    const { boxes, rows } = packFree(sizes(list.length, rand, fit), GRID_COLS);
    const forms = formsFor(boxes, rand);
    return drawBoxes(boxes, rows, w, h, unit, GAP, { forms, slant: unit * SCALE * SLANT }).map((c, i) => ({
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
      // Escape lets go of the field; then the arrows move between the cells
      e.preventDefault();
      input.blur();
    }
  }

  /** With the field let go, a letter or digit takes it up again, and is typed
   *  — all but h j k l, which move between the cells (see App). With an action
   *  chosen, a digit acts instead, on the tier of that number, and other keys
   *  wait for Escape to let the action go. */
  function onWindowKey(e: KeyboardEvent) {
    if (gains || e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
    // with an action chosen, a digit picks its tier, by number; letters are
    // ignored — often the rest of a name that already found its action
    if (selected && e.key.length === 1 && !"hjkl ".includes(e.key)) {
      e.preventDefault();
      const tier = /^[1-9]$/.test(e.key) ? (selected.tiers ?? [])[Number(e.key) - 1] : null;
      if (tier && !acting) act(tier.index);
      return;
    }
    if (document.activeElement === input || e.key.length !== 1 || e.key === " ") return;
    if ("hjkl".includes(e.key)) return;
    const t = e.target as HTMLElement | null;
    if (t && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
    e.preventDefault();
    selected = null;
    query += e.key;
    raiseKeyboard();
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
        const rankBefore = was?.rank ?? "α";
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
        roko: r.journey_reset ? "seu hp acabou. a jornada recomeçou do primeiro estágio." : r.roko,
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
      // what an act paid gives way to the home
      if (gains) {
        onHome();
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

<svelte:window on:keydown={onWindowKey} />

{#if gains}
  <!-- after an act, what it paid; then back to the home -->
  <GainsScreen
    title={gains.title}
    tokens={gains.tokens}
    marks={gains.marks}
    gains={gains.list}
    roko={gains.roko}
    onDone={onHome}
  />
{:else}
<div class="act" class:typing={typing && keyboardUp} class:choosing={!!selected} style="--unit: {unit || 52}px; --row: {(unit || 52) * GRID_COLS}px">
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
      {#each selected.tiers ?? [] as t, n (t.index)}
        <button class="tier" disabled={acting} on:click={() => act(t.index)}>
          <!-- its number on the keyboard -->
          <span class="tier-key">{n + 1}</span>
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

  <!-- two buttons: the page (back a step with something chosen), and home -->
  <div class="bar">
    <span class="pages" aria-hidden="true">{#if pages > 1}{#each Array(pages) as _, i}<i class:on={i === page}></i>{/each}{/if}</span>
    <button class="page-btn" aria-label={selected ? "cancelar" : "próxima página"} on:click={nextPage}><Icon name={selected ? "left" : "right"} /></button>
    <button class="home-btn" aria-label="início" on:click={home}><Icon name="circle" size={16} /></button>
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
    /* no gap: the cells and the bar are rows of the same grid */
    background: transparent;
    user-select: none;
    -webkit-user-select: none;
  }

  .display {
    position: relative;
    flex: 0 0 18%;
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
    width: var(--row);
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
  .tier { position: relative; }
  .tier-key { position: absolute; top: 0.3rem; left: 0.45rem; font-size: 0.7rem; opacity: 0.55; }
  .tier-label { font-size: 0.85rem; }
  .tier-marks { font-size: 1.3rem; }

  /* the bar is the grid's bottom row, under the cells: where it stands across
     two squares, the page button across three, home in the last */
  .bar {
    position: relative;
    flex: 0 0 var(--unit);
    align-self: flex-end;
    width: var(--row);
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    column-gap: 12px;
    /* in line with the cells, which stand GAP in from their squares */
    padding: 6px;
    box-sizing: border-box;
  }
  .act.typing .bar { display: none; }
  /* see-through, square-cornered, outlined in cyan */
  .tier, .page-btn, .home-btn {
    background: transparent;
    border: 1.5px solid var(--ink);
    border-radius: 0;
    color: var(--ink);
    cursor: pointer;
    transition: background 0.06s;
  }
  .page-btn, .home-btn { display: flex; align-items: center; justify-content: center; }
  /* pressed, a wash of the cyan */
  .page-btn { grid-column: 3 / 6; }
  .tier:active:not(:disabled), .page-btn:active, .home-btn:active {
    background: rgba(0, 240, 255, 0.25);
  }
  .pages {
    grid-column: 1 / 3;
    align-self: center;
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
