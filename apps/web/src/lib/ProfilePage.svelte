<script lang="ts">
  import { onMount } from "svelte";
  import { API_BASE, deleteAccount, fetchSessionInfo, fetchUser, setRecoveryEmail, type SessionInfo, type UserState } from "./api";

  export let onLogout: (everywhere: boolean) => void;

  let info: SessionInfo | null = null;
  let user: UserState | null = null;
  let loading = true;
  let error: string | null = null;
  let confirmAll = false;

  // The recovery e-mail is changed with the password, like deleting.
  let editingEmail = false;
  let emailDraft = "";
  let emailPassword = "";
  let emailBusy = false;
  let emailError: string | null = null;

  function startEmail() {
    editingEmail = true;
    emailDraft = info?.email ?? "";
    emailPassword = "";
    emailError = null;
  }

  async function saveEmail() {
    if (!emailPassword || emailBusy || !info) return;
    emailBusy = true;
    emailError = null;
    try {
      info = { ...info, email: await setRecoveryEmail(emailDraft.trim(), emailPassword) };
      editingEmail = false;
    } catch (e: any) {
      emailError = e?.message ?? "erro";
    } finally {
      emailBusy = false;
      emailPassword = "";
    }
  }

  // Deleting asks for the password again, and only then for the click.
  let deleting = false;
  let deletePassword = "";
  let deleteBusy = false;
  let deleteError: string | null = null;

  function cancelDelete() {
    deleting = false;
    deletePassword = "";
    deleteError = null;
  }

  async function confirmDelete() {
    if (!deletePassword || deleteBusy) return;
    deleteBusy = true;
    deleteError = null;
    try {
      await deleteAccount(deletePassword);
    } catch (e: any) {
      deleteError = e?.message ?? "erro";
    } finally {
      deleteBusy = false;
    }
  }

  onMount(async () => {
    try {
      const [i, u] = await Promise.all([fetchSessionInfo(), fetchUser()]);
      info = i;
      user = u;
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

    {#if user}
      <section class="card">
        <h2>jornada</h2>
        <dl class="rows">
          <dt>day</dt><dd>{user.day} <span class="muted-sub">desde o primeiro login</span></dd>
          <dt>streak</dt><dd>{user.consecutive_days} <span class="muted-sub">dias consecutivos</span></dd>
          <dt>stage</dt><dd>{user.stage} <span class="muted-sub">checkpoint em {user.days_until_next_checkpoint}d</span></dd>
        </dl>
      </section>
    {/if}

    <section class="card">
      <h2>conta</h2>
      <dl class="rows">
        <dt>user id</dt><dd>{info.user_id}</dd>
        <dt>username</dt><dd>{info.username}</dd>
        <dt>criada em</dt><dd>{info.created_at.slice(0, 10)}</dd>
        <dt>e-mail</dt>
        <dd>
          {#if !editingEmail}
            {info.email ?? "—"}
            <button class="inline" on:click={startEmail}>{info.email ? "alterar" : "adicionar"}</button>
          {/if}
        </dd>
      </dl>
      {#if editingEmail}
        <div class="email-edit">
          <p class="muted-sub">usado só para recuperar a senha; deixe vazio para remover</p>
          <input class="password" type="email" placeholder="e-mail" autocomplete="email" bind:value={emailDraft} />
          <input
            class="password"
            type="password"
            placeholder="sua senha"
            autocomplete="current-password"
            bind:value={emailPassword}
            on:keydown={(e) => e.key === "Enter" && saveEmail()}
          />
          <div class="confirm">
            <button class="save" disabled={!emailPassword || emailBusy} on:click={saveEmail}>
              {emailBusy ? "..." : "salvar"}
            </button>
            <button class="ghost" on:click={() => (editingEmail = false)}>cancelar</button>
          </div>
          {#if emailError}<p class="error">{emailError}</p>{/if}
        </div>
      {/if}
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

  <section class="card">
    <h2>excluir conta</h2>
    {#if deleting}
      <p class="warn">
        Apaga a conta e todos os dados dela — atributos, ações, registros, agenda e
        projetos — em todos os dispositivos. Não pode ser desfeito.
      </p>
      <input
        class="password"
        type="password"
        placeholder="sua senha"
        autocomplete="current-password"
        bind:value={deletePassword}
        on:keydown={(e) => e.key === "Enter" && confirmDelete()}
      />
      <div class="confirm">
        <button class="danger" disabled={!deletePassword || deleteBusy} on:click={confirmDelete}>
          {deleteBusy ? "..." : "excluir para sempre"}
        </button>
        <button class="ghost" on:click={cancelDelete}>cancelar</button>
      </div>
      {#if deleteError}<p class="error">{deleteError}</p>{/if}
    {:else}
      <button class="exit" on:click={() => (deleting = true)}>
        <span class="exit-label">excluir conta</span>
        <span class="muted-sub">apaga a conta e todos os dados</span>
      </button>
    {/if}
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
    /* fixed, so the values line up from one card to the next */
    grid-template-columns: 8rem 1fr;
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
  .danger:disabled { opacity: 0.4; cursor: not-allowed; }
  .inline {
    margin-left: 0.6rem;
    padding: 0;
    background: transparent;
    border: none;
    color: #808080;
    font: inherit;
    font-size: 0.75rem;
    text-decoration: underline;
    cursor: pointer;
  }
  .inline:hover { color: #ffffff; }
  .email-edit { margin-top: 0.9rem; }
  .email-edit .muted-sub { display: block; margin-bottom: 0.6rem; }
  .email-edit .password:focus { border-color: #ffffff; }
  .save {
    padding: 0.45rem 0.85rem;
    border: 1px solid #ffffff;
    border-radius: 4px;
    background: #000000;
    color: #ffffff;
    font: inherit;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .save:hover:not(:disabled) { background: #ffffff; color: #000000; }
  .save:disabled { opacity: 0.4; cursor: not-allowed; }
  .warn {
    margin: 0 0 0.75rem;
    color: #cccccc;
    font-size: 0.85rem;
    line-height: 1.45;
  }
  .password {
    display: block;
    width: 100%;
    max-width: 20rem;
    box-sizing: border-box;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #ffffff;
    padding: 0.55rem 0.8rem;
    font: inherit;
    font-size: 0.9rem;
    outline: none;
    margin-bottom: 0.75rem;
  }
  .password:focus { border-color: #ff4d4d; }

  @media (max-width: 768px) {
    .page { padding: 0.75rem 0.9rem; }
  }
</style>
