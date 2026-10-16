<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import {
    buyPackageAction,
    fetchActions,
    fetchShopCatalog,
    fetchUser,
    formatCode,
    type CatalogAction,
    type CatalogGroup,
  } from "./api";
  import { GRID_COLS, SHRINK, drawBoxes, pack, polyPath, type Size } from "./homeLayout";
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
  // middle, a bar with two blank buttons at the bottom. It opens on its first
  // screen — where what is bought with points will live — and the centre button
  // turns the page, through the catalog one attribute after the other; with an
  // action chosen it goes back a step instead. The right one goes home. All of
  // it is the shop tile's pale cyan, see-through and square-cornered, shrunk into the
  // bottom-right corner.

  const SHOP_COLOR = "#7af9ff";
  // text on the dark backdrop
  const SHOP_DEEP = "#ffffff";
  // On the grid of three squares across, at most five rows.
  const ROWS = 5;
  const PER_PAGE = 10;
  const GAP = 11;
  const DELAY = [0, 110, 60, 170, 30, 220, 140, 90, 200, 50];

  const TYPE_LABEL: Record<number, string> = {
    0: "sessão", 1: "reps", 2: "segundos", 3: "minutos", 4: "horas",
    5: "letras", 6: "linhas", 7: "palavras", 8: "grupo",
  };

  let groups: CatalogGroup[] = [];
  let buildPoints = 0;
  let owned: Set<string> = new Set();
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
  // the squares keep their size from page to page; the bar, the tiers and the
  // panels are as wide as a row of them (SHRINK of the width before the cells
  // have been measured)
  $: side = width && height ? Math.min((width * SHRINK) / GRID_COLS, height / ROWS) : 0;
  $: row = side ? `${side * GRID_COLS}px` : `${SHRINK * 100}%`;
  $: cells = layout(onPage, stop, width, height, side);

  /** A cell's size by what it costs: a rectangle for the dear ones, a square,
   *  a quarter for the free. */
  const sizeOf = (a: CatalogAction): Size => (a.cost >= 3 ? "rect" : a.cost > 0 ? "square" : "quarter");

  /** The page's cells on the grid, each as large as it costs; when they would
   *  not fit the rows, the last rectangles give way to squares. */
  function layout(list: CatalogAction[], seed: number, w: number, h: number, side: number) {
    if (!list.length || !w || !h) return [];
    const wanted = list.map(sizeOf);
    let packed = pack(wanted);
    for (let i = wanted.length - 1; packed.rows > ROWS && i >= 0; i--) {
      if (wanted[i] === "rect") {
        wanted[i] = "square";
        packed = pack(wanted);
      }
    }
    return drawBoxes(packed.boxes, packed.rows, w, h, side, GAP).map((c, i) => {
      const small = c.h < 52;
      // a quarter holds only the first letters of the name
      const name = list[i].name;
      return {
        action: list[i],
        d: polyPath(c.shape),
        cx: c.cx,
        cy: c.cy,
        lines: c.w < 50 ? [name.slice(0, Math.max(2, Math.floor((c.w - 6) / 7)))] : wrap(name, c.w, small ? 1 : c.h < 80 ? 2 : 3),
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
  async function load() {
    try {
      const [cat, user, acts] = await Promise.all([
        fetchShopCatalog(),
        fetchUser().catch(() => null),
        fetchActions().catch(() => []),
      ]);
      groups = cat;
      buildPoints = user?.build_points ?? 0;
      owned = new Set(acts.map((a) => a.name.toUpperCase()));
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
    // the new page comes on, with the sound of it
    powerOn();
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

<div class="shop" style="--ink: {SHOP_COLOR}; --deep: {SHOP_DEEP}; --row: {row}">
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
          `${buildPoints} bp`,
        ].filter(Boolean).join(" · ")}
      </p>
    {:else}
      <p class="big">shop</p>
      <p class="small">{buildPoints} build points</p>
    {/if}
  </div>

  {#if selected && group}
    {@const a = selected}
    <!-- the colored area: the stats, then the question -->
    <button class="panel" class:asking={confirming} disabled={buying} on:click={press}>
      {#if confirming}
        {#if buildPoints < a.cost}
          <span class="ask">faltam {a.cost - buildPoints} bp</span>
          <span class="ask-sub">saldo {buildPoints} bp</span>
        {:else}
          <span class="ask">{buying ? "…" : "adquirir?"}</span>
          <span class="ask-sub">{a.cost} bp · saldo {buildPoints} bp</span>
        {/if}
      {:else}
        <div class="sheet">
        <dl class="stats">
          {#if a.code}<dt>id</dt><dd>{formatCode(a.code)}</dd>{/if}
          <dt>tipo</dt><dd>{TYPE_LABEL[a.type] ?? a.type}</dd>
          <dt>dificuldade</dt><dd>d{a.diff}</dd>
          {#if tokensLine(a)}<dt>tokens</dt><dd>{tokensLine(a)}</dd>{/if}
          <dt>custo</dt><dd>{a.cost} bp</dd>
        </dl>
        {#if a.leaves.length}
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
                {#if !c.small}<tspan class="cost" x={c.cx} dy="16">{c.action.cost ? `${c.action.cost} bp` : "grátis"}</tspan>{/if}
              </text>
            </g>
          {/each}
        </svg>
      {/if}
    </div>
  {:else}
    <!-- the first screen: what is bought with points will stand here -->
    <div class="first" bind:clientWidth={width} bind:clientHeight={height}>
      <div class="vault"></div>
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
    <!-- two blank buttons: the page, and home -->
    <button class="page-btn" aria-label={selected ? "voltar" : "próxima página"} on:click={nextPage}></button>
    <button class="home-btn" aria-label="início" on:click={home}></button>
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
    gap: 10px;
    background: transparent;
    user-select: none;
    -webkit-user-select: none;
  }

  .display {
    flex: 0 0 24%;
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
  /* empty for now: what points buy will fill it */
  .vault {
    flex: 1;
    align-self: flex-end;
    width: var(--row);
    border: 1.5px dashed var(--ink);
    opacity: 0.35;
  }
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

  /* the bar is a row of the grid, under the cells */
  .bar {
    position: relative;
    flex: 0 0 44px;
    align-self: flex-end;
    width: var(--row);
    /* three columns, like the grid's squares: where it stands, the page, home */
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    column-gap: 22px;
    /* in line with the cells, which stand GAP in from their squares */
    padding: 0 11px;
    box-sizing: border-box;
  }
  /* see-through, square-cornered, outlined in cyan */
  .maker, .page-btn, .home-btn {
    background: transparent;
    border: 1.5px solid var(--ink);
    border-radius: 0;
    cursor: pointer;
    transition: background 0.06s;
  }
  /* pressed, a wash of the cyan */
  .maker:active, .page-btn:active, .home-btn:active {
    background: rgba(122, 249, 255, 0.25);
  }
  .ticks {
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
