<script lang="ts">
  import { onMount } from "svelte";
  import Modal from "./Modal.svelte";
  import { fetchActions, fetchAttributes, fetchAttributeTree, flattenConceptualNodes, createAgendaItem, updateAgendaItem, type AgendaItem } from "./api";

  export let onClose: () => void;
  export let onCreated: (item: AgendaItem) => void;
  export let initialItem: AgendaItem | null = null;
  export let onUpdated: ((item: AgendaItem) => void) | null = null;

  const editMode = initialItem != null;

  function parseHMFromStr(s: string | null | undefined): [number | null, number | null] {
    if (!s || s.length < 4) return [null, null];
    const t = s.replace(":", "");
    const h = parseInt(t.slice(0, 2), 10);
    const m = parseInt(t.slice(2, 4), 10);
    if (isNaN(h) || isNaN(m)) return [null, null];
    return [h, m];
  }

  const [initStartH, initStartM] = parseHMFromStr(initialItem?.start ?? null);
  const [initEndH, initEndM] = parseHMFromStr(initialItem?.end ?? null);

  let startH: number | null = initStartH;
  let startM: number | null = initStartM;
  let endEnabled = initEndH != null;
  let endH: number | null = initEndH;
  let endM: number | null = initEndM;
  let selectedDays: Set<string> = initialItem?.day
    ? new Set([initialItem.day])
    : new Set(["*"]);
  let label = initialItem?.label ?? "";
  let suggestions: { kind: "action" | "attribute" | "concept"; id: string; name: string; path?: string }[] = [];
  let busy = false;
  let error: string | null = null;

  const DAYS = [
    { value: "SEG", letter: "S" },
    { value: "TER", letter: "T" },
    { value: "QUA", letter: "Q" },
    { value: "QUI", letter: "Q" },
    { value: "SEX", letter: "S" },
    { value: "SAB", letter: "S" },
    { value: "DOM", letter: "D" },
  ];

  const DAY_FULL: Record<string, string> = {
    "*": "diário", SEG: "segunda", TER: "terça", QUA: "quarta",
    QUI: "quinta", SEX: "sexta", SAB: "sábado", DOM: "domingo",
  };

  function getVal(part: "h" | "m", which: "start" | "end"): number | null {
    if (which === "start") return part === "h" ? startH : startM;
    return part === "h" ? endH : endM;
  }
  function setVal(part: "h" | "m", which: "start" | "end", v: number | null) {
    if (which === "start") {
      if (part === "h") startH = v; else startM = v;
    } else {
      if (part === "h") endH = v; else endM = v;
    }
  }

  function tick(part: "h" | "m", which: "start" | "end", delta: number) {
    const max = part === "h" ? 23 : 59;
    const cur = getVal(part, which) ?? 0;
    const next = (cur + delta + max + 1) % (max + 1);
    setVal(part, which, next);
  }

  function pad(n: number): string {
    return n.toString().padStart(2, "0");
  }
  function showVal(n: number | null, focused: boolean): string {
    if (n === null) return "";
    return focused ? String(n) : pad(n);
  }

  let focStartH = false, focStartM = false, focEndH = false, focEndM = false;

  function clampNum(v: number, max: number): number {
    if (Number.isNaN(v)) return 0;
    if (v < 0) return 0;
    if (v > max) return max;
    return v;
  }

  function onTimeKey(e: KeyboardEvent, part: "h" | "m", which: "start" | "end") {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      tick(part, which, 1);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      tick(part, which, -1);
    }
  }

  function onTimeInput(e: Event, part: "h" | "m", which: "start" | "end") {
    const raw = (e.target as HTMLInputElement).value.trim();
    if (raw === "") {
      setVal(part, which, null);
      return;
    }
    const n = parseInt(raw, 10);
    const max = part === "h" ? 23 : 59;
    setVal(part, which, clampNum(n, max));
  }

  function toggleDay(d: string) {
    const next = new Set(selectedDays);
    if (d === "*") {
      next.clear();
      next.add("*");
    } else {
      next.delete("*");
      if (next.has(d)) next.delete(d);
      else next.add(d);
      if (next.size === 0) next.add("*");
    }
    selectedDays = next;
  }

  onMount(async () => {
    try {
      const [actions, attrs, tree] = await Promise.all([
        fetchActions().catch(() => []),
        fetchAttributes().catch(() => []),
        fetchAttributeTree().catch(() => ({ roots: [] as any })),
      ]);
      const conceptNodes = flattenConceptualNodes(tree as any);
      suggestions = [
        ...conceptNodes.map((c) => ({ kind: "concept" as const, id: c.key, name: c.name, path: c.path })),
        ...actions.map((a) => ({ kind: "action" as const, id: a.id, name: a.name })),
        ...attrs.map((a) => ({ kind: "attribute" as const, id: a.key, name: a.name })),
      ];
    } catch {}
  });

  $: filteredSuggestions = label.trim()
    ? suggestions
        .filter((s) => s.name.toLowerCase().includes(label.trim().toLowerCase()))
        .slice(0, 8)
    : [];

  function pick(s: { kind: string; id: string; name: string }) {
    label = s.name;
  }

  async function submit() {
    if (busy) return;
    error = null;
    if (!label.trim()) { error = "label obrigatório"; return; }
    if (startH === null || startM === null) { error = "horário de início obrigatório"; return; }
    if (endEnabled && (endH === null || endM === null)) { error = "horário de fim incompleto"; return; }
    const startStr = pad(startH) + pad(startM);
    const endStr = endEnabled ? pad(endH!) + pad(endM!) : null;
    const matched = suggestions.find((s) => s.name.toLowerCase() === label.trim().toLowerCase());
    busy = true;
    try {
      if (editMode && initialItem?.id) {
        const updated = await updateAgendaItem(initialItem.id, {
          start: startStr,
          end: endStr,
          day: Array.from(selectedDays)[0] ?? "*",
          label: matched?.name ?? label.trim(),
          label_kind: matched?.kind ?? initialItem.label_kind ?? "text",
          label_id: matched?.id ?? null,
        });
        onUpdated?.(updated);
        onClose();
      } else {
        const days = Array.from(selectedDays);
        const created: AgendaItem[] = [];
        for (const d of days) {
          const item = await createAgendaItem({
            start: startStr,
            end: endStr,
            day: d,
            label: matched?.name ?? label.trim(),
            label_kind: matched?.kind ?? "text",
            label_id: matched?.id ?? null,
          });
          created.push(item);
        }
        created.forEach(onCreated);
        onClose();
      }
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      busy = false;
    }
  }
</script>

<Modal title={editMode ? "editar item" : "novo item de agenda"} {onClose}>
  <div class="form">
    <div class="row">
      <span class="row-label">início</span>
      <div class="time-row">
        <div class="time-picker">
          <div class="tp-col">
            <button type="button" class="tp-arrow" on:click={() => tick("h", "start", 1)} tabindex="-1">▲</button>
            <input
              class="tp-val"
              type="text"
              inputmode="numeric"
              maxlength="2"
              placeholder="00"
              value={showVal(startH, focStartH)}
              on:focus={() => (focStartH = true)}
              on:blur={() => (focStartH = false)}
              on:input={(e) => onTimeInput(e, "h", "start")}
              on:keydown={(e) => onTimeKey(e, "h", "start")}
            />
            <button type="button" class="tp-arrow" on:click={() => tick("h", "start", -1)} tabindex="-1">▼</button>
          </div>
          <span class="tp-sep">:</span>
          <div class="tp-col">
            <button type="button" class="tp-arrow" on:click={() => tick("m", "start", 1)} tabindex="-1">▲</button>
            <input
              class="tp-val"
              type="text"
              inputmode="numeric"
              maxlength="2"
              placeholder="00"
              value={showVal(startM, focStartM)}
              on:focus={() => (focStartM = true)}
              on:blur={() => (focStartM = false)}
              on:input={(e) => onTimeInput(e, "m", "start")}
              on:keydown={(e) => onTimeKey(e, "m", "start")}
            />
            <button type="button" class="tp-arrow" on:click={() => tick("m", "start", -1)} tabindex="-1">▼</button>
          </div>
        </div>
        <span class="format-hint">24h</span>
      </div>
    </div>

    <div class="row">
      <span class="row-label">fim</span>
      <div class="end-wrap">
        <label class="end-toggle">
          <input type="checkbox" bind:checked={endEnabled} />
          <span>{endEnabled ? "definido" : "sem fim"}</span>
        </label>
        {#if endEnabled}
          <div class="time-picker">
            <div class="tp-col">
              <button type="button" class="tp-arrow" on:click={() => tick("h", "end", 1)} tabindex="-1">▲</button>
              <input
                class="tp-val"
                type="text"
                inputmode="numeric"
                maxlength="2"
                placeholder="00"
                value={showVal(endH, focEndH)}
                on:focus={() => (focEndH = true)}
                on:blur={() => (focEndH = false)}
                on:input={(e) => onTimeInput(e, "h", "end")}
                on:keydown={(e) => onTimeKey(e, "h", "end")}
              />
              <button type="button" class="tp-arrow" on:click={() => tick("h", "end", -1)} tabindex="-1">▼</button>
            </div>
            <span class="tp-sep">:</span>
            <div class="tp-col">
              <button type="button" class="tp-arrow" on:click={() => tick("m", "end", 1)} tabindex="-1">▲</button>
              <input
                class="tp-val"
                type="text"
                inputmode="numeric"
                maxlength="2"
                placeholder="00"
                value={showVal(endM, focEndM)}
                on:focus={() => (focEndM = true)}
                on:blur={() => (focEndM = false)}
                on:input={(e) => onTimeInput(e, "m", "end")}
                on:keydown={(e) => onTimeKey(e, "m", "end")}
              />
              <button type="button" class="tp-arrow" on:click={() => tick("m", "end", -1)} tabindex="-1">▼</button>
            </div>
          </div>
        {/if}
      </div>
    </div>

    <div class="row">
      <span class="row-label">dia</span>
      <div class="day-picker">
        {#each DAYS as d (d.value)}
          <button
            type="button"
            class="day-btn"
            class:active={selectedDays.has(d.value)}
            on:click={() => toggleDay(d.value)}
            title={DAY_FULL[d.value]}
          >
            {d.letter}
          </button>
        {/each}
        <button
          type="button"
          class="day-btn all"
          class:active={selectedDays.has("*")}
          on:click={() => toggleDay("*")}
          title="diário"
          aria-label="diário"
        >
          ◼
        </button>
      </div>
    </div>

    <div class="row label-row">
      <span class="row-label">label</span>
      <div class="autocomplete">
        <input type="text" placeholder="ação, conceitual ou texto" bind:value={label} />
        {#if filteredSuggestions.length > 0 && label.trim()}
          <ul class="dropdown">
            {#each filteredSuggestions as s (s.kind + ':' + s.id)}
              <li>
                <button type="button" on:click={() => pick(s)}>
                  <span class="kind {s.kind}">{s.kind === "action" ? "act" : s.kind === "concept" ? "cnc" : "atr"}</span>
                  <span class="name">{s.kind === "concept" && s.path ? s.path : s.name}</span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>

    {#if error}<p class="err">{error}</p>{/if}
    <div class="actions">
      <button class="ghost" on:click={onClose}>cancelar</button>
      <button class="primary" on:click={submit} disabled={busy}>{busy ? "..." : editMode ? "salvar" : "adicionar"}</button>
    </div>
  </div>
</Modal>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    min-width: 340px;
  }
  .row {
    display: grid;
    grid-template-columns: 4rem 1fr;
    align-items: center;
    gap: 0.75rem;
  }
  .row-label {
    color: #555;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
  }
  .time-picker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 0.3rem 0.6rem;
  }
  .tp-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.05rem;
  }
  .tp-arrow {
    background: transparent;
    border: none;
    color: #444;
    font-size: 0.65rem;
    line-height: 1;
    cursor: pointer;
    padding: 0;
    transition: color 0.1s;
  }
  .tp-arrow:hover {
    color: #6cf;
  }
  .tp-val {
    color: #ddd;
    font-size: 1rem;
    font-variant-numeric: tabular-nums;
    width: 1.7em;
    text-align: center;
    background: transparent;
    border: none;
    outline: none;
    padding: 0;
    font-family: inherit;
  }
  .tp-val:focus {
    color: #6cf;
  }
  .tp-val::placeholder {
    color: #2a2a2a;
  }
  .time-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .format-hint {
    color: #444;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    padding: 0.15rem 0.35rem;
  }
  .tp-sep {
    color: #555;
    font-size: 1rem;
  }
  .end-wrap {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .end-toggle {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    color: #888;
    font-size: 0.75rem;
    cursor: pointer;
  }
  .end-toggle input {
    accent-color: #6cf;
    margin: 0;
  }
  .day-picker {
    display: flex;
    gap: 0.3rem;
    flex-wrap: wrap;
  }
  .day-btn {
    width: 30px;
    height: 30px;
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    color: #888;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.12s;
    padding: 0;
  }
  .day-btn:hover { color: #ccc; border-color: #555; }
  .day-btn.active {
    background: #0a1820;
    border-color: #6cf;
    color: #6cf;
  }
  .day-btn.all {
    margin-left: 0.4rem;
    font-size: 0.7rem;
  }
  input, select {
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    color: #ddd;
    padding: 0.5rem 0.6rem;
    font: inherit;
    font-size: 0.9rem;
    outline: none;
  }
  input:focus, select:focus { border-color: #6cf; }
  .label-row {
    align-items: start;
  }
  .autocomplete {
    position: relative;
  }
  .autocomplete input {
    width: 100%;
    box-sizing: border-box;
  }
  .dropdown {
    list-style: none;
    margin: 0.25rem 0 0;
    padding: 0;
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    max-height: 180px;
    overflow-y: auto;
  }
  .dropdown li button {
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
  .dropdown li button:hover {
    background: #141414;
  }
  .kind {
    font-size: 0.65rem;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .kind.action { color: #6cf; background: #0a1820; }
  .kind.attribute { color: #cf6; background: #15200a; }
  .kind.concept { color: #a78bfa; background: #1a1525; }
  .name { color: #ddd; }
  .err {
    color: #f66;
    font-size: 0.8rem;
    margin: 0;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
    margin-top: 0.5rem;
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
