<script lang="ts">
  import Home from "./lib/Home.svelte";
  import ScreenHeader from "./lib/ScreenHeader.svelte";
  import RokoPage from "./lib/RokoPage.svelte";
  import LogsPanel from "./lib/LogsPanel.svelte";
  import ActScreen from "./lib/ActScreen.svelte";
  import Shop from "./lib/Shop.svelte";
  import BuildScreen from "./lib/BuildScreen.svelte";
  import SkillTree from "./lib/SkillTree.svelte";
  import MeTabs from "./lib/MeTabs.svelte";
  import Journey from "./lib/Journey.svelte";
  import UserSelect from "./lib/UserSelect.svelte";
  import { modalOpen } from "./lib/Modal.svelte";
  import { directionOf, moveFocus } from "./lib/keynav";
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
  let frame: HTMLElement | undefined;
  let pageParams: Record<string, any> = {};

  // agenda and profile are tabs of me now; the old names still land there
  const ME_TABS: Record<string, string> = { agenda: "agenda", profile: "profile" };

  // a tile and the page it opens
  const TILE_PAGE: Record<HomeOptionId, string> = {
    act: "act", logs: "logs", shop: "shop", roko: "roko", attributes: "me", journey: "journey", build: "build",
  };
  // the tile a page belongs to, for the icon in its header
  const PAGE_OPTION = Object.fromEntries(HOME_OPTIONS.map((o) => [TILE_PAGE[o.id], o]));
  const TITLES: Record<string, string> = {
    act: "agir", logs: "logs", shop: "shop", roko: "roko", me: "atributos", journey: "jornada", build: "construir", skills: "skills",
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
    // The keyboard, where no field or modal has it (they answer it themselves):
    // Escape is the back button; the arrows or h j k l move between buttons and
    // Enter presses the one reached; space turns the page; and a, s, e open
    // agir, the shop and atributos — except on agir, where letters type.
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || modalOpen() || !username || e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName))) return;
      if (e.key === "Escape") {
        if (handleBack()) return;
        if (page !== "home") goHome();
        return;
      }
      const dir = directionOf(e.key);
      if (dir) {
        e.preventDefault();
        if (frame) moveFocus(frame, dir);
        return;
      }
      if (e.key === " ") {
        const turn = frame?.querySelector<HTMLButtonElement>(".page-btn");
        if (turn) {
          e.preventDefault();
          turn.click();
        }
        return;
      }
      const jump: Record<string, string> = { a: "act", s: "shop", e: "me" };
      if (page !== "act" && jump[e.key] && jump[e.key] !== page) {
        e.preventDefault();
        nav(jump[e.key]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("keydown", onKey);
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
<div class="frame" bind:this={frame}>
  {#if !username}
    <UserSelect {onSelected} />
  {:else if page === "home"}
    <Home onOpen={(id) => nav(TILE_PAGE[id])} hint={suggestedOption()} />
  {:else if page === "act"}
    <!-- the acting screen has its own bar, with the way home, and no header -->
    <ActScreen onHome={goHome} />
  {:else if page === "shop"}
    <!-- so is the shop, walked the same way -->
    <Shop onHome={goHome} initialSection={pageParams.section ?? null} />
  {:else if page === "build"}
    <!-- and the page for building buttons on the grid -->
    <BuildScreen onHome={goHome} />
  {:else}
    <div class="app">
      <ScreenHeader option={PAGE_OPTION[page] ?? null} title={TITLES[page] ?? page} onBack={goHome} />
      <div class="page" class:padded={page === "logs"}>
        {#if page === "logs"}
          <LogsPanel />
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
    border: 1.5px solid rgba(255, 255, 255, 0.14);
    border-radius: 28px;
    /* clip, not hidden: nothing inside can scroll the frame, not even focus
       bringing a cell into view */
    overflow: clip;
    /* the deep green the wave rises from */
    background: #000000;
    /* the backdrop below stays under everything inside the frame */
    isolation: isolate;
  }
  /* The backdrop: black, with a faint band of green three times the frame's
     height sliding up and down through it, so the screens alternate between
     black and a glow of green behind the cells. Moved by transform, so the phone
     only composites it. */
  .frame::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 300%;
    z-index: -1;
    background: linear-gradient(
      to bottom,
      #000000 0%,
      #000000 30%,
      #04200f 50%,
      #000000 70%,
      #000000 100%
    );
    animation: drift 12s ease-in-out infinite alternate;
    pointer-events: none;
  }
  @keyframes drift {
    from { transform: translateY(0); }
    to { transform: translateY(-66.6%); }
  }
  @media (prefers-reduced-motion: reduce) {
    .frame::before { animation: none; transform: translateY(-33.3%); }
  }
  /* the pages with a header stay on white, to be read */
  .app {
    background: #ffffff;
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
