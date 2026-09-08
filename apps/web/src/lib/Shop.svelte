<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchUser,
    fetchActions,
    type Action,
  } from "./api";
  import { userVersion } from "./store";

  export let initialSection: string | null = null;
  void initialSection;

  let actions: Action[] = [];
  let buildPoints = 0;
  let loading = true;
  let error: string | null = null;
  let query = "";
  let lastUserVersion = 0;

  async function load() {
    error = null;
    try {
      const [userActions, user] = await Promise.all([
        fetchActions(),
        fetchUser().catch(() => null),
      ]);
      actions = userActions;
      buildPoints = user?.build_points ?? 0;
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

  $: filtered = actions.filter((a) =>
    a.name.toLowerCase().includes(query.trim().toLowerCase())
  );
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
      <ul class="actions">
        {#each filtered as a (a.id)}
          <li>
            <span class="a-name">{a.name}</span>
            <span class="owned-tag">adquirida!</span>
          </li>
        {/each}
        {#if filtered.length === 0}
          <li class="muted">nenhuma ação</li>
        {/if}
      </ul>
    </div>
  {/if}
</section>

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
  .a-name { color: #ddd; font-size: 0.88rem; flex: 1; }
  .owned-tag {
    color: #555;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.3rem 0.5rem;
  }

  .muted { color: #555; }
  .error { color: #f66; }
</style>
