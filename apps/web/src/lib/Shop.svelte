<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import {
    buyPackageAction,
    discover,
    fetchShop,
    formatCode,
    type CatalogAction,
    type ShopAction,
    type ShopState,
  } from "./api";
  import { GRID_COLS, GRID_GAP, SLANT, drawBoxes, formsFor, gridUnit, packFree, polyPath, seeded } from "./homeLayout";
  import Icon from "./Icon.svelte";
  import { primeAudio } from "./dtmf";
  import { gains as gainsSound, powerOn, tap } from "./sfx";
  import { bumpUser, setBackHandler, userVersion } from "./store";
  import ShopForge from "./ShopForge.svelte";

  /** Back to the tile home. */
  export let onHome: () => void;
  /** Kept for links that still name a section; the shop opens on its first screen. */
  export let initialSection: string | null = null;
  void initialSection;

  // The shop is walked like the acting screen: a display on top, cells in the
  // middle, a bar with two buttons — an arrow, a circle — at the bottom. It opens on its first
  // screen, where the catalog is discovered, and the centre button turns the
  // page, through what was discovered one attribute after the other; with an
  // action chosen it goes back a step instead. The right one goes home. All of
  // it is the shop tile's pale cyan, see-through and square-cornered, shrunk into the
  // bottom-right corner.
  //
  // Only what was discovered is sold. Discovering changes with use: frames of
  // static to tap open, one by one; then a single button for the day's; then
  // nothing to do, they open on arrival. And the interface evolves too: after
  // TURNS_TO_SLIDER turns of the page, the arrow becomes the grooved slider,
  // slid to walk the catalog and tapped to go back a step.

  const SHOP_COLOR = "#7af9ff";
  // text on the dark backdrop
  const SHOP_DEEP = "#ffffff";
  // On the grid every screen shares; a button here takes SCALE × SCALE of its
  // squares, twice as wide for the dear ones, SMALL × SMALL for the free.
  const SCALE = 3;
  const SMALL = 2;
  const PER_PAGE = 6;
  const GAP = GRID_GAP;
  const DELAY = [0, 110, 60, 170, 30, 220, 140, 90, 200, 50];

  const TYPE_LABEL: Record<number, string> = {
    0: "sessão", 1: "reps", 2: "segundos", 3: "minutos", 4: "horas",
    5: "letras", 6: "linhas", 7: "palavras", 8: "grupo",
  };

  // the turns of the page that make the arrow a slider, and the slider's steps
  const TURNS_TO_SLIDER = 1000;
  const TURNS_KEY = "evove_shop_turns";
  const STEP = 34;
  const TAP_SLOP = 6;

  let groups: ShopState["groups"] = [];
  let buildPoints = 0;
  let owned: Set<string> = new Set();
  let found: Pick<ShopState, "phase" | "left" | "rate" | "found" | "catalog"> | null = null;
  // frames opened today, and what each showed
  let opened: string[] = [];
  let discovering = false;
  let loading = true;
  let message: string[] = [];
  let lastUserVersion = 0;

  // where the pages stand: 0 is the first screen, then a page of a group each
  let stop = 0;
  // a cell tapped shows its stats; a tap on them asks; a tap on the question buys
  let selected: CatalogAction | null = null;
  let confirming = false;
  let buying = false;
  let forge: "patch" | "attr" | null = null;
  let width = 0;
  let height = 0;

  // ---- the stops: the first screen, then every page of every group ----
  type Stop = { group: number; page: number; pages: number } | null;

  // groups by name, as the slider walks them
  $: byName = [...groups].sort((a, b) => a.name.localeCompare(b.name, "pt"));
  // what is owned leaves the shop; a group with nothing left leaves the slider
  $: sorted = byName
    .map((g) => ({ ...g, actions: g.actions.filter((a) => !owned.has(a.name.toUpperCase())) }))
    .filter((g) => g.actions.length > 0);
  $: stops = [
    null,
    ...sorted.flatMap((g, gi) => {
      const pages = Math.max(1, Math.ceil(g.actions.length / PER_PAGE));
      return Array.from({ length: pages }, (_, page) => ({ group: gi, page, pages }));
    }),
  ] as Stop[];
  $: if (stop >= stops.length) stop = stops.length - 1;
  $: here = stops[stop] ?? null;
  $: group = here ? sorted[here.group] : null;
  $: onPage = group && here ? group.actions.slice(here.page * PER_PAGE, (here.page + 1) * PER_PAGE) : [];
  // the grid's squares, and how many rows of them fit; the bar and the panels
  // are as wide as a row of them
  $: unit = gridUnit(width);
  $: fit = unit ? Math.floor(height / unit) : 0;
  $: cells = layout(onPage, stop, width, height, unit, fit);

  /** A cell's size by what it costs, in its own squares: two side by side for
   *  the dear ones, one, or two thirds of one for the free — times SCALE, in
   *  the grid's. */
  const sizeOf = (a: CatalogAction): [number, number] =>
    a.cost >= 300 ? [2 * SCALE, SCALE] : a.cost > 0 ? [SCALE, SCALE] : [SMALL, SMALL];

  /** The page's cells on the grid, each as large as it costs; when they would
   *  not fit the rows, the last ones give way to smaller sizes, a step at a
   *  time, until they fit or all are as small as they go. */
  function layout(list: CatalogAction[], seed: number, w: number, h: number, unit: number, fit: number) {
    if (!list.length || !w || !h || !fit) return [];
    const wanted = list.map(sizeOf);
    let packed = packFree(wanted, GRID_COLS);
    for (let i = wanted.length - 1; packed.rows > fit && wanted.some((s) => s[0] > SMALL); i = (i || wanted.length) - 1) {
      if (wanted[i][0] <= SMALL) continue;
      wanted[i] = wanted[i][0] > SCALE ? [SCALE, SCALE] : [SMALL, SMALL];
      packed = packFree(wanted, GRID_COLS);
    }
    const forms = formsFor(packed.boxes, seeded(seed));
    return drawBoxes(packed.boxes, packed.rows, w, h, unit, GAP, { forms, slant: unit * SCALE * SLANT }).map((c, i) => {
      const small = c.h < 52;
      return {
        action: list[i],
        d: polyPath(c.shape),
        cx: c.cx,
        cy: c.cy,
        lines: wrap(list[i].name, c.w, small ? 1 : c.h < 80 ? 2 : 3),
        small,
      };
    });
  }

  /** Breaks a name into lines that fit a cell. */
  function wrap(name: string, cellW: number, max: number): string[] {
    const perLine = Math.max(5, Math.floor((cellW - 14) / 7.6));
    const lines: string[] = [];
    let line = "";
    for (const word of name.split(/\s+/)) {
      if (line && (line + " " + word).length > perLine) {
        lines.push(line);
        line = word;
      } else line = line ? `${line} ${word}` : word;
    }
    if (line) lines.push(line);
    return lines.slice(0, max);
  }

  // ---- loading ----
  function apply(state: ShopState) {
    groups = state.groups;
    buildPoints = state.points;
    owned = new Set(state.groups.flatMap((g) => g.actions.filter((a) => a.owned).map((a) => a.name.toUpperCase())));
    found = { phase: state.phase, left: state.left, rate: state.rate, found: state.found, catalog: state.catalog };
    if (state.new.length) message = [state.new.length === 1 ? "descoberta" : `${state.new.length} descobertas`, state.new.join(" · ").toLowerCase()];
  }

  async function load() {
    try {
      apply(await fetchShop());
    } catch (e: any) {
      message = [e?.message ?? "erro ao carregar"];
    } finally {
      loading = false;
    }
  }

  $: if ($userVersion !== lastUserVersion) {
    lastUserVersion = $userVersion;
    if (lastUserVersion > 0) load();
  }

  // ---- moving: the centre button turns the page, or goes back a step ----
  /** One step back: from the question to the stats, from the stats to the
   *  cells, from the cells to the first screen. False when there is none. */
  function back(): boolean {
    if (confirming) confirming = false;
    else if (selected) selected = null;
    else if (stop > 0) {
      stop = 0;
      message = [];
    } else return false;
    return true;
  }

  function nextPage() {
    primeAudio();
    if (selected) {
      tap(0);
      back();
      return;
    }
    stop = (stop + 1) % stops.length;
    message = [];
    turns = countTurn();
    // the new page comes on, with the sound of it
    powerOn();
  }

  // ---- the interface that evolves: turns of the page, kept on the device ----
  function readTurns(): number {
    try {
      return Number(localStorage.getItem(TURNS_KEY) ?? 0) || 0;
    } catch {
      return 0;
    }
  }
  function countTurn(): number {
    const n = readTurns() + 1;
    try {
      localStorage.setItem(TURNS_KEY, String(n));
    } catch {
      // nowhere to keep it: the arrow stays an arrow
    }
    return n;
  }
  let turns = readTurns();
  $: slider = turns >= TURNS_TO_SLIDER;

  function goTo(next: number) {
    next = Math.max(0, Math.min(stops.length - 1, next));
    if (next === stop) return;
    stop = next;
    selected = null;
    confirming = false;
    message = [];
    tap(stop);
  }
  // the grooves follow the finger, and stop following past the last stop
  let groove = 0;
  let dragging = false;
  let startX = 0;
  let startStop = 0;
  let startGroove = 0;
  let moved = false;
  function onDown(e: PointerEvent) {
    primeAudio();
    dragging = true;
    moved = false;
    startX = e.clientX;
    startStop = stop;
    startGroove = groove;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onMove(e: PointerEvent) {
    if (!dragging) return;
    let dx = e.clientX - startX;
    if (Math.abs(dx) > TAP_SLOP) moved = true;
    if (!moved) return;
    const min = -startStop * STEP - STEP * 0.4;
    const max = (stops.length - 1 - startStop) * STEP + STEP * 0.4;
    dx = Math.max(min, Math.min(max, dx));
    groove = startGroove + dx;
    goTo(startStop + Math.trunc(dx / STEP));
  }
  function onUp() {
    if (!dragging) return;
    dragging = false;
    if (moved) {
      groove = startGroove + (stop - startStop) * STEP;
      if (stop !== startStop) powerOn();
      return;
    }
    tap(0);
    if (!back()) onHome();
  }
  function onSliderKey(e: KeyboardEvent) {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") goTo(stop + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") goTo(stop - 1);
    else if (e.key === "Enter" || e.key === " " || e.key === "Backspace") {
      if (!back()) onHome();
    } else return;
    e.preventDefault();
  }

  // ---- discovering ----
  async function open() {
    if (discovering || !found || found.left <= 0) return;
    primeAudio();
    tap(9);
    discovering = true;
    try {
      const state = await discover();
      opened = [...opened, ...state.new];
      apply(state);
      gainsSound();
    } catch (e: any) {
      message = [e?.message ?? "erro ao descobrir"];
    } finally {
      discovering = false;
    }
  }

  /** Static on a canvas: random grey pixels, a dozen frames a second. */
  function noise(canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    const w = (canvas.width = 48);
    const h = (canvas.height = 48);
    const img = ctx?.createImageData(w, h);
    let raf = 0;
    let last = 0;
    const draw = (t: number) => {
      raf = requestAnimationFrame(draw);
      if (!ctx || !img || t - last < 80) return;
      last = t;
      for (let i = 0; i < img.data.length; i += 4) {
        const v = Math.random() * 255;
        img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
        img.data[i + 3] = 255;
      }
      ctx.putImageData(img, 0, 0);
    };
    raf = requestAnimationFrame(draw);
    return { destroy: () => cancelAnimationFrame(raf) };
  }

  function home() {
    primeAudio();
    tap(0);
    onHome();
  }

  // ---- choosing, then buying ----
  function choose(a: CatalogAction) {
    primeAudio();
    tap(9);
    message = [];
    selected = a;
    confirming = false;
  }

  /** After a purchase the stops shift: stay on the group's page, or the one now
   *  in its place when the group is gone. */
  async function stayOn(key: string, page: number) {
    await tick();
    const gi = sorted.findIndex((g) => g.key === key);
    if (gi < 0) return;
    const found = stops.findIndex((s) => s && s.group === gi && s.page === Math.min(page, s.pages - 1));
    if (found >= 0) stop = found;
  }

  async function press() {
    if (!selected || buying || !group) return;
    primeAudio();
    if (!confirming) {
      tap(5);
      confirming = true;
      return;
    }
    if (buildPoints < selected.cost) {
      tap(0);
      confirming = false;
      return;
    }
    const a = selected;
    const at = here;
    const key = group.key;
    buying = true;
    try {
      const res = await buyPackageAction(a.package_attribute, a.name);
      buildPoints = res.build_points;
      owned = new Set([...owned, a.name.toUpperCase()]);
      stayOn(key, at?.page ?? 0);
      gainsSound();
      message = ["adquirida", a.name.toLowerCase()];
      selected = null;
      confirming = false;
      bumpUser();
    } catch (e: any) {
      message = [e?.message ?? "erro ao adquirir"];
      confirming = false;
    } finally {
      buying = false;
    }
  }

  function openForge(mode: "patch" | "attr") {
    primeAudio();
    tap(3);
    forge = mode;
  }

  const tokensLine = (a: CatalogAction) =>
    a.token_gain ? `+${a.token_gain} tokens por execução` : a.token_cost ? `−${a.token_cost} tokens por execução` : null;

  onMount(() => {
    setBackHandler(() => {
      if (forge) {
        forge = null;
        return true;
      }
      return back();
    });
    load().then(() => groups.length && powerOn());
  });

  onDestroy(() => setBackHandler(null));
</script>

<div class="shop" style="--ink: {SHOP_COLOR}; --deep: {SHOP_DEEP}; --unit: {unit || 52}px; --row: {(unit || 52) * GRID_COLS}px">
  <!-- the display: where the slider stands, what was chosen, what happened -->
  <div class="display">
    {#if loading}
      <p class="small">…</p>
    {:else if message.length}
      {#each message as line, i}<p class={i === 0 ? "big" : "small"}>{line}</p>{/each}
    {:else if selected && group}
      <p class="big">{selected.name}</p>
    {:else if group && here}
      <p class="small">
        {[
          `${group.actions.length} ${group.actions.length === 1 ? "item" : "itens"}`,
          here.pages > 1 ? `${here.page + 1}/${here.pages}` : null,
          `${buildPoints} pts`,
        ].filter(Boolean).join(" · ")}
      </p>
    {:else}
      <p class="big">shop</p>
      <p class="small">{buildPoints} pontos{#if found} · {found.found}/{found.catalog} descobertas{/if}</p>
    {/if}
  </div>

  {#if selected && group}
    {@const a = selected}
    <!-- the colored area: the stats, then the question -->
    <button class="panel" class:asking={confirming} disabled={buying} on:click={press}>
      {#if confirming}
        {#if buildPoints < a.cost}
          <span class="ask">faltam {a.cost - buildPoints} pts</span>
          <span class="ask-sub">saldo {buildPoints} pts</span>
        {:else}
          <span class="ask">{buying ? "…" : "adquirir?"}</span>
          <span class="ask-sub">{a.cost} pts · saldo {buildPoints} pts</span>
        {/if}
      {:else}
        <div class="sheet">
        <dl class="stats">
          {#if a.code}<dt>id</dt><dd>{formatCode(a.code)}</dd>{/if}
          <dt>tipo</dt><dd>{TYPE_LABEL[a.type] ?? a.type}</dd>
          <dt>dificuldade</dt><dd>d{a.diff}</dd>
          {#if tokensLine(a)}<dt>tokens</dt><dd>{tokensLine(a)}</dd>{/if}
          <dt>custo</dt><dd>{a.cost} pts</dd>
          <dt>autor</dt><dd>by {(a as ShopAction).author ?? "roko"}</dd>
        </dl>
        {#if a.leaves?.length}
          <ul class="leaves">
            {#each a.leaves as l (l.key)}
              <li><span>{l.name}</span><span>{Math.round(l.weight * 100)}%</span></li>
            {/each}
          </ul>
        {/if}
        </div>
      {/if}
    </button>
  {:else if group}
    <div class="cells" bind:clientWidth={width} bind:clientHeight={height}>
      {#if width && height}
        <svg viewBox="0 0 {width} {height}" {width} {height}>
          {#each cells as c, i (c.action.name)}
            <g class="cell" role="button" tabindex="0" aria-label={c.action.name}
              style="--delay: {DELAY[i % DELAY.length]}ms"
              on:click={() => choose(c.action)}
              on:keydown={(e) => e.key === "Enter" && choose(c.action)}>
              <path class="shape" d={c.d} />
              <text x={c.cx} y={c.cy - (c.lines.length * 14) / 2 + (c.small ? 7 : 0)}>
                {#each c.lines as line, j}<tspan x={c.cx} dy={j === 0 ? 0 : 14}>{line}</tspan>{/each}
                {#if !c.small}<tspan class="cost" x={c.cx} dy="16">{c.action.cost ? `${c.action.cost} pts` : "grátis"}</tspan>{/if}
              </text>
            </g>
          {/each}
        </svg>
      {/if}
    </div>
  {:else}
    <!-- the first screen: where the catalog is discovered -->
    <div class="first" bind:clientWidth={width} bind:clientHeight={height}>
      <div class="vault">
        {#if !found}
          <p class="vault-note">…</p>
        {:else if found.left <= 0}
          <p class="vault-note">{found.found >= found.catalog ? "tudo descoberto" : "nada mais hoje · volte amanhã"}</p>
        {:else if found.phase === "frames"}
          <!-- frames of static: each tap opens one -->
          <div class="frames">
            {#each Array(found.left) as _, i (i)}
              <button class="static" disabled={discovering} aria-label="descobrir" on:click={open}>
                <canvas use:noise></canvas>
              </button>
            {/each}
          </div>
        {:else if found.phase === "button"}
          <button class="discover" disabled={discovering} on:click={open}>
            <Icon name="scan" size={28} />
            <span>descobrir {found.left}</span>
          </button>
        {:else}
          <p class="vault-note">as descobertas chegam sozinhas</p>
        {/if}
        {#if opened.length}
          <p class="vault-found">{opened.join(" · ").toLowerCase()}</p>
        {/if}
      </div>
      <div class="makers">
        <button class="maker" on:click={() => openForge("patch")}>+ patch</button>
        <button class="maker" on:click={() => openForge("attr")}>+ atributo</button>
      </div>
    </div>
  {/if}

  <div class="bar">
    <!-- where it stands: a tick per stop -->
    <span class="ticks" aria-hidden="true">
      {#each stops as _, i}<i class:on={i === stop}></i>{/each}
    </span>
    <!-- two buttons: the page (back a step with something chosen), and home -->
    {#if slider}
      <!-- the grooved button: slid, it walks the catalog; tapped, it goes back -->
      <div
        class="slider"
        class:dragging
        role="slider"
        tabindex="0"
        aria-label="explorar o shop"
        aria-valuemin={0}
        aria-valuemax={stops.length - 1}
        aria-valuenow={stop}
        style="--groove: {groove}px"
        on:pointerdown={onDown}
        on:pointermove={onMove}
        on:pointerup={onUp}
        on:pointercancel={onUp}
        on:keydown={onSliderKey}
      ></div>
    {:else}
      <button class="page-btn" aria-label={selected ? "voltar" : "próxima página"} on:click={nextPage}><Icon name={selected ? "left" : "right"} /></button>
    {/if}
    <button class="home-btn" aria-label="início" on:click={home}><Icon name="circle" size={16} /></button>
  </div>
</div>

{#if forge}
  <ShopForge mode={forge} onClose={() => (forge = null)} />
{/if}

<style>
  .shop {
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
    flex: 0 0 16%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: flex-end;
    text-align: right;
    gap: 0.4rem;
    padding: 0.5rem 0.4rem;
    overflow: hidden;
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
  svg { display: block; width: 100%; height: 100%; }
  .cell {
    cursor: pointer;
    outline: none;
    transform-box: fill-box;
    transform-origin: 50% 50%;
    animation:
      tube-on 0.45s cubic-bezier(0.2, 0.8, 0.3, 1) var(--delay) both,
      settle 0.35s steps(1) calc(var(--delay) + 0.45s) 1;
  }
  @media (prefers-reduced-motion: reduce) {
    .cell { animation: none; }
  }
  .shape {
    /* see-through: a faint wash of the cyan, and its outline */
    fill: var(--ink);
    fill-opacity: 0.1;
    stroke: var(--ink);
    stroke-width: 1.5;
    stroke-linejoin: miter;
  }
  text {
    fill: var(--ink);
    font-family: var(--font-mono);
    font-size: 11.5px;
    text-anchor: middle;
    dominant-baseline: middle;
    text-transform: uppercase;
  }
  .cost { font-size: 10px; opacity: 0.7; }
  /* pressed, the wash fills in */
  .cell:focus-visible .shape, .cell:active .shape {
    fill-opacity: 0.3;
  }
  @media (hover: hover) {
    .cell:hover .shape { fill-opacity: 0.3; }
  }

  .panel {
    flex: 1;
    min-height: 0;
    align-self: flex-end;
    width: var(--row);
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.4rem 1.5rem;
    background: rgba(122, 249, 255, 0.1);
    border: 1.5px solid var(--ink);
    border-radius: 0;
    color: var(--ink);
    font-family: var(--font-mono);
    text-align: left;
    cursor: pointer;
    overflow-y: auto;
    animation: tube-on 0.4s cubic-bezier(0.2, 0.8, 0.3, 1) both;
  }
  .panel.asking { justify-content: center; align-items: center; text-align: center; animation: none; }
  .panel:disabled { cursor: wait; }
  /* on a wide screen the stats stay a column you can read, not a line across it */
  .sheet {
    width: 100%;
    max-width: 30rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    font-size: 1rem;
  }
  @media (min-width: 700px) {
    .panel .sheet { font-size: 1.35rem; max-width: 36rem; }
  }
  .stats {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.35rem 1rem;
    margin: 0;
    font-size: 0.85em;
  }
  .stats dt { text-transform: uppercase; font-size: 0.82em; opacity: 0.7; align-self: center; }
  .stats dd { margin: 0; }
  .leaves {
    list-style: none;
    margin: 0;
    padding: 0.6rem 0 0;
    border-top: 1.5px solid rgba(122, 249, 255, 0.5);
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.8em;
  }
  .leaves li { display: flex; justify-content: space-between; gap: 1rem; }
  .ask { font-size: 2rem; text-transform: uppercase; }
  .ask-sub { font-size: 0.85rem; opacity: 0.7; }

  .first {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  /* where the catalog is discovered */
  .vault {
    flex: 1;
    min-height: 0;
    align-self: flex-end;
    width: var(--row);
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    gap: 10px;
    padding: 6px;
    box-sizing: border-box;
    border: 1.5px dashed color-mix(in srgb, var(--ink) 40%, transparent);
  }
  .vault-note, .vault-found {
    margin: 0;
    color: var(--ink);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    text-align: right;
    text-transform: uppercase;
    opacity: 0.7;
  }
  .vault-found { opacity: 1; color: #ffffff; }
  .frames { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .static {
    aspect-ratio: 1;
    padding: 0;
    border: 1.5px solid var(--ink);
    background: #000000;
    cursor: pointer;
    overflow: hidden;
  }
  .static canvas { width: 100%; height: 100%; display: block; opacity: 0.55; image-rendering: pixelated; }
  .static:active canvas { opacity: 0.9; }
  .discover {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.8rem;
    min-height: 4.5rem;
    background: transparent;
    border: 1.5px solid var(--ink);
    color: var(--ink);
    font-family: var(--font-mono);
    font-size: 0.95rem;
    text-transform: uppercase;
    cursor: pointer;
  }
  .discover:active { background: rgba(122, 249, 255, 0.25); }
  .slider {
    grid-column: 3 / 6;
    border: 1.5px solid var(--ink);
    /* the grooves: thin ridges that roll with the finger, like a thumb wheel */
    background:
      linear-gradient(90deg, #000000 0%, transparent 22%, transparent 78%, #000000 100%),
      repeating-linear-gradient(90deg, var(--ink) 0 1.5px, transparent 1.5px 9px);
    background-position: 0 0, var(--groove) 0;
    opacity: 0.85;
    cursor: ew-resize;
    touch-action: none;
    outline: none;
  }
  .slider.dragging, .slider:focus-visible { border-color: #ffffff; opacity: 1; }
  .makers { display: flex; gap: 8px; align-self: flex-end; width: var(--row); }
  .maker {
    flex: 1;
    min-height: 2.6rem;
    color: var(--ink);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    text-transform: uppercase;
    cursor: pointer;
  }

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
  /* see-through, square-cornered, outlined in cyan */
  .maker, .page-btn, .home-btn {
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
  .maker:active, .page-btn:active, .home-btn:active {
    background: rgba(122, 249, 255, 0.25);
  }
  .ticks {
    grid-column: 1 / 3;
    align-self: center;
    min-width: 0;
    overflow: hidden;
    display: flex;
    align-items: center;
    gap: 3px;
    pointer-events: none;
  }
  .ticks i {
    flex: 0 1 6px;
    height: 10px;
    background: var(--deep);
    opacity: 0.25;
  }
  .ticks i.on { opacity: 1; height: 18px; }
</style>
