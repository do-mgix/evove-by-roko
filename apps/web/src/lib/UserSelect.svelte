<script lang="ts">
  import { login, register } from "./api";

  export let onSelected: (name: string) => void;

  let mode: "login" | "register" = "login";
  let username = "";
  let password = "";
  let confirmPassword = "";
  let busy = false;
  let error: string | null = null;

  $: canSubmit =
    username.trim().length > 0 &&
    password.length >= 8 &&
    (mode === "login" || password === confirmPassword);

  function switchMode(next: "login" | "register") {
    mode = next;
    error = null;
    password = "";
    confirmPassword = "";
  }

  async function submit() {
    if (!canSubmit || busy) return;
    busy = true;
    error = null;
    try {
      const fn = mode === "login" ? login : register;
      const session = await fn(username.trim(), password);
      password = "";
      confirmPassword = "";
      onSelected(session.username);
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      busy = false;
    }
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "Enter") submit();
  }
</script>

<section class="page">
  <div class="card">
    <h1>roko</h1>

    <p class="hint">{mode === "login" ? "entrar" : "criar perfil"}</p>

    <input
      type="text"
      placeholder="usuário"
      autocomplete="username"
      maxlength="24"
      bind:value={username}
      on:keydown={onKey}
    />
    <input
      type="password"
      placeholder="senha"
      autocomplete={mode === "login" ? "current-password" : "new-password"}
      bind:value={password}
      on:keydown={onKey}
    />
    {#if mode === "register"}
      <input
        type="password"
        placeholder="repita a senha"
        autocomplete="new-password"
        bind:value={confirmPassword}
        on:keydown={onKey}
      />
      {#if password.length > 0 && password.length < 8}
        <p class="rule">mínimo de 8 caracteres</p>
      {:else if confirmPassword.length > 0 && password !== confirmPassword}
        <p class="rule">as senhas não conferem</p>
      {/if}
    {/if}

    <div class="actions">
      <button class="primary" on:click={submit} disabled={!canSubmit || busy}>
        {busy ? "..." : mode === "login" ? "entrar" : "criar"}
      </button>
    </div>

    <button class="link" on:click={() => switchMode(mode === "login" ? "register" : "login")}>
      {mode === "login" ? "criar um perfil novo" : "já tenho um perfil"}
    </button>

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
    max-width: calc(100vw - 2rem);
    box-sizing: border-box;
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
    margin-bottom: 0.75rem;
  }
  input:focus {
    border-color: #6cf;
  }
  .rule {
    color: #ca6;
    font-size: 0.75rem;
    margin: -0.35rem 0 0.75rem;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }
  .primary {
    padding: 0.55rem 1rem;
    border: 1px solid #6cf;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.15s;
    background: #6cf;
    color: #0a0a0a;
    flex: 1;
  }
  .primary:hover:not(:disabled) {
    background: #4ad;
  }
  .primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .link {
    display: block;
    width: 100%;
    margin-top: 0.9rem;
    background: transparent;
    border: none;
    color: #666;
    font: inherit;
    font-size: 0.78rem;
    text-decoration: underline;
    cursor: pointer;
    padding: 0;
  }
  .link:hover {
    color: #6cf;
  }
  .error {
    color: #f66;
    font-size: 0.8rem;
    margin-top: 0.75rem;
  }
</style>
