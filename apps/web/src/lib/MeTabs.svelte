<script module lang="ts">
  export type MeTab = "me" | "agenda" | "profile";
</script>

<script lang="ts">
  import MePage from "./MePage.svelte";
  import Calendar from "./Calendar.svelte";
  import ProfilePage from "./ProfilePage.svelte";

  /** Everything about the profile under one entry of the nav: its attributes and
   *  actions, its agenda, and the account with log out. */
  export let tab: MeTab = "me";
  export let onTab: (tab: MeTab) => void;
  export let onLogout: (everywhere: boolean) => void;

  const TABS: { id: MeTab; label: string }[] = [
    { id: "me", label: "me" },
    { id: "agenda", label: "agenda" },
    { id: "profile", label: "perfil" },
  ];
</script>

<div class="me-tabs">
  <div class="strip" role="tablist">
    {#each TABS as t (t.id)}
      <button
        class="tab"
        class:on={tab === t.id}
        role="tab"
        aria-selected={tab === t.id}
        on:click={() => onTab(t.id)}
      >
        {t.label}
      </button>
    {/each}
  </div>
  <div class="body">
    {#if tab === "agenda"}
      <Calendar />
    {:else if tab === "profile"}
      <ProfilePage {onLogout} />
    {:else}
      <MePage />
    {/if}
  </div>
</div>

<style>
  .me-tabs {
    display: flex;
    flex-direction: column;
    height: 100%;
  }
  .strip {
    display: flex;
    gap: 0.25rem;
    padding: 0.75rem 2rem 0;
    border-bottom: 1px solid #333333;
    flex: none;
  }
  .tab {
    padding: 0.5rem 0.9rem;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    color: #808080;
    font: inherit;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
  }
  .tab:hover { color: #cccccc; }
  .tab.on {
    color: #00e5ff;
    border-bottom-color: #00e5ff;
  }
  .body {
    flex: 1;
    min-height: 0;
  }

  @media (max-width: 768px) {
    .strip { padding: 0.25rem 0.5rem 0; }
    /* three equal thumbs across the width */
    .tab {
      flex: 1;
      padding: 0.7rem 0.5rem;
    }
  }
</style>
