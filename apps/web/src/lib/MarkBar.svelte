<script lang="ts">
  /** Marks toward the next rank: a thick white bar cut into one segment per mark,
   *  rounded only at its ends, with the count floating in the middle. */
  export let marks = 0;
  export let need = 3;
  export let size: "lg" | "md" = "lg";
  /** What floats over the bar; `marks/need` unless given. */
  export let label: string | null = null;
  /** Makes each segment a button: clicking the n-th picks n. */
  export let onPick: ((units: number) => void) | null = null;

  $: segments = Math.max(1, Math.floor(need));
  $: filled = Math.max(0, Math.min(segments, Math.floor(marks)));
  // past a few dozen segments the gaps stop reading as units
  $: continuous = segments > 40 && !onPick;
  $: text = label ?? `${filled}/${segments}`;
</script>

<div
  class="markbar {size}"
  class:continuous
  role="progressbar"
  aria-valuemin={0}
  aria-valuemax={segments}
  aria-valuenow={filled}
  aria-valuetext={text}
>
  {#if continuous}
    <div class="fill" style="width: {(filled / segments) * 100}%"></div>
  {:else}
    {#each Array(segments) as _, i (i)}
      {#if onPick}
        <button
          type="button"
          class="seg pick"
          class:on={i < filled}
          aria-label="{i + 1} de {segments}"
          on:click={() => onPick?.(i + 1)}
        ></button>
      {:else}
        <span class="seg" class:on={i < filled}></span>
      {/if}
    {/each}
  {/if}
  <span class="count">{text}</span>
</div>

<style>
  /* the radius and the clipping live on the bar, so only its two ends are rounded */
  .markbar {
    position: relative;
    display: flex;
    gap: 2px;
    width: 100%;
    border-radius: 999px;
    overflow: hidden;
  }
  .markbar.lg { height: 22px; }
  .markbar.md { height: 16px; }
  .markbar.continuous { background: #333333; }
  .seg { flex: 1; min-width: 2px; background: #333333; }
  .seg.on { background: #ffffff; }
  .seg.pick {
    border: none;
    padding: 0;
    margin: 0;
    cursor: pointer;
  }
  .seg.pick:hover { background: #808080; }
  .seg.pick.on:hover { background: #cccccc; }
  .fill { height: 100%; background: #ffffff; }
  .count {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #808080;
    font-size: 0.68rem;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    pointer-events: none;
  }
  .lg .count { font-size: 0.75rem; }
</style>
