<script lang="ts">
  import { DOT_R } from "./homeLayout";
  import { ICONS, type IconName } from "./icons";

  /** Which icon. */
  export let name: IconName;
  /** Its side, in pixels. */
  export let size = 20;
</script>

<!-- drawn in the colour of the text around it -->
<svg class="icon" viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
  {#if ICONS[name].d}<path d={ICONS[name].d} />{/if}
  {#each ICONS[name].dots as [x, y]}<circle cx={x} cy={y} r={DOT_R * 1.2} />{/each}
</svg>

<style>
  .icon {
    display: block;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
    pointer-events: none;
  }
  circle { fill: currentColor; stroke: none; }
</style>
