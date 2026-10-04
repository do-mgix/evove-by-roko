<script lang="ts" context="module">
  /** One attribute that gained from the act: where its bar was, where it is. */
  export type Gain = {
    key: string;
    name: string;
    rankBefore: string;
    rank: string;
    /** segments filled before the act, on the current rank's bar (0 after a rank up) */
    from: number;
    marks: number;
    need: number;
  };
</script>

<script lang="ts">
  import { onMount } from "svelte";
  import MarkBar from "./MarkBar.svelte";
  import { keyFeedback, primeAudio } from "./dtmf";

  /** The top line: what was done, and how much of it. */
  export let title: string;
  /** Tokens the act moved, signed: released after the cap took its cut, or spent. */
  export let tokens: number;
  export let marks: number;
  export let gains: Gain[] = [];
  /** Below the gains: what roko says. Fixed for now. */
  export let roko = "registrado. o que vem a seguir?";
  export let onDone: () => void;

  // Everything else is gone; the gains arrive one after the other.
  let step = 0;
  onMount(() => {
    const timers = [
      setTimeout(() => (step = 1), 350), // tokens
      setTimeout(() => (step = 2), 1100), // marks and the bars
      setTimeout(() => (step = 3), 2600), // roko
    ];
    return () => timers.forEach(clearTimeout);
  });

  function done() {
    primeAudio();
    keyFeedback("#");
    onDone();
  }

  const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "0");
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="gains" role="button" tabindex="0" aria-label="continuar" on:click={done}
  on:keydown={(e) => (e.key === "Enter" || e.key === "Escape") && done()}>
  <p class="title">{title}</p>

  <div class="body">
    {#if step >= 1}
      <p class="line tokens" class:spent={tokens < 0}>{signed(tokens)} <span>tokens</span></p>
    {/if}
    {#if step >= 2}
      <p class="line marks">+{marks} <span>{marks === 1 ? "marca" : "marcas"}</span></p>
      {#each gains as g (g.key)}
        <div class="attr">
          <div class="attr-head">
            <span class="attr-name">{g.name}</span>
            <span class="attr-rank">{g.rankBefore === g.rank ? g.rank : `${g.rankBefore} → ${g.rank}`}</span>
          </div>
          <MarkBar marks={g.marks} need={g.need} from={g.from} size="md" tone="gold" />
        </div>
      {/each}
    {/if}
  </div>

  {#if step >= 3}
    <p class="roko">{roko}</p>
  {/if}
</div>

<style>
  .gains {
    position: absolute;
    inset: 0;
    padding: 1.5rem 1.25rem;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    background: #000000;
    color: #ffffff;
    font-family: var(--font-display);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    cursor: pointer;
    outline: none;
    user-select: none;
    -webkit-user-select: none;
  }
  .title {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 500;
    color: #ffd23f;
  }
  .body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 1rem;
  }
  .line {
    margin: 0;
    font-size: 2.4rem;
    font-weight: 600;
    animation: arrive 0.35s ease-out;
  }
  .line span { font-size: 0.95rem; font-weight: 400; color: #808080; }
  .tokens { color: #2fe0e6; }
  .tokens.spent { color: #ff6fb5; }
  .marks { color: #ffd23f; }
  .attr { animation: arrive 0.35s ease-out; }
  .attr-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.4rem;
    font-size: 0.75rem;
  }
  .attr-name { color: #ffffff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .attr-rank { color: #ffd23f; flex-shrink: 0; }
  .roko {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.5;
    color: #ff9a3c;
    animation: arrive 0.6s ease-out;
  }
  @keyframes arrive {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: none; }
  }
</style>
