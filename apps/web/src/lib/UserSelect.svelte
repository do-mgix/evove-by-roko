<script lang="ts">
  import { onMount } from "svelte";
  import { fetchUsers, createUser, setUsername } from "./api";

  export let onSelected: (name: string) => void;

  let users: string[] = [];
  let loading = true;
  let error: string | null = null;

  let mode: "list" | "create" = "list";
  let newName = "";
  let creating = false;

  onMount(async () => {
    try {
      users = await fetchUsers();
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  });

  function pick(name: string) {
    setUsername(name);
    onSelected(name);
  }

  async function confirmCreate() {
    if (!newName.trim() || creating) return;
    creating = true;
    error = null;
    try {
      const res = await createUser(newName.trim());
      pick(res.name);
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      creating = false;
    }
  }
</script>

<section class="page">
  <div class="card">
    <h1>roko</h1>

    {#if loading}
      <p class="muted">…</p>
    {:else if mode === "list"}
      <div class="list-section">
        <p class="hint">selecione um usuário</p>
        <ul class="users">
          {#each users as u (u)}
            <li>
              <button class="user-btn" on:click={() => pick(u)}>{u}</button>
            </li>
          {/each}
          {#if users.length === 0}
            <li class="muted">nenhum usuário</li>
          {/if}
        </ul>
        <button class="primary" on:click={() => { mode = "create"; newName = ""; error = null; }}>
          + criar novo
        </button>
      </div>
    {:else}
      <div class="create-section">
        <p class="hint">novo usuário</p>
        <input
          type="text"
          placeholder="nome"
          bind:value={newName}
          on:keydown={(e) => e.key === "Enter" && confirmCreate()}
          maxlength="24"
        />
        <div class="actions">
          <button class="ghost" on:click={() => { mode = "list"; error = null; }}>cancelar</button>
          <button class="primary" on:click={confirmCreate} disabled={!newName.trim() || creating}>
            {creating ? "..." : "confirmar"}
          </button>
        </div>
      </div>
    {/if}

    {#if error}
      <p class="error">{error}</p>
    {/if}
  </div>
</section>

<style>
  .page {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    color: #e5e5e5;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .card {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 8px;
    padding: 2rem 2.5rem;
    width: 320px;
  }
  h1 {
    margin: 0 0 1.5rem;
    color: #6cf;
    font-size: 1.5rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    text-align: center;
  }
  .hint {
    color: #555;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 0 0 0.75rem;
  }
  .users {
    list-style: none;
    padding: 0;
    margin: 0 0 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .user-btn {
    width: 100%;
    text-align: left;
    background: #111;
    border: 1px solid #222;
    border-radius: 4px;
    color: #e5e5e5;
    padding: 0.6rem 0.85rem;
    font: inherit;
    font-size: 0.9rem;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
  }
  .user-btn:hover {
    border-color: #6cf;
    color: #6cf;
  }
  input {
    width: 100%;
    box-sizing: border-box;
    background: #111;
    border: 1px solid #333;
    border-radius: 4px;
    color: #e5e5e5;
    padding: 0.6rem 0.85rem;
    font: inherit;
    font-size: 0.95rem;
    outline: none;
    margin-bottom: 1rem;
  }
  input:focus {
    border-color: #6cf;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
  }
  .primary,
  .ghost {
    padding: 0.55rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.15s;
  }
  .primary {
    background: #6cf;
    color: #0a0a0a;
    border-color: #6cf;
    flex: 1;
  }
  .primary:hover:not(:disabled) {
    background: #4ad;
  }
  .primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .ghost {
    background: transparent;
    color: #888;
    border-color: #333;
  }
  .ghost:hover {
    color: #ccc;
    border-color: #555;
  }
  .muted {
    color: #555;
    font-size: 0.85rem;
  }
  .error {
    color: #f66;
    font-size: 0.8rem;
    margin-top: 0.75rem;
  }
</style>
