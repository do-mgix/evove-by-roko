<script lang="ts">
  import { onMount } from "svelte";
  import { flip } from "svelte/animate";
  import {
    fetchActions,
    fetchUser,
    fetchAttributes,
    fetchAgendaToday,
    actOnAction,
    type Action,
    type UserState,
    type Attribute,
    type AgendaToday,
  } from "./api";
  import UserPanel from "./UserPanel.svelte";
  import LogsPanel from "./LogsPanel.svelte";
  import AgendaPanel from "./AgendaPanel.svelte";
  import EmptySlot from "./EmptySlot.svelte";
  import WidgetTray from "./WidgetTray.svelte";
  import Modal from "./Modal.svelte";
  import { bumpLogs, bumpUser, userVersion } from "./store";

  export let onNav: (page: string, params?: Record<string, any>) => void = () => {};

  // ---- data fetching (existing) ----
  let actions: Action[] = [];
  let attributes: Attribute[] = [];
  let user: UserState | null = null;
  let agenda: AgendaToday = { day: null, items: [] };
  let query = "";
  let loading = true;
  let error: string | null = null;
  let inputEl: HTMLInputElement;
  let selectedAction: Action | null = null;
  let acting: string | null = null;
  let lastAct: { name: string; diff: number } | null = null;
  let lastActTimer: any = null;
  let lastUserVersion = 0;
  let pendingNoteFor: Action | null = null;
  let noteValue = "";
  let noteInputEl: HTMLInputElement | undefined;

  const TYPE_LABEL: Record<number, string> = {
    0: "session", 1: "reps", 2: "seconds", 3: "minutes", 4: "hours",
    5: "letters", 6: "lines", 7: "words", 8: "group",
  };

  $: filtered = actions.filter((a) =>
    a.name.toLowerCase().includes(query.trim().toLowerCase())
  );

  $: if ($userVersion !== lastUserVersion) {
    lastUserVersion = $userVersion;
    if (lastUserVersion > 0) refreshUserAndAttrs();
  }

  async function refreshUserAndAttrs() {
    try {
      const [u, a] = await Promise.all([fetchUser(), fetchAttributes()]);
      user = u;
      attributes = a;
    } catch {}
  }

  onMount(async () => {
    inputEl?.focus();
    try {
      const [actionsRes, userRes, attrsRes, agendaRes] = await Promise.all([
        fetchActions(),
        fetchUser(),
        fetchAttributes(),
        fetchAgendaToday(),
      ]);
      actions = actionsRes;
      user = userRes;
      attributes = attrsRes;
      agenda = agendaRes;
    } catch (e: any) {
      error = e?.message ?? "Erro ao carregar dados";
    } finally {
      loading = false;
    }
  });

  function promptNote(action: Action) {
    pendingNoteFor = action;
    noteValue = "";
    setTimeout(() => noteInputEl?.focus(), 0);
  }

  async function confirmNote() {
    if (!pendingNoteFor) return;
    const action = pendingNoteFor;
    const note = noteValue.trim();
    pendingNoteFor = null;
    noteValue = "";
    await doAct(action, note ? { note } : {});
  }

  async function doAct(action: Action, opts: { value?: number; note?: string } = {}) {
    if (acting) return;
    acting = action.id;
    try {
      const res = await actOnAction(action.id, opts);
      const idx = actions.findIndex((a) => a.id === action.id);
      if (idx >= 0) {
        actions[idx] = { ...actions[idx], value: res.value, score: res.score };
        actions = actions;
      }
      lastAct = { name: res.name, diff: Math.round(res.score_diff) };
      bumpLogs();
      bumpUser();
      if (lastActTimer) clearTimeout(lastActTimer);
      lastActTimer = setTimeout(() => (lastAct = null), 2200);
      if (selectedAction?.id === action.id) {
        selectedAction = { ...selectedAction, value: res.value, score: res.score };
      }
    } catch (e: any) {
      error = e?.message ?? "erro ao agir";
    } finally {
      acting = null;
    }
  }

  function onSearchKey(e: KeyboardEvent) {
    if (e.key === "Enter" && filtered.length === 1) {
      promptNote(filtered[0]);
      query = "";
    }
  }

  function onNoteKey(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      confirmNote();
    } else if (e.key === "Escape") {
      pendingNoteFor = null;
    }
  }

  // ---- slots & D&D ----
  // 4 slots indexed: 0=top-left, 1=top-right, 2=bottom-left, 3=bottom-right
  const WIDGETS = [
    { id: "actions", label: "action", icon: "◆" },
    { id: "agenda", label: "agenda", icon: "▤" },
    { id: "logs", label: "logs", icon: "≡" },
  ];
  const SLOT_POS: Record<number, { row: number; col: number }> = {
    0: { row: 0, col: 0 }, 1: { row: 0, col: 1 },
    2: { row: 1, col: 0 }, 3: { row: 1, col: 1 },
  };

  let slots: (string | null)[] = ["actions", "agenda", null, "logs"];
  let dragSource: { kind: "tray" | "slot"; widgetId: string; from?: number } | null = null;
  let dragOverIdx: number | null = null;
  let dragOverPos: { x: number; y: number } | null = null; // 0..1 in slot

  $: trayWidgets = WIDGETS.filter((w) => !slots.includes(w.id));
  $: widgetById = Object.fromEntries(WIDGETS.map((w) => [w.id, w]));

  function startSlotDrag(e: DragEvent, slotIdx: number) {
    const widgetId = slots[slotIdx];
    if (!widgetId) return;
    dragSource = { kind: "slot", widgetId, from: slotIdx };
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", widgetId);
    }
  }

  function startTrayDrag(e: DragEvent, widgetId: string) {
    dragSource = { kind: "tray", widgetId };
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "copy";
      e.dataTransfer.setData("text/plain", widgetId);
    }
  }

  function onSlotDragOver(e: DragEvent, slotIdx: number) {
    if (!dragSource) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = dragSource.kind === "tray" ? "copy" : "move";
    dragOverIdx = slotIdx;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    dragOverPos = {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
  }

  function onSlotDragLeave() {
    dragOverIdx = null;
    dragOverPos = null;
  }

  function pickEmptyByDirection(empties: number[], target: number, pos: { x: number; y: number } | null): number {
    if (empties.length === 1) return empties[0];
    if (!pos) return empties[0];
    // Drop direction: where on target the user is hovering. Push displaced AWAY from that side.
    const t = SLOT_POS[target];
    // Score each empty by alignment with desired displacement
    const horizontalBias = pos.x; // 0=left, 1=right
    const verticalBias = pos.y; // 0=top, 1=bottom
    let best = empties[0];
    let bestScore = -Infinity;
    for (const idx of empties) {
      const e = SLOT_POS[idx];
      const dCol = e.col - t.col; // -1..1
      const dRow = e.row - t.row;
      // Higher score if empty is on the OPPOSITE side of where user hovered
      const score =
        (horizontalBias > 0.5 ? -dCol : dCol) +
        (verticalBias > 0.5 ? -dRow : dRow);
      if (score > bestScore) {
        bestScore = score;
        best = idx;
      }
    }
    return best;
  }

  function onSlotDrop(e: DragEvent, slotIdx: number) {
    if (!dragSource) return;
    e.preventDefault();
    const { kind, widgetId, from } = dragSource;
    const next = slots.slice();

    if (kind === "slot") {
      if (from === slotIdx) {
        cleanupDrag();
        return;
      }
      const targetWidget = next[slotIdx];
      next[from!] = targetWidget; // swap (source is always the only empty after move)
      next[slotIdx] = widgetId;
    } else {
      // from tray
      const targetWidget = next[slotIdx];
      next[slotIdx] = widgetId;
      if (targetWidget) {
        // displace existing to nearest empty by direction
        const empties: number[] = [];
        for (let i = 0; i < 4; i++) if (i !== slotIdx && next[i] === null) empties.push(i);
        if (empties.length > 0) {
          const dest = pickEmptyByDirection(empties, slotIdx, dragOverPos);
          next[dest] = targetWidget;
        }
      }
    }

    slots = next;
    cleanupDrag();
  }

  function cleanupDrag() {
    dragSource = null;
    dragOverIdx = null;
    dragOverPos = null;
  }
</script>

<div class="layout">
  <main class="grid-wrap">
    <div class="grid">
      {#each slots as widgetId, idx (idx)}
        <section
          class="cell"
          class:drag-over={dragOverIdx === idx && dragSource}
          on:dragover={(e) => onSlotDragOver(e, idx)}
          on:dragleave={onSlotDragLeave}
          on:drop={(e) => onSlotDrop(e, idx)}
        >
          {#if widgetId === null}
            <EmptySlot dragOver={dragOverIdx === idx && !!dragSource} />
          {:else}
            <div class="window">
              <div
                class="window-header"
                draggable="true"
                on:dragstart={(e) => startSlotDrag(e, idx)}
                on:dragend={cleanupDrag}
              >
                <span class="window-icon">{widgetById[widgetId]?.icon}</span>
                <span class="window-label">{widgetById[widgetId]?.label}</span>
                <span class="grip">⋮⋮</span>
              </div>
              <div class="window-body">
                {#if widgetId === "actions"}
                  <input
                    type="text"
                    placeholder="Buscar ação..."
                    bind:value={query}
                    bind:this={inputEl}
                    on:keydown={onSearchKey}
                  />
                  {#if lastAct}
                    <div class="last-act">+{lastAct.diff} xp · {lastAct.name}</div>
                  {/if}
                  {#if loading}
                    <p class="muted">carregando...</p>
                  {:else if error}
                    <p class="error">{error}</p>
                  {:else if actions.length === 0}
                    <ul class="actions">
                      <li
                        class="empty-cta"
                        on:click={() => onNav("shop", { section: "actions" })}
                        on:keydown={(e) => e.key === "Enter" && onNav("shop", { section: "actions" })}
                        role="button"
                        tabindex="0"
                      >
                        <span class="id">+</span>
                        <span class="name">nova ação</span>
                        <span class="meta">→ shop</span>
                      </li>
                    </ul>
                  {:else if filtered.length === 0}
                    <p class="muted">nenhuma ação encontrada</p>
                  {:else}
                    <ul class="actions">
                      {#each filtered as a (a.id)}
                        <li>
                          <button class="row" on:click={() => (selectedAction = a)}>
                            <span class="id">{a.id}</span>
                            <span class="name">{a.name}</span>
                            <span class="meta">d{a.diff}{a.token_cost ? ` · ${a.token_cost}t` : ""}</span>
                          </button>
                          <button
                            class="act-btn"
                            on:click|stopPropagation={() => promptNote(a)}
                            disabled={acting === a.id}
                            title="agir"
                          >
                            {acting === a.id ? "…" : "→"}
                          </button>
                        </li>
                      {/each}
                    </ul>
                    <button class="new-action" on:click={() => onNav("shop", { section: "actions" })}>
                      + nova ação
                    </button>
                  {/if}
                {:else if widgetId === "agenda"}
                  <AgendaPanel {agenda} />
                {:else if widgetId === "logs"}
                  <LogsPanel />
                {/if}
              </div>
            </div>
          {/if}
        </section>
      {/each}
    </div>
    <WidgetTray widgets={trayWidgets} onWidgetDragStart={startTrayDrag} />
  </main>

  <aside class="sidebar">
    {#if user}
      <UserPanel {user} {attributes} />
    {/if}
  </aside>
</div>

{#if pendingNoteFor}
  <Modal title="nota" onClose={() => (pendingNoteFor = null)}>
    <p class="note-target">para <span class="hl">{pendingNoteFor.name}</span></p>
    <p class="note-hint">número ou texto · Enter para confirmar</p>
    <input
      class="note-input"
      type="text"
      bind:value={noteValue}
      bind:this={noteInputEl}
      on:keydown={onNoteKey}
    />
    <div class="confirm-row">
      <button class="ghost" on:click={() => (pendingNoteFor = null)}>cancelar</button>
      <button class="primary" on:click={confirmNote} disabled={acting !== null}>
        {acting ? "..." : "agir"}
      </button>
    </div>
  </Modal>
{/if}

{#if selectedAction}
  <Modal title="action" onClose={() => (selectedAction = null)}>
    <dl class="details">
      <dt>id</dt><dd>{selectedAction.id}</dd>
      <dt>name</dt><dd class="hl">{selectedAction.name}</dd>
      <dt>type</dt><dd>{TYPE_LABEL[selectedAction.type] ?? selectedAction.type}</dd>
      <dt>diff</dt><dd>d{selectedAction.diff}</dd>
      <dt>value</dt><dd>{selectedAction.value}</dd>
      <dt>score</dt><dd>{selectedAction.score} xp</dd>
      {#if selectedAction.token_cost}<dt>custo</dt><dd>{selectedAction.token_cost} tokens</dd>{/if}
    </dl>
    <div class="confirm-row">
      <button class="ghost" on:click={() => (selectedAction = null)}>fechar</button>
      <button
        class="primary"
        on:click={() => {
          if (selectedAction) {
            const a = selectedAction;
            selectedAction = null;
            promptNote(a);
          }
        }}
        disabled={acting !== null}
      >
        {acting ? "..." : "agir →"}
      </button>
    </div>
  </Modal>
{/if}

<style>
  .layout {
    display: grid;
    grid-template-columns: 1fr 240px;
    gap: 1rem;
    padding: 1.5rem;
    height: 100%;
    box-sizing: border-box;
  }
  .grid-wrap {
    display: flex;
    flex-direction: column;
    min-height: 0;
    gap: 0.75rem;
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
    gap: 1rem;
    flex: 1;
    min-height: 0;
  }
  .sidebar {
    min-height: 0;
    overflow: hidden;
  }
  .cell {
    overflow: hidden;
    min-height: 0;
    position: relative;
  }
  .cell.drag-over::after {
    content: "";
    position: absolute;
    inset: 0;
    border: 2px dashed #6cf;
    border-radius: 6px;
    pointer-events: none;
    z-index: 5;
  }

  .window {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    overflow: hidden;
  }
  .window-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.85rem;
    border-bottom: 1px solid #1a1a1a;
    background: #0a0a0a;
    cursor: grab;
    user-select: none;
  }
  .window-header:active {
    cursor: grabbing;
  }
  .window-icon {
    color: #6cf;
    font-size: 0.9rem;
  }
  .window-label {
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.7rem;
    flex: 1;
  }
  .grip {
    color: #2a2a2a;
    font-size: 0.7rem;
    letter-spacing: -0.1em;
  }
  .window-body {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding: 0.6rem 0.85rem;
  }

  input {
    background: #111;
    border: 1px solid #333;
    border-radius: 4px;
    color: #e5e5e5;
    padding: 0.55rem 0.75rem;
    font: inherit;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.9rem;
    outline: none;
    margin-bottom: 0.5rem;
  }
  input:focus {
    border-color: #6cf;
  }
  .actions {
    list-style: none;
    padding: 0;
    margin: 0;
    overflow-y: auto;
    flex: 1;
  }
  .actions li {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid #161616;
  }
  .actions li .row {
    display: grid;
    grid-template-columns: 3.5rem 1fr auto;
    gap: 0.7rem;
    align-items: baseline;
    flex: 1;
    padding: 0.35rem 0.5rem;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    font-size: 0.85rem;
    text-align: left;
    cursor: pointer;
  }
  .actions li .row:hover {
    background: #141414;
  }
  .act-btn {
    background: transparent;
    border: none;
    color: #444;
    font-size: 1.15rem;
    line-height: 1;
    padding: 0 0.6rem;
    cursor: pointer;
    transition: color 0.15s, transform 0.1s;
  }
  .act-btn:hover:not(:disabled) {
    color: #6cf;
    transform: translateX(2px);
  }
  .act-btn:disabled {
    color: #222;
    cursor: default;
  }
  .id {
    color: #555;
  }
  .name {
    color: #e5e5e5;
  }
  .meta {
    color: #666;
    font-size: 0.78rem;
  }
  .actions li.empty-cta {
    display: grid;
    grid-template-columns: 3.5rem 1fr auto;
    gap: 1.5rem;
    align-items: baseline;
    padding: 0.5rem 0.75rem;
    cursor: pointer;
    color: #888;
    background: #0f0f0f;
    border: 1px dashed #2a2a2a;
    border-radius: 4px;
    margin-top: 0.25rem;
    font-size: 0.85rem;
  }
  .actions li.empty-cta:hover {
    border-style: solid;
    color: #ccc;
  }
  .actions li.empty-cta .id,
  .actions li.empty-cta .name { color: inherit; }
  .actions li.empty-cta .meta { color: #555; }
  .new-action {
    margin-top: 0.6rem;
    padding: 0.55rem 0.75rem;
    background: transparent;
    border: 1px dashed #2a2a2a;
    border-radius: 4px;
    color: #888;
    font: inherit;
    font-size: 0.85rem;
    letter-spacing: 0.05em;
    cursor: pointer;
    text-align: center;
    transition: all 0.15s;
  }
  .new-action:hover {
    background: #141414;
    border-color: #555;
    border-style: solid;
    color: #ccc;
  }
  .last-act {
    color: #6cf;
    font-size: 0.78rem;
    margin: 0 0 0.5rem;
    animation: fade 2.2s ease-out forwards;
  }
  @keyframes fade {
    0%, 70% { opacity: 1; }
    100% { opacity: 0; }
  }

  .muted { color: #666; }
  .error { color: #f66; }

  .details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.4rem 1rem;
    margin: 0 0 1.25rem;
  }
  .details dt {
    color: #555;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
  }
  .details dd { color: #ddd; margin: 0; font-size: 0.9rem; }
  .hl { color: #6cf; }
  .note-target {
    color: #888;
    margin: 0 0 0.4rem;
    font-size: 0.9rem;
  }
  .note-hint {
    color: #555;
    margin: 0 0 0.75rem;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .note-input {
    width: 100%;
    box-sizing: border-box;
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    color: #ddd;
    padding: 0.6rem 0.85rem;
    font: inherit;
    font-size: 0.95rem;
    outline: none;
    margin-bottom: 1rem;
  }
  .note-input:focus { border-color: #6cf; }
  .confirm-row { display: flex; gap: 0.5rem; justify-content: flex-end; }
  .ghost, .primary {
    padding: 0.5rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.15s;
  }
  .ghost {
    background: transparent;
    color: #888;
    border-color: #333;
  }
  .ghost:hover {
    color: #ccc;
    border-color: #555;
  }
  .primary {
    background: #6cf;
    color: #0a0a0a;
    border-color: #6cf;
  }
  .primary:hover:not(:disabled) {
    background: #4ad;
  }
  .primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
</style>
