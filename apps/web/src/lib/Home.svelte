<script lang="ts">
  import { onMount } from "svelte";
  import {
    DOT_R,
    GLYPHS,
    HOME_OPTIONS,
    centroid,
    displace,
    inset,
    outline,
    smoothPath,
    type HomeOptionId,
    type Point,
  } from "./homeLayout";
  import { keyFeedback, primeAudio } from "./dtmf";

  export let onOpen: (id: HomeOptionId) => void;
  /** The option suggested next: it glows a little. Never named, only shown. */
  export let hint: HomeOptionId | null = null;

  // half the gap between two cells, in pixels — the walls drift, so it is generous
  const GAP = 8;
  const RADIUS = 22;
  // how far the walls drift, in pixels, and how fast (radians per second)
  const DRIFT = 3.5;
  const SPEED = 0.35;

  let width = 0;
  let height = 0;
  let pressed: HomeOptionId | null = null;
  let t = 0;

  // The still part: each cell's rounded outline, its centre and its glyph size.
  $: cells = HOME_OPTIONS.filter((o) => o.unlocked).map((o) => {
    const shape = inset(o.polygon.map(([x, y]) => [x * width, y * height] as Point), GAP);
    const [cx, cy] = centroid(shape);
    const xs = shape.map((p) => p[0]);
    const ys = shape.map((p) => p[1]);
    const w = Math.max(...xs) - Math.min(...xs);
    const h = Math.max(...ys) - Math.min(...ys);
    const ring = outline(shape, RADIUS);
    // the inner membrane: the same outline drawn a few pixels in
    const k = Math.max(0.8, 1 - 10 / Math.min(w, h));
    const inner = ring.map(([x, y]) => [cx + (x - cx) * k, cy + (y - cy) * k] as Point);
    return { ...o, ring, inner, cx, cy, glyph: Math.max(22, Math.min(w * 0.3, h * 0.24, 56)) };
  });

  // The living part: the walls drift through the field, all together.
  $: drawn = cells.map((c) => ({
    ...c,
    wall: smoothPath(displace(c.ring, DRIFT, t)),
    membrane: smoothPath(displace(c.inner, DRIFT * 1.6, t + 1.7)),
  }));

  onMount(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    let last = performance.now();
    let acc = 0;
    const loop = (now: number) => {
      acc += (now - last) / 1000;
      last = now;
      // ~24 frames a second is plenty for something this slow
      if (acc >= 1 / 24) {
        t += acc * SPEED;
        acc = 0;
      }
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
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
        <defs>
          <!-- a faint light from inside each cell, like something alive -->
          <radialGradient id="cell-light" cx="50%" cy="46%" r="70%">
            <stop offset="0%" stop-color="#1c1b18" />
            <stop offset="60%" stop-color="#0b0b0a" />
            <stop offset="100%" stop-color="#050505" />
          </radialGradient>
        </defs>
        {#each drawn as c (c.id)}
          <g
            class="cell"
            class:pressed={pressed === c.id}
            class:hint={hint === c.id && pressed !== c.id}
            role="button"
            tabindex="0"
            aria-label={c.label}
            on:pointerdown={() => press(c.id, c.tone)}
            on:pointerup={() => release(c.id)}
            on:pointerleave={() => pressed === c.id && (pressed = null)}
            on:pointercancel={() => (pressed = null)}
            on:keydown={(e) => onKey(e, c.id, c.tone)}
            style="transform-origin: {c.cx}px {c.cy}px"
          >
            <path class="wall" d={c.wall} />
            <path class="membrane" d={c.membrane} />
            <g class="glyph" transform="translate({c.cx - c.glyph / 2} {c.cy - c.glyph / 2}) scale({c.glyph / 24})">
              <path d={GLYPHS[c.id].d} stroke-width={(24 / c.glyph) * 1.7} />
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
    overflow: visible;
  }
  .cell {
    --bone: #e6e1d3;
    cursor: pointer;
    outline: none;
    transition: transform 0.12s;
  }
  .wall {
    fill: url(#cell-light);
    stroke: var(--bone);
    stroke-width: 1.2;
    stroke-opacity: 0.75;
    transition: stroke-opacity 0.15s, filter 0.15s;
  }
  .membrane {
    fill: none;
    stroke: var(--bone);
    stroke-width: 0.8;
    stroke-opacity: 0.18;
  }
  .glyph path {
    fill: none;
    stroke: var(--bone);
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .glyph circle { fill: var(--bone); }
  .glyph {
    opacity: 0.85;
    transition: opacity 0.15s, filter 0.15s;
  }
  .cell:focus-visible .wall { stroke-opacity: 1; stroke-width: 2; }
  .cell.pressed { transform: scale(0.975); }
  .cell.pressed .wall { stroke-opacity: 1; filter: drop-shadow(0 0 8px var(--bone)); }
  .cell.pressed .glyph { opacity: 1; filter: drop-shadow(0 0 6px var(--bone)); }

  /* a hint, never a caption: the suggested cell breathes light outwards */
  .cell.hint .wall { animation: glow 3.2s ease-in-out infinite; }
  .cell.hint .glyph { animation: wake 3.2s ease-in-out infinite; }
  @keyframes glow {
    0%, 100% { filter: drop-shadow(0 0 0 var(--bone)); stroke-opacity: 0.75; }
    50% { filter: drop-shadow(0 0 12px var(--bone)); stroke-opacity: 1; }
  }
  @keyframes wake {
    0%, 100% { opacity: 0.85; }
    50% { opacity: 1; filter: drop-shadow(0 0 5px var(--bone)); }
  }
  @media (prefers-reduced-motion: reduce) {
    .cell.hint .wall { animation: none; filter: drop-shadow(0 0 8px var(--bone)); }
    .cell.hint .glyph { animation: none; }
  }
</style>
