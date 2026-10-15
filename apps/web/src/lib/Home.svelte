<script lang="ts">
  import {
    DOT_R,
    GLYPHS,
    HOME_OPTIONS,
    centroid,
    inset,
    roundedPath,
    shade,
    type HomeOptionId,
    type Point,
  } from "./homeLayout";
  import { onMount } from "svelte";
  import { primeAudio } from "./dtmf";
  import { powerOn, tap } from "./sfx";

  export let onOpen: (id: HomeOptionId) => void;
  /** The option suggested next: its outline is lit. Never named, only shown. */
  export let hint: HomeOptionId | null = null;

  // The upper part of the screen stays empty: the cells live where a thumb
  // reaches. TOP is where they begin, as a fraction of the height.
  const TOP = 0.42;
  // half the gap between two cells, in pixels
  const GAP = 6;
  // how round the cells' corners are, in pixels
  const RADIUS = 14;
  // When the screen comes on, each cell lights up like a tube set warming, at
  // its own moment: an uneven order reads as a machine, an even one as a menu.
  const DELAY: Record<HomeOptionId, number> = {
    act: 0, logs: 70, journey: 130, shop: 190, roko: 260, attributes: 340,
  };

  let width = 0;
  let height = 0;
  let pressed: HomeOptionId | null = null;

  // Plain shapes, drawn once per size: nothing on this screen animates.
  $: cells = HOME_OPTIONS.filter((o) => o.unlocked).map((o) => {
    const area = height * (1 - TOP);
    const shape = inset(o.polygon.map(([x, y]) => [x * width, height * TOP + y * area] as Point), GAP);
    const [cx, cy] = centroid(shape);
    const xs = shape.map((p) => p[0]);
    const ys = shape.map((p) => p[1]);
    const w = Math.max(...xs) - Math.min(...xs);
    const h = Math.max(...ys) - Math.min(...ys);
    return {
      ...o,
      d: roundedPath(shape, RADIUS),
      cx,
      cy,
      glyph: Math.max(28, Math.min(w * 0.5, h * 0.5, 96)),
    };
  });

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
        <!-- each cell solid in its color, lit from the top left; pressed, the
             light moves to the far side -->
        <defs>
          {#each cells as c (c.id)}
            <radialGradient id="home-{c.id}" cx="35%" cy="25%" r="100%">
              <stop offset="0" stop-color={shade(c.color, 0.3)} />
              <stop offset="0.55" stop-color={c.color} />
              <stop offset="1" stop-color={shade(c.color, -0.1)} />
            </radialGradient>
            <radialGradient id="home-{c.id}-down" cx="50%" cy="50%" r="80%">
              <stop offset="0" stop-color={shade(c.color, -0.04)} />
              <stop offset="1" stop-color={shade(c.color, -0.16)} />
            </radialGradient>
          {/each}
        </defs>
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
            style="--fill: url(#home-{c.id}); --fill-down: url(#home-{c.id}-down); --ink: {shade(c.color, -0.6)}; --delay: {DELAY[c.id]}ms"
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
    background: var(--void);
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
  .shape {
    fill: var(--fill);
    stroke: #ffffff;
    stroke-opacity: 0.4;
    stroke-width: 1;
    filter: drop-shadow(0 2px 4px rgba(60, 30, 50, 0.16));
  }
  .glyph path {
    fill: none;
    stroke: var(--ink);
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .glyph circle { fill: var(--ink); }

  /* a hint, never a caption: the suggested cell's outline is lit */
  .cell.hint .shape { stroke-opacity: 1; stroke-width: 2.5; }

  /* pressed: the light on the far side, the shadow shrunk under it — hover only
     where there is a real pointer: on a touch screen it sticks to the last cell */
  .cell:focus-visible .shape { stroke-opacity: 1; }
  .cell.pressed .shape {
    fill: var(--fill-down);
    filter: drop-shadow(0 1px 1px rgba(60, 30, 50, 0.18));
  }
  @media (hover: hover) {
    .cell:hover .shape { stroke-opacity: 1; }
  }
</style>
