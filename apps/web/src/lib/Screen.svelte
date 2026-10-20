<script lang="ts">
  import { GRID_COLS, gridUnit } from "./homeLayout";

  /** The one color of the screen: outlines, icons and the wash of what is pressed. */
  export let ink = "#00f0ff";
  /** The side of one of the grid's squares, for the page to size its cells by. */
  export let unit = 52;
  /** How tall the middle is, for the page to cut its lists into pages that fit. */
  export let bodyHeight = 0;
  /** The display's share of the height: what is said on top. */
  export let display = "16%";

  // The screen every dark page shares, as the acting screen and the shop are
  // built: the display on top, right-aligned; the middle, as wide as a row of the
  // grid and gathered in the bottom-right corner; the bar, the grid's bottom row,
  // with its buttons. Nothing scrolls: a page that holds more turns its pages.
  let width = 0;
  $: unit = gridUnit(width) || 52;
</script>

<div class="screen" bind:clientWidth={width} style="--ink: {ink}; --unit: {unit}px; --row: {unit * GRID_COLS}px; --display: {display}">
  <div class="display"><slot name="display" /></div>
  <div class="body" bind:clientHeight={bodyHeight}><slot /></div>
  <div class="bar"><slot name="bar" /></div>
</div>

<style>
  .screen {
    position: absolute;
    inset: 0;
    padding: 10px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    background: transparent;
    color: #ffffff;
    user-select: none;
    -webkit-user-select: none;
  }
  .display {
    flex: 0 0 var(--display);
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: flex-end;
    text-align: right;
    gap: 0.35rem;
    padding: 0.5rem 0.4rem;
    overflow: hidden;
  }
  .body {
    flex: 1;
    min-height: 0;
    align-self: flex-end;
    width: var(--row);
    max-width: 100%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    gap: 8px;
    padding: 6px;
    box-sizing: border-box;
    overflow: hidden;
  }
  .bar {
    flex: 0 0 var(--unit);
    align-self: flex-end;
    width: var(--row);
    max-width: 100%;
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    column-gap: 12px;
    padding: 6px;
    box-sizing: border-box;
  }

  /* What the pages put in it. The display speaks in two sizes. */
  .screen :global(.big),
  .screen :global(.small) {
    margin: 0;
    font-family: var(--font-mono);
    color: #ffffff;
    overflow-wrap: anywhere;
  }
  .screen :global(.big) { font-size: 1.5rem; line-height: 1.15; text-transform: uppercase; }
  .screen :global(.small) { font-size: 0.85rem; opacity: 0.7; }
  /* text already in capitals, its Greek ranks kept small (see text.ts) */
  .screen :global(.keep) { text-transform: none; }
  /* a button of the bar or of the page: see-through, square-cornered, outlined */
  .screen :global(.key) {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    min-width: 0;
    background: transparent;
    border: 1.5px solid var(--ink);
    border-radius: 0;
    color: var(--ink);
    font-family: var(--font-mono);
    font-size: 0.78rem;
    text-transform: uppercase;
    cursor: pointer;
    transition: background 0.06s;
  }
  .screen :global(.key:active:not(:disabled)),
  .screen :global(.key.on) {
    background: color-mix(in srgb, var(--ink) 25%, transparent);
  }
  .screen :global(.key:disabled) { opacity: 0.35; cursor: default; }
  .screen :global(.key.ghost) { border-style: dashed; opacity: 0.6; }
  /* home is always the bar's last square, under the thumb */
  .bar > :global(.home) { grid-column: 6; }
  /* the ticks of where a page stands */
  .screen :global(.ticks) {
    align-self: center;
    min-width: 0;
    overflow: hidden;
    display: flex;
    align-items: center;
    gap: 3px;
  }
  .screen :global(.ticks i) {
    flex: 0 0 auto;
    width: 4px;
    height: 10px;
    background: #ffffff;
    opacity: 0.3;
  }
  .screen :global(.ticks i.on) { opacity: 1; height: 16px; }
  /* a row of a list: a line of text, outlined, a tap opens it */
  .screen :global(.row) {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    width: 100%;
    min-height: 2.6rem;
    padding: 0.35rem 0.7rem;
    box-sizing: border-box;
    background: color-mix(in srgb, var(--ink) 8%, transparent);
    border: 1.5px solid color-mix(in srgb, var(--ink) 70%, transparent);
    border-radius: 0;
    color: #ffffff;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    text-align: left;
    cursor: pointer;
  }
  .screen :global(.row:active) { background: color-mix(in srgb, var(--ink) 25%, transparent); }
  .screen :global(.row .grow) { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .screen :global(.row .tag) { flex: none; color: var(--ink); font-size: 0.72rem; }
  .screen :global(.label) {
    margin: 0;
    color: var(--ink);
    font-family: var(--font-mono);
    font-size: 0.68rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    opacity: 0.85;
  }
  /* a box of text to write in */
  .screen :global(.field) {
    width: 100%;
    box-sizing: border-box;
    padding: 0.6rem 0.7rem;
    background: color-mix(in srgb, var(--ink) 6%, transparent);
    border: 1.5px solid var(--ink);
    border-radius: 0;
    color: #ffffff;
    font-family: var(--font-mono);
    font-size: 0.9rem;
    outline: none;
    resize: none;
  }
  .screen :global(.field::placeholder) { color: rgba(255, 255, 255, 0.35); }
  .screen :global(.empty) {
    margin: 0;
    padding: 0.8rem 0;
    color: rgba(255, 255, 255, 0.5);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    text-align: right;
  }
</style>
