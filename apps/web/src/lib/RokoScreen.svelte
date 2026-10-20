<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import { fetchEntities, talkTo, type Entity } from "./api";
  import { DOT_R, GLYPHS } from "./homeLayout";
  import Icon from "./Icon.svelte";
  import Screen from "./Screen.svelte";
  import { primeAudio } from "./dtmf";
  import { powerOn, tap } from "./sfx";
  import { setBackHandler } from "./store";
  import { caps } from "./text";

  /** Back to the tile home. */
  export let onHome: () => void;

  // The entity's screen, text above all, as the autobattler is: its name, a box
  // where what it says is typed out, and a tap anywhere on the box asks it for a
  // line — if it is there, and if it wants to answer. Roko is the first entity;
  // the arrow walks to the next when there are more.

  const TYPE_MS = 28;

  let list: Entity[] = [];
  let index = 0;
  let showStats = false;
  let line = "";
  let typed = "";
  let away = false;
  let asking = false;
  let typer: any = null;
  let talks = 0;

  $: entity = list[index] ?? null;
  $: ink = entity?.color ?? "#3dfff0";

  function type(text: string) {
    if (typer) clearInterval(typer);
    line = text;
    typed = "";
    let i = 0;
    typer = setInterval(() => {
      i += 1;
      typed = text.slice(0, i);
      if (i % 3 === 0) tap(i % 10);
      if (i >= text.length) {
        clearInterval(typer);
        typer = null;
      }
    }, TYPE_MS);
  }

  async function ask() {
    if (!entity || asking) return;
    primeAudio();
    if (typer) {
      // a tap while it types finishes the line
      clearInterval(typer);
      typer = null;
      typed = line;
      return;
    }
    asking = true;
    try {
      const r = await talkTo(entity.id);
      talks += 1;
      away = !r.present;
      type(r.present ? (r.line ?? "…") : `${entity.name} NÃO ESTÁ AQUI.`);
    } catch (e: any) {
      type(String(e?.message ?? "…").toUpperCase());
    } finally {
      asking = false;
    }
  }

  function next() {
    primeAudio();
    tap(2);
    index = (index + 1) % Math.max(1, list.length);
    showStats = false;
    typed = line = "";
    powerOn();
  }

  function toggleStats() {
    primeAudio();
    tap(5);
    showStats = !showStats;
  }

  onMount(async () => {
    setBackHandler(() => {
      if (showStats) {
        showStats = false;
        return true;
      }
      return false;
    });
    try {
      list = await fetchEntities();
      powerOn();
      await tick();
      ask();
    } catch (e: any) {
      type(String(e?.message ?? "…").toUpperCase());
    }
  });
  onDestroy(() => {
    setBackHandler(null);
    if (typer) clearInterval(typer);
  });
</script>

<Screen {ink} display="20%">
  <svelte:fragment slot="display">
    {#if entity}
      <svg viewBox="0 0 24 24" class="eye" class:away aria-hidden="true">
        <path d={GLYPHS.roko.d} />
        {#each GLYPHS.roko.dots as [x, y]}<circle cx={x} cy={y} r={DOT_R} />{/each}
      </svg>
      <p class="name">{entity.name}</p>
      <p class="small">{entity.title}</p>
    {/if}
  </svelte:fragment>

  {#if showStats && entity}
    <dl class="stats">
      {#each Object.entries(entity.stats) as [k, v] (k)}<dt>{k}</dt><dd>{caps(String(v))}</dd>{/each}
      <dt>personalidade</dt><dd>{caps(entity.personality)}</dd>
      <dt>presença</dt><dd>{Math.round(entity.presence * 100)}%</dd>
      <dt>conversas</dt><dd>{talks}</dd>
    </dl>
  {:else}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div class="box" class:away role="button" tabindex="0" aria-label="falar com {entity?.name ?? 'a entidade'}"
      on:click={ask} on:keydown={(e) => (e.key === "Enter" || e.key === " ") && ask()}>
      <p class="said">{typed}<span class="caret" class:blink={!typer}>▍</span></p>
      <p class="hint">{asking ? "…" : "toque para ouvir"}</p>
    </div>
  {/if}

  <svelte:fragment slot="bar">
    <button class="key" aria-label="stats" class:on={showStats} on:click={toggleStats}><Icon name="bars" /></button>
    <button class="key talk" aria-label="falar" disabled={showStats} on:click={ask}><Icon name="chat" /></button>
    <button class="key" aria-label="próxima entidade" disabled={list.length < 2} on:click={next}><Icon name="right" /></button>
    <button class="key home" aria-label="início" on:click={() => { primeAudio(); tap(0); onHome(); }}><Icon name="circle" size={16} /></button>
  </svelte:fragment>
</Screen>

<style>
  .eye {
    width: 2.6rem;
    height: 2.6rem;
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.4;
    stroke-linecap: round;
    filter: drop-shadow(0 0 6px var(--ink));
  }
  .eye circle { fill: var(--ink); stroke: none; }
  .eye.away { opacity: 0.25; filter: none; }
  .name {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.6rem;
    font-weight: 600;
    letter-spacing: 0.25em;
    color: var(--ink);
  }
  .box {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 1.2rem 1rem;
    border: 1.5px solid var(--ink);
    background: color-mix(in srgb, var(--ink) 5%, transparent);
    cursor: pointer;
    outline: none;
  }
  .box.away { border-style: dashed; opacity: 0.6; }
  .box:active { background: color-mix(in srgb, var(--ink) 14%, transparent); }
  .said {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.15rem;
    font-weight: 500;
    line-height: 1.55;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #ffffff;
    overflow-wrap: anywhere;
  }
  .caret { color: var(--ink); }
  .caret.blink { animation: blink 1s steps(1) infinite; }
  @keyframes blink { 50% { opacity: 0; } }
  .hint {
    margin: 0;
    align-self: flex-end;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--ink);
    opacity: 0.6;
    text-transform: uppercase;
  }
  .stats {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.5rem 1rem;
    margin: 0;
    padding: 1rem;
    border: 1.5px solid var(--ink);
    font-family: var(--font-display);
    font-size: 0.85rem;
    text-transform: uppercase;
  }
  .stats dt { color: var(--ink); font-size: 0.7rem; letter-spacing: 0.12em; align-self: center; }
  .stats dd { margin: 0; text-align: right; color: #ffffff; text-transform: none; }
  .talk { grid-column: 2 / 5; }
</style>
