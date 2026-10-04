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

  // The upper part of the screen stays empty: the cells live where a thumb
  // reaches. TOP is where they begin, as a fraction of the height.
  const TOP = 0.42;
  // half the gap between two cells, in pixels — the walls drift, so it is generous
  const GAP = 8;
  const RADIUS = 22;
  // how far the walls drift, in pixels, and how fast (radians per second)
  const DRIFT = 3.5;
  const SPEED = 0.35;
  // The cells are drawn on a canvas this many CSS pixels per canvas pixel and
  // scaled back up smoothly: a soft, low-resolution signal, never quite in focus.
  const RES = 2.2;
  // teal, the one color of the interface
  const INK = [95, 227, 208];
  const ink = (a: number) => `rgba(${INK[0]}, ${INK[1]}, ${INK[2]}, ${a})`;

  let width = 0;
  let height = 0;
  let pressed: HomeOptionId | null = null;
  let t = 0;
  let canvas: HTMLCanvasElement;

  // The still part: each cell's rounded outline, its centre and its glyph size.
  $: cells = HOME_OPTIONS.filter((o) => o.unlocked).map((o) => {
    const area = height * (1 - TOP);
    const px = o.polygon.map(([x, y]) => [x * width, height * TOP + y * area] as Point);
    const shape = inset(px, GAP);
    const [cx, cy] = centroid(shape);
    const xs = shape.map((p) => p[0]);
    const ys = shape.map((p) => p[1]);
    const w = Math.max(...xs) - Math.min(...xs);
    const h = Math.max(...ys) - Math.min(...ys);
    const ring = outline(shape, RADIUS, 16);
    // the inner membrane: the same outline drawn a few pixels in
    const k = Math.max(0.8, 1 - 9 / Math.min(w, h));
    const inner = ring.map(([x, y]) => [cx + (x - cx) * k, cy + (y - cy) * k] as Point);
    return { ...o, ring, inner, target: smoothPath(ring), cx, cy, r: Math.max(w, h) * 0.7, glyph: Math.max(20, Math.min(w * 0.3, h * 0.3, 48)) };
  });

  // The living part: the walls drift through the field, all together. Only the
  // canvas follows them; the touch targets keep the still outline, a few pixels off
  // at most, so nothing in the DOM changes while the cells breathe.
  $: drawn = cells.map((c) => ({
    ...c,
    wall: smoothPath(displace(c.ring, DRIFT, t)),
    membrane: smoothPath(displace(c.inner, DRIFT * 1.6, t + 1.7)),
  }));

  $: if (canvas && width && height) paint(drawn, pressed, hint, t);

  function paint(list: typeof drawn, down: HomeOptionId | null, glow: HomeOptionId | null, time: number) {
    const cw = Math.max(1, Math.round(width / RES));
    const ch = Math.max(1, Math.round(height / RES));
    if (canvas.width !== cw || canvas.height !== ch) {
      canvas.width = cw;
      canvas.height = ch;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    ctx.setTransform(1 / RES, 0, 0, 1 / RES, 0, 0);
    // the breath of the suggested cell, 0..1
    const breath = (Math.sin(time * 2.4) + 1) / 2;
    for (const c of list) {
      const lit = c.id === down ? 1 : c.id === glow ? breath : 0;
      const wall = new Path2D(c.wall);
      // a faint light from inside, like something alive
      const light = ctx.createRadialGradient(c.cx, c.cy * 0.98, 0, c.cx, c.cy, c.r);
      light.addColorStop(0, `rgba(14, 52, 48, ${0.75 + lit * 0.25})`);
      light.addColorStop(0.6, "rgba(5, 20, 19, 0.9)");
      light.addColorStop(1, "rgba(2, 8, 8, 1)");
      ctx.fillStyle = light;
      ctx.fill(wall);
      ctx.shadowColor = ink(0.9);
      ctx.shadowBlur = lit > 0.05 ? lit * 18 : 0;
      ctx.strokeStyle = ink(0.7 + lit * 0.3);
      ctx.lineWidth = 1.3;
      ctx.stroke(wall);
      ctx.shadowBlur = 0;
      ctx.strokeStyle = ink(0.16);
      ctx.lineWidth = 0.9;
      ctx.stroke(new Path2D(c.membrane));

      const g = GLYPHS[c.id];
      ctx.save();
      ctx.translate(c.cx - c.glyph / 2, c.cy - c.glyph / 2);
      ctx.scale(c.glyph / 24, c.glyph / 24);
      // glow only where it is meant to show; a canvas shadow is not free
      ctx.shadowColor = ink(1);
      ctx.shadowBlur = lit * 12;
      ctx.strokeStyle = ink(0.85 + lit * 0.15);
      ctx.fillStyle = ink(0.85 + lit * 0.15);
      ctx.lineWidth = (24 / c.glyph) * 1.8;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.stroke(new Path2D(g.d));
      for (const [x, y] of g.dots) {
        ctx.beginPath();
        ctx.arc(x, y, DOT_R, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }

  onMount(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // Six frames a second: the walls move a fraction of a pixel per frame, so it
    // still reads as smooth, and the cost grows with the rate — at 12 it took a
    // third of a core on a mid phone. A timer rather than requestAnimationFrame,
    // which would wake the page sixty times a second only to skip most of them.
    const FPS = 6;
    let last = performance.now();
    const timer = setInterval(() => {
      const now = performance.now();
      if (document.visibilityState === "visible") t += ((now - last) / 1000) * SPEED;
      last = now;
    }, 1000 / FPS);
    return () => clearInterval(timer);
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
    <canvas bind:this={canvas} aria-hidden="true"></canvas>
    {#if width > 0 && height > 0}
      <!-- invisible: the touch targets, keyboard focus and screen-reader names -->
      <svg viewBox="0 0 {width} {height}" width={width} height={height}>
        {#each cells as c (c.id)}
          <path
            class="target"
            d={c.target}
            role="button"
            tabindex="0"
            aria-label={c.label}
            on:pointerdown={() => press(c.id, c.tone)}
            on:pointerup={() => release(c.id)}
            on:pointerleave={() => pressed === c.id && (pressed = null)}
            on:pointercancel={() => (pressed = null)}
            on:keydown={(e) => onKey(e, c.id, c.tone)}
          />
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
    position: relative;
    width: 100%;
    height: 100%;
  }
  canvas,
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
  }
  /* scaled up smoothly from a fraction of the resolution, never quite sharp */
  canvas {
    image-rendering: auto;
  }
  .target {
    fill: #000000;
    fill-opacity: 0;
    cursor: pointer;
    outline: none;
  }
  .target:focus-visible {
    stroke: rgb(95, 227, 208);
    stroke-width: 2;
  }
</style>
