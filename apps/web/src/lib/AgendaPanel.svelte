<script lang="ts">
  import type { AgendaItem, AgendaToday } from "./api";
  import { fetchAgendaToday } from "./api";
  import Modal from "./Modal.svelte";
  import AgendaForm from "./AgendaForm.svelte";
  export let agenda: AgendaToday;

  let selected: AgendaItem | null = null;
  let showForm = false;

  async function refresh() {
    try {
      agenda = await fetchAgendaToday();
    } catch {}
  }

  function onCreated() {
    refresh();
  }

  function fmtTime(s: string): string {
    if (s.length === 4) return `${s.slice(0, 2)}:${s.slice(2)}`;
    return s;
  }
  function durationMin(start: string, end: string): number {
    const p = (s: string) => parseInt(s.slice(0, 2)) * 60 + parseInt(s.slice(2));
    let d = p(end) - p(start);
    if (d < 0) d += 24 * 60;
    return d;
  }

  function nowMin(): number {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }
  function parseHHMM(s: string): number | null {
    const t = s.replace(":", "");
    if (t.length !== 4) return null;
    const h = parseInt(t.slice(0, 2));
    const m = parseInt(t.slice(2));
    if (Number.isNaN(h) || Number.isNaN(m)) return null;
    return h * 60 + m;
  }
  function isActive(start: string, end: string | null | undefined): boolean {
    const s = parseHHMM(start);
    const cur = nowMin();
    if (s == null) return false;
    if (!end) return cur >= s && cur < s + 60;
    const e = parseHHMM(end);
    if (e == null) return false;
    if (s < e) return s <= cur && cur < e;
    return cur >= s || cur < e;
  }
</script>

<div class="panel">
  <header class="head">
    <span class="panel-title">agenda · {agenda.day ?? "?"}</span>
    <button class="add-btn" on:click={() => (showForm = true)} title="adicionar item">+</button>
  </header>
  {#if agenda.items.length === 0}
    <p class="empty">sem agenda</p>
  {:else}
    <ul>
      {#each agenda.items as item, i (i)}
        <li class:active={isActive(item.start, item.end)}>
          <button class="row" on:click={() => (selected = item)}>
            <span class="time">{item.start}{item.end ? `-${item.end}` : ""}</span>
            <span class="label">{item.label}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

{#if selected}
  <Modal title="agenda" onClose={() => (selected = null)}>
    <dl class="details">
      <dt>label</dt><dd class="hl">{selected.label}</dd>
      <dt>start</dt><dd>{fmtTime(selected.start)}</dd>
      {#if selected.end}<dt>end</dt><dd>{fmtTime(selected.end)}</dd>{/if}
      {#if selected.end}<dt>duration</dt><dd>{durationMin(selected.start, selected.end)} min</dd>{/if}
      {#if selected.day}<dt>day</dt><dd>{selected.day === "*" ? "diário" : selected.day}</dd>{/if}
      <dt>active</dt><dd>{isActive(selected.start, selected.end) ? "yes" : "no"}</dd>
    </dl>
  </Modal>
{/if}

{#if showForm}
  <AgendaForm onClose={() => (showForm = false)} {onCreated} />
{/if}

<style>
  .panel {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    overflow: auto;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.6rem;
  }
  .add-btn {
    background: transparent;
    border: 1px solid #2a2a2a;
    color: #888;
    width: 22px;
    height: 22px;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
    line-height: 1;
    padding: 0;
  }
  .add-btn:hover {
    border-color: #6cf;
    color: #6cf;
  }
  .panel-title {
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.7rem;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  li {
    border-bottom: 1px solid #161616;
  }
  .row {
    display: grid;
    grid-template-columns: 6.5rem 1fr;
    gap: 0.6rem;
    align-items: baseline;
    width: 100%;
    padding: 0.35rem 0.3rem;
    background: transparent;
    border: none;
    font: inherit;
    font-size: 0.82rem;
    color: #888;
    text-align: left;
    cursor: pointer;
  }
  .row:hover {
    background: #141414;
  }
  li.active .row {
    color: #6cf;
  }
  .time {
    color: #555;
    font-size: 0.78rem;
  }
  li.active .time {
    color: #6cf;
  }
  .details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.4rem 1rem;
    margin: 0;
  }
  .details dt {
    color: #555;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
    margin: 0;
  }
  .details dd {
    color: #ddd;
    margin: 0;
    font-size: 0.85rem;
  }
  .hl {
    color: #6cf;
  }
  .empty {
    color: #555;
    font-size: 0.85rem;
  }
</style>
