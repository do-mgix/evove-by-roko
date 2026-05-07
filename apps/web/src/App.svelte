<script lang="ts">
  import NavBar from "./lib/NavBar.svelte";
  import Dashboard from "./lib/Dashboard.svelte";
  import Shop from "./lib/Shop.svelte";
  import SkillTree from "./lib/SkillTree.svelte";
  import UserPage from "./lib/UserPage.svelte";
  import Calendar from "./lib/Calendar.svelte";
  import Journey from "./lib/Journey.svelte";
  import UserSelect from "./lib/UserSelect.svelte";
  import { getUsername, clearUsername } from "./lib/api";

  let username = getUsername();
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

  function logout() {
    clearUsername();
    username = null;
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
</style>
