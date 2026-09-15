<script lang="ts">
  import { onMount } from "svelte";
  import { API_BASE, fetchSessionInfo, type SessionInfo } from "./api";

  export let onLogout: (everywhere: boolean) => void;

  let info: SessionInfo | null = null;
  let loading = true;
  let error: string | null = null;
  let confirmAll = false;

  onMount(async () => {
    try {
      info = await fetchSessionInfo();
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  });

  // Timestamps come back without a zone: print them as the server wrote them
  // instead of letting the browser guess one.
  const stamp = (iso: string) => iso.slice(0, 16).replace("T", " ");
</script>

<section class="page">
  {#if loading}
    <p class="muted">carregando...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if info}
    <header class="head">
      <h1>{info.username}</h1>
      <span class="muted">profile</span>
    </header>

    <section class="card">
      <h2>conta</h2>
      <dl class="rows">
        <dt>user id</dt><dd>{info.user_id}</dd>
        <dt>username</dt><dd>{info.username}</dd>
        <dt>criada em</dt><dd>{info.created_at.slice(0, 10)}</dd>
      </dl>
    </section>

    <section class="card">
      <h2>sessão</h2>
      <dl class="rows">
        <dt>iniciada</dt><dd>{stamp(info.session.created_at)}</dd>
        <dt>expira</dt><dd>{stamp(info.session.expires_at)}</dd>
        <dt>sessões ativas</dt><dd>{info.active_sessions}</dd>
        <dt>api</dt><dd>{API_BASE}</dd>
      </dl>
    </section>
  {/if}

  <!-- Outside the load: signing out must work even when the details fail. -->
  <section class="card">
    <h2>log out</h2>
    <div class="exits">
      <button class="exit" on:click={() => onLogout(false)}>
        <span class="exit-label">log out</span>
        <span class="muted-sub">encerra só esta sessão</span>
      </button>
      {#if confirmAll}
        <div class="confirm">
          <span>encerrar todas as sessões, inclusive esta?</span>
          <button class="danger" on:click={() => onLogout(true)}>encerrar</button>
          <button class="ghost" on:click={() => (confirmAll = false)}>cancelar</button>
        </div>
      {:else}
        <button class="exit" on:click={() => (confirmAll = true)}>
          <span class="exit-label">log out everywhere</span>
          <span class="muted-sub">encerra a sessão em todos os dispositivos</span>
        </button>
      {/if}
    </div>
  </section>
</section>

<style>
  .page {
    padding: 1.75rem 2rem;
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
    height: 100%;
    overflow-y: auto;
    box-sizing: border-box;
  }
  .head {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }
  h1 {
    margin: 0;
    color: #ffffff;
    font-size: 1.4rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  h2 {
    margin: 0 0 0.75rem;
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
  }
  .muted { color: #808080; font-size: 0.78rem; }
  .muted-sub { color: #808080; font-size: 0.7rem; }
  .error { color: #ff4d4d; }

  .card {
    background: #000000;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0.95rem 1.1rem;
    margin-bottom: 1rem;
    max-width: 36rem;
  }
  .rows {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.45rem 1.5rem;
    margin: 0;
  }
  dt {
    align-self: center;
    color: #808080;
    text-transform: uppercase;
    font-size: 0.65rem;
    letter-spacing: 0.08em;
  }
  dd {
    margin: 0;
    color: #ffffff;
    font-size: 0.9rem;
    overflow-wrap: anywhere;
  }

  .exits {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }
  .exit {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.2rem;
    padding: 0.6rem 0.85rem;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #ffffff;
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .exit:hover { border-color: #ff4d4d; }
  .exit:hover .exit-label { color: #ff4d4d; }
  .exit-label {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .confirm {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.6rem;
    font-size: 0.85rem;
  }
  .danger,
  .ghost {
    padding: 0.45rem 0.85rem;
    border-radius: 4px;
    font: inherit;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .danger {
    border: 1px solid #ff4d4d;
    background: #ff4d4d;
    color: #000000;
  }
  .ghost {
    border: 1px solid #333333;
    background: #000000;
    color: #808080;
  }
  .ghost:hover { color: #cccccc; }

  @media (max-width: 768px) {
    .page { padding: 0.75rem 0.9rem; }
  }
</style>
