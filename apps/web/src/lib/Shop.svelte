<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchShopCatalog,
    fetchUser,
    fetchActions,
    buyPackageAction,
    type CatalogGroup,
    type CatalogAction,
  } from "./api";
  import { userVersion, bumpUser } from "./store";
  import Modal from "./Modal.svelte";

  export let initialSection: string | null = null;
  void initialSection;

  let groups: CatalogGroup[] = [];
  let buildPoints = 0;
  let owned: Set<string> = new Set();
  let loading = true;
  let error: string | null = null;
  let busy: string | null = null;
  let selected: { group: CatalogGroup; action: CatalogAction } | null = null;
  let query = "";
  let openSet: Set<string> = new Set();
  let lastUserVersion = 0;

  const TYPE_LABEL: Record<number, string> = {
    0: "session", 1: "reps", 2: "seconds", 3: "minutes", 4: "hours",
    5: "letters", 6: "lines", 7: "words", 8: "group",
  };

  async function load() {
    try {
      const [cat, user, userActions] = await Promise.all([
        fetchShopCatalog(),
        fetchUser().catch(() => null),
        fetchActions().catch(() => []),
      ]);
      groups = cat;
      buildPoints = user?.build_points ?? 0;
      owned = new Set(userActions.map((a) => a.name.toUpperCase()));
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(load);

  $: if ($userVersion !== lastUserVersion) {
    lastUserVersion = $userVersion;
    if (lastUserVersion > 0) load();
  }

  function toggle(key: string) {
    const next = new Set(openSet);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    openSet = next;
  }

  $: q = query.trim().toLowerCase();
  $: filteredView = groups.map((g) => {
    const matches = q
      ? g.actions.filter((a) => a.name.toLowerCase().includes(q))
      : g.actions;
    return { group: g, actions: matches };
  });
  $: if (q) {
    const next = new Set<string>();
    for (const v of filteredView) if (v.actions.length > 0) next.add(v.group.key);
    openSet = next;
  }

  async function buy(group: CatalogGroup, action: CatalogAction) {
    if (busy) return;
    busy = `${group.key}:${action.name}`;
    error = null;
    try {
      const res = await buyPackageAction(action.package_attribute, action.name);
      buildPoints = res.build_points;
      owned = new Set([...owned, action.name.toUpperCase()]);
      bumpUser();
      if (selected?.action.name === action.name) selected = null;
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      busy = null;
    }
  }
</script>

<section class="page">
  <header class="topbar">
    <span class="title">shop</span>
    <div class="bp-badge">
      <span class="bp-label">build points</span>
      <span class="bp-value">{buildPoints}</span>
    </div>
  </header>

  <div class="search-row">
    <input type="text" placeholder="Buscar ação..." bind:value={query} />
  </div>

  {#if loading}
    <p class="muted">…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else}
    <div class="list">
      {#each filteredView as v (v.group.key)}
        {#if !q || v.actions.length > 0}
          {@const open = openSet.has(v.group.key)}
          <button class="pkg-head" on:click={() => toggle(v.group.key)}>
            <span class="caret">{open ? "▾" : "▸"}</span>
            <span class="pkg-name">{v.group.name}</span>
            <span class="pkg-count">{v.actions.length}</span>
          </button>
          {#if open}
            <ul class="actions">
              {#each v.actions as a (a.name)}
                {@const acquired = owned.has(a.name.toUpperCase())}
                <li class:owned={acquired}>
                  <button class="info" on:click={() => (selected = { group: v.group, action: a })}>
                    <span class="a-name">{a.name}</span>
                    <span class="a-meta">
                      {TYPE_LABEL[a.type] ?? a.type} · d{a.diff}{a.token_cost ? ` · ${a.token_cost}t` : ""}
                    </span>
                  </button>
                  {#if acquired}
                    <span class="owned-tag">owned</span>
                  {:else}
                    <button
                      class="buy"
                      on:click|stopPropagation={() => buy(v.group, a)}
                      disabled={busy === `${v.group.key}:${a.name}` || buildPoints < a.cost}
                    >
                      {busy === `${v.group.key}:${a.name}` ? "..." : `${a.cost} bp`}
                    </button>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        {/if}
      {/each}
    </div>
  {/if}
</section>

{#if selected}
  {@const selectedAcquired = owned.has(selected.action.name.toUpperCase())}
  <Modal title={selectedAcquired ? "ação" : "comprar ação"} onClose={() => (selected = null)}>
    <dl class="details">
      <dt>nome</dt><dd class="hl">{selected.action.name}</dd>
      <dt>zona</dt><dd>{selected.group.name}</dd>
      <dt>tipo</dt><dd>{TYPE_LABEL[selected.action.type] ?? selected.action.type}</dd>
      <dt>dificuldade</dt><dd>d{selected.action.diff}</dd>
      {#if !selectedAcquired}
        <dt>custo (bp)</dt><dd>{selected.action.cost}</dd>
      {/if}
      {#if selected.action.token_cost && selected.action.token_cost > 0}
        <dt>custo por uso</dt><dd>{selected.action.token_cost} tokens</dd>
      {/if}
      {#if !selectedAcquired}
        <dt>saldo (bp)</dt><dd>{buildPoints}</dd>
      {:else}
        <dt>status</dt><dd class="hl">owned</dd>
      {/if}
    </dl>
    {#if selected.action.leaves && selected.action.leaves.length > 0}
      <div class="leaves-block">
        <div class="leaves-title">estimula</div>
        <ul class="leaves">
          {#each selected.action.leaves as l}
            <li><span class="leaf-name">{l.name}</span><span class="leaf-weight">{Math.round(l.weight * 100)}%</span></li>
          {/each}
        </ul>
      </div>
    {/if}
    <div class="confirm-row">
      <button class="ghost" on:click={() => (selected = null)}>fechar</button>
      {#if !selectedAcquired}
        <button
          class="primary"
          on:click={() => buy(selected!.group, selected!.action)}
          disabled={busy !== null || buildPoints < selected.action.cost}
        >
          {busy ? "..." : "confirmar compra"}
        </button>
      {/if}
    </div>
  </Modal>
{/if}

<style>
  .page {
    height: 100%;
    box-sizing: border-box;
    padding: 1.5rem 2rem;
    color: #e5e5e5;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .topbar {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .title {
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 1.05rem;
  }
  .bp-badge {
    margin-left: auto;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    background: #0a1418;
    border: 1px solid #1d3340;
    padding: 0.4rem 0.85rem;
    border-radius: 4px;
  }
  .bp-label {
    color: #555;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .bp-value { color: #6cf; font-weight: bold; font-size: 1rem; }
  .search-row { margin-bottom: 0.75rem; }
  .search-row input {
    width: 100%;
    box-sizing: border-box;
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    color: #ddd;
    padding: 0.55rem 0.75rem;
    font: inherit;
    font-size: 0.9rem;
    outline: none;
  }
  .search-row input:focus { border-color: #6cf; }

  .list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .pkg-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    width: 100%;
    padding: 0.5rem 0.95rem;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
    text-align: left;
  }
  .pkg-head:hover { background: #141414; }
  .caret {
    color: #555;
    font-size: 0.75rem;
    width: 1em;
  }
  .pkg-name {
    color: #ddd;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.88rem;
    flex: 1;
  }
  .pkg-count {
    color: #555;
    font-size: 0.78rem;
  }
  .actions {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .actions li {
    display: flex;
    align-items: center;
    padding: 0.45rem 0.95rem 0.45rem 2.1rem;
  }
  .actions li.owned { opacity: 0.4; }
  .info {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.15rem;
    flex: 1;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    padding: 0.2rem 0;
  }
  .info:hover .a-name { color: #6cf; }
  .info:disabled { cursor: default; }
  .a-name { color: #ddd; font-size: 0.88rem; }
  .a-meta { color: #555; font-size: 0.7rem; }
  .buy {
    background: transparent;
    border: 1px solid #2a2a2a;
    color: #888;
    padding: 0.32rem 0.65rem;
    border-radius: 4px;
    font: inherit;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
    min-width: 60px;
  }
  .buy:hover:not(:disabled) {
    border-color: #6cf;
    color: #6cf;
  }
  .buy:disabled { opacity: 0.4; cursor: not-allowed; }
  .owned-tag {
    color: #555;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.3rem 0.5rem;
  }

  .muted { color: #555; }
  .error { color: #f66; }

  .details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.5rem 1rem;
    margin: 0 0 1.25rem;
  }
  .details dt {
    color: #555;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
  }
  .details dd { color: #ddd; margin: 0; font-size: 0.9rem; }
  .hl { color: #6cf; }
  .leaves-block {
    margin: 0 0 1.25rem;
    padding: 0.6rem 0.75rem;
    background: #0a0a0a;
    border: 1px solid #1a1a1a;
    border-radius: 4px;
  }
  .leaves-title {
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.65rem;
    margin-bottom: 0.4rem;
  }
  .leaves {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .leaves li {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
  }
  .leaf-name { color: #bbb; }
  .leaf-weight { color: #6cf; font-variant-numeric: tabular-nums; }
  .confirm-row { display: flex; gap: 0.5rem; justify-content: flex-end; }
  .ghost, .primary {
    padding: 0.5rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .ghost { background: transparent; color: #888; border-color: #333; }
  .ghost:hover { color: #ccc; border-color: #555; }
  .primary { background: #6cf; color: #0a0a0a; border-color: #6cf; }
  .primary:hover:not(:disabled) { background: #4ad; }
  .primary:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
