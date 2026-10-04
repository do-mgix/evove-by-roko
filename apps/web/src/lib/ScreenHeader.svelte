<script lang="ts">
  import { keyFeedback, primeAudio } from "./dtmf";
  import { DOT_R, GLYPHS, type HomeOption } from "./homeLayout";

  /** The option this page belongs to: its glyph stands for it, as on the tile. */
  export let option: HomeOption | null = null;
  /** Read by screen readers, and shown only for a page with no tile. */
  export let title: string;
  export let onBack: () => void;

  function back() {
    primeAudio();
    keyFeedback("*");
    onBack();
  }
</script>

<header class="screen-header">
  <button class="back" on:click={back} aria-label="voltar">‹</button>
  {#if option}
    <svg class="mark" viewBox="0 0 24 24" role="img" aria-label={title} style="--color: {option.color}">
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
    border-bottom: 1px solid #333333;
    background: #000000;
    flex-shrink: 0;
  }
  .back {
    width: 2.2rem;
    height: 2.2rem;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 3px;
    color: #cccccc;
    font: inherit;
    font-size: 1.3rem;
    line-height: 1;
    cursor: pointer;
  }
  .back:active { border-color: #00e5ff; color: #00e5ff; }
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
    color: #ffffff;
  }
</style>
