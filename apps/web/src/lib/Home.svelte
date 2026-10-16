<script lang="ts">
  import {
    DOT_R,
    GLYPHS,
    HOME_OPTIONS,
    HOME_ASPECT,
    HOME_COLS,
    HOME_ROWS,
    SLANT,
    formShape,
    polyPath,
    type HomeOptionId,
  } from "./homeLayout";
  import { onMount } from "svelte";
  import { primeAudio } from "./dtmf";
  import { powerOn, tap } from "./sfx";

  export let onOpen: (id: HomeOptionId) => void;
  /** The option suggested next: its outline is lit. Never named, only shown. */
  export let hint: HomeOptionId | null = null;

  // The cells gather in the bottom-right corner on a grid of narrow upright
  // units: at most WIDE of the width and HIGH of the height.
  const WIDE = 0.75;
  const HIGH = 0.68;
  // half the gap between two cells, in pixels
  const GAP = 9;
  // When the screen comes on, each cell lights up like a tube set warming, at
  // its own moment: an uneven order reads as a machine, an even one as a menu.
  const DELAY: Record<HomeOptionId, number> = {
    act: 0, logs: 70, journey: 130, shop: 190, roko: 260, attributes: 340,
  };

  let width = 0;
  let height = 0;
  let pressed: HomeOptionId | null = null;

  // Plain shapes, drawn once per size: nothing on this screen animates.
  $: shown = HOME_OPTIONS.filter((o) => o.unlocked);
  $: unit = Math.min((width * WIDE) / HOME_COLS, (height * HIGH) / (HOME_ROWS * HOME_ASPECT));
  $: cells = draw(shown, width, height, unit);

  function draw(options: typeof HOME_OPTIONS, w: number, h: number, u: number) {
    const tall = u * HOME_ASPECT;
    const left = w - HOME_COLS * u;
    const top = h - HOME_ROWS * tall;
    return options.map((o) => {
      const [bx, by, bw, bh] = o.box;
      const x0 = left + bx * u + GAP;
      const y0 = top + by * tall + GAP;
      const x1 = left + (bx + bw) * u - GAP;
      const y1 = top + (by + bh) * tall - GAP;
      const shape = formShape(x0, y0, x1, y1, o.form, u * SLANT);
      return {
        ...o,
        d: polyPath(shape),
        cx: (x0 + x1) / 2,
        cy: (y0 + y1) / 2,
        glyph: Math.max(20, Math.min((x1 - x0) * 0.5, (y1 - y0) * 0.5, 64)),
      };
    });
  }

  // the screen comes on with a sound, when one has been allowed (after a tap)
  onMount(() => powerOn());

  function press(id: HomeOptionId, tone: string) {
    primeAudio();
    tap(Number(tone));
    pressed = id;
  }

  // Opening waits for the click, not the pointer going up: the click that follows
  // a pointerup would otherwise land on whatever the next screen puts under the
  // finger — on agir, an action, chosen without being asked for.
  function open(id: HomeOptionId) {
    pressed = null;
    onOpen(id);
  }

  function onKey(e: KeyboardEvent, id: HomeOptionId, tone: string) {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    primeAudio();
    tap(Number(tone));
    onOpen(id);
  }
</script>

<div class="home">
  <div class="stage" bind:clientWidth={width} bind:clientHeight={height}>
    {#if width > 0 && height > 0}
      <svg viewBox="0 0 {width} {height}" width={width} height={height}>
        {#each cells as c (c.id)}
          <g
            class="cell"
            class:pressed={pressed === c.id}
            class:hint={hint === c.id}
            role="button"
            tabindex="0"
            aria-label={c.label}
            on:pointerdown={() => press(c.id, c.tone)}
            on:click={() => open(c.id)}
            on:pointerleave={() => pressed === c.id && (pressed = null)}
            on:pointercancel={() => (pressed = null)}
            on:keydown={(e) => onKey(e, c.id, c.tone)}
            style="--color: {c.color}; --delay: {DELAY[c.id]}ms"
          >
            <path class="shape" d={c.d} />
            <g class="glyph" transform="translate({c.cx - c.glyph / 2} {c.cy - c.glyph / 2}) scale({c.glyph / 24})">
              <path d={GLYPHS[c.id].d} stroke-width={(24 / c.glyph) * 2.4} />
              {#each GLYPHS[c.id].dots as [x, y]}<circle cx={x} cy={y} r={DOT_R} />{/each}
            </g>
          </g>
        {/each}
      </svg>
    {/if}
  </div>
</div>

<style>
  /* fills the frame App draws around the whole interface */
  .home {
    position: absolute;
    inset: 0;
    /* keeps the square corners of the cells clear of the frame's round ones */
    padding: 10px;
    box-sizing: border-box;
    background: transparent;
    touch-action: manipulation;
    user-select: none;
    -webkit-user-select: none;
  }
  .stage {
    width: 100%;
    height: 100%;
  }
  svg {
    display: block;
    width: 100%;
    height: 100%;
  }
  .cell {
    cursor: pointer;
    outline: none;
    /* scale each cell about its own centre */
    transform-box: fill-box;
    transform-origin: 50% 50%;
    /* the tube comes on — a bright line opening into the picture — then the
       picture settles with a few quick flickers */
    animation:
      tube-on 0.5s cubic-bezier(0.2, 0.8, 0.3, 1) var(--delay) both,
      settle 0.4s steps(1) calc(var(--delay) + 0.5s) 1;
  }
  @media (prefers-reduced-motion: reduce) {
    .cell { animation: none; }
  }
  /* see-through: a faint wash of the option's neon, its outline, its glyph */
  .shape {
    fill: var(--color);
    fill-opacity: 0.1;
    stroke: var(--color);
    stroke-width: 1.5;
    stroke-linejoin: miter;
  }
  .glyph path {
    fill: none;
    stroke: var(--color);
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .glyph circle { fill: var(--color); }

  /* a hint, never a caption: the suggested cell's outline is thicker */
  .cell.hint .shape { stroke-width: 2.5; }

  /* pressed, the wash fills in — hover only where there is a real pointer: on a
     touch screen it sticks to the last cell */
  .cell:focus-visible .shape, .cell.pressed .shape { fill-opacity: 0.3; }
  @media (hover: hover) {
    .cell:hover .shape { fill-opacity: 0.3; }
  }
</style>
