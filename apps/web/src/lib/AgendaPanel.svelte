<script lang="ts">
  import { onMount } from "svelte";
  import type { AgendaItem, AgendaToday, LogEntry } from "./api";
  import { fetchAgendaToday, deleteAgendaItem, fetchLogs } from "./api";
  import { logsVersion } from "./store";
  import Modal from "./Modal.svelte";
  import AgendaForm from "./AgendaForm.svelte";
  export let agenda: AgendaToday;

  let selected: AgendaItem | null = null;
  let showForm = false;
  let editingItem: AgendaItem | null = null;
  let confirmingDelete = false;
  let saving = false;
  let error: string | null = null;
  let todayLogs: LogEntry[] = [];
  let lastLogsVersion = 0;

  $: sortedItems = [...agenda.items].sort((a, b) => a.start.localeCompare(b.start));

  $: if ($logsVersion !== lastLogsVersion) {
    lastLogsVersion = $logsVersion;
    refreshLogs();
  }

  async function refreshLogs() {
    try {
      const res = await fetchLogs(0);
      todayLogs = res.logs;
    } catch {}
  }

  async function refresh() {
    try {
      agenda = await fetchAgendaToday();
    } catch {}
  }

  onMount(refreshLogs);

  function logTimeMin(ts: string): number | null {
    const m = ts.match(/:\s*(\d{2}):(\d{2}):/);
    if (!m) return null;
    return parseInt(m[1]) * 60 + parseInt(m[2]);
  }

  function logMatches(log: LogEntry, label: string): boolean {
    if (!label) return false;
    return (log.content || "").toUpperCase().includes(label.toUpperCase());
  }

  function logInWindow(t: number, s: number | null, e: number | null): boolean {
    if (s == null || t < s) return false;
    if (e == null) return true;
    if (e <= s) return true;
    return t < e;
  }

  function checkState(logs: LogEntry[], label: string, start: string, end: string | null | undefined, nextStart?: string): 0 | 1 | 2 {
    if (logs.length === 0) return 0;
    const matches = logs.filter((l) => logMatches(l, label));
    if (matches.length === 0) return 0;
    const s = parseHHMM(start);
    const effectiveEnd = end || nextStart || null;
    const e = effectiveEnd ? parseHHMM(effectiveEnd) : null;
    for (const log of matches) {
      const t = logTimeMin(log.timestamp);
      if (t == null) continue;
      if (logInWindow(t, s, e)) return 2;
    }
    return 1;
  }

  function onCreated() {
    refresh();
  }

  function closeModal() {
    selected = null;
    confirmingDelete = false;
    error = null;
  }

  function startEdit() {
    editingItem = selected;
    closeModal();
  }

  function onUpdated() {
    editingItem = null;
    refresh();
  }

  async function doDelete() {
    if (!selected || saving) return;
    saving = true;
    try {
      await deleteAgendaItem(selected.id!);
      agenda = { ...agenda, items: agenda.items.filter((it) => it.id !== selected!.id) };
      closeModal();
    } catch (e: any) {
      error = e?.message ?? "erro ao apagar";
    } finally {
      saving = false;
    }
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
  function isActive(start: string, end: string | null | undefined, nextStart?: string): boolean {
    const s = parseHHMM(start);
    const cur = nowMin();
    if (s == null || cur < s) return false;
    const effectiveEnd = end || nextStart || null;
    if (!effectiveEnd) return true;
    const e = parseHHMM(effectiveEnd);
    if (e == null) return true;
    if (e <= s) return true;
    return cur < e;
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
      {#each sortedItems as item, i (i)}
        {@const cs = checkState(todayLogs, item.label, item.start, item.end, sortedItems[i + 1]?.start)}
        <li class:active={isActive(item.start, item.end, sortedItems[i + 1]?.start)}>
          <button class="row" on:click={() => (selected = item)}>
            <span class="time">{item.start}{item.end ? `-${item.end}` : ""}</span>
            <span class="label">{item.label}</span>
            {#if cs === 2}<span class="check check2">✓✓</span>{:else if cs === 1}<span class="check check1">✓</span>{/if}
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

{#if selected}
  <Modal title="agenda" onClose={closeModal}>
    <dl class="details">
      <dt>label</dt><dd class="hl">{selected.label}</dd>
      <dt>start</dt><dd>{fmtTime(selected.start)}</dd>
      {#if selected.end}<dt>end</dt><dd>{fmtTime(selected.end)}</dd>{/if}
      {#if selected.end}<dt>duration</dt><dd>{durationMin(selected.start, selected.end)} min</dd>{/if}
      {#if selected.day}<dt>day</dt><dd>{selected.day === "*" ? "diário" : selected.day}</dd>{/if}
      <dt>active</dt><dd>{isActive(selected.start, selected.end) ? "yes" : "no"}</dd>
    </dl>

    {#if confirmingDelete}
      <div class="action-block">
        <p class="confirm-msg">apagar este item?</p>
        <div class="row-btns">
          <button class="ghost" on:click={() => (confirmingDelete = false)} disabled={saving}>não</button>
          <button class="danger" on:click={doDelete} disabled={saving}>{saving ? "..." : "apagar"}</button>
        </div>
      </div>
    {:else}
      {#if error}<p class="err">{error}</p>{/if}
      <div class="row-btns">
        <button class="ghost" on:click={startEdit}>editar</button>
        <button class="danger-ghost" on:click={() => (confirmingDelete = true)}>apagar</button>
      </div>
    {/if}
  </Modal>
{/if}

{#if showForm}
  <AgendaForm onClose={() => (showForm = false)} {onCreated} />
{/if}

{#if editingItem}
  <AgendaForm
    initialItem={editingItem}
    onClose={() => (editingItem = null)}
    onCreated={onCreated}
    {onUpdated}
  />
{/if}

<style>
  .panel {
    background: #000000;
    border: 1px solid #333333;
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
    border: 1px solid #333333;
    color: #808080;
    width: 22px;
    height: 22px;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
    line-height: 1;
    padding: 0;
  }
  .add-btn:hover {
    border-color: #00e5ff;
    color: #00e5ff;
  }
  .panel-title {
    color: #808080;
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
    border-bottom: 1px solid #333333;
  }
  .row {
    display: grid;
    grid-template-columns: 6.5rem 1fr auto;
    gap: 0.6rem;
    align-items: baseline;
    width: 100%;
    padding: 0.35rem 0.3rem;
    background: transparent;
    border: none;
    font: inherit;
    font-size: 0.82rem;
    color: #808080;
    text-align: left;
    cursor: pointer;
  }
  .row:hover {
    background: #000000;
  }
  li.active .row {
    color: #00e5ff;
  }
  .time {
    color: #808080;
    font-size: 0.78rem;
  }
  li.active .time {
    color: #00e5ff;
  }
  .check {
    font-size: 0.7rem;
    align-self: center;
  }
  .check1 { color: #808080; }
  .check2 { color: #00e5ff; }
  .details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.4rem 1rem;
    margin: 0;
  }
  .details dt {
    color: #808080;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
    margin: 0;
  }
  .details dd {
    color: #ffffff;
    margin: 0;
    font-size: 0.85rem;
  }
  .hl {
    color: #00e5ff;
  }
  .empty {
    color: #808080;
    font-size: 0.85rem;
  }
  .action-block {
    margin-top: 0.8rem;
  }
  .confirm-msg {
    color: #cccccc;
    font-size: 0.85rem;
    margin: 0 0 0.6rem;
  }
  .row-btns {
    display: flex;
    gap: 0.5rem;
  }
  .ghost {
    background: transparent;
    border: 1px solid #333333;
    color: #808080;
    padding: 0.3rem 0.8rem;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
    font-size: 0.82rem;
  }
  .ghost:hover:not(:disabled) {
    border-color: #00e5ff;
    color: #00e5ff;
  }
  .danger {
    background: transparent;
    border: 1px solid #4d1a1a;
    color: #ff4d4d;
    padding: 0.3rem 0.8rem;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
    font-size: 0.82rem;
  }
  .danger:hover:not(:disabled) {
    border-color: #ff4d4d;
    color: #ff4d4d;
  }
  .danger-ghost {
    background: transparent;
    border: 1px solid transparent;
    color: #cc6666;
    padding: 0.3rem 0.8rem;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
    font-size: 0.82rem;
  }
  .danger-ghost:hover {
    color: #ff4d4d;
  }
  .err {
    color: #ff4d4d;
    font-size: 0.8rem;
    margin: 0.4rem 0 0;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
