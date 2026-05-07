<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchCalendar,
    fetchLogsByDate,
    fetchActions,
    createAgendaItem,
    type CalendarMonth,
    type LogEntry,
    type Action,
  } from "./api";
  import Modal from "./Modal.svelte";

  const now = new Date();
  let viewYear = now.getFullYear();
  let viewMonth = now.getMonth() + 1; // 1-based

  let cal: CalendarMonth | null = null;
  let loading = true;
  let error: string | null = null;
  let selectedDate: string | null = null;
  let dayLogs: LogEntry[] = [];
  let dayLogsLoading = false;
  let actions: Action[] = [];
  let showEventForm = false;
  let eventDate = "";
  let eventLabel = "";
  let eventActionQuery = "";
  let eventActionId: string | null = null;
  let eventActionName: string | null = null;
  let eventBusy = false;
  let showPicker = false;

  const MONTHS_PT = [
    "janeiro","fevereiro","março","abril","maio","junho",
    "julho","agosto","setembro","outubro","novembro","dezembro",
  ];
  const WEEKDAYS = ["S", "T", "Q", "Q", "S", "S", "D"];

  $: todayIso = new Date().toISOString().slice(0, 10);

  async function load() {
    loading = true;
    error = null;
    try {
      cal = await fetchCalendar(viewYear, viewMonth);
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    actions = await fetchActions().catch(() => []);
    load();
  });

  function changeMonth(delta: number) {
    let m = viewMonth + delta;
    let y = viewYear;
    if (m < 1) { m = 12; y -= 1; }
    if (m > 12) { m = 1; y += 1; }
    viewMonth = m;
    viewYear = y;
    selectedDate = null;
    dayLogs = [];
    load();
  }

  // Build grid cells: leading blanks (start on monday) + days
  $: cells = (() => {
    if (!cal) return [];
    const first = new Date(cal.year, cal.month - 1, 1);
    // Convert sunday=0..saturday=6 to monday=0..sunday=6
    const dow = (first.getDay() + 6) % 7;
    const last = new Date(cal.year, cal.month, 0).getDate();
    const out: ({ iso: string; n: number } | null)[] = [];
    for (let i = 0; i < dow; i++) out.push(null);
    for (let d = 1; d <= last; d++) {
      const iso = `${cal.year}-${String(cal.month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      out.push({ iso, n: d });
    }
    return out;
  })();

  function isFuture(iso: string): boolean {
    return iso > todayIso;
  }

  async function pickDay(iso: string) {
    if (isFuture(iso)) {
      eventDate = iso;
      eventLabel = "";
      eventActionQuery = "";
      eventActionId = null;
      eventActionName = null;
      showEventForm = true;
      return;
    }
    selectedDate = iso;
    dayLogsLoading = true;
    try {
      const res = await fetchLogsByDate(iso);
      dayLogs = res.logs;
    } catch {
      dayLogs = [];
    } finally {
      dayLogsLoading = false;
    }
  }

  $: actionSuggestions = eventActionQuery.trim()
    ? actions
        .filter((a) => a.name.toLowerCase().includes(eventActionQuery.trim().toLowerCase()))
        .slice(0, 6)
    : [];

  function pickAction(a: Action) {
    eventActionId = a.id;
    eventActionName = a.name;
    eventActionQuery = a.name;
  }

  function clearAction() {
    eventActionId = null;
    eventActionName = null;
    eventActionQuery = "";
  }

  async function submitEvent() {
    if (eventBusy) return;
    if (!eventLabel.trim() && !eventActionId) return;
    eventBusy = true;
    try {
      const labelText = eventLabel.trim() || eventActionName || "";
      await createAgendaItem({
        start: "",
        end: null,
        day: "*",
        date: eventDate,
        label: labelText,
        label_kind: eventActionId ? "action" : "text",
        label_id: eventActionId,
      } as any);
      showEventForm = false;
      load();
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      eventBusy = false;
    }
  }

  // Year/month picker
  const YEARS = (() => {
    const y = now.getFullYear();
    const out: number[] = [];
    for (let i = y - 5; i <= y + 5; i++) out.push(i);
    return out;
  })();
  function selectMonth(y: number, m: number) {
    viewYear = y;
    viewMonth = m;
    showPicker = false;
    selectedDate = null;
    dayLogs = [];
    load();
  }

  function fmtDDMM(iso: string): string {
    if (!iso || iso.length < 10) return iso;
    return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
  }

  function display(content: string): string {
    const noteMatch = content.match(/^(.+?)\s*:\s*(.+)$/);
    if (noteMatch) return noteMatch[2].trim();
    const valueMatch = content.match(/^(\d+)\s*[xX]\s*(.+)$/);
    if (valueMatch) return valueMatch[2].trim();
    return content;
  }
</script>

<section class="page">
  <header class="topbar">
    <button class="nav" on:click={() => changeMonth(-1)} aria-label="anterior">‹</button>
    <button class="month-label" on:click={() => (showPicker = !showPicker)}>
      {MONTHS_PT[viewMonth - 1]} {viewYear}
    </button>
    <button class="nav" on:click={() => changeMonth(1)} aria-label="próximo">›</button>
    {#if showPicker}
      <div class="picker">
        <div class="picker-section">
          <span class="picker-label">ano</span>
          <div class="years">
            {#each YEARS as y (y)}
              <button class:active={y === viewYear} on:click={() => (viewYear = y)}>{y}</button>
            {/each}
          </div>
        </div>
        <div class="picker-section">
          <span class="picker-label">mês</span>
          <div class="months">
            {#each MONTHS_PT as m, i (i)}
              <button class:active={i + 1 === viewMonth} on:click={() => selectMonth(viewYear, i + 1)}>
                {m.slice(0, 3)}
              </button>
            {/each}
          </div>
        </div>
      </div>
    {/if}
  </header>

  {#if loading}
    <p class="muted">…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if cal}
    <div class="layout">
      <div class="cal">
        <div class="weekdays">
          {#each WEEKDAYS as w, i (i)}
            <span class="wd">{w}</span>
          {/each}
        </div>
        <div class="grid">
          {#each cells as c, i (i)}
            {#if c === null}
              <div class="cell blank"></div>
            {:else}
              {@const data = cal.days[c.iso]}
              {@const future = isFuture(c.iso)}
              {@const isToday = c.iso === todayIso}
              <button
                class="cell"
                class:has-logs={(data?.log_count ?? 0) > 0}
                class:has-events={(data?.events?.length ?? 0) > 0}
                class:future
                class:today={isToday}
                class:selected={selectedDate === c.iso}
                on:click={() => pickDay(c.iso)}
              >
                <span class="day-num">{c.n}</span>
                {#if (data?.events?.length ?? 0) > 0}
                  <span class="ev-labels">
                    {#each data.events.slice(0, 2) as ev (ev.id)}
                      <span class="ev-pill" title={ev.label}>{ev.label}</span>
                    {/each}
                    {#if data.events.length > 2}
                      <span class="ev-more">+{data.events.length - 2}</span>
                    {/if}
                  </span>
                {/if}
                <span class="markers">
                  {#if (data?.log_count ?? 0) > 0}<span class="dot logs" title="{data.log_count} log(s)"></span>{/if}
                </span>
              </button>
            {/if}
          {/each}
        </div>
      </div>

      <aside class="day-panel">
        {#if selectedDate}
          <header class="dp-head">
            <span class="dp-date">{fmtDDMM(selectedDate)}</span>
            <span class="dp-count">{dayLogs.length} logs</span>
          </header>
          {#if cal.days[selectedDate]?.events?.length}
            <div class="events">
              {#each cal.days[selectedDate].events as ev (ev.id)}
                <div class="event">
                  <span class="ev-tag">evento</span>
                  <span class="ev-label">{ev.label}</span>
                </div>
              {/each}
            </div>
          {/if}
          {#if dayLogsLoading}
            <p class="muted">…</p>
          {:else if dayLogs.length === 0}
            <p class="muted">sem logs</p>
          {:else}
            <ul class="logs">
              {#each dayLogs as l (l.id)}
                <li>
                  <span class="log-content">{display(l.content)}</span>
                  <span class="log-xp">+{l.xp}</span>
                </li>
              {/each}
            </ul>
          {/if}
        {:else}
          <p class="muted">selecione uma data</p>
          <p class="hint">clique em uma data passada para ver logs · clique em uma futura para criar evento</p>
        {/if}
      </aside>
    </div>
  {/if}
</section>

{#if showEventForm}
  <Modal title="evento especial" onClose={() => (showEventForm = false)}>
    <p class="ev-target">para <span class="hl">{fmtDDMM(eventDate)}</span></p>

    <div class="field">
      <span class="field-label">ação <span class="opt">(opcional)</span></span>
      {#if eventActionId}
        <div class="picked-action">
          <span class="kind">act</span>
          <span class="name">{eventActionName}</span>
          <button class="clear-btn" on:click={clearAction}>×</button>
        </div>
      {:else}
        <input
          type="text"
          class="ev-input"
          placeholder="buscar ação..."
          bind:value={eventActionQuery}
        />
        {#if actionSuggestions.length > 0}
          <ul class="suggestions">
            {#each actionSuggestions as a (a.id)}
              <li>
                <button type="button" on:click={() => pickAction(a)}>
                  <span class="kind">act</span>
                  <span class="name">{a.name}</span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}
    </div>

    <div class="field">
      <span class="field-label">label</span>
      <input
        type="text"
        class="ev-input"
        placeholder={eventActionName ? `ex.: com mãe (deixe vazio para usar "${eventActionName}")` : "texto livre"}
        bind:value={eventLabel}
      />
    </div>

    <div class="confirm-row">
      <button class="ghost" on:click={() => (showEventForm = false)}>cancelar</button>
      <button class="primary" on:click={submitEvent} disabled={eventBusy || (!eventLabel.trim() && !eventActionId)}>
        {eventBusy ? "..." : "criar"}
      </button>
    </div>
  </Modal>
{/if}

<style>
  .page {
    height: 100%;
    box-sizing: border-box;
    padding: 1.5rem 2rem;
    color: #e5e5e5;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .topbar {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 1rem;
    position: relative;
  }
  .month-label {
    background: transparent;
    border: 1px solid transparent;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.95rem;
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
  }
  .month-label:hover {
    border-color: #2a2a2a;
    color: #6cf;
  }
  .picker {
    position: absolute;
    top: 2.6rem;
    left: 2.5rem;
    background: #0d0d0d;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 0.85rem;
    z-index: 20;
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    min-width: 280px;
  }
  .picker-label {
    color: #555;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
    display: block;
  }
  .years, .months {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 0.25rem;
  }
  .picker button {
    background: transparent;
    border: 1px solid #1f1f1f;
    color: #888;
    padding: 0.3rem 0.4rem;
    border-radius: 3px;
    font: inherit;
    font-size: 0.75rem;
    cursor: pointer;
  }
  .picker button:hover { border-color: #6cf; color: #6cf; }
  .picker button.active { background: #0a1820; border-color: #6cf; color: #6cf; }
  .nav {
    background: #111;
    border: 1px solid #2a2a2a;
    color: #888;
    width: 28px;
    height: 28px;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
  }
  .nav:hover { color: #6cf; border-color: #6cf; }

  .layout {
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: 1rem;
    flex: 1;
    min-height: 0;
  }
  .cal {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .weekdays {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 0.4rem;
    margin-bottom: 0.4rem;
  }
  .wd {
    color: #444;
    text-align: center;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 0.4rem;
    flex: 1;
    min-height: 0;
  }
  .cell {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 4px;
    color: #888;
    font: inherit;
    cursor: pointer;
    padding: 0.4rem 0.5rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 50px;
    text-align: left;
  }
  .cell:hover:not(.blank):not(:disabled) {
    border-color: #6cf;
    color: #ccc;
  }
  .cell.blank {
    background: transparent;
    border: none;
    cursor: default;
  }
  .cell.has-logs {
    background: #0a1418;
    border-color: #1d3340;
    color: #ccc;
  }
  .cell.future {
    background: #0a0a0a;
    border-style: dashed;
  }
  .cell.future:hover {
    border-color: #888;
    color: #ccc;
  }
  .cell.today {
    border-color: #6cf;
    color: #6cf;
  }
  .cell.selected {
    border-color: #6cf;
    background: #0a2030;
    color: #6cf;
  }
  .day-num {
    font-size: 0.85rem;
    font-weight: bold;
  }
  .ev-labels {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    margin-top: 0.2rem;
    overflow: hidden;
  }
  .ev-pill {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    border-radius: 3px;
    padding: 0.05rem 0.3rem;
    font-size: 0.65rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ev-more {
    color: #f59e0b;
    font-size: 0.6rem;
  }
  .markers {
    display: flex;
    gap: 0.2rem;
    margin-top: auto;
  }
  .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
  }
  .dot.logs { background: #6cf; }
  .dot.ev { background: #f59e0b; }

  .day-panel {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    overflow-y: auto;
    min-height: 0;
  }
  .dp-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.6rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #1a1a1a;
  }
  .dp-date {
    color: #6cf;
    font-weight: bold;
    font-size: 0.95rem;
  }
  .dp-count { color: #555; font-size: 0.78rem; }

  .events {
    margin-bottom: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .event {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    padding: 0.4rem 0.5rem;
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 4px;
  }
  .ev-tag {
    color: #f59e0b;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .ev-label { color: #ddd; font-size: 0.85rem; }

  .logs {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .logs li {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.3rem 0;
    border-bottom: 1px solid #161616;
    font-size: 0.85rem;
  }
  .log-content { color: #ddd; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .log-xp { color: #555; font-size: 0.75rem; }
  .muted { color: #555; }
  .hint { color: #444; font-size: 0.78rem; margin-top: 0.5rem; }
  .error { color: #f66; }

  .ev-target { color: #888; margin: 0 0 0.85rem; }
  .field {
    margin-bottom: 0.85rem;
  }
  .field-label {
    display: block;
    color: #555;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    margin-bottom: 0.3rem;
  }
  .opt {
    color: #444;
    text-transform: none;
    letter-spacing: 0;
  }
  .picked-action {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: #0a1820;
    border: 1px solid #1d3340;
    border-radius: 4px;
    padding: 0.5rem 0.75rem;
  }
  .clear-btn {
    margin-left: auto;
    background: transparent;
    border: none;
    color: #555;
    font-size: 1.2rem;
    line-height: 1;
    cursor: pointer;
    padding: 0;
  }
  .clear-btn:hover { color: #f66; }
  .hl { color: #6cf; }
  .ev-input {
    width: 100%;
    box-sizing: border-box;
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    color: #ddd;
    padding: 0.55rem 0.75rem;
    font: inherit;
    font-size: 0.9rem;
    outline: none;
    margin-bottom: 0.5rem;
  }
  .ev-input:focus { border-color: #6cf; }
  .suggestions {
    list-style: none;
    margin: 0 0 0.75rem;
    padding: 0;
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    max-height: 160px;
    overflow-y: auto;
  }
  .suggestions li button {
    display: flex;
    width: 100%;
    align-items: baseline;
    gap: 0.5rem;
    padding: 0.4rem 0.6rem;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    font-size: 0.85rem;
    text-align: left;
    cursor: pointer;
  }
  .suggestions li button:hover { background: #141414; }
  .kind {
    color: #6cf;
    background: #0a1820;
    font-size: 0.65rem;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .name { color: #ddd; }

  .confirm-row {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
  }
  .ghost, .primary {
    padding: 0.5rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .ghost { background: transparent; color: #888; border-color: #333; }
  .ghost:hover { color: #ccc; border-color: #555; }
  .primary { background: #6cf; color: #0a0a0a; border-color: #6cf; }
  .primary:hover:not(:disabled) { background: #4ad; }
  .primary:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
