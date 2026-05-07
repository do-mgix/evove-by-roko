<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchPackages,
    fetchUser,
    fetchActions,
    buyPackageAction,
    type Package,
    type PackageAction,
  } from "./api";
  import { userVersion, bumpUser } from "./store";
  import Modal from "./Modal.svelte";

  export let initialSection: string | null = null;
  void initialSection;

  let packages: Package[] = [];
  let buildPoints = 0;
  let owned: Set<string> = new Set();
  let loading = true;
  let error: string | null = null;
  let busy: string | null = null;
  let selected: { pkg: Package; action: PackageAction } | null = null;
  let query = "";
  let openSet: Set<string> = new Set();
  let lastUserVersion = 0;

  const TYPE_LABEL: Record<number, string> = {
    0: "session", 1: "reps", 2: "seconds", 3: "minutes", 4: "hours",
    5: "letters", 6: "lines", 7: "words", 8: "group",
  };

  async function load() {
    try {
      const [pkgs, user, userActions] = await Promise.all([
        fetchPackages(),
        fetchUser().catch(() => null),
        fetchActions().catch(() => []),
      ]);
      packages = pkgs;
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

  function toggle(attr: string) {
    const next = new Set(openSet);
    if (next.has(attr)) next.delete(attr);
    else next.add(attr);
    openSet = next;
  }

  $: q = query.trim().toLowerCase();
  $: filteredView = packages.map((p) => {
    const matches = q
      ? p.actions.filter((a) => a.name.toLowerCase().includes(q))
      : p.actions;
    return { pkg: p, actions: matches };
  });
  $: if (q) {
    // expand all packages with matching items when searching
    const next = new Set<string>();
    for (const v of filteredView) if (v.actions.length > 0) next.add(v.pkg.attribute);
    openSet = next;
  }

  async function buy(pkg: Package, action: PackageAction) {
    if (busy) return;
    busy = `${pkg.attribute}:${action.name}`;
    error = null;
    try {
      const res = await buyPackageAction(pkg.attribute, action.name);
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
      {#each filteredView as v (v.pkg.attribute)}
        {#if !q || v.actions.length > 0}
          <div class="package" style="--accent: {v.pkg.color ?? '#6cf'};">
            <button class="pkg-head" on:click={() => toggle(v.pkg.attribute)}>
              <span class="caret">{openSet.has(v.pkg.attribute) ? "▾" : "▸"}</span>
              <span class="pkg-name">{v.pkg.attribute}</span>
              <span class="pkg-count">{v.actions.length}</span>
            </button>
            {#if openSet.has(v.pkg.attribute)}
              <ul class="actions">
                {#each v.actions as a (a.name)}
                  {@const acquired = owned.has(a.name.toUpperCase())}
                  <li class:owned={acquired}>
                    <button class="info" on:click={() => (selected = { pkg: v.pkg, action: a })} disabled={acquired}>
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
                        on:click|stopPropagation={() => buy(v.pkg, a)}
                        disabled={busy === `${v.pkg.attribute}:${a.name}` || buildPoints < a.cost}
                      >
                        {busy === `${v.pkg.attribute}:${a.name}` ? "..." : `${a.cost} bp`}
                      </button>
                    {/if}
                  </li>
                {/each}
              </ul>
            {/if}
          </div>
        {/if}
      {/each}
    </div>
  {/if}
</section>

{#if selected}
  <Modal title="comprar ação" onClose={() => (selected = null)}>
    <dl class="details">
      <dt>nome</dt><dd class="hl">{selected.action.name}</dd>
      <dt>atributo</dt><dd>{selected.pkg.attribute}</dd>
      <dt>tipo</dt><dd>{TYPE_LABEL[selected.action.type] ?? selected.action.type}</dd>
      <dt>dificuldade</dt><dd>d{selected.action.diff}</dd>
      <dt>custo (bp)</dt><dd>{selected.action.cost}</dd>
      {#if selected.action.token_cost && selected.action.token_cost > 0}
        <dt>custo por uso</dt><dd>{selected.action.token_cost} tokens</dd>
      {/if}
      <dt>saldo (bp)</dt><dd>{buildPoints}</dd>
    </dl>
    <div class="confirm-row">
      <button class="ghost" on:click={() => (selected = null)}>cancelar</button>
      <button
        class="primary"
        on:click={() => buy(selected!.pkg, selected!.action)}
        disabled={busy !== null || buildPoints < selected.action.cost}
      >
        {busy ? "..." : "confirmar compra"}
      </button>
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
    gap: 0.5rem;
  }
  .package {
    background: #0d0d0d;
    border: 1px solid color-mix(in srgb, var(--accent) 20%, #1f1f1f);
    border-radius: 6px;
    overflow: hidden;
  }
  .pkg-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    width: 100%;
    padding: 0.7rem 0.95rem;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
    text-align: left;
  }
  .pkg-head:hover { background: color-mix(in srgb, var(--accent) 6%, transparent); }
  .caret {
    color: #555;
    font-size: 0.75rem;
    width: 1em;
  }
  .pkg-name {
    color: var(--accent);
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
    border-top: 1px solid color-mix(in srgb, var(--accent) 18%, #1a1a1a);
  }
  .actions li {
    display: flex;
    align-items: center;
    padding: 0.45rem 0.95rem;
    border-bottom: 1px solid #161616;
  }
  .actions li:last-child { border-bottom: none; }
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
  .info:hover .a-name { color: var(--accent); }
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
    border-color: var(--accent);
    color: var(--accent);
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
