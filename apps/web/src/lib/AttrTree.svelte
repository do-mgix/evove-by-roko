<script lang="ts">
  import type { AttrNode } from "./api";

  /** One attribute and, on demand, everything under it. Renders itself for
   *  children, so depth is whatever the graph has. */
  export let node: AttrNode;
  export let maxPower = 1;

  let open = false;

  $: hasKids = !!node.children?.length;
  $: leveled = node.level != null && node.max_level != null;
  $: fill = leveled
    ? (node.progress_to_next ?? 0) * 100
    : Math.max(0, Math.min(100, (node.power / maxPower) * 100));
  // A link that is not the node's primary parent: the node lives elsewhere and
  // is shown here because this attribute draws on it (Força → Peitoral).
  $: borrowed = node.primary === false;
</script>

<li class="node" class:borrowed>
  <button class="row" on:click={() => hasKids && (open = !open)} class:leaf={!hasKids} aria-expanded={hasKids ? open : undefined}>
    <span class="caret">{hasKids ? (open ? "▾" : "▸") : "·"}</span>
    <span class="name">{node.name}{#if borrowed}<span class="ref" title="ligação não primária">↗</span>{/if}</span>
    {#if node.weight != null}<span class="weight">{Math.round(node.weight * 100)}%</span>{/if}
    <span class="meta">
      {#if leveled}
        lvl {node.is_leaf ? node.permanent_level : node.level?.toFixed(1)}/{node.max_level}
      {:else}
        {Math.round(node.power).toLocaleString()}
      {/if}
    </span>
  </button>
  <div class="bar"><div class="fill" style="width: {fill}%"></div></div>
  {#if node.is_leaf && node.half_life_hours}
    <div class="sub">meia-vida {(node.half_life_hours / 24).toFixed(0)}d · grau {node.degree}</div>
  {/if}
  {#if open && hasKids}
    <ul class="kids">
      {#each node.children ?? [] as child (child.key)}
        <svelte:self node={child} {maxPower} />
      {/each}
    </ul>
  {/if}
</li>

<style>
  .node { list-style: none; }
  .row {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    width: 100%;
    padding: 0.3rem 0;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .row.leaf { cursor: default; }
  .row:not(.leaf):hover .name { color: #6cf; }
  .caret { color: #555; width: 1em; font-size: 0.75rem; flex: 0 0 auto; }
  .name { color: #ddd; font-size: 0.85rem; flex: 1; min-width: 0; }
  .ref { color: #666; margin-left: 0.3rem; font-size: 0.75rem; }
  .weight { color: #555; font-size: 0.7rem; font-variant-numeric: tabular-nums; }
  .meta { color: #888; font-size: 0.75rem; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .bar {
    height: 2px;
    background: #1a1a1a;
    margin: 0 0 0.25rem 1.5em;
    border-radius: 1px;
    overflow: hidden;
  }
  .fill { height: 100%; background: #6cf; }
  .borrowed .name { color: #999; font-style: italic; }
  .borrowed .fill { background: #357; }
  .sub { color: #444; font-size: 0.65rem; margin: -0.15rem 0 0.3rem 1.5em; }
  .kids {
    margin: 0 0 0.25rem 0.5rem;
    padding-left: 0.75rem;
    border-left: 1px solid #1f1f1f;
  }
</style>
