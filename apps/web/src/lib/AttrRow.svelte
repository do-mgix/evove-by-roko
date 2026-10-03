<script lang="ts">
  import type { AttrNode } from "./api";
  import MarkBar from "./MarkBar.svelte";

  /** One attribute: its name, rank and the marks toward the next rank. */
  export let node: AttrNode;
  /** A muted line under the bar. */
  export let note: string | null = null;
  /** Makes the row a button. */
  export let onOpen: (() => void) | null = null;
  /** With a reward waiting (`node.claim`), a tap takes it instead of opening. */
  export let onClaim: (() => void) | null = null;

  $: claimable = !!(node.claim && onClaim);
  $: tap = claimable ? onClaim : onOpen;
  $: gain = node.claim
    ? [`+${node.claim.tokens}t`, `+${node.claim.skill_points} skill`].join(" · ")
    : "";
</script>

{#snippet body()}
  <span class="row">
    <span class="name">{node.name}</span>
    {#if node.weight != null}<span class="weight">{Math.round(node.weight * 100)}%</span>{/if}
    <span class="rank">{node.rank}</span>
  </span>
  <MarkBar marks={node.max ? node.need : node.marks} need={node.need} size="md" tone="gold" label={node.max ? "máx" : null} />
  {#if note}<span class="note">{note}</span>{/if}
{/snippet}

<li class="attr" class:custom={node.custom} class:claimable>
  {#if claimable}<span class="gain">{gain}</span>{/if}
  {#if tap}
    <button type="button" class="hit" on:click={tap} title={claimable ? "tocar para receber" : undefined}>{@render body()}</button>
  {:else}
    {@render body()}
  {/if}
</li>

<style>
  .attr {
    list-style: none;
    min-width: 0;
    padding: 0.3rem 0 0.5rem;
  }
  .attr.claimable {
    position: relative;
    margin-top: 0.9rem;
    padding: 0.4rem 0.55rem 0.5rem;
    border: 1px solid #e8c547;
    border-radius: 6px;
  }
  .gain {
    position: absolute;
    top: -0.8rem;
    right: 0.5rem;
    padding: 0 0.35rem;
    background: #000000;
    color: #e8c547;
    font-size: 0.7rem;
    font-variant-numeric: tabular-nums;
  }
  .hit {
    display: block;
    width: 100%;
    padding: 0;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .hit:hover .name { color: #00e5ff; }
  .row {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
  }
  .name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #ffffff;
    font-size: 0.85rem;
  }
  .custom .name { color: #00e5ff; }
  .weight { color: #808080; font-size: 0.7rem; font-variant-numeric: tabular-nums; }
  .rank { color: #00e5ff; font-weight: bold; font-size: 0.8rem; }
  .note {
    display: block;
    margin-top: 0.3rem;
    color: #808080;
    font-size: 0.68rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
