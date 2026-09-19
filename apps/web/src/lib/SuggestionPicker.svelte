<script lang="ts">
  import { fetchAttributeSuggestions, fold, sameName } from "./api";
  import type { SuggestionCatalog, SuggestionNode } from "./api";

  /** Names the profile already has, so a suggestion can say it will be reused. */
  export let existing: string[] = [];
  /** Called with the picked node's whole path, root first. */
  export let onPick: (path: string[]) => void;

  const MAX_RESULTS = 30;

  let catalogs: SuggestionCatalog[] = [];
  let active = 0;
  let query = "";
  /** Where the drill-down is, when there is no query. */
  let openKey: string | null = null;
  let error: string | null = null;

  fetchAttributeSuggestions()
    .then((c) => (catalogs = c))
    .catch((e) => (error = e?.message ?? "erro"));

  $: catalog = catalogs[active];
  $: byKey = new Map((catalog?.nodes ?? []).map((n) => [n.key, n]));

  function pathOf(n: SuggestionNode): SuggestionNode[] {
    const out: SuggestionNode[] = [];
    let cur: SuggestionNode | undefined = n;
    while (cur) {
      out.unshift(cur);
      cur = cur.parent ? byKey.get(cur.parent) : undefined;
    }
    return out;
  }

  // no query: one level at a time, so nothing ever renders the whole catalog.
  // with a query: the matches, capped.
  $: q = fold(query.trim());
  $: matches = !catalog
    ? []
    : q
      ? catalog.nodes.filter((n) => fold(n.label).includes(q) || fold(n.source_label).includes(q))
      : catalog.nodes.filter((n) => n.parent === openKey);
  $: shown = matches.slice(0, MAX_RESULTS);
  $: hidden = matches.length - shown.length;
  $: trail = openKey && byKey.has(openKey) ? pathOf(byKey.get(openKey)!) : [];

  function hasChildren(n: SuggestionNode): boolean {
    return (catalog?.nodes ?? []).some((c) => c.parent === n.key);
  }

  function owned(label: string): boolean {
    return existing.some((e) => sameName(e, label));
  }

  function choose(n: SuggestionNode) {
    onPick(pathOf(n).map((p) => p.label));
  }

  function switchCatalog(i: number) {
    active = i;
    openKey = null;
    query = "";
  }
</script>

<div class="picker">
  {#if error}
    <p class="muted small">catálogo indisponível — use o campo de texto</p>
  {:else if !catalogs.length}
    <p class="muted small">carregando…</p>
  {:else}
    <div class="tabs">
      {#each catalogs as c, i (c.key)}
        <button type="button" class="tab" class:on={i === active} on:click={() => switchCatalog(i)}>
          {c.name}
        </button>
      {/each}
    </div>

    <input
      class="field"
      type="text"
      placeholder="buscar — física, gestão, escrita…"
      bind:value={query}
    />

    {#if !q && trail.length}
      <div class="trail">
        <button type="button" class="crumb" on:click={() => (openKey = null)}>tudo</button>
        {#each trail as t (t.key)}
          <span class="sep">›</span>
          <button type="button" class="crumb" on:click={() => (openKey = t.key)}>{t.label}</button>
        {/each}
      </div>
    {/if}

    <ul class="results">
      {#each shown as n (n.key)}
        {@const path = pathOf(n)}
        <li>
          <button type="button" class="hit" on:click={() => choose(n)} title={n.source_label}>
            <span class="label">{n.label}</span>
            {#if q && path.length > 1}
              <span class="where">{path.slice(0, -1).map((p) => p.label).join(" › ")}</span>
            {/if}
            {#if owned(n.label)}<span class="tag">já existe</span>{/if}
          </button>
          {#if !q && hasChildren(n)}
            <button type="button" class="into" on:click={() => (openKey = n.key)} title="abrir">›</button>
          {/if}
        </li>
      {/each}
      {#if !shown.length}
        <li class="muted small empty">nada com esse nome — use o campo de texto</li>
      {/if}
    </ul>
    {#if hidden > 0}<p class="muted small">+{hidden} — refine a busca</p>{/if}
    <p class="muted small source">{catalog.source}</p>
  {/if}
</div>

<style>
  .picker {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .tabs {
    display: flex;
    gap: 0.3rem;
  }
  .tab {
    flex: 1;
    padding: 0.3rem 0.5rem;
    background: transparent;
    border: 1px solid #2a2a2a;
    color: #888;
    font: inherit;
    font-size: 0.75rem;
    cursor: pointer;
  }
  .tab.on {
    border-color: #00e5ff;
    color: #00e5ff;
  }
  .trail {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.72rem;
  }
  .crumb {
    background: none;
    border: 0;
    padding: 0;
    color: #888;
    font: inherit;
    cursor: pointer;
  }
  .crumb:hover {
    color: #00e5ff;
  }
  .sep {
    color: #444;
  }
  .results {
    list-style: none;
    margin: 0;
    padding: 0;
    max-height: 13rem;
    overflow-y: auto;
    border: 1px solid #1e1e1e;
  }
  .results li {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid #1a1a1a;
  }
  .results li:last-child {
    border-bottom: 0;
  }
  .hit {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    min-width: 0;
    padding: 0.35rem 0.5rem;
    background: none;
    border: 0;
    color: #ddd;
    font: inherit;
    font-size: 0.8rem;
    text-align: left;
    cursor: pointer;
  }
  .hit:hover {
    background: #141414;
    color: #00e5ff;
  }
  .label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .where {
    flex: 1;
    min-width: 0;
    color: #666;
    font-size: 0.7rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tag {
    flex: none;
    color: #7a7a2a;
    font-size: 0.65rem;
  }
  .into {
    flex: none;
    width: 1.6rem;
    background: none;
    border: 0;
    border-left: 1px solid #1a1a1a;
    color: #555;
    font: inherit;
    cursor: pointer;
  }
  .into:hover {
    color: #00e5ff;
  }
  .empty,
  .source {
    padding: 0.35rem 0.5rem;
  }
  .muted {
    color: #666;
  }
  .small {
    font-size: 0.72rem;
  }
</style>
