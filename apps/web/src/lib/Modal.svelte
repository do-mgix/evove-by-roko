<script lang="ts">
  export let title = "";
  export let onClose: () => void;

  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }
</script>

<svelte:window on:keydown={onKey} />

<div
  class="backdrop"
  on:click={onClose}
  on:keydown={(e) => e.key === "Enter" && onClose()}
  role="button"
  tabindex="-1"
></div>

<div class="modal" role="dialog" aria-modal="true">
  <header>
    <span class="title">{title}</span>
    <button class="close" on:click={onClose} aria-label="fechar">×</button>
  </header>
  <div class="body">
    <slot />
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    z-index: 99;
  }
  .modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    min-width: 320px;
    max-width: 90vw;
    max-height: 80vh;
    background: #111;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    color: #e5e5e5;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
    z-index: 100;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #1f1f1f;
  }
  .title {
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.75rem;
  }
  .close {
    background: transparent;
    border: none;
    color: #555;
    font-size: 1.4rem;
    line-height: 1;
    cursor: pointer;
    padding: 0 0.3rem;
  }
  .close:hover {
    color: #f66;
  }
  .body {
    padding: 1rem 1.25rem;
    overflow-y: auto;
  }
</style>
