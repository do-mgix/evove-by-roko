<script lang="ts">
  import Home from "./lib/Home.svelte";
  import ScreenHeader from "./lib/ScreenHeader.svelte";
  import RokoPage from "./lib/RokoPage.svelte";
  import LogsPanel from "./lib/LogsPanel.svelte";
  import Dashboard from "./lib/Dashboard.svelte";
  import Shop from "./lib/Shop.svelte";
  import SkillTree from "./lib/SkillTree.svelte";
  import MeTabs from "./lib/MeTabs.svelte";
  import Journey from "./lib/Journey.svelte";
  import UserSelect from "./lib/UserSelect.svelte";
  import { onMount } from "svelte";
  import type { HomeOptionId } from "./lib/homeLayout";
  import {
    fetchSessionInfo,
    getToken,
    getUsername,
    logout as apiLogout,
    logoutEverywhere,
    setUnauthorizedHandler,
  } from "./lib/api";

  // A session kept from a previous launch signs straight in; the server renews
  // it while it is in use, so the app stays signed in until someone logs out.
  let username: string | null = getToken() ? getUsername() : null;

  // A rejected session anywhere in the app drops straight back to login,
  // instead of every panel failing on its own.
  onMount(() => {
    setUnauthorizedHandler(() => (username = null));
    // check the kept session once; a 401 lands in the handler above
    if (username) fetchSessionInfo().catch(() => {});
    return () => setUnauthorizedHandler(null);
  });
  // "home" is the tile screen; every other page opens over it, full screen,
  // and going back always lands on the tiles
  let page = "home";
  let pageParams: Record<string, any> = {};
  let dashKey = 0;

  // agenda and profile are tabs of me now; the old names still land there
  const ME_TABS: Record<string, string> = { agenda: "agenda", profile: "profile" };

  // a tile and the page it opens
  const TILE_PAGE: Record<HomeOptionId, string> = {
    act: "act", logs: "logs", shop: "shop", roko: "roko", attributes: "me", journey: "journey",
  };
  const TITLES: Record<string, string> = {
    act: "agir", logs: "logs", shop: "shop", roko: "roko", me: "atributos", journey: "jornada", skills: "skills",
  };

  function nav(p: string, params: Record<string, any> = {}) {
    if (p in ME_TABS) {
      params = { ...params, tab: ME_TABS[p] };
      p = "me";
    }
    if (p === "home") return goHome();
    // One history entry per visit away from the tiles: Android's back button
    // walks the WebView history, so it lands on the tiles and, from there,
    // leaves the app.
    if (page === "home") history.pushState({ page: p }, "");
    else history.replaceState({ page: p }, "");
    page = p;
    pageParams = params;
  }

  function goHome() {
    if (page === "home") return;
    if (history.state?.page) history.back();   // the popstate below lands home
    else page = "home";
  }

  onMount(() => {
    const onPop = () => {
      page = "home";
      pageParams = {};
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  });

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
{:else if page === "home"}
  <Home onOpen={(id) => nav(TILE_PAGE[id])} />
{:else}
  <div class="app">
    <ScreenHeader title={TITLES[page] ?? page} onBack={goHome} />
    <div class="page" class:padded={page === "logs"}>
      {#if page === "act"}
        {#key dashKey}
          <Dashboard onNav={nav} />
        {/key}
      {:else if page === "logs"}
        <LogsPanel />
      {:else if page === "shop"}
        <Shop initialSection={pageParams.section ?? null} />
      {:else if page === "roko"}
        <RokoPage />
      {:else if page === "me"}
        <MeTabs tab={pageParams.tab ?? "me"} onTab={(tab) => nav("me", { tab })} onLogout={logout} />
      {:else if page === "journey"}
        <Journey />
      {:else if page === "skills"}
        <!-- on hold: no tile, kept for when it comes back -->
        <SkillTree />
      {/if}
    </div>
  </div>
{/if}

<style>
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: 100dvh;
    width: 100vw;
  }
  .page {
    flex: 1;
    min-height: 0;
    min-width: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding-bottom: env(safe-area-inset-bottom);
  }
  .page.padded { padding: 0.75rem 0.75rem calc(0.75rem + env(safe-area-inset-bottom)); box-sizing: border-box; }
</style>
