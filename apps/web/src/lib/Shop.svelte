<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import {
    buyPackageAction,
    fetchActions,
    fetchShopCatalog,
    fetchUser,
    formatCode,
    type CatalogAction,
    type CatalogGroup,
  } from "./api";
  import { centroid, inset, type Point } from "./homeLayout";
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
  // middle, a bar at the bottom. It opens on its first screen — where what is
  // bought with points will live — and the grooved button at the bottom right is
  // slid to walk the catalog, one attribute after the other, each in its color.
  // A tap on it goes back one step, and from the first screen, home.

  const SHOP_COLOR = "#ff6fb5";
  const COLS = 2;
  const ROWS = 5;
  // a little smaller than the acting screen's cells: five rows, not four
  const PER_PAGE = COLS * ROWS;
  const GAP = 5;
  const DELAY = [0, 110, 60, 170, 30, 220, 140, 90, 200, 50];
  // the slider: a step every STEP pixels of drag, past TAP_SLOP it is no tap
  const STEP = 34;
  const TAP_SLOP = 6;

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

  // where the slider stands: 0 is the first screen, then a page of a group each
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

  // groups by name, as the slider walks them; each takes its own hue, so sliding
  // runs through the spectrum
  $: sorted = [...groups].sort((a, b) => a.name.localeCompare(b.name, "pt"));
  $: colors = sorted.map((_, i) => `hsl(${Math.round((i * 360) / Math.max(1, sorted.length) + 190) % 360} 95% 62%)`);
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
  $: color = here ? colors[here.group] : SHOP_COLOR;
  $: onPage = group && here ? group.actions.slice(here.page * PER_PAGE, (here.page + 1) * PER_PAGE) : [];
  $: cells = layout(onPage, stop, width, height);

  // takes the set, so the template follows it when a purchase changes it
  const isOwned = (a: CatalogAction, set: Set<string>) => set.has(a.name.toUpperCase());
  // a free action still takes some room
  const weight = (a: CatalogAction) => Math.max(1, a.cost);

  /** The page's cells, two to a row, each as large as it costs: a row is as tall
   *  as the sum of its costs, and split between its two by their costs. The rows
   *  sit at the bottom, under the thumb; a short page does not stretch to fill. */
  function layout(list: CatalogAction[], seed: number, w: number, h: number) {
    if (!list.length || !w || !h) return [];
    const rows: CatalogAction[][] = [];
    for (let i = 0; i < list.length; i += COLS) rows.push(list.slice(i, i + COLS));
    const used = Math.min(1, Math.max(rows.length, 2) / ROWS);
    const top = 1 - used;

    // row heights, never thinner than half an even share
    const sums = rows.map((r) => r.reduce((s, a) => s + weight(a), 0));
    const total = sums.reduce((s, x) => s + x, 0);
    const floor = 0.5 / rows.length;
    let shares = sums.map((s) => Math.max(floor, s / total));
    const k = shares.reduce((s, x) => s + x, 0);
    shares = shares.map((s) => s / k);

    let state = ((seed + 7) * 2654435761) >>> 0 || 1;
    const rand = () => {
      state ^= state << 13;
      state ^= state >>> 17;
      state ^= state << 5;
      return ((state >>> 0) % 10000) / 10000 - 0.5;
    };

    // the lines between rows run across the whole width, tilted a little
    const lines: [number, number][] = [[top, top]];
    let y = top;
    shares.forEach((s, i) => {
      y += s * used;
      const inner = i < shares.length - 1;
      const j = inner ? s * used * 0.25 : 0;
      lines.push([y + rand() * j, y + rand() * j]);
    });
    const at = (line: [number, number], x: number) => line[0] + (line[1] - line[0]) * x;

    const out: { action: CatalogAction; points: string; cx: number; cy: number; lines: string[]; small: boolean }[] = [];
    rows.forEach((row, r) => {
      const T = lines[r];
      const B = lines[r + 1];
      let polys: Point[][];
      if (row.length === 1) {
        polys = [[[0, T[0]], [1, T[1]], [1, B[1]], [0, B[0]]]];
      } else {
        const split = Math.min(0.75, Math.max(0.25, weight(row[0]) / sums[r]));
        const sT = split + rand() * 0.08;
        const sB = split + rand() * 0.08;
        polys = [
          [[0, at(T, 0)], [sT, at(T, sT)], [sB, at(B, sB)], [0, at(B, 0)]],
          [[sT, at(T, sT)], [1, at(T, 1)], [1, at(B, 1)], [sB, at(B, sB)]],
        ];
      }
      row.forEach((action, i) => {
        const shape = inset(polys[i].map(([px, py]) => [px * w, py * h] as Point), GAP);
        const [cx, cy] = centroid(shape);
        const xs = shape.map((p) => p[0]);
        const ys = shape.map((p) => p[1]);
        const cellW = Math.max(...xs) - Math.min(...xs);
        const cellH = Math.max(...ys) - Math.min(...ys);
        const small = cellH < 52;
        out.push({
          action,
          points: shape.map((p) => p.join(",")).join(" "),
          cx,
          cy,
          lines: wrap(action.name, cellW, small ? 1 : cellH < 80 ? 2 : 3),
          small,
        });
      });
    });
    return out;
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

  // ---- moving: the slider walks the stops, a tap on it goes back a step ----
  function goTo(next: number) {
    next = Math.max(0, Math.min(stops.length - 1, next));
    if (next === stop) return;
    stop = next;
    selected = null;
    confirming = false;
    message = [];
    tap(stop);
  }

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
    // a little give past either end, no more
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
      // the grooves settle on the step they stopped at
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
    }
    else return;
    e.preventDefault();
  }

  // a mouse wheel walks it too
  let wheelAcc = 0;
  function onWheel(e: WheelEvent) {
    e.preventDefault();
    wheelAcc += Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
    if (Math.abs(wheelAcc) < 40) return;
    const dir = Math.sign(wheelAcc);
    wheelAcc = 0;
    const before = stop;
    goTo(stop + dir);
    groove += (stop - before) * STEP;
  }

  // ---- choosing, then buying ----
  function choose(a: CatalogAction) {
    primeAudio();
    tap(9);
    message = [];
    selected = a;
    confirming = false;
  }

  async function press() {
    if (!selected || buying || !group) return;
    primeAudio();
    if (isOwned(selected, owned)) {
      tap(0);
      return;
    }
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
    buying = true;
    try {
      const res = await buyPackageAction(a.package_attribute, a.name);
      buildPoints = res.build_points;
      owned = new Set([...owned, a.name.toUpperCase()]);
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

<div class="shop" style="--ink: {color}">
  <!-- the display: where the slider stands, what was chosen, what happened -->
  <div class="display">
    {#if loading}
      <p class="small">…</p>
    {:else if message.length}
      {#each message as line, i}<p class={i === 0 ? "big" : "small"}>{line}</p>{/each}
    {:else if selected && group}
      <p class="big">{selected.name}</p>
      <p class="small">{group.name}</p>
    {:else if group && here}
      <p class="big">{group.name}</p>
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
    {@const got = isOwned(a, owned)}
    <!-- the colored area: the stats, then the question -->
    <button class="panel" class:asking={confirming} class:got disabled={buying} on:click={press}>
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
          {#if got}
            <dt>status</dt><dd>adquirida</dd>
          {:else}
            <dt>custo</dt><dd>{a.cost} bp</dd>
          {/if}
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
            <g class="cell" class:got={isOwned(c.action, owned)} role="button" tabindex="0" aria-label={c.action.name}
              style="--delay: {DELAY[i % DELAY.length]}ms"
              on:click={() => choose(c.action)}
              on:keydown={(e) => e.key === "Enter" && choose(c.action)}>
              <polygon points={c.points} />
              <text x={c.cx} y={c.cy - (c.lines.length * 14) / 2 + (c.small ? 7 : 0)}>
                {#each c.lines as line, j}<tspan x={c.cx} dy={j === 0 ? 0 : 14}>{line}</tspan>{/each}
                {#if !c.small}<tspan class="cost" x={c.cx} dy="16">{isOwned(c.action, owned) ? "✓" : c.action.cost ? `${c.action.cost} bp` : "grátis"}</tspan>{/if}
              </text>
            </g>
          {/each}
        </svg>
      {/if}
    </div>
  {:else}
    <!-- the first screen: what is bought with points will stand here -->
    <div class="first">
      <div class="vault"></div>
      <div class="makers">
        <button class="maker" on:click={() => openForge("patch")}>+ patch</button>
        <button class="maker" on:click={() => openForge("attr")}>+ atributo</button>
      </div>
    </div>
  {/if}

  <div class="bar">
    <!-- where it stands: a tick per stop, in its color -->
    <span class="ticks" aria-hidden="true">
      {#each stops as s, i}<i class:on={i === stop} style="--c: {s ? colors[s.group] : SHOP_COLOR}"></i>{/each}
    </span>
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
      on:wheel={onWheel}
    ></div>
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
    background: #000000;
    user-select: none;
    -webkit-user-select: none;
  }

  .display {
    flex: 0 0 24%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    gap: 0.4rem;
    padding: 0.5rem 0.4rem;
    overflow: hidden;
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
  polygon {
    fill: var(--ink);
    fill-opacity: 0.12;
    stroke: var(--ink);
    stroke-opacity: 0.6;
    stroke-width: 1.5;
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
  /* what is already owned stays, faded, with no fill */
  .cell.got polygon { fill-opacity: 0; stroke-opacity: 0.3; stroke-dasharray: 4 4; }
  .cell.got text { opacity: 0.45; }
  .cell:focus-visible polygon, .cell:active polygon { stroke: #ffffff; stroke-opacity: 1; fill-opacity: 0.25; }
  .cell:focus-visible text, .cell:active text { fill: #ffffff; }
  @media (hover: hover) {
    .cell:hover polygon { stroke: #ffffff; stroke-opacity: 1; }
    .cell:hover text { fill: #ffffff; }
  }

  .panel {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.4rem 1.5rem;
    background: var(--ink);
    border: none;
    /* cut like a cell, not a box: in pixels, so a wide screen does not cut into the text */
    clip-path: polygon(0 14px, 100% 0, calc(100% - 10px) 100%, 6px calc(100% - 10px));
    color: #000000;
    font-family: var(--font-mono);
    text-align: left;
    cursor: pointer;
    overflow-y: auto;
    animation: tube-on 0.4s cubic-bezier(0.2, 0.8, 0.3, 1) both;
  }
  .panel.got { opacity: 0.5; cursor: default; }
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
    border-top: 1.5px solid rgba(0, 0, 0, 0.35);
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
    border: 1.5px dashed var(--ink);
    opacity: 0.25;
  }
  .makers { display: flex; gap: 8px; }
  .maker {
    flex: 1;
    min-height: 3rem;
    background: #000000;
    border: 1.5px solid var(--ink);
    color: var(--ink);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    text-transform: uppercase;
    cursor: pointer;
  }
  .maker:active { border-color: #ffffff; color: #ffffff; }

  .bar {
    position: relative;
    flex: 0 0 56px;
    display: flex;
    align-items: stretch;
    justify-content: flex-end;
  }
  .slider {
    width: 40%;
    border: 1.5px solid var(--ink);
    /* the grooves: thin ridges that roll with the finger, like a thumb wheel */
    background:
      linear-gradient(90deg, #000000 0%, transparent 22%, transparent 78%, #000000 100%),
      repeating-linear-gradient(90deg, var(--ink) 0 1.5px, transparent 1.5px 9px);
    background-position: 0 0, var(--groove) 0;
    background-size: 100% 100%, 100% 100%;
    opacity: 0.85;
    cursor: ew-resize;
    touch-action: none;
    outline: none;
  }
  .slider.dragging, .slider:focus-visible { border-color: #ffffff; opacity: 1; }
  @media (hover: hover) {
    .slider:hover { border-color: #ffffff; }
  }
  .ticks {
    position: absolute;
    left: 0;
    right: 44%;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 3px;
    pointer-events: none;
  }
  .ticks i {
    flex: 0 1 6px;
    height: 10px;
    background: var(--c);
    opacity: 0.25;
  }
  .ticks i.on { opacity: 1; height: 18px; }
</style>
