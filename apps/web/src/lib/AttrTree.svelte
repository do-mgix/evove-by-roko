<script lang="ts">
  import { formatCode, userAttrAsNode, type AttrNode } from "./api";

  /** One attribute and, on demand, everything under it. Renders itself for
   *  children, so depth is whatever the graph has. */
  export let node: AttrNode;
  export let maxPower = 1;

  let open = false;

  $: patches = node.patches ?? [];
  $: hasKids = !!node.children?.length || patches.length > 0;
  $: leveled = node.level != null && node.max_level != null;
  $: fill = leveled
    ? (node.progress_to_next ?? 0) * 100
    : Math.max(0, Math.min(100, (node.power / maxPower) * 100));
  // A link that is not the node's primary parent: the node lives elsewhere and
  // is shown here because this attribute draws on it (Força → Peitoral).
  $: borrowed = node.primary === false;
</script>

<li class="node" class:borrowed class:custom={node.custom}>
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
      {#each patches as p (p.id)}
        <!-- where the base action would sit: the patch and the attributes it trains.
             Display only; none of it enters this node's power. -->
        <li class="patch">
          <div class="patch-head">
            <span class="caret">↳</span>
            <span class="pname">{p.name}</span>
            <span class="pid">{formatCode(p.id)}</span>
          </div>
          <ul class="kids">
            {#each p.attributes as a (a.id)}
              <svelte:self node={userAttrAsNode(a)} {maxPower} />
            {/each}
          </ul>
        </li>
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
  .row:not(.leaf):hover .name { color: #00e5ff; }
  .caret { color: #808080; width: 1em; font-size: 0.75rem; flex: 0 0 auto; }
  .name { color: #ffffff; font-size: 0.85rem; flex: 1; min-width: 0; }
  .ref { color: #808080; margin-left: 0.3rem; font-size: 0.75rem; }
  .weight { color: #808080; font-size: 0.7rem; font-variant-numeric: tabular-nums; }
  .meta { color: #808080; font-size: 0.75rem; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .bar {
    height: 2px;
    background: #333333;
    margin: 0 0 0.25rem 1.5em;
    border-radius: 1px;
    overflow: hidden;
  }
  .fill { height: 100%; background: #00e5ff; }
  .borrowed .name { color: #808080; font-style: italic; }
  .borrowed .fill { background: #000000; }
  .sub { color: #808080; font-size: 0.65rem; margin: -0.15rem 0 0.3rem 1.5em; }
  .kids {
    margin: 0 0 0.25rem 0.5rem;
    padding-left: 0.75rem;
    border-left: 1px solid #333333;
  }
  .patch { list-style: none; margin: 0.15rem 0; }
  .patch-head { display: flex; align-items: baseline; gap: 0.5rem; padding: 0.3rem 0; }
  .pname { flex: 1; min-width: 0; color: #00e5ff; font-size: 0.85rem; text-transform: lowercase; }
  .pid { color: #808080; font-size: 0.7rem; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .patch > .kids { border-left: 1px dashed #00e5ff; }
  .custom > .row .name { color: #00e5ff; }
</style>
