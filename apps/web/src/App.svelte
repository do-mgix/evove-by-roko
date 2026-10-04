<script lang="ts">
  import Home from "./lib/Home.svelte";
  import ScreenHeader from "./lib/ScreenHeader.svelte";
  import RokoPage from "./lib/RokoPage.svelte";
  import LogsPanel from "./lib/LogsPanel.svelte";
  import ActScreen from "./lib/ActScreen.svelte";
  import Shop from "./lib/Shop.svelte";
  import SkillTree from "./lib/SkillTree.svelte";
  import MeTabs from "./lib/MeTabs.svelte";
  import Journey from "./lib/Journey.svelte";
  import UserSelect from "./lib/UserSelect.svelte";
  import { onMount } from "svelte";
  import { App as NativeApp } from "@capacitor/app";
  import { Capacitor } from "@capacitor/core";
  import { HOME_OPTIONS, suggestedOption, type HomeOptionId } from "./lib/homeLayout";
  import { handleBack } from "./lib/store";
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

  // agenda and profile are tabs of me now; the old names still land there
  const ME_TABS: Record<string, string> = { agenda: "agenda", profile: "profile" };

  // a tile and the page it opens
  const TILE_PAGE: Record<HomeOptionId, string> = {
    act: "act", logs: "logs", shop: "shop", roko: "roko", attributes: "me", journey: "journey",
  };
  // the tile a page belongs to, for the icon in its header
  const PAGE_OPTION = Object.fromEntries(HOME_OPTIONS.map((o) => [TILE_PAGE[o.id], o]));
  const TITLES: Record<string, string> = {
    act: "agir", logs: "logs", shop: "shop", roko: "roko", me: "atributos", journey: "jornada", skills: "skills",
  };

  function nav(p: string, params: Record<string, any> = {}) {
    if (p in ME_TABS) {
      params = { ...params, tab: ME_TABS[p] };
      p = "me";
    }
    if (p === "home") return goHome();
    // One history entry per visit away from the tiles, so the browser's back
    // lands on them; Android's back button is wired to the same below.
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
    // Android's back button: from a page, back to the tiles; from the tiles,
    // out of the app. Without this listener Capacitor just closes the activity.
    const backButton = Capacitor.isNativePlatform()
      ? NativeApp.addListener("backButton", () => {
          if (handleBack()) return;
          if (page !== "home") goHome();
          else NativeApp.exitApp();
        })
      : null;
    return () => {
      window.removeEventListener("popstate", onPop);
      backButton?.then((h) => h.remove());
    };
  });

  function onSelected(name: string) {
    username = name;
    page = "home";
    pageParams = {};
  }

  async function logout(everywhere: boolean) {
    username = null;
    await (everywhere ? logoutEverywhere() : apiLogout());
  }
</script>

<!-- The frame: a fixed border around the whole interface, inside the screen's
     margins, that stays put whatever is showing. -->
<div class="frame">
  {#if !username}
    <UserSelect {onSelected} />
  {:else if page === "home"}
    <Home onOpen={(id) => nav(TILE_PAGE[id])} hint={suggestedOption()} />
  {:else if page === "act"}
    <!-- the acting screen has its own bar, with the way home, and no header -->
    <ActScreen onHome={goHome} />
  {:else}
    <div class="app">
      <ScreenHeader option={PAGE_OPTION[page] ?? null} title={TITLES[page] ?? page} onBack={goHome} />
      <div class="page" class:padded={page === "logs"}>
        {#if page === "logs"}
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
</div>

<style>
  .frame {
    position: fixed;
    top: calc(env(safe-area-inset-top) + 8px);
    right: calc(env(safe-area-inset-right) + 8px);
    bottom: calc(env(safe-area-inset-bottom) + 8px);
    left: calc(env(safe-area-inset-left) + 8px);
    border: 1.5px solid rgba(255, 255, 255, 0.7);
    border-radius: 28px;
    overflow: hidden;
    background: #000000;
  }
  .app {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
  }
  .page {
    flex: 1;
    min-height: 0;
    min-width: 0;
    overflow-y: auto;
    overflow-x: hidden;
  }
  .page.padded { padding: 0.75rem; box-sizing: border-box; }
</style>
