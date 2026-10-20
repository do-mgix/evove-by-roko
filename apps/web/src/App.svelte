<script lang="ts">
  import Home from "./lib/Home.svelte";
  import ScreenHeader from "./lib/ScreenHeader.svelte";
  import RokoScreen from "./lib/RokoScreen.svelte";
  import LogsPanel from "./lib/LogsPanel.svelte";
  import ActScreen from "./lib/ActScreen.svelte";
  import Shop from "./lib/Shop.svelte";
  import BuildScreen from "./lib/BuildScreen.svelte";
  import SkillTree from "./lib/SkillTree.svelte";
  import AgendaScreen from "./lib/AgendaScreen.svelte";
  import JourneyScreen from "./lib/JourneyScreen.svelte";
  import MeScreen from "./lib/MeScreen.svelte";
  import MePage from "./lib/MePage.svelte";
  import ProfilePage from "./lib/ProfilePage.svelte";
  import Calendar from "./lib/Calendar.svelte";
  import UserSelect from "./lib/UserSelect.svelte";
  import { modalOpen } from "./lib/Modal.svelte";
  import { directionOf, moveFocus } from "./lib/keynav";
  import { onMount } from "svelte";
  import { App as NativeApp } from "@capacitor/app";
  import { Capacitor } from "@capacitor/core";
  import { HOME_OPTIONS, unlockedFor, type HomeOptionId } from "./lib/homeLayout";
  import { handleBack, userVersion } from "./lib/store";
  import { recordOpen, suggestedOption } from "./lib/usage";
  import {
    fetchSessionInfo,
    fetchUser,
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

  // a tile and the page it opens
  const TILE_PAGE: Record<HomeOptionId, string> = {
    act: "act", logs: "agenda", shop: "shop", roko: "roko", attributes: "me", journey: "journey", build: "build",
  };
  // the pages read on white, each under the dark page it opens from
  const PARENT: Record<string, string> = { profile: "me", details: "me", calendar: "agenda", logs: "agenda" };
  const PAGE_OPTION = { ...Object.fromEntries(HOME_OPTIONS.map((o) => [TILE_PAGE[o.id], o])),
    profile: HOME_OPTIONS.find((o) => o.id === "attributes"), details: HOME_OPTIONS.find((o) => o.id === "attributes"),
    calendar: HOME_OPTIONS.find((o) => o.id === "logs"), logs: HOME_OPTIONS.find((o) => o.id === "logs") };
  const TITLES: Record<string, string> = {
    profile: "perfil", details: "atributos e ações", calendar: "calendário", logs: "registros", skills: "skills",
  };

  // The home reveals its options as acts are logged. The count is kept on the
  // device too, so the home draws at once; an option seen for the first time
  // comes on last, glowing.
  const ACTS_KEY = "evove_acts";
  const SEEN_KEY = "evove_seen_options";
  const readNumber = (key: string) => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? NaN : Number(raw);
    } catch {
      return NaN;
    }
  };
  let acts = readNumber(ACTS_KEY);
  let seen: Set<HomeOptionId> = (() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) ?? "null") ?? []);
    } catch {
      return new Set();
    }
  })();
  // until the count is known, every option
  $: visible = Number.isFinite(acts) ? unlockedFor(acts) : null;
  $: fresh = visible && seen.size ? new Set([...visible].filter((id) => !seen.has(id))) : new Set<HomeOptionId>();

  async function countActs() {
    try {
      const u = await fetchUser();
      acts = u.acts ?? 0;
      try {
        localStorage.setItem(ACTS_KEY, String(acts));
      } catch {
        // drawn from the server every time, then
      }
    } catch {
      // offline: the last count stands
    }
  }
  let lastUserVersion = -1;
  $: if (username && $userVersion !== lastUserVersion) {
    lastUserVersion = $userVersion;
    countActs();
  }
  function markSeen(ids: Set<HomeOptionId> | null) {
    if (!ids) return;
    seen = new Set([...seen, ...ids]);
    try {
      localStorage.setItem(SEEN_KEY, JSON.stringify([...seen]));
    } catch {
      // every option stays new to this device
    }
  }

  function open(id: HomeOptionId) {
    recordOpen(id);
    markSeen(visible ?? unlockedFor(Infinity));
    nav(TILE_PAGE[id]);
  }

  function nav(p: string, params: Record<string, any> = {}) {
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
          if (PARENT[page]) nav(PARENT[page]);
          else if (page !== "home") goHome();
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
        if (PARENT[page]) nav(PARENT[page]);
        else if (page !== "home") goHome();
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
      const typing = page === "act" || page === "agenda";
      if (!typing && jump[e.key] && jump[e.key] !== page) {
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
    <Home onOpen={open} hint={suggestedOption(visible ?? unlockedFor(Infinity))} {visible} {fresh} />
  {:else if page === "act"}
    <!-- the dark pages have their own bar, with the way home, and no header -->
    <ActScreen onHome={goHome} />
  {:else if page === "shop"}
    <Shop onHome={goHome} initialSection={pageParams.section ?? null} />
  {:else if page === "build"}
    <BuildScreen onHome={goHome} />
  {:else if page === "agenda"}
    <AgendaScreen onHome={goHome} onCalendar={() => nav("calendar")} onLogs={() => nav("logs")} />
  {:else if page === "journey"}
    <JourneyScreen onHome={goHome} />
  {:else if page === "roko"}
    <RokoScreen onHome={goHome} />
  {:else if page === "me"}
    <MeScreen onHome={goHome} onProfile={() => nav("profile")} onDetails={() => nav("details")} />
  {:else}
    <div class="app">
      <ScreenHeader option={PAGE_OPTION[page] ?? null} title={TITLES[page] ?? page}
        onBack={() => (PARENT[page] ? nav(PARENT[page]) : goHome())} />
      <div class="page" class:padded={page === "logs"}>
        {#if page === "logs"}
          <LogsPanel />
        {:else if page === "profile"}
          <ProfilePage onLogout={logout} />
        {:else if page === "details"}
          <MePage />
        {:else if page === "calendar"}
          <Calendar />
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
