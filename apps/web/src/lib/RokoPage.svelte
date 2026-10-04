<script lang="ts">
  import { DOT_R, GLYPHS } from "./homeLayout";
</script>

<!-- Roko does not talk yet: the eye is open and the line is empty. -->
<section class="roko">
  <svg viewBox="0 0 24 24" class="eye" aria-hidden="true">
    <path d={GLYPHS.roko.d} />
    {#each GLYPHS.roko.dots as [x, y]}<circle cx={x} cy={y} r={DOT_R} />{/each}
  </svg>
  <p class="line">…</p>
</section>

<style>
  .roko {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1.5rem;
  }
  .eye {
    width: 6rem;
    height: 6rem;
    fill: none;
    stroke: #ff9a3c;
    stroke-width: 1;
    stroke-linecap: round;
  }
  .eye circle { fill: #ff9a3c; stroke: none; }
  .line {
    margin: 0;
    color: #808080;
    font-family: var(--font-mono);
    font-size: 1.2rem;
    letter-spacing: 0.3em;
  }
</style>
