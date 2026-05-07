<script lang="ts">
  export let current: string;
  export let onNav: (page: string) => void;
  export let onLogout: () => void;

  const items = [
    { id: "home", label: "home", icon: "◆" },
    { id: "agenda", label: "agenda", icon: "▦" },
    { id: "journey", label: "journey", icon: "↝" },
    { id: "shop", label: "shop", icon: "$" },
    { id: "skills", label: "skills", icon: "✦" },
    { id: "user", label: "user", icon: "@" },
  ];
</script>

<nav class="navbar">
  {#each items as item (item.id)}
    <button
      class="nav-btn"
      class:active={current === item.id}
      on:click={() => onNav(item.id)}
      title={item.label}
    >
      <span class="icon">{item.icon}</span>
      <span class="label">{item.label}</span>
    </button>
  {/each}

  <div class="spacer"></div>

  <button class="nav-btn logout" on:click={onLogout} title="log out">
    <span class="icon">⏻</span>
    <span class="label">log out</span>
  </button>
</nav>

<style>
  .navbar {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 1.5rem 0.5rem;
    background: #0a0a0a;
    border-right: 1px solid #1a1a1a;
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
    color: #555;
    font-family: inherit;
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
  }
  .nav-btn:hover {
    color: #ccc;
    background: #141414;
  }
  .nav-btn.active {
    color: #6cf;
    background: #111;
  }
  .spacer {
    flex: 1;
  }
  .nav-btn.logout:hover {
    color: #f66;
  }
  .icon {
    font-size: 1.1rem;
    line-height: 1;
  }
  .label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
</style>
