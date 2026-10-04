<script lang="ts">
  import { HOME_OPTIONS, ICONS, centroid, inset, type HomeOptionId, type Point } from "./homeLayout";
  import { keyFeedback, primeAudio } from "./dtmf";

  export let onOpen: (id: HomeOptionId) => void;

  // half the gap between two tiles, in pixels
  const GAP = 3;

  let width = 0;
  let height = 0;
  let pressed: HomeOptionId | null = null;

  $: tiles = HOME_OPTIONS.filter((o) => o.unlocked).map((o) => {
    const px = o.polygon.map(([x, y]) => [x * width, y * height] as Point);
    const shape = inset(px, GAP);
    const [cx, cy] = centroid(shape);
    const xs = shape.map((p) => p[0]);
    const ys = shape.map((p) => p[1]);
    // the icon grows with the tile, within reason
    const span = Math.min(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    const size = Math.max(22, Math.min(span * 0.34, 120));
    return {
      ...o,
      points: shape.map((p) => p.join(",")).join(" "),
      cx,
      cy,
      size,
      labelSize: Math.max(11, Math.min(size * 0.3, 20)),
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
      {#each tiles as t (t.id)}
        <g
          class="tile"
          class:pressed={pressed === t.id}
          role="button"
          tabindex="0"
          aria-label={t.label}
          on:pointerdown={() => press(t.id, t.tone)}
          on:pointerup={() => release(t.id)}
          on:pointerleave={() => pressed === t.id && (pressed = null)}
          on:pointercancel={() => (pressed = null)}
          on:keydown={(e) => onKey(e, t.id, t.tone)}
          style="transform-origin: {t.cx}px {t.cy}px"
        >
          <polygon points={t.points} />
          <path
            class="icon"
            d={ICONS[t.icon]}
            transform="translate({t.cx - t.size / 2} {t.cy - t.size * 0.7}) scale({t.size / 24})"
            stroke-width={24 / t.size * 2.2}
          />
          <text x={t.cx} y={t.cy + t.size * 0.55} font-size={t.labelSize}>{t.label.toUpperCase()}</text>
        </g>
      {/each}
    </svg>
  {/if}
  </div>
</div>

<style>
  .home {
    position: fixed;
    inset: 0;
    /* clear the status bar and the gesture bar on a phone */
    padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
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
  .tile {
    cursor: pointer;
    outline: none;
    transition: transform 0.08s;
  }
  polygon {
    fill: #000000;
    stroke: #ffffff;
    stroke-width: 1;
    transition: stroke 0.12s;
  }
  .icon {
    fill: none;
    stroke: #cccccc;
    stroke-linecap: square;
    stroke-linejoin: miter;
    transition: stroke 0.12s;
  }
  text {
    fill: #808080;
    font-family: var(--font-display);
    font-weight: 500;
    letter-spacing: 0.2em;
    text-anchor: middle;
    dominant-baseline: hanging;
    transition: fill 0.12s;
  }
  .tile:focus-visible polygon { stroke-width: 2; }
  .tile:hover .icon { stroke: #ffffff; }
  .tile.pressed { transform: scale(0.98); }
  .tile.pressed polygon { stroke: #00e5ff; }
  .tile.pressed .icon { stroke: #00e5ff; }
  .tile.pressed text { fill: #00e5ff; }
</style>
