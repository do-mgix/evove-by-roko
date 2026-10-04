<script lang="ts">
  import { keyFeedback, primeAudio } from "./dtmf";

  /** The option's name, as on its tile. */
  export let title: string;
  export let onBack: () => void;

  function back() {
    primeAudio();
    keyFeedback("*");
    onBack();
  }
</script>

<header class="screen-header">
  <button class="back" on:click={back} aria-label="voltar">‹</button>
  <span class="title">{title}</span>
</header>

<style>
  .screen-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: calc(env(safe-area-inset-top) + 0.5rem) 0.9rem 0.5rem;
    border-bottom: 1px solid #333333;
    background: #000000;
    flex-shrink: 0;
  }
  .back {
    width: 2.2rem;
    height: 2.2rem;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 3px;
    color: #cccccc;
    font: inherit;
    font-size: 1.3rem;
    line-height: 1;
    cursor: pointer;
  }
  .back:active { border-color: #00e5ff; color: #00e5ff; }
  .title {
    font-family: var(--font-display);
    font-weight: 500;
    font-size: 0.85rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #ffffff;
  }
</style>
