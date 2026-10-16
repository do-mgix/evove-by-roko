<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { GRID_COLS, SHRINK, SLANT, formShape, polyPath, type Box, type Form } from "./homeLayout";
  import { primeAudio } from "./dtmf";
  import { powerOn, tap } from "./sfx";
  import { setBackHandler } from "./store";

  /** Back to the tile home. */
  export let onHome: () => void;

  // A page for building buttons on the grid: the grid's squares lie faint in
  // the bottom-right corner; a tap on one square and then another makes a button
  // across the rectangle between them. A tap on a button turns it to the next
  // form; two quick taps take it away. What is built is kept on this device.

  const FORMS: Form[] = ["rect", "trap", "prism", "pairL", "pairR"];
  // half the gap between two cells, in pixels
  const GAP = 6;
  // two taps closer than this are one double tap
  const DOUBLE_MS = 280;
  const KEY = "evove_built";

  type Built = { box: Box; form: Form };

  let built: Built[] = load();
  // the first square of a button being made
  let first: [number, number] | null = null;
  let width = 0;
  let height = 0;
  // a button tapped once, waiting to see whether a second tap follows
  let pending: { index: number; timer: ReturnType<typeof setTimeout> } | null = null;

  $: side = width ? (width * SHRINK) / GRID_COLS : 0;
  $: rows = side ? Math.floor(height / side) : 0;
  $: left = width - GRID_COLS * side;
  $: top = height - rows * side;
  $: squares = Array.from({ length: rows * GRID_COLS }, (_, i) => [i % GRID_COLS, Math.floor(i / GRID_COLS)] as [number, number]);
  $: taken = new Set(built.flatMap((b) => cover(b.box)));
  $: cells = built.map((b) => draw(b, side, left, top));

  function load(): Built[] {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) ?? "[]");
      return Array.isArray(raw) ? raw : [];
    } catch {
      return [];
    }
  }

  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(built));
    } catch {
      // nowhere to keep it: it lasts as long as the page
    }
  }

  /** The squares a box covers, as "x,y". */
  function cover([x, y, w, h]: Box): string[] {
    const out: string[] = [];
    for (let i = x; i < x + w; i++) for (let j = y; j < y + h; j++) out.push(`${i},${j}`);
    return out;
  }

  function draw(b: Built, s: number, l: number, t: number) {
    const [x, y, w, h] = b.box;
    const x0 = l + x * s + GAP;
    const y0 = t + y * s + GAP;
    const x1 = l + (x + w) * s - GAP;
    const y1 = t + (y + h) * s - GAP;
    return { d: polyPath(formShape(x0, y0, x1, y1, b.form, s * SLANT)), form: b.form };
  }

  function square(x: number, y: number) {
    primeAudio();
    if (taken.has(`${x},${y}`)) return;
    if (!first) {
      tap(2);
      first = [x, y];
      return;
    }
    const [fx, fy] = first;
    first = null;
    if (fx === x && fy === y) {
      tap(0);
      return;
    }
    const box: Box = [Math.min(fx, x), Math.min(fy, y), Math.abs(fx - x) + 1, Math.abs(fy - y) + 1];
    // a button only where the squares are free
    if (cover(box).some((k) => taken.has(k))) {
      tap(0);
      return;
    }
    tap(7);
    built = [...built, { box, form: "rect" }];
    save();
  }

  function button(index: number) {
    primeAudio();
    first = null;
    if (pending && pending.index === index) {
      // the second of two quick taps: away with it
      clearTimeout(pending.timer);
      pending = null;
      tap(0);
      built = built.filter((_, i) => i !== index);
      save();
      return;
    }
    if (pending) clearTimeout(pending.timer);
    pending = {
      index,
      timer: setTimeout(() => {
        pending = null;
        tap(5);
        built = built.map((b, i) => (i === index ? { ...b, form: FORMS[(FORMS.indexOf(b.form) + 1) % FORMS.length] } : b));
        save();
      }, DOUBLE_MS),
    };
  }

  function home() {
    primeAudio();
    tap(0);
    onHome();
  }

  onMount(() => {
    setBackHandler(() => {
      if (!first) return false;
      first = null;
      return true;
    });
    powerOn();
  });

  onDestroy(() => {
    setBackHandler(null);
    if (pending) clearTimeout(pending.timer);
  });
</script>

<div class="build" style="--cell: {side ? `${side - 2 * GAP}px` : '18%'}; --gap: {GAP}px">
  <div class="display">
    <p class="small">{first ? "toque outra casa" : built.length ? `${built.length} ${built.length === 1 ? "botão" : "botões"}` : "toque duas casas"}</p>
  </div>

  <div class="grid" bind:clientWidth={width} bind:clientHeight={height}>
    {#if side && rows}
      <svg viewBox="0 0 {width} {height}" {width} {height}>
        {#each squares as [x, y] (`${x},${y}`)}
          {#if !taken.has(`${x},${y}`)}
            <rect
              class="square"
              class:first={first && first[0] === x && first[1] === y}
              x={left + x * side + GAP}
              y={top + y * side + GAP}
              width={side - 2 * GAP}
              height={side - 2 * GAP}
              role="button"
              tabindex="-1"
              aria-label="casa {x + 1}, {y + 1}"
              on:click={() => square(x, y)}
              on:keydown={(e) => e.key === "Enter" && square(x, y)}
            />
          {/if}
        {/each}
        {#each cells as c, i (built[i])}
          <path
            class="cell"
            d={c.d}
            role="button"
            tabindex="0"
            aria-label="botão {i + 1}"
            on:click={() => button(i)}
            on:keydown={(e) => e.key === "Enter" && button(i)}
          />
        {/each}
      </svg>
    {/if}
  </div>

  <div class="bar">
    <button class="home-btn" aria-label="início" on:click={home}></button>
  </div>
</div>

<style>
  .build {
    --ink: #00e0ff;
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
    flex: 0 0 12%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: flex-end;
    padding: 0.5rem 0.4rem;
  }
  .small {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.85rem;
    color: #ffffff;
    opacity: 0.7;
  }
  .grid { flex: 1; min-height: 0; }
  svg { display: block; width: 100%; height: 100%; overflow: visible; }

  /* the grid's squares, faint until one is chosen */
  .square {
    fill: var(--ink);
    fill-opacity: 0.03;
    stroke: var(--ink);
    stroke-opacity: 0.18;
    stroke-width: 1;
    cursor: pointer;
    outline: none;
  }
  .square.first { fill-opacity: 0.25; stroke-opacity: 1; }

  /* a built button: see-through, its outline in the neon */
  .cell {
    fill: var(--ink);
    fill-opacity: 0.1;
    stroke: var(--ink);
    stroke-width: 1.5;
    stroke-linejoin: miter;
    cursor: pointer;
    outline: none;
    transform-box: fill-box;
    transform-origin: 50% 50%;
    animation: tube-on 0.4s cubic-bezier(0.2, 0.8, 0.3, 1) both;
  }
  .cell:active, .cell:focus-visible { fill-opacity: 0.3; }
  @media (prefers-reduced-motion: reduce) {
    .cell { animation: none; }
  }

  .bar {
    flex: 0 0 44px;
    display: flex;
    justify-content: flex-end;
  }
  /* home sits under the grid's last column */
  .home-btn {
    width: var(--cell);
    margin-right: var(--gap);
    background: transparent;
    border: 1.5px solid var(--ink);
    border-radius: 0;
    cursor: pointer;
  }
  .home-btn:active { background: rgba(0, 224, 255, 0.25); }
</style>
