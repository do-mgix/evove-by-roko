<script lang="ts">
  import NavBar from "./lib/NavBar.svelte";
  import Dashboard from "./lib/Dashboard.svelte";
  import Shop from "./lib/Shop.svelte";
  import SkillTree from "./lib/SkillTree.svelte";
  import UserPage from "./lib/UserPage.svelte";
  import Calendar from "./lib/Calendar.svelte";
  import Journey from "./lib/Journey.svelte";
  import UserSelect from "./lib/UserSelect.svelte";
  import { onMount } from "svelte";
  import { logout as apiLogout, setUnauthorizedHandler } from "./lib/api";

  // The login screen is always the entry point: a session kept in localStorage
  // from a previous visit is not enough to skip it.
  let username: string | null = null;

  // A rejected session anywhere in the app drops straight back to login,
  // instead of every panel failing on its own.
  onMount(() => {
    setUnauthorizedHandler(() => (username = null));
    return () => setUnauthorizedHandler(null);
  });
  let page = "home";
  let pageParams: Record<string, any> = {};
  let dashKey = 0;

  function nav(p: string, params: Record<string, any> = {}) {
    page = p;
    pageParams = params;
  }

  function onSelected(name: string) {
    username = name;
    page = "home";
    pageParams = {};
    dashKey++;
  }

  async function logout() {
    username = null;
    await apiLogout();
  }
</script>

{#if !username}
  <UserSelect {onSelected} />
{:else}
  <div class="app">
    <NavBar current={page} onNav={nav} onLogout={logout} />
    <div class="page">
      {#if page === "home"}
        {#key dashKey}
          <Dashboard onNav={nav} />
        {/key}
      {:else if page === "agenda"}
        <Calendar />
      {:else if page === "journey"}
        <Journey />
      {:else if page === "shop"}
        <Shop initialSection={pageParams.section ?? null} />
      {:else if page === "skills"}
        <SkillTree />
      {:else if page === "user"}
        <UserPage />
      {/if}
    </div>
  </div>
{/if}

<style>
  .app {
    display: flex;
    height: 100vh;
    width: 100vw;
  }
  .page {
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }

  /* column-reverse puts the page above the bar without reordering the markup,
     so the nav keeps coming first for keyboard and screen readers. */
  @media (max-width: 768px) {
    .app {
      flex-direction: column-reverse;
      height: 100dvh;
    }
    .page {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      overflow-x: hidden;
    }
  }
</style>
