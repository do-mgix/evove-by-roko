<script lang="ts">
  import {
    DOT_R,
    GLYPHS,
    HOME_OPTIONS,
    centroid,
    inset,
    type HomeOptionId,
    type Point,
  } from "./homeLayout";
  import { keyFeedback, primeAudio } from "./dtmf";

  export let onOpen: (id: HomeOptionId) => void;
  /** The option suggested next: its outline is lit. Never named, only shown. */
  export let hint: HomeOptionId | null = null;

  // The upper part of the screen stays empty: the cells live where a thumb
  // reaches. TOP is where they begin, as a fraction of the height.
  const TOP = 0.42;
  // half the gap between two cells, in pixels
  const GAP = 6;

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
      points: shape.map((p) => p.join(",")).join(" "),
      cx,
      cy,
      glyph: Math.max(28, Math.min(w * 0.5, h * 0.5, 96)),
    };
  });

  function press(id: HomeOptionId, tone: string) {
    primeAudio();
    keyFeedback(tone);
    pressed = id;
  }

  function release(id: HomeOptionId) {
    if (pressed !== id) return;
    pressed = null;
    onOpen(id);
  }

  function onKey(e: KeyboardEvent, id: HomeOptionId, tone: string) {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    primeAudio();
    keyFeedback(tone);
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
            on:pointerup={() => release(c.id)}
            on:pointerleave={() => pressed === c.id && (pressed = null)}
            on:pointercancel={() => (pressed = null)}
            on:keydown={(e) => onKey(e, c.id, c.tone)}
            style="--color: {c.color}"
          >
            <polygon points={c.points} />
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
    background: #000000;
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
    --ink: var(--color);
    cursor: pointer;
    outline: none;
  }
  polygon {
    fill: #000000;
    stroke: var(--ink);
    stroke-opacity: 0.55;
    stroke-width: 1.5;
    stroke-linejoin: miter;
  }
  .glyph path {
    fill: none;
    stroke: var(--ink);
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .glyph circle { fill: var(--ink); }

  /* a hint, never a caption: the suggested cell's outline is lit */
  .cell.hint polygon { stroke-opacity: 1; stroke-width: 2.5; }

  /* hover and press turn the cell white */
  .cell:hover,
  .cell:focus-visible,
  .cell.pressed { --ink: #ffffff; }
  .cell:hover polygon,
  .cell:focus-visible polygon,
  .cell.pressed polygon { stroke-opacity: 1; }
</style>
