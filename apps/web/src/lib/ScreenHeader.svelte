<script lang="ts">
  import { primeAudio } from "./dtmf";
  import { tap } from "./sfx";
  import { DOT_R, GLYPHS, shade, type HomeOption } from "./homeLayout";

  /** The option this page belongs to: its glyph stands for it, as on the tile. */
  export let option: HomeOption | null = null;
  /** Read by screen readers, and shown only for a page with no tile. */
  export let title: string;
  export let onBack: () => void;

  function back() {
    primeAudio();
    tap(0);
    onBack();
  }
</script>

<header class="screen-header">
  <button class="back" on:click={back} aria-label="voltar">‹</button>
  {#if option}
    <svg class="mark" viewBox="0 0 24 24" role="img" aria-label={title} style="--color: {shade(option.color, -0.3)}">
      <path d={GLYPHS[option.id].d} />
      {#each GLYPHS[option.id].dots as [x, y]}<circle cx={x} cy={y} r={DOT_R} />{/each}
    </svg>
  {:else}
    <span class="title">{title}</span>
  {/if}
</header>

<style>
  .screen-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 0.9rem;
    border-bottom: 1px solid #d4d4d4;
    background: #ffffff;
    flex-shrink: 0;
  }
  .back {
    width: 2.2rem;
    height: 2.2rem;
    background: #ffffff;
    border: 1px solid #d4d4d4;
    border-radius: 3px;
    color: #444444;
    font: inherit;
    font-size: 1.3rem;
    line-height: 1;
    cursor: pointer;
  }
  .back:active { border-color: #00838f; color: #00838f; }
  .mark {
    width: 1.6rem;
    height: 1.6rem;
    fill: none;
    stroke: var(--color);
    stroke-width: 1.7;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .mark circle { fill: var(--color); stroke: none; }
  .title {
    font-family: var(--font-display);
    font-weight: 500;
    font-size: 0.85rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #111111;
  }
</style>
