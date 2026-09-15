<script module lang="ts">
  // Modals open on top of one another; only the topmost answers Escape, so closing
  // a confirmation leaves the modal under it open.
  const stack: object[] = [];
</script>

<script lang="ts">
  import { onDestroy } from "svelte";

  export let title = "";
  export let onClose: () => void;
  /** "page" takes most of the screen, like a page of its own. */
  export let size: "default" | "page" = "default";

  const self = {};
  stack.push(self);
  onDestroy(() => stack.splice(stack.indexOf(self), 1));

  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape" && stack[stack.length - 1] === self) onClose();
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

<div class="modal {size}" role="dialog" aria-modal="true">
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
    background: #000000;
    border: 1px solid #333333;
    border-radius: 8px;
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
    z-index: 100;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .modal.page {
    width: min(1100px, 94vw);
    max-width: none;
    height: 88vh;
    max-height: none;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #333333;
  }
  .title {
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.75rem;
  }
  .close {
    background: transparent;
    border: none;
    color: #808080;
    font-size: 1.4rem;
    line-height: 1;
    cursor: pointer;
    padding: 0 0.3rem;
  }
  .close:hover {
    color: #ff4d4d;
  }
  .body {
    padding: 1rem 1.25rem;
    overflow-y: auto;
  }
  .page .body {
    flex: 1;
    min-height: 0;
  }

  @media (max-width: 768px) {
    .modal {
      min-width: 0;
      width: calc(100vw - 1.5rem);
      max-width: none;
      max-height: 85dvh;
    }
    .modal.page {
      height: 92dvh;
      max-height: none;
    }
  }
</style>
