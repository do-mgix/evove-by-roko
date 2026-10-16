<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { DOT_R, GRID_COLS, GRID_GAP, SLANT, formShape, formsFor, gridUnit, packFree, polyPath, type Box, type Form } from "./homeLayout";
  import { BUTTON_ICONS, ICONS, type IconName } from "./icons";
  import Icon from "./Icon.svelte";
  import { primeAudio } from "./dtmf";
  import { powerOn, tap } from "./sfx";
  import { setBackHandler } from "./store";

  /** Back to the tile home. */
  export let onHome: () => void;

  // A page for building buttons on the grid: the grid's squares lie faint in
  // the bottom-right corner; a tap on one square and then another makes a button
  // across the rectangle between them, wearing an icon. A tap on a button turns
  // it to the next form, a long press to the next icon, and two quick taps take
  // it away. The bar's wide button throws a whole layout at random. What is
  // built is kept on this device.

  const FORMS: Form[] = ["rect", "trap", "prism", "pairL", "pairR"];
  const GAP = GRID_GAP;
  // two taps closer than this are one double tap
  const DOUBLE_MS = 280;
  // a press held this long is a long press
  const LONG_MS = 450;
  // the sizes a random layout draws from, in squares
  const SIZES: [number, number][] = [[1, 1], [2, 1], [1, 2], [2, 2], [3, 2], [2, 3], [3, 3]];
  const KEY = "evove_built";

  type Built = { box: Box; form: Form; icon?: IconName };

  let built: Built[] = load();
  // the first square of a button being made
  let first: [number, number] | null = null;
  let width = 0;
  let height = 0;
  // a button tapped once, waiting to see whether a second tap follows
  let pending: { index: number; timer: ReturnType<typeof setTimeout> } | null = null;
  // a press being held, and whether it already turned into a long press
  let holding: ReturnType<typeof setTimeout> | null = null;
  let held = false;

  // the grid every screen shares
  $: side = gridUnit(width);
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
    return {
      d: polyPath(formShape(x0, y0, x1, y1, b.form, s * SLANT)),
      icon: b.icon ?? null,
      cx: (x0 + x1) / 2,
      cy: (y0 + y1) / 2,
      size: Math.min(36, Math.min(x1 - x0, y1 - y0) * 0.42),
    };
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
    built = [...built, { box, form: "rect", icon: pick(BUTTON_ICONS) }];
    save();
  }

  const pick = <T,>(list: T[]): T => list[Math.floor(Math.random() * list.length)];

  /** A press on a button: held long enough, it turns the button's icon. */
  function press(index: number) {
    held = false;
    if (holding) clearTimeout(holding);
    holding = setTimeout(() => {
      holding = null;
      held = true;
      primeAudio();
      tap(3);
      built = built.map((b, i) =>
        i === index ? { ...b, icon: BUTTON_ICONS[(BUTTON_ICONS.indexOf(b.icon ?? "dots") + 1) % BUTTON_ICONS.length] } : b,
      );
      save();
    }, LONG_MS);
  }

  function release() {
    if (holding) clearTimeout(holding);
    holding = null;
  }

  function button(index: number) {
    primeAudio();
    first = null;
    // the click that ends a long press is not a tap
    if (held) {
      held = false;
      return;
    }
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

  /** A whole layout at random: buttons of assorted sizes packed into the
   *  bottom-right corner while they fit, in assorted forms and icons. */
  function shuffle() {
    primeAudio();
    first = null;
    if (!rows) return;
    const rand = () => Math.random() - 0.5;
    const want = 4 + Math.floor(Math.random() * 6);
    let sizes: [number, number][] = [];
    for (let k = 0; k < want * 3 && sizes.length < want; k++) {
      const next = [...sizes, pick(SIZES)];
      if (packFree(next, GRID_COLS).rows <= rows) sizes = next;
    }
    const { boxes, rows: used } = packFree(sizes, GRID_COLS);
    // packed from the top: lower them to the bottom of the grid
    const lowered = boxes.map(([x, y, w, h]): Box => [x, y + rows - used, w, h]);
    const forms = formsFor(lowered, rand);
    built = lowered.map((box, i) => ({ box, form: forms[i], icon: pick(BUTTON_ICONS) }));
    save();
    powerOn();
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
    release();
  });
</script>

<div class="build" style="--unit: {side || 52}px; --row: {(side || 52) * GRID_COLS}px; --gap: {GAP}px">
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
          <g
            class="cell"
            role="button"
            tabindex="0"
            aria-label="botão {i + 1}"
            on:pointerdown={() => press(i)}
            on:pointerup={release}
            on:pointerleave={release}
            on:pointercancel={release}
            on:click={() => button(i)}
            on:keydown={(e) => e.key === "Enter" && button(i)}
          >
            <path class="shape" d={c.d} />
            {#if c.icon}
              <g class="icon" transform="translate({c.cx - c.size / 2} {c.cy - c.size / 2}) scale({c.size / 24})">
                {#if ICONS[c.icon].d}<path d={ICONS[c.icon].d} stroke-width={(24 / c.size) * 1.8} />{/if}
                {#each ICONS[c.icon].dots as [x, y]}<circle cx={x} cy={y} r={DOT_R * 1.2} />{/each}
              </g>
            {/if}
          </g>
        {/each}
      </svg>
    {/if}
  </div>

  <div class="bar">
    <button class="shuffle-btn" aria-label="layout aleatório" on:click={shuffle}><Icon name="shuffle" /></button>
    <button class="home-btn" aria-label="início" on:click={home}><Icon name="circle" size={16} /></button>
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
    /* no gap: the squares and the bar are rows of the same grid */
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

  /* a built button: see-through, its outline and icon in the neon */
  .cell {
    cursor: pointer;
    outline: none;
    transform-box: fill-box;
    transform-origin: 50% 50%;
    animation: tube-on 0.4s cubic-bezier(0.2, 0.8, 0.3, 1) both;
    -webkit-touch-callout: none;
  }
  .shape {
    fill: var(--ink);
    fill-opacity: 0.1;
    stroke: var(--ink);
    stroke-width: 1.5;
    stroke-linejoin: miter;
  }
  .cell:active .shape, .cell:focus-visible .shape { fill-opacity: 0.3; }
  .icon path { fill: none; stroke: var(--ink); stroke-linecap: round; stroke-linejoin: round; }
  .icon circle { fill: var(--ink); }
  .icon { pointer-events: none; }
  @media (prefers-reduced-motion: reduce) {
    .cell { animation: none; }
  }

  /* the grid's bottom row: the shuffle across three squares, home in the last */
  .bar {
    flex: 0 0 var(--unit);
    align-self: flex-end;
    width: var(--row);
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    column-gap: calc(2 * var(--gap));
    padding: var(--gap);
    box-sizing: border-box;
  }
  .shuffle-btn, .home-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: 1.5px solid var(--ink);
    border-radius: 0;
    color: var(--ink);
    cursor: pointer;
  }
  .shuffle-btn { grid-column: 3 / 6; }
  .home-btn { grid-column: 6; }
  .shuffle-btn:active, .home-btn:active { background: rgba(0, 224, 255, 0.25); }
</style>
