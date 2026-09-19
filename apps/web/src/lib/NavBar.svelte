<script lang="ts">
  export let current: string;
  export let onNav: (page: string) => void;

  // home sits in the middle, where a thumb rests on a phone. Profile and the agenda
  // live inside me; skills is on hold, so it has no entry (the page is still in App).
  const items = [
    { id: "shop", label: "shop", icon: "$" },
    { id: "me", label: "me", icon: "◈" },
    { id: "home", label: "início", icon: "◆", main: true },
    { id: "journey", label: "journey", icon: "↝" },
    { id: "soon", label: "soon", icon: "⋯", title: "coming soon" },
  ];
</script>

<nav class="navbar">
  {#each items as item (item.id)}
    <button
      class="nav-btn"
      class:main={item.main}
      class:active={current === item.id}
      on:click={() => onNav(item.id)}
      title={item.title ?? item.label}
      aria-current={current === item.id ? "page" : undefined}
    >
      <span class="icon">{item.icon}</span>
      <span class="label">{item.label}</span>
    </button>
  {/each}
</nav>

<style>
  .navbar {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 1.5rem 0.5rem;
    background: #000000;
    border-right: 1px solid #333333;
    height: 100vh;
    box-sizing: border-box;
    width: 72px;
  }
  .nav-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.2rem;
    padding: 0.6rem 0.3rem;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: #808080;
    font-family: inherit;
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
  }
  .nav-btn:hover {
    color: #cccccc;
    background: #000000;
  }
  .nav-btn.active {
    color: #00e5ff;
    background: #000000;
  }
  .icon {
    font-size: 1.1rem;
    line-height: 1;
  }
  .label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
  }
  /* início is the one boxed target: the screen the app opens on */
  .nav-btn.main .icon {
    display: grid;
    place-items: center;
    width: 2.1rem;
    height: 2.1rem;
    border: 1px solid #333333;
    border-radius: 6px;
  }
  .nav-btn.main.active .icon { border-color: #00e5ff; }

  @media (max-width: 768px) {
    .navbar {
      flex-direction: row;
      align-items: stretch;
      justify-content: space-around;
      width: 100%;
      height: auto;
      gap: 0;
      padding: 0.25rem 0.25rem;
      padding-bottom: calc(0.25rem + env(safe-area-inset-bottom, 0px));
      border-right: none;
      border-top: 1px solid #333333;
      flex-shrink: 0;
    }
    .nav-btn {
      flex: 1;
      min-width: 0;
      min-height: 3.25rem;
      padding: 0.35rem 0.15rem;
    }
    .nav-btn.main .icon {
      width: 1.9rem;
      height: 1.9rem;
    }
  }
</style>
