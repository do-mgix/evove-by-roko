<script lang="ts">
  /** Marks toward the next rank: a thick bar cut into one rounded segment per mark. */
  export let marks = 0;
  export let need = 3;
  export let size: "lg" | "md" = "lg";

  $: segments = Math.max(1, Math.floor(need));
  $: filled = Math.max(0, Math.min(segments, Math.floor(marks)));
  // past a few dozen segments the gaps stop reading as units
  $: continuous = segments > 40;
</script>

<div class="markbar {size}" role="progressbar" aria-valuemin={0} aria-valuemax={segments} aria-valuenow={filled}>
  {#if continuous}
    <div class="track"><div class="fill" style="width: {(filled / segments) * 100}%"></div></div>
  {:else}
    {#each Array(segments) as _, i (i)}
      <span class="seg" class:on={i < filled}></span>
    {/each}
  {/if}
</div>

<style>
  .markbar { display: flex; gap: 3px; width: 100%; }
  .markbar.lg { height: 12px; }
  .markbar.md { height: 8px; gap: 2px; }
  .seg { flex: 1; min-width: 2px; background: #333333; border-radius: 999px; }
  .seg.on { background: #00e5ff; }
  .track { flex: 1; background: #333333; border-radius: 999px; overflow: hidden; }
  .fill { height: 100%; background: #00e5ff; border-radius: 999px; }
</style>
