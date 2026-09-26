<script lang="ts">
  import { onMount } from "svelte";
  import { flip } from "svelte/animate";
  import {
    fetchActions,
    fetchUser,
    fetchAgendaToday,
    actOnAction,
    fetchActionWindow,
    formatCode,
    fold,
    type Action,
    type UserState,
    type AgendaToday,
  } from "./api";
  import LogsPanel from "./LogsPanel.svelte";
  import AgendaPanel from "./AgendaPanel.svelte";
  import ProjectsPanel from "./ProjectsPanel.svelte";
  import EmptySlot from "./EmptySlot.svelte";
  import WidgetTray from "./WidgetTray.svelte";
  import Modal from "./Modal.svelte";
  import DialPad from "./DialPad.svelte";
  import { primeAudio, keyFeedback, buzz } from "./dtmf";
  import { bumpLogs, bumpUser, userVersion } from "./store";

  export let onNav: (page: string, params?: Record<string, any>) => void = () => {};

  // ---- data fetching (existing) ----
  let actions: Action[] = [];
  let user: UserState | null = null;
  let agenda: AgendaToday = { day: null, items: [] };
  let query = "";
  let loading = true;
  let error: string | null = null;
  let nameEl: HTMLInputElement;
  let idEl: HTMLInputElement;
  let selectedAction: Action | null = null;
  let acting: string | null = null;
  let lastAct: { name: string; marks: number; window: number } | null = null;
  let lastActTimer: any = null;
  let lastUserVersion = 0;
  let pendingNoteFor: Action | null = null;
  let noteValue = "";
  let noteInputEl: HTMLInputElement | undefined;
  let chosenTier: number | null = null;
  let windowMarks: number | null = null;
  let tiersEl: HTMLDivElement | undefined;

  // ---- responsive ----
  const MOBILE_QUERY = "(max-width: 768px)";
  let isMobile = false;
  onMount(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    const apply = () => (isMobile = mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  });

  // ---- dial input ----
  // Two searches, one under the other: by name, and by id. The id buffer is an
  // action id and nothing else — no secondary operators, and matching an id goes
  // straight to the note modal. Whichever was typed in last is the one that filters.
  let dialBuffer = "";
  let padOpen = false;

  $: byPrefix = actions.filter((a) => a.id.startsWith(dialBuffer));

  function openPad() {
    if (padOpen) return;
    padOpen = true;
    primeAudio();            // the tap is the gesture browsers require
  }

  function togglePad() {
    if (padOpen) padOpen = false;
    else {
      openPad();
      setTimeout(() => idEl?.focus(), 0);
    }
  }

  function onNameInput() {
    dialBuffer = "";
  }

  /** Fire as soon as the buffer names exactly one action and nothing longer
   *  shares the prefix — the second half matters once ids become hierarchical. */
  function tryResolve() {
    if (!dialBuffer) return;
    const exact = actions.filter((a) => a.id === dialBuffer);
    const prefixed = actions.filter((a) => a.id.startsWith(dialBuffer));
    if (exact.length === 1 && prefixed.length === 1) forceResolve();
  }

  function forceResolve() {
    const exact = actions.filter((a) => a.id === dialBuffer);
    if (exact.length !== 1) return;
    const action = exact[0];
    dialBuffer = "";
    promptNote(action);
  }

  function pushDigit(d: string) {
    query = "";
    dialBuffer += d;
    tryResolve();
  }

  function popDigit() {
    dialBuffer = dialBuffer.slice(0, -1);
  }

  /** Physical numpad while the field has focus, so clicking keys stays optional. */
  function onDialKey(e: KeyboardEvent) {
    if (e.key >= "0" && e.key <= "9") {
      e.preventDefault();
      keyFeedback(e.key);
      pushDigit(e.key);
    } else if (e.key === "Backspace") {
      e.preventDefault();
      keyFeedback("*");
      popDigit();
    } else if (e.key === "Enter") {
      e.preventDefault();
      keyFeedback("#");
      forceResolve();
    } else if (e.key === "Escape") {
      e.preventDefault();
      buzz([15, 5, 15]);
      dialBuffer = "";
    } else if (e.key.length === 1) {
      // the field mirrors dialBuffer; block anything that would desync it
      e.preventDefault();
    }
  }

  const TYPE_LABEL: Record<number, string> = {
    0: "session", 1: "reps", 2: "seconds", 3: "minutes", 4: "hours",
    5: "letters", 6: "lines", 7: "words", 8: "group",
  };

  $: textQuery = fold(query.trim());
  $: filtered = dialBuffer ? byPrefix : actions.filter((a) => fold(a.name).includes(textQuery));

  $: if ($userVersion !== lastUserVersion) {
    lastUserVersion = $userVersion;
    if (lastUserVersion > 0) refreshUserAndAttrs();
  }

  async function refreshUserAndAttrs() {
    try {
      user = await fetchUser();
    } catch {}
  }

  onMount(async () => {
    // on a phone, focusing would throw the keyboard over the list before anything is asked
    if (!window.matchMedia(MOBILE_QUERY).matches) nameEl?.focus();
    try {
      const [actionsRes, userRes, agendaRes] = await Promise.all([
        fetchActions(),
        fetchUser(),
        fetchAgendaToday(),
      ]);
      actions = actionsRes;
      user = userRes;
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
    chosenTier = null;
    windowMarks = null;
    fetchActionWindow(action.id)
      .then((w) => {
        if (pendingNoteFor?.id === action.id) windowMarks = w.window_marks;
      })
      .catch(() => {});
    // focus the tiers, not the note: after dialing an id, a digit picks the tier
    setTimeout(() => tiersEl?.focus(), 0);
  }

  async function confirmNote() {
    if (!pendingNoteFor || chosenTier === null) return;
    const action = pendingNoteFor;
    const option = chosenTier;
    const note = noteValue.trim();
    pendingNoteFor = null;
    noteValue = "";
    await doAct(action, note ? { option, note } : { option });
  }

  async function doAct(action: Action, opts: { option: number; note?: string }) {
    if (acting) return;
    acting = action.id;
    try {
      const res = await actOnAction(action.id, opts);
      const idx = actions.findIndex((a) => a.id === action.id);
      if (idx >= 0) {
        actions[idx] = { ...actions[idx], value: res.value, score: res.score };
        actions = actions;
      }
      lastAct = { name: res.name, marks: res.marks, window: res.window_marks };
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

  /** 1–6 pick a tier, Enter acts, Escape closes — while focus is on the tiers. */
  function onTierKey(e: KeyboardEvent) {
    const count = pendingNoteFor?.tiers?.length ?? 0;
    if (e.key >= "1" && e.key <= String(count)) {
      e.preventDefault();
      chosenTier = Number(e.key) - 1;
    } else if (e.key === "Enter") {
      e.preventDefault();
      confirmNote();
    } else if (e.key === "Escape") {
      pendingNoteFor = null;
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
    { id: "projects", label: "projects", icon: "≡" },
  ];
  const SLOT_POS: Record<number, { row: number; col: number }> = {
    0: { row: 0, col: 0 }, 1: { row: 0, col: 1 },
    2: { row: 1, col: 0 }, 3: { row: 1, col: 1 },
  };

  let slots: (string | null)[] = ["actions", "agenda", "projects", "logs"];
  const MOBILE_SLOTS = ["actions", "logs"];
  $: visibleSlots = isMobile ? MOBILE_SLOTS : slots;
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
  {#if user}
    <div class="statusbar">
      <span class="sb-item"><span class="sb-label">tokens</span>{user.tokens}/{user.max_tokens}</span>
      <span class="sb-sep">·</span>
      <span class="sb-item"><span class="sb-label">energia</span>{user.energy}</span>
      {#if lastAct}
        <span class="sb-act">+{lastAct.marks} {lastAct.marks === 1 ? "marca" : "marcas"} · {lastAct.name} · {lastAct.window}/5 na janela</span>
      {/if}
    </div>
  {/if}

  <main class="grid-wrap">
    <div class="grid" class:stacked={isMobile}>
      {#each visibleSlots as widgetId, idx (idx)}
        <section
          class="cell"
          class:drag-over={!isMobile && dragOverIdx === idx && dragSource}
          on:dragover={(e) => !isMobile && onSlotDragOver(e, idx)}
          on:dragleave={onSlotDragLeave}
          on:drop={(e) => !isMobile && onSlotDrop(e, idx)}
        >
          {#if widgetId === null}
            <EmptySlot dragOver={dragOverIdx === idx && !!dragSource} />
          {:else}
            <div class="window">
              <div
                class="window-header"
                draggable={!isMobile}
                on:dragstart={(e) => startSlotDrag(e, idx)}
                on:dragend={cleanupDrag}
              >
                <span class="window-icon">{widgetById[widgetId]?.icon}</span>
                <span class="window-label">{widgetById[widgetId]?.label}</span>
                {#if !isMobile}<span class="grip">⋮⋮</span>{/if}
              </div>
              <div class="window-body">
                {#if widgetId === "actions"}
                  <div class="searches">
                    <div class="search-field">
                      <input
                        type="text"
                        placeholder="buscar ação..."
                        enterkeyhint="go"
                        bind:value={query}
                        bind:this={nameEl}
                        on:input={onNameInput}
                        on:focus={() => (padOpen = false)}
                        on:keydown={onSearchKey}
                      />
                    </div>
                    <div class="search-field" class:on={padOpen}>
                      <input
                        type="text"
                        class="dial"
                        placeholder="id da ação"
                        value={formatCode(dialBuffer)}
                        readonly={isMobile}
                        inputmode={isMobile ? "none" : "numeric"}
                        bind:this={idEl}
                        on:click={openPad}
                        on:keydown={onDialKey}
                      />
                      <button
                        type="button"
                        class="dial-toggle"
                        class:on={padOpen}
                        on:click={togglePad}
                        title={padOpen ? "fechar teclado" : "teclado numérico"}
                      >
                        123
                      </button>
                    </div>
                  </div>
                  {#if padOpen}
                    <DialPad
                      buffer={dialBuffer}
                      touch={isMobile}
                      onDigit={(d) => pushDigit(d)}
                      onBackspace={popDigit}
                      onClear={() => (dialBuffer = "")}
                      onConfirm={forceResolve}
                    />
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
                        <li class:patch={!!a.base_action_id}>
                          <button class="row" on:click={() => (selectedAction = a)}>
                            <span class="id">{formatCode(a.id)}</span>
                            <span class="name">{a.name}</span>
                            <span class="meta">d{a.diff}{a.token_gain ? ` · +${a.token_gain}t` : a.token_cost ? ` · -${a.token_cost}t` : ""}</span>
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
                {:else if widgetId === "projects"}
                    <ProjectsPanel />
                {/if}
              </div>
            </div>
          {/if}
        </section>
      {/each}
    </div>
    {#if !isMobile}
      <WidgetTray widgets={trayWidgets} onWidgetDragStart={startTrayDrag} />
    {/if}
  </main>
</div>

{#if pendingNoteFor}
  <Modal title="agir" onClose={() => (pendingNoteFor = null)}>
    <p class="note-target">para <span class="hl">{pendingNoteFor.name}</span></p>
    <p class="note-hint">
      teclas 1–6 · enter para agir · {windowMarks === null ? "…" : `${windowMarks}/5 marcas nas últimas 6h`}
    </p>
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="tiers" tabindex="0" role="radiogroup" aria-label="faixa" bind:this={tiersEl} on:keydown={onTierKey}>
      {#each pendingNoteFor.tiers ?? [] as t (t.index)}
        <button
          class="tier"
          class:chosen={chosenTier === t.index}
          role="radio"
          aria-checked={chosenTier === t.index}
          on:click={() => (chosenTier = t.index)}
        >
          <span class="tier-key">{t.index + 1}</span>
          <span class="tier-label">{t.label}</span>
          <span class="tier-marks">{t.marks}</span>
        </button>
      {/each}
    </div>
    <input
      class="note-input"
      type="text"
      placeholder="nota (opcional)"
      bind:value={noteValue}
      bind:this={noteInputEl}
      on:keydown={onNoteKey}
    />
    <div class="confirm-row">
      <button class="ghost" on:click={() => (pendingNoteFor = null)}>cancelar</button>
      <button class="primary" on:click={confirmNote} disabled={acting !== null || chosenTier === null}>
        {acting ? "..." : "agir"}
      </button>
    </div>
  </Modal>
{/if}

{#if selectedAction}
  <Modal title="action" onClose={() => (selectedAction = null)}>
    <dl class="details">
      <dt>id</dt><dd>{formatCode(selectedAction.id)}</dd>
      <dt>name</dt><dd class="hl">{selectedAction.name}</dd>
      <dt>type</dt><dd>{TYPE_LABEL[selectedAction.type] ?? selectedAction.type}</dd>
      <dt>diff</dt><dd>d{selectedAction.diff}</dd>
      <dt>execuções</dt><dd>{selectedAction.value}</dd>
      <dt>marcas</dt><dd>{selectedAction.score}</dd>
      {#if selectedAction.token_gain}<dt>rende</dt><dd>+{selectedAction.token_gain} tokens</dd>{/if}
      {#if selectedAction.token_cost}<dt>consome</dt><dd>{selectedAction.token_cost} tokens</dd>{/if}
      {#if selectedAction.attributes?.length}
        <dt>treina</dt><dd>{selectedAction.attributes.map((x) => x.name).join(", ")}</dd>
      {/if}
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
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1.5rem;
    height: 100%;
    box-sizing: border-box;
  }
  .statusbar {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    font-size: 0.78rem;
    color: #808080;
    flex-wrap: wrap;
  }
  .sb-label {
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.65rem;
    margin-right: 0.35rem;
  }
  .sb-sep { color: #333333; }
  .sb-act {
    color: #00e5ff;
    margin-left: auto;
    animation: fade 2.2s ease-out forwards;
    text-transform: lowercase;
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
  .cell {
    overflow: hidden;
    min-height: 0;
    position: relative;
  }
  .cell.drag-over::after {
    content: "";
    position: absolute;
    inset: 0;
    border: 2px dashed #00e5ff;
    border-radius: 6px;
    pointer-events: none;
    z-index: 5;
  }

  .window {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 6px;
    overflow: hidden;
  }
  .window-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.85rem;
    border-bottom: 1px solid #333333;
    background: #000000;
    cursor: grab;
    user-select: none;
  }
  .window-header:active {
    cursor: grabbing;
  }
  .window-icon {
    color: #00e5ff;
    font-size: 0.9rem;
  }
  .window-label {
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.7rem;
    flex: 1;
  }
  .grip {
    color: #333333;
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
    background: #000000;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #ffffff;
    padding: 0.55rem 0.75rem;
    font: inherit;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 0.9rem;
    outline: none;
    margin-bottom: 0.5rem;
  }
  input:focus {
    border-color: #00e5ff;
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
    border-bottom: 1px solid #333333;
  }
  .actions li .row {
    display: grid;
    grid-template-columns: 5.6rem 1fr auto;
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
    background: #000000;
  }
  .act-btn {
    background: transparent;
    border: none;
    color: #808080;
    font-size: 1.15rem;
    line-height: 1;
    padding: 0 0.6rem;
    cursor: pointer;
    transition: color 0.15s, transform 0.1s;
  }
  .act-btn:hover:not(:disabled) {
    color: #00e5ff;
    transform: translateX(2px);
  }
  .act-btn:disabled {
    color: #333333;
    cursor: default;
  }
  .id {
    color: #808080;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .name {
    color: #ffffff;
    text-transform: lowercase;
  }
  .meta {
    color: #808080;
    font-size: 0.78rem;
  }
  .actions li.empty-cta {
    display: grid;
    grid-template-columns: 5.6rem 1fr auto;
    gap: 1.5rem;
    align-items: baseline;
    padding: 0.5rem 0.75rem;
    cursor: pointer;
    color: #808080;
    background: #000000;
    border: 1px dashed #333333;
    border-radius: 4px;
    margin-top: 0.25rem;
    font-size: 0.85rem;
  }
  .actions li.empty-cta:hover {
    border-style: solid;
    color: #cccccc;
  }
  .actions li.empty-cta .id,
  .actions li.empty-cta .name { color: inherit; }
  .actions li.empty-cta .meta { color: #808080; }
  .new-action {
    margin-top: 0.6rem;
    padding: 0.55rem 0.75rem;
    background: transparent;
    border: 1px dashed #333333;
    border-radius: 4px;
    color: #808080;
    font: inherit;
    font-size: 0.85rem;
    letter-spacing: 0.05em;
    cursor: pointer;
    text-align: center;
    transition: all 0.15s;
  }
  .new-action:hover {
    background: #000000;
    border-color: #808080;
    border-style: solid;
    color: #cccccc;
  }
  .searches {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    margin-bottom: 0.5rem;
  }
  .search-field {
    display: flex;
    align-items: stretch;
    border: 1px solid #333333;
    border-radius: 4px;
  }
  .search-field:focus-within,
  .search-field.on { border-color: #00e5ff; }
  .search-field input {
    flex: 1;
    min-width: 0;
    border: none;
    margin: 0;
  }
  .search-field input.dial {
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.06em;
  }
  .dial-toggle {
    flex: 0 0 auto;
    padding: 0 0.75rem;
    background: transparent;
    border: none;
    border-left: 1px solid #333333;
    color: #808080;
    font: inherit;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: color 0.15s;
  }
  .dial-toggle:hover { color: #cccccc; }
  .dial-toggle.on { color: #00e5ff; }
  @keyframes fade {
    0%, 70% { opacity: 1; }
    100% { opacity: 0; }
  }

  .muted { color: #808080; }
  .error { color: #ff4d4d; }

  .grid.stacked {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    flex: none;
  }

  @media (max-width: 768px) {
    .layout {
      padding: 0.75rem;
      height: auto;
      min-height: 100%;
    }
    .grid-wrap { overflow: visible; }
    .grid.stacked .cell { min-height: 15rem; }
    .statusbar { font-size: 0.72rem; }
    .sb-act { margin-left: 0; width: 100%; }
  }

  .details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.4rem 1rem;
    margin: 0 0 1.25rem;
  }
  .details dt {
    color: #808080;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
  }
  .details dd { color: #ffffff; margin: 0; font-size: 0.9rem; }
  .hl { color: #00e5ff; text-transform: lowercase; }
  .note-target {
    color: #808080;
    margin: 0 0 0.4rem;
    font-size: 0.9rem;
  }
  .note-hint {
    color: #808080;
    margin: 0 0 0.75rem;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .note-input {
    width: 100%;
    box-sizing: border-box;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #ffffff;
    padding: 0.6rem 0.85rem;
    font: inherit;
    font-size: 0.95rem;
    outline: none;
    margin-bottom: 1rem;
  }
  .note-input:focus { border-color: #00e5ff; }
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
    color: #808080;
    border-color: #333333;
  }
  .ghost:hover {
    color: #cccccc;
    border-color: #808080;
  }
  .primary {
    background: #000000;
    color: #ffffff;
    border-color: #ffffff;
  }
  .primary:hover:not(:disabled) {
    background: #ffffff;
    color: #000000;
  }
  .primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  /* a patch sits right under its base, one step in */
  .actions li.patch .name { position: relative; padding-left: 0.9rem; }
  .actions li.patch .name::before { content: "↳"; position: absolute; left: 0; color: #808080; }
  .tiers {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.4rem;
    margin: 0 0 0.85rem;
    outline: none;
  }
  .tier {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 6px;
    color: #ffffff;
    padding: 0.55rem 0.6rem;
    font: inherit;
    font-size: 0.85rem;
    text-align: left;
    cursor: pointer;
  }
  .tier:hover { border-color: #808080; }
  .tier.chosen { border-color: #00e5ff; color: #00e5ff; }
  .tier-key { color: #808080; font-size: 0.7rem; }
  .tier-label { flex: 1; min-width: 0; }
  .tier-marks { color: #00e5ff; font-size: 0.75rem; font-variant-numeric: tabular-nums; }
  @media (max-width: 520px) {
    .tiers { grid-template-columns: repeat(2, 1fr); }
  }
</style>
