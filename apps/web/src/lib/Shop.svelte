<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchUser,
    fetchActions,
    type Action,
  } from "./api";
  import { userVersion, bumpUser } from "./store";
  import Modal from "./Modal.svelte";

  export let initialSection: string | null = null;
  void initialSection;

  let actions: Action[] = [];
  let buildPoints = 0;
  let loading = true;
  let error: string | null = null;
  let busy: string | null = null;
  let selected: { action: Action } | null = null;
  let query = "";
  let openSet: Set<string> = new Set();
  let lastUserVersion = 0;

  async function load() {
    try {
      const [userActions, user] = await Promise.all([
          fetchActions().catch(() => []),
          fetchUser().catch(() => []),
      ]);
          actions = userActions;
          buildPoints = user.build_points;
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(load);
    
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
  <div class="list">
    <ul class="actions">
      {#each filtered as a}
        <li>
          <span class="a-name">{a.name}</span>
          <span class="owned-tag">adquirida!</span>
        </li>
      {/each}
    </ul>
  </div>
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
