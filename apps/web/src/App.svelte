<script lang="ts">
  import NavBar from "./lib/NavBar.svelte";
  import Dashboard from "./lib/Dashboard.svelte";
  import Shop from "./lib/Shop.svelte";
  import SkillTree from "./lib/SkillTree.svelte";
  import MeTabs from "./lib/MeTabs.svelte";
  import Journey from "./lib/Journey.svelte";
  import UserSelect from "./lib/UserSelect.svelte";
  import { onMount } from "svelte";
  import { logout as apiLogout, logoutEverywhere, setUnauthorizedHandler } from "./lib/api";

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

  // agenda and profile are tabs of me now; the old names still land there
  const ME_TABS: Record<string, string> = { agenda: "agenda", profile: "profile" };

  function nav(p: string, params: Record<string, any> = {}) {
    if (p in ME_TABS) {
      params = { ...params, tab: ME_TABS[p] };
      p = "me";
    }
    page = p;
    pageParams = params;
  }

  function onSelected(name: string) {
    username = name;
    page = "home";
    pageParams = {};
    dashKey++;
  }

  async function logout(everywhere: boolean) {
    username = null;
    await (everywhere ? logoutEverywhere() : apiLogout());
  }
</script>

{#if !username}
  <UserSelect {onSelected} />
{:else}
  <div class="app">
    <NavBar current={page} onNav={nav} />
    <div class="page">
      {#if page === "home"}
        {#key dashKey}
          <Dashboard onNav={nav} />
        {/key}
      {:else if page === "journey"}
        <Journey />
      {:else if page === "shop"}
        <Shop initialSection={pageParams.section ?? null} />
      {:else if page === "me"}
        <MeTabs tab={pageParams.tab ?? "me"} onTab={(tab) => nav("me", { tab })} onLogout={logout} />
      {:else if page === "soon"}
        <section class="soon">
          <span class="soon-icon">⋯</span>
          <p>coming soon</p>
        </section>
      {:else if page === "skills"}
        <!-- on hold: no entry in the nav, kept for when it comes back -->
        <SkillTree />
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
  .soon {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    color: #808080;
  }
  .soon-icon { color: #333333; font-size: 2rem; line-height: 1; }
  .soon p {
    margin: 0;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
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
