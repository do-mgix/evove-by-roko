<script lang="ts">
  import { keyFeedback, buzz } from "./dtmf";

  /** Digits currently buffered. Owned by the parent so it can match actions. */
  export let buffer: string;
  export let onDigit: (d: string) => void;
  export let onBackspace: () => void;
  export let onClear: () => void;
  export let onConfirm: () => void;
  /** Phone-style tall keys for thumbs; flat rectangles for a physical numpad. */
  export let touch = false;

  const DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];
  const LETTERS: Record<string, string> = {
    "2": "abc", "3": "def", "4": "ghi", "5": "jkl",
    "6": "mno", "7": "pqrs", "8": "tuv", "9": "wxyz",
  };

  let pressed: string | null = null;
  let holdTimer: any = null;

  function flash(key: string) {
    pressed = key;
    setTimeout(() => (pressed === key ? (pressed = null) : null), 120);
  }

  function digit(d: string) {
    keyFeedback(d);
    flash(d);
    onDigit(d);
  }

  function backspace() {
    keyFeedback("*");
    flash("del");
    onBackspace();
  }

  /** Holding delete clears the whole buffer, as the original keypad did. */
  function holdStart() {
    clearTimeout(holdTimer);
    holdTimer = setTimeout(() => {
      holdTimer = null;
      buzz([15, 5, 15]);
      onClear();
    }, 500);
  }

  function holdEnd(fired: boolean) {
    if (holdTimer) {
      clearTimeout(holdTimer);
      holdTimer = null;
      if (fired) backspace();
    }
  }

  function confirm() {
    keyFeedback("#");
    flash("ok");
    onConfirm();
  }
</script>

<div class="dialpad" class:touch>
  {#each DIGITS as d (d)}
    <button
      type="button"
      class="key"
      class:pressed={pressed === d}
      on:click={() => digit(d)}
      tabindex="-1"
    >
      <span class="num">{d}</span>
      <span class="letters">{LETTERS[d] ?? ""}</span>
    </button>
  {/each}

  <button
    type="button"
    class="key aux"
    class:pressed={pressed === "del"}
    on:pointerdown={holdStart}
    on:pointerup={() => holdEnd(true)}
    on:pointerleave={() => holdEnd(false)}
    title="apagar · segure para limpar"
    tabindex="-1"
  >
    <span class="num">⌫</span>
  </button>

  <button
    type="button"
    class="key"
    class:pressed={pressed === "0"}
    on:click={() => digit("0")}
    tabindex="-1"
  >
    <span class="num">0</span>
    <span class="letters"></span>
  </button>

  <button
    type="button"
    class="key aux ok"
    class:pressed={pressed === "ok"}
    on:click={confirm}
    disabled={buffer.length === 0}
    title="agir"
    tabindex="-1"
  >
    <span class="num">→</span>
  </button>
</div>

<style>
  .dialpad {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.35rem;
    margin-top: 0.5rem;
  }
  .key {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.05rem;
    /* flat rectangles: the physical numpad is the real input here */
    height: 2.1rem;
    background: #0d0d0d;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    color: #bbb;
    font: inherit;
    cursor: pointer;
    user-select: none;
    transition: border-color 0.12s, color 0.12s, transform 0.08s;
  }
  .key:hover:not(:disabled) { border-color: #444; color: #ddd; }
  .key.pressed,
  .key:active:not(:disabled) {
    border-color: #6cf;
    color: #6cf;
    transform: scale(0.96);
  }
  .key:disabled { opacity: 0.3; cursor: default; }
  .num { font-size: 0.85rem; line-height: 1; }
  .letters {
    font-size: 0.5rem;
    letter-spacing: 0.06em;
    color: #444;
    text-transform: uppercase;
    min-height: 0.6rem;
  }
  .aux .num { color: #888; }
  .ok.pressed .num, .ok:active:not(:disabled) .num { color: #6cf; }

  /* Touch: tall keys sized for a thumb, since there is no physical keypad. */
  .dialpad.touch {
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
  .dialpad.touch .key {
    height: 3.4rem;
    border-radius: 8px;
    box-shadow: 0 0 12px rgba(255, 255, 255, 0.04);
  }
  .dialpad.touch .num { font-size: 1.25rem; }
  .dialpad.touch .letters { font-size: 0.55rem; }
</style>
