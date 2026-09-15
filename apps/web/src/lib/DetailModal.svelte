<script module lang="ts">
  export type Subject =
    | { kind: "attribute"; key: string }
    | { kind: "custom"; id: number }
    | { kind: "action"; id: string }
    | { kind: "patch"; id: string };
</script>

<script lang="ts">
  import { onMount } from "svelte";
  import Modal from "./Modal.svelte";
  import MarkBar from "./MarkBar.svelte";
  import {
    fetchActionWindow,
    flattenUserAttributes,
    formatCode,
    setPatchWeight,
    unlinkPatchAttribute,
    updatePatch,
    updateUserAttribute,
    type Action,
    type AttrNode,
    type UserAttribute,
  } from "./api";

  /** One attribute or action of the me page: what it is worth, what computes it and
   *  what it computes. Only what the user created — custom attributes and patches —
   *  can be edited; the default graph and the catalog are shared by everyone. */
  export let subject: Subject;
  export let roots: AttrNode[];
  export let custom: UserAttribute[];
  export let actions: Action[];
  export let onClose: () => void;
  /** Refetches what the page shows; the modal redraws from the new props. */
  export let onChanged: () => Promise<void>;

  type Link = { patchId: string; attrId: number };
  type Removal = { kind: "detach"; attrId: number; name: string } | ({ kind: "unlink"; name: string } & Link);
  type Row = {
    key: string;
    name: string;
    note?: string;
    rank?: string;
    custom?: boolean;
    weight?: number;
    link?: Link; // a patch's link to this attribute: its weight can change
    remove?: Removal;
  };
  type Stat = { label: string; value: string };
  type Pending = { title: string; lines: string[]; confirm: string; run: () => Promise<unknown> };

  const SEPARATOR = " · ";
  const WEIGHT_UNITS = 10;

  let busy = false;
  let error: string | null = null;
  let pending: Pending | null = null;
  let editingName = false;
  let nameDraft = "";
  let editingParents = false;
  let editingChildren = false;
  let parentDraft: number | null = null;
  let parentIdsDraft = new Set<number>();
  let windowLabel = "…";

  onMount(async () => {
    if (subject.kind !== "action" && subject.kind !== "patch") return;
    try {
      const w = await fetchActionWindow(subject.id);
      windowLabel = `${w.window_marks}/${w.limit} em ${w.hours}h`;
    } catch {
      windowLabel = "—";
    }
  });

  /** Every attribute of the graph once, and the links into each. */
  function indexGraph(list: AttrNode[]) {
    const nodes = new Map<string, AttrNode>();
    const parents = new Map<string, { node: AttrNode; weight: number; primary: boolean }[]>();
    const visit = (n: AttrNode) => {
      if (nodes.has(n.key)) return;
      nodes.set(n.key, n);
      for (const c of n.children ?? []) {
        parents.set(c.key, [...(parents.get(c.key) ?? []), { node: n, weight: c.weight ?? 1, primary: c.primary !== false }]);
        visit(c);
      }
    };
    list.forEach(visit);
    return { nodes, parents };
  }

  const flatCustom = (list: UserAttribute[]): UserAttribute[] => list.flatMap((a) => [a, ...flatCustom(a.children)]);
  const subtree = (a: UserAttribute): number[] => [a.id, ...a.children.flatMap(subtree)];
  // a leaf holding marks takes no children; the server refuses it too
  const holdsMarks = (a: UserAttribute) => a.is_leaf && (a.total_marks > 0 || a.rank_index > 0);
  const patchLabel = (name: string) => (name.split(SEPARATOR).slice(1).join(SEPARATOR) || name).toLowerCase();
  const pct = (w: number) => `${Math.round(w * 100)}%`;
  const rankStats = (a: { total_marks: number; marks: number; need: number; max: boolean; rank: string }): Stat[] => [
    { label: "marcas totais", value: String(a.total_marks) },
    { label: "marcas atuais", value: a.max ? "máx" : `${a.marks}/${a.need}` },
    { label: "rank", value: a.rank },
  ];

  $: graph = indexGraph(roots);
  $: customList = flatCustom(custom);
  $: customById = new Map(customList.map((a) => [a.id, a]));
  $: actionById = new Map(actions.map((a) => [a.id, a]));
  $: paths = new Map(flattenUserAttributes(custom).map((o) => [o.id, o.path]));

  $: node = subject.kind === "attribute" ? graph.nodes.get(subject.key) ?? null : null;
  $: attr = subject.kind === "custom" ? customById.get(subject.id) ?? null : null;
  $: action = subject.kind === "action" || subject.kind === "patch" ? actionById.get(subject.id) ?? null : null;

  $: kindLabel = { attribute: "atributo", custom: "atributo custom", action: "ação", patch: "patch" }[subject.kind];
  $: name = node?.name ?? attr?.name ?? (action ? (action.base_action_id ? patchLabel(action.name) : action.name.toLowerCase()) : "");
  $: renamable = !!attr || !!action?.base_action_id;
  $: canEditParents = renamable;
  $: blocked = new Set(attr ? subtree(attr) : []);

  $: stats = node
    ? [...rankStats(node), { label: "grau", value: String(node.degree) }]
    : attr
      ? [...rankStats(attr), { label: "grau", value: "custom" }]
      : action
        ? [
            { label: "marcas totais", value: String(Math.floor(action.score ?? 0)) },
            { label: "marcas atuais", value: windowLabel },
            { label: "execuções", value: String(action.value ?? 0) },
            action.base_action_id
              ? { label: "base", value: (actionById.get(action.base_action_id)?.name ?? "").toLowerCase() }
              : { label: "id", value: formatCode(action.id) },
          ]
        : [];

  $: parents = parentRows(node, attr, action, graph, customById);
  $: children = childRows(node, attr, graph, actions);
  $: canEditChildren = !!attr && children.some((r) => r.remove);

  function parentRows(
    node: AttrNode | null,
    attr: UserAttribute | null,
    action: Action | null,
    g: ReturnType<typeof indexGraph>,
    byId: Map<number, UserAttribute>,
  ): Row[] {
    if (node) {
      return (g.parents.get(node.key) ?? []).map((p) => ({
        key: p.node.key,
        name: p.node.name,
        rank: p.node.rank,
        weight: p.weight,
        note: p.primary ? "primário" : "ligação",
      }));
    }
    if (attr) {
      const p = attr.parent_id != null ? byId.get(attr.parent_id) : null;
      return p ? [{ key: `user:${p.id}`, name: p.name, rank: p.rank, custom: true }] : [];
    }
    if (action?.base_action_id) {
      return (action.attributes ?? []).map((x) => ({
        key: `user:${x.id}`,
        name: x.name,
        rank: byId.get(x.id)?.rank,
        weight: x.weight,
        custom: true,
      }));
    }
    if (action) {
      return (action.leaves ?? []).map((l) => ({ key: l.key, name: l.name, rank: g.nodes.get(l.key)?.rank, weight: l.weight }));
    }
    return [];
  }

  function childRows(node: AttrNode | null, attr: UserAttribute | null, g: ReturnType<typeof indexGraph>, all: Action[]): Row[] {
    if (node) {
      const rows: Row[] = (node.children ?? []).map((c) => ({
        key: c.key,
        name: c.name,
        rank: c.rank,
        weight: c.weight ?? 1,
        note: c.primary === false ? "ligação" : undefined,
      }));
      // a leaf is computed by the actions that feed it
      for (const a of all) {
        const leaf = a.leaves?.find((l) => l.key === node.key);
        if (leaf) rows.push({ key: `action:${a.id}`, name: a.name.toLowerCase(), note: a.base_action_id ? "patch" : "ação", weight: leaf.weight });
      }
      return rows;
    }
    if (attr) {
      return [
        ...attr.children.map((c) => ({
          key: `user:${c.id}`,
          name: c.name,
          rank: c.rank,
          custom: true,
          // a custom parent is the plain mean of its children
          weight: 1 / attr.children.length,
          remove: { kind: "detach", attrId: c.id, name: c.name } as Removal,
        })),
        ...(attr.patches ?? []).map((p) => ({
          key: `patch:${p.id}`,
          name: p.name.toLowerCase(),
          note: `patch · ${formatCode(p.id)}`,
          weight: p.weight,
          link: { patchId: p.id, attrId: attr.id },
          remove: { kind: "unlink", patchId: p.id, attrId: attr.id, name: p.name.toLowerCase() } as Removal,
        })),
      ];
    }
    return [];
  }

  async function run(fn: () => Promise<unknown>): Promise<boolean> {
    busy = true;
    error = null;
    try {
      await fn();
      await onChanged();
      return true;
    } catch (e: any) {
      error = e?.message ?? "erro";
      return false;
    } finally {
      busy = false;
    }
  }

  async function confirmPending() {
    const p = pending;
    pending = null;
    if (p && (await run(p.run))) editingParents = false;
  }

  function focus(el: HTMLInputElement) {
    el.focus();
    el.select();
  }

  function startName() {
    nameDraft = name;
    editingName = true;
  }

  async function saveName() {
    const next = nameDraft.trim().replace(/\s+/g, " ").toLowerCase();
    if (!next || next === name) {
      editingName = false;
      return;
    }
    const s = subject;
    const ok = await run(() =>
      s.kind === "patch" ? updatePatch(s.id, { name: next }) : updateUserAttribute((s as { id: number }).id, { name: next }),
    );
    if (ok) editingName = false;
  }

  function onNameKey(e: KeyboardEvent) {
    if (e.key === "Enter") saveName();
    if (e.key === "Escape") {
      e.stopPropagation(); // the modal would close on it too
      editingName = false;
    }
  }

  function startParents() {
    parentDraft = attr?.parent_id ?? null;
    parentIdsDraft = new Set((action?.attributes ?? []).map((x) => x.id));
    editingParents = true;
  }

  function toggleParent(id: number) {
    const next = new Set(parentIdsDraft);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    parentIdsDraft = next;
  }

  const nameOf = (id: number) => customById.get(id)?.name ?? String(id);
  const nameList = (ids: number[]) => ids.map(nameOf).join(", ");

  function askParents() {
    if (attr) {
      if (parentDraft === attr.parent_id) return void (editingParents = false);
      const from = attr.parent_id != null ? customById.get(attr.parent_id) ?? null : null;
      const to = parentDraft != null ? nameOf(parentDraft) : null;
      const id = attr.id;
      const target = parentDraft;
      pending = {
        title: "alterar pai",
        confirm: "alterar",
        lines: [
          `${attr.name} passa para ${to ?? "a raiz"}, com as marcas que tem.`,
          ...(from ? [`${from.name} para de computar as marcas de ${attr.name} para si.`] : []),
          ...(from && from.children.length === 1 ? [`${from.name} fica sem filhos e mantém o total que tem agora.`] : []),
          ...(to ? [`${to} passa a computar as marcas de ${attr.name}.`] : []),
        ],
        run: () => updateUserAttribute(id, { parent_id: target }),
      };
    } else if (action) {
      const before = new Set((action.attributes ?? []).map((x) => x.id));
      const removed = [...before].filter((id) => !parentIdsDraft.has(id));
      const added = [...parentIdsDraft].filter((id) => !before.has(id));
      if (!removed.length && !added.length) return void (editingParents = false);
      const id = action.id;
      const ids = [...parentIdsDraft];
      pending = {
        title: "alterar pais",
        confirm: "alterar",
        lines: [
          ...(removed.length ? [`${nameList(removed)} ${removed.length > 1 ? "param" : "para"} de computar as marcas deste patch para si.`] : []),
          ...(added.length ? [`${nameList(added)} ${added.length > 1 ? "passam" : "passa"} a computar as marcas deste patch, a 100%.`] : []),
          ...(ids.length === 0 ? ["o patch fica sem atributos custom e continua rodando como a ação base."] : []),
        ],
        run: () => updatePatch(id, { attribute_ids: ids }),
      };
    }
  }

  function askRemove(r: Removal) {
    if (!attr) return;
    const owner = attr.name;
    if (r.kind === "detach") {
      pending = {
        title: "remover filho",
        confirm: "remover",
        lines: [
          `${r.name} deixa de ser filho de ${owner} e vira um atributo raiz, com as marcas que tem.`,
          `${owner} para de computar as marcas de ${r.name} para si.`,
          ...(attr.children.length === 1 ? [`${owner} fica sem filhos e mantém o total que tem agora.`] : []),
        ],
        run: () => updateUserAttribute(r.attrId, { parent_id: null }),
      };
    } else {
      const only = (actionById.get(r.patchId)?.attributes?.length ?? 0) <= 1;
      pending = {
        title: "remover filho",
        confirm: "remover",
        lines: [
          `${owner} para de computar as marcas do patch ${r.name} para si.`,
          ...(only ? [`${r.name} fica sem atributos custom e continua rodando como a ação base.`] : []),
        ],
        run: () => unlinkPatchAttribute(r.patchId, r.attrId),
      };
    }
  }

  const pickWeight = (link: Link, units: number) => run(() => setPatchWeight(link.patchId, link.attrId, units / WEIGHT_UNITS));
</script>

<Modal title={kindLabel} size="page" {onClose}>
  {#if !node && !attr && !action}
    <p class="muted">não encontrado</p>
  {:else}
    <header class="name-row">
      {#if editingName}
        <input
          class="name-input"
          type="text"
          maxlength={action ? 48 : 64}
          bind:value={nameDraft}
          use:focus
          on:keydown={onNameKey}
        />
        <button class="ghost" on:click={() => (editingName = false)}>cancelar</button>
        <button class="primary" on:click={saveName} disabled={busy}>salvar</button>
      {:else}
        <h2 class="name" class:custom={!!attr}>{name}</h2>
        {#if renamable}
          <button class="edit" title="renomear" aria-label="renomear" on:click={startName}>✎</button>
        {/if}
      {/if}
    </header>

    <dl class="stats">
      {#each stats as s (s.label)}
        <div class="stat"><dt>{s.label}</dt><dd>{s.value}</dd></div>
      {/each}
    </dl>

    {#if error}<p class="error">{error}</p>{/if}

    <div class="lists">
      <section>
        <div class="list-head">
          <h3>pais</h3>
          {#if canEditParents}
            <button
              class="edit"
              class:on={editingParents}
              title="alterar pais"
              aria-label="alterar pais"
              on:click={() => (editingParents ? (editingParents = false) : startParents())}
            >✎</button>
          {/if}
        </div>
        <ul class="striped">
          {#if editingParents && attr}
            <li>
              <label class="pick">
                <input type="radio" name="parent" value={null} bind:group={parentDraft} />
                <span class="row-name">nenhum — raiz</span>
              </label>
            </li>
            {#each customList as c (c.id)}
              {@const off = blocked.has(c.id) || holdsMarks(c)}
              <li>
                <label class="pick" class:off>
                  <input type="radio" name="parent" value={c.id} bind:group={parentDraft} disabled={off} />
                  <span class="row-name">{paths.get(c.id)}</span>
                  {#if !blocked.has(c.id) && holdsMarks(c)}<span class="row-note">tem marcas próprias</span>{/if}
                </label>
              </li>
            {/each}
          {:else if editingParents && action}
            {#each customList as c (c.id)}
              <li>
                <label class="pick">
                  <input type="checkbox" checked={parentIdsDraft.has(c.id)} on:change={() => toggleParent(c.id)} />
                  <span class="row-name">{paths.get(c.id)}</span>
                </label>
              </li>
            {:else}
              <li class="empty">nenhum atributo custom — crie na loja</li>
            {/each}
          {:else}
            {#each parents as r (r.key)}
              <li class="row">
                <span class="row-name" class:custom={r.custom}>{r.name}</span>
                {#if r.note}<span class="row-note">{r.note}</span>{/if}
                {#if r.weight != null}<span class="row-pct">{pct(r.weight)}</span>{/if}
                {#if r.rank}<span class="row-rank">{r.rank}</span>{/if}
              </li>
            {:else}
              <li class="empty">{attr ? "raiz — sem pai" : "sem pais"}</li>
            {/each}
          {/if}
        </ul>
        {#if editingParents}
          <div class="edit-actions">
            <button class="ghost" on:click={() => (editingParents = false)}>cancelar</button>
            <button class="primary" on:click={askParents} disabled={busy}>salvar</button>
          </div>
        {/if}
      </section>

      <section>
        <div class="list-head">
          <h3>filhos</h3>
          {#if canEditChildren}
            <button
              class="edit"
              class:on={editingChildren}
              title="editar filhos"
              aria-label="editar filhos"
              on:click={() => (editingChildren = !editingChildren)}
            >✎</button>
          {/if}
        </div>
        <ul class="striped">
          {#each children as r (r.key)}
            {@const link = editingChildren ? r.link : undefined}
            <li class="row">
              {#if editingChildren && r.remove}
                {@const removal = r.remove}
                <button class="remove" title="remover filho" aria-label="remover filho" disabled={busy} on:click={() => askRemove(removal)}>−</button>
              {/if}
              <span class="row-main">
                <span class="row-name" class:custom={r.custom}>{r.name}</span>
                {#if r.note}<span class="row-note">{r.note}</span>{/if}
              </span>
              {#if r.rank}<span class="row-rank">{r.rank}</span>{/if}
              {#if r.weight != null}
                <div class="row-weight" class:picking={!!link}>
                  <MarkBar
                    marks={Math.round(r.weight * WEIGHT_UNITS)}
                    need={WEIGHT_UNITS}
                    size="md"
                    label={pct(r.weight)}
                    onPick={link ? (units) => pickWeight(link, units) : null}
                  />
                </div>
              {/if}
            </li>
          {:else}
            <li class="empty">sem filhos</li>
          {/each}
        </ul>
        {#if editingChildren}
          <p class="hint">clique numa unidade da barra para mudar o peso de um patch</p>
        {/if}
      </section>
    </div>
  {/if}
</Modal>

{#if pending}
  <Modal title={pending.title} onClose={() => (pending = null)}>
    <div class="confirm">
      {#each pending.lines as line, i (i)}
        <p>{line}</p>
      {/each}
      <div class="edit-actions">
        <button class="ghost" on:click={() => (pending = null)}>cancelar</button>
        <button class="danger" on:click={confirmPending}>{pending.confirm}</button>
      </div>
    </div>
  </Modal>
{/if}

<style>
  .muted { color: #808080; font-size: 0.8rem; }
  .error { color: #ff4d4d; font-size: 0.8rem; margin: 0 0 0.75rem; }

  .name-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 1rem;
  }
  .name {
    margin: 0;
    color: #ffffff;
    font-size: 1.4rem;
    letter-spacing: 0.04em;
    overflow-wrap: anywhere;
  }
  .name.custom { color: #00e5ff; }
  .name-input {
    flex: 1;
    min-width: 0;
    max-width: 24rem;
    background: #000000;
    border: 1px solid #00e5ff;
    border-radius: 4px;
    color: #ffffff;
    padding: 0.4rem 0.6rem;
    font: inherit;
    font-size: 1.1rem;
    text-transform: lowercase;
    outline: none;
  }

  .stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem 2rem;
    margin: 0 0 1.25rem;
    max-width: 36rem;
  }
  .stat {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.35rem 0;
    border-bottom: 1px solid #1a1a1a;
  }
  dt {
    color: #808080;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  dd {
    margin: 0;
    color: #ffffff;
    font-size: 0.95rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  /* minmax(0, …): a long name ellipsizes instead of widening its column past the modal */
  .lists {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.25rem;
  }
  /* as tall as its edit button, so both lists start level with or without one */
  .list-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 1.8rem;
    margin-bottom: 0.4rem;
  }
  h3 {
    margin: 0;
    color: #808080;
    font-size: 0.72rem;
    font-weight: normal;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .striped {
    list-style: none;
    margin: 0;
    padding: 0;
    height: 22rem;
    overflow-y: auto;
    border: 1px solid #333333;
    border-radius: 6px;
  }
  .striped > li:nth-child(odd) { background: #0a0a0a; }
  .striped > li:nth-child(even) { background: #1c1c1c; }
  .row,
  .empty,
  .pick {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    min-height: 2.4rem;
    padding: 0.35rem 0.75rem;
    box-sizing: border-box;
  }
  .empty { color: #808080; font-size: 0.8rem; }
  .row-main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }
  .row-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.85rem;
  }
  .row-main .row-name { flex: 0 1 auto; }
  .row-name.custom { color: #00e5ff; }
  .row-note {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #808080;
    font-size: 0.68rem;
  }
  .row-pct { color: #808080; font-size: 0.72rem; font-variant-numeric: tabular-nums; }
  .row-rank { color: #00e5ff; font-weight: bold; font-size: 0.8rem; min-width: 1ch; text-align: right; }
  .row-weight { flex: 0 0 9rem; }
  .row-weight.picking { flex-basis: 11rem; }

  .pick { cursor: pointer; }
  .pick input { accent-color: #00e5ff; margin: 0; }
  .pick.off { cursor: not-allowed; opacity: 0.45; }
  .hint { color: #808080; font-size: 0.7rem; margin: 0.4rem 0 0; }

  .edit {
    background: transparent;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #808080;
    width: 1.8rem;
    height: 1.8rem;
    font-size: 0.95rem;
    line-height: 1;
    cursor: pointer;
  }
  .edit:hover { color: #ffffff; border-color: #808080; }
  .edit.on { color: #000000; background: #00e5ff; border-color: #00e5ff; }
  .remove {
    flex: 0 0 auto;
    width: 1.5rem;
    height: 1.5rem;
    background: transparent;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #808080;
    font-size: 1rem;
    line-height: 1;
    cursor: pointer;
  }
  .remove:hover:not(:disabled) { color: #ff4d4d; border-color: #ff4d4d; }

  .edit-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 0.6rem;
  }
  .ghost,
  .primary,
  .danger {
    padding: 0.4rem 0.85rem;
    border-radius: 4px;
    font: inherit;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .ghost { background: #000000; border: 1px solid #333333; color: #808080; }
  .ghost:hover { color: #cccccc; }
  .primary { background: #00e5ff; border: 1px solid #00e5ff; color: #000000; }
  .danger { background: #ff4d4d; border: 1px solid #ff4d4d; color: #000000; }
  .primary:disabled { opacity: 0.4; cursor: not-allowed; }

  .confirm { max-width: 28rem; }
  .confirm p { margin: 0 0 0.6rem; font-size: 0.85rem; line-height: 1.4; }

  @media (max-width: 768px) {
    .stats { grid-template-columns: minmax(0, 1fr); gap: 0; }
    .lists { grid-template-columns: minmax(0, 1fr); }
    .striped { height: 16rem; }
    .row-weight { flex-basis: 6.5rem; }
    .row-weight.picking { flex-basis: 8rem; }
  }
</style>
