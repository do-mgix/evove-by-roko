<script lang="ts">
  import { onMount } from "svelte";
  import { flip } from "svelte/animate";
  import { fetchLogs, reorderLogs, type LogEntry } from "./api";
  import { logsVersion } from "./store";
  import Modal from "./Modal.svelte";

  let selected: LogEntry | null = null;
  let lastVersion = 0;
  let draggedId: number | null = null;

  let offset = 0;
  let logs: LogEntry[] = [];
  let day: number | null = null;
  let dateStr = "";
  let loading = false;
  let error: string | null = null;

  async function load(o: number) {
    loading = true;
    error = null;
    try {
      const res = await fetchLogs(o);
      logs = res.logs;
      day = res.day;
      dateStr = res.date;
      offset = res.offset;
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(() => load(0));

  // Refetch when an external action bumps the version (e.g., after acting)
  $: if ($logsVersion !== lastVersion) {
    lastVersion = $logsVersion;
    if (lastVersion > 0) load(offset);
  }

  function go(delta: number) {
    if (offset + delta > 0) return;
    load(offset + delta);
  }

  // Swipe handling
  let dragX: number | null = null;
  let dragStart = 0;
  const SWIPE_THRESHOLD = 60;

  function isInteractive(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null;
    return !!el?.closest("button");
  }

  function pointerDown(e: PointerEvent) {
    if (isInteractive(e.target)) return;
    dragStart = e.clientX;
    dragX = 0;
  }
  function pointerMove(e: PointerEvent) {
    if (dragX == null) return;
    dragX = e.clientX - dragStart;
  }
  function pointerUp(_e: PointerEvent) {
    if (dragX == null) return;
    const dx = dragX;
    dragX = null;
    if (Math.abs(dx) < SWIPE_THRESHOLD) return;
    if (dx > 0) go(-1);
    else go(1);
  }

  function relativeLabel(o: number): string {
    if (o === 0) return "today";
    if (o === -1) return "yesterday";
    if (o === 1) return "tomorrow";
    return o < 0 ? `${o}d` : `+${o}d`;
  }

  function formatDate(iso: string): string {
    if (!iso) return "";
    const [_y, m, d] = iso.split("-");
    return `${d}/${m}`;
  }

  const _DAYS_PT = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SAB"];
  function weekday(iso: string): string {
    if (!iso) return "";
    const dt = new Date(iso + "T00:00:00");
    return _DAYS_PT[dt.getDay()] ?? "";
  }

  function onDragStart(e: DragEvent, id: number) {
    draggedId = id;
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(id));
    }
  }

  function onDragOver(e: DragEvent, targetId: number) {
    if (draggedId === null || draggedId === targetId) return;
    e.preventDefault();
    const fromIdx = logs.findIndex((l) => l.id === draggedId);
    const toIdx = logs.findIndex((l) => l.id === targetId);
    if (fromIdx === -1 || toIdx === -1 || fromIdx === toIdx) return;
    const next = logs.slice();
    const [moved] = next.splice(fromIdx, 1);
    next.splice(toIdx, 0, moved);
    logs = next;
  }

  async function onDragEnd() {
    if (draggedId === null) return;
    draggedId = null;
    if (day == null) return;
    try {
      await reorderLogs(day, logs.map((l) => l.id));
      logs = logs.map((l, i) => ({ ...l, order: i + 1 }));
    } catch (e: any) {
      error = e?.message ?? "erro ao reordenar";
    }
  }

  function display(content: string): string {
    const noteMatch = content.match(/^(.+?)\s*:\s*(.+)$/);
    if (noteMatch) return noteMatch[2].trim();
    const valueMatch = content.match(/^(\d+)\s*[xX]\s*(.+)$/);
    if (valueMatch) return valueMatch[2].trim();
    return content;
  }
</script>

<div
  class="panel"
  on:pointerdown={pointerDown}
  on:pointermove={pointerMove}
  on:pointerup={pointerUp}
  on:pointercancel={pointerUp}
  style:transform={dragX != null ? `translateX(${Math.max(-40, Math.min(40, dragX / 4))}px)` : ""}
>
  <header class="head">
    <span class="panel-title">logs</span>
    <span class="day-indicator">
      <span class="weekday">{weekday(dateStr)}</span>
      <span class="rel">{relativeLabel(offset)}</span>
      {#if day != null}<span class="meta">day {day}</span>{/if}
      {#if dateStr}<span class="meta">{formatDate(dateStr)}</span>{/if}
    </span>
  </header>

  <button class="nav left" on:click={() => go(-1)} aria-label="dia anterior">‹</button>
  <button class="nav right" on:click={() => go(1)} disabled={offset >= 0} aria-label="próximo dia">›</button>

  {#if loading}
    <p class="empty">…</p>
  {:else if error}
    <p class="empty error">{error}</p>
  {:else if logs.length === 0}
    <p class="empty">sem logs</p>
  {:else}
    <ul>
      {#each logs as l (l.id)}
        <li
          animate:flip={{ duration: 220 }}
          draggable="true"
          class:dragging={draggedId === l.id}
          on:dragstart={(e) => onDragStart(e, l.id)}
          on:dragover={(e) => onDragOver(e, l.id)}
          on:dragend={onDragEnd}
          on:drop|preventDefault
        >
          <button class="log-row" on:click={() => (selected = l)}>
            <span class="grip" aria-hidden="true">⋮⋮</span>
            <span class="content">{display(l.content)}</span>
            <span class="xp">+{l.xp}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

{#if selected}
  <Modal title="log" onClose={() => (selected = null)}>
    <dl class="details">
      <dt>id</dt><dd>{selected.id}</dd>
      <dt>timestamp</dt><dd>{selected.timestamp}</dd>
      <dt>order</dt><dd>{selected.order}</dd>
      <dt>xp</dt><dd>+{selected.xp}</dd>
      <dt>content</dt><dd class="content-full">{selected.content}</dd>
    </dl>
  </Modal>
{/if}

<style>
  .panel {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
    touch-action: pan-y;
    user-select: none;
    transition: transform 0.05s linear;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.6rem;
  }
  .panel-title {
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.7rem;
  }
  .day-indicator {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    color: #888;
    font-size: 0.72rem;
  }
  .weekday {
    color: #6cf;
    font-weight: bold;
    letter-spacing: 0.08em;
  }
  .rel {
    color: #aaa;
  }
  .meta {
    color: #555;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }
  li {
    border-bottom: 1px solid #161616;
  }
  .log-row {
    display: flex;
    width: 100%;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.4rem 0.3rem;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    text-align: left;
    gap: 0.5rem;
  }
  .log-row:hover {
    background: #141414;
  }
  .grip {
    color: #2a2a2a;
    font-size: 0.7rem;
    cursor: grab;
    user-select: none;
  }
  li.dragging {
    opacity: 0.3;
  }
  li.dragging .log-row {
    background: #0a0a0a;
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
    word-break: break-word;
  }
  .content-full {
    color: #6cf;
  }
  .content {
    color: #ddd;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 75%;
  }
  .xp {
    color: #666;
    font-size: 0.75rem;
  }
  .empty {
    color: #555;
    font-size: 0.85rem;
  }
  .empty.error {
    color: #f66;
  }
  .nav {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 36px;
    border: none;
    background: transparent;
    color: #444;
    font-size: 2.4rem;
    line-height: 1;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.15s, color 0.15s, transform 0.1s;
    z-index: 1;
    padding: 0;
  }
  .nav.left {
    left: 0;
  }
  .nav.right {
    right: 0;
  }
  .panel:hover .nav {
    opacity: 1;
  }
  .nav:hover:not(:disabled) {
    color: #6cf;
    transform: scale(1.2);
  }
  .nav:disabled {
    cursor: default;
    color: #222;
  }
</style>
