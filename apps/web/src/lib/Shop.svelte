<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchShopCatalog,
    fetchUser,
    fetchActions,
    buyPackageAction,
    formatCode,
    fetchUserAttributes,
    createUserAttribute,
    createPatch,
    flattenUserAttributes,
    type CatalogGroup,
    type CatalogAction,
    type Action,
    type UserAttribute,
  } from "./api";
  import { userVersion, bumpUser } from "./store";
  import Modal from "./Modal.svelte";

  export let initialSection: string | null = null;
  void initialSection;

  let groups: CatalogGroup[] = [];
  let buildPoints = 0;
  let owned: Set<string> = new Set();
  let loading = true;
  let error: string | null = null;
  let busy: string | null = null;
  let selected: { group: CatalogGroup; action: CatalogAction } | null = null;
  let query = "";
  let openSet: Set<string> = new Set();
  let lastUserVersion = 0;

  const TYPE_LABEL: Record<number, string> = {
    0: "sessão", 1: "reps", 2: "segundos", 3: "minutos", 4: "horas",
    5: "letras", 6: "linhas", 7: "palavras", 8: "grupo",
  };

  function priceLabel(cost: number) {
    return cost > 0 ? `${cost} bp` : "adquirir";
  }

  /** " · +20t" for productivity, " · -15t" for leisure, "" for neutral. */
  function tokenLabel(a: { token_cost?: number; token_gain?: number }) {
    if (a.token_gain) return ` · +${a.token_gain}t`;
    if (a.token_cost) return ` · -${a.token_cost}t`;
    return "";
  }

  async function load() {
    error = null;
    try {
      const [cat, user, acts, attrs] = await Promise.all([
        fetchShopCatalog(),
        fetchUser().catch(() => null),
        fetchActions().catch(() => []),
        fetchUserAttributes().catch(() => []),
      ]);
      groups = cat;
      buildPoints = user?.build_points ?? 0;
      userActions = acts;
      userAttrs = attrs;
      owned = new Set(acts.map((a) => a.name.toUpperCase()));
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(load);

  $: if ($userVersion !== lastUserVersion) {
    lastUserVersion = $userVersion;
    if (lastUserVersion > 0) load();
  }

  function toggle(key: string) {
    const next = new Set(openSet);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    openSet = next;
  }

  $: q = query.trim().toLowerCase();
  $: filteredView = groups.map((g) => {
    const matches = q
      ? g.actions.filter((a) => a.name.toLowerCase().includes(q))
      : g.actions;
    return { group: g, actions: matches };
  });
  $: matchCount = filteredView.reduce((n, v) => n + v.actions.length, 0);
  $: if (q) {
    const next = new Set<string>();
    for (const v of filteredView) if (v.actions.length > 0) next.add(v.group.key);
    openSet = next;
  }

  function buyKey(groupKey: string, name: string) {
    return `${groupKey}:${name}`;
  }

  async function buy(group: CatalogGroup, action: CatalogAction) {
    if (busy) return;
    busy = buyKey(group.key, action.name);
    error = null;
    try {
      const res = await buyPackageAction(action.package_attribute, action.name);
      buildPoints = res.build_points;
      owned = new Set([...owned, action.name.toUpperCase()]);
      bumpUser();
      if (selected?.action.name === action.name) selected = null;
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      busy = null;
    }
  }

  // ---- patches and user attributes ----

  let userActions: Action[] = [];
  let userAttrs: UserAttribute[] = [];

  $: costByName = new Map(
    groups.flatMap((g) => g.actions.map((a) => [a.name.toUpperCase(), a.cost] as [string, number])),
  );
  $: attrOptions = flattenUserAttributes(userAttrs);
  $: baseActions = userActions.filter((a) => !a.base_action_id);

  let patchOpen = false;
  let patchBase: Action | null = null;
  let patchBaseQuery = "";
  let patchName = "";
  let patchAttrIds: Set<number> = new Set();
  let patchNewAttrs: string[] = [];
  let patchNewAttrDraft = "";
  let patchBusy = false;
  let patchError: string | null = null;

  $: baseOptions = baseActions.filter((a) =>
    a.name.toLowerCase().includes(patchBaseQuery.trim().toLowerCase()),
  );
  $: patchCost = patchBase ? costByName.get(patchBase.name.toUpperCase()) ?? 0 : 0;
  $: nextPatchId = patchBase ? nextFreePatchId(patchBase, userActions) : "";
  $: patchReady =
    !!patchBase &&
    !!nextPatchId &&
    patchName.trim().length > 0 &&
    patchAttrIds.size + patchNewAttrs.length > 0 &&
    buildPoints >= patchCost;

  /** Mirrors the server: the base's id plus the lowest free two digits. */
  function nextFreePatchId(base: Action, all: Action[]): string {
    const used = new Set(all.filter((a) => a.base_action_id === base.id).map((a) => a.id.slice(base.id.length)));
    for (let n = 1; n <= 99; n++) {
      const suffix = String(n).padStart(2, "0");
      if (!used.has(suffix)) return base.id + suffix;
    }
    return "";
  }

  function openPatch() {
    patchBase = null;
    patchBaseQuery = "";
    patchName = "";
    patchAttrIds = new Set();
    patchNewAttrs = [];
    patchNewAttrDraft = "";
    patchError = null;
    patchOpen = true;
  }

  function toggleAttr(id: number) {
    const next = new Set(patchAttrIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    patchAttrIds = next;
  }

  /** A name that already exists selects that attribute instead of creating a twin. */
  function addNewAttr() {
    const name = patchNewAttrDraft.trim().replace(/\s+/g, " ");
    if (!name) return;
    const existing = attrOptions.find((o) => o.name.toLowerCase() === name.toLowerCase());
    if (existing) patchAttrIds = new Set([...patchAttrIds, existing.id]);
    else if (!patchNewAttrs.some((n) => n.toLowerCase() === name.toLowerCase())) patchNewAttrs = [...patchNewAttrs, name];
    patchNewAttrDraft = "";
  }

  function removeNewAttr(name: string) {
    patchNewAttrs = patchNewAttrs.filter((n) => n !== name);
  }

  async function submitPatch() {
    if (!patchReady || !patchBase || patchBusy) return;
    patchBusy = true;
    patchError = null;
    try {
      const res = await createPatch({
        base_action_id: patchBase.id,
        name: patchName.trim(),
        attribute_ids: [...patchAttrIds],
        new_attributes: patchNewAttrs,
      });
      buildPoints = res.build_points;
      patchOpen = false;
      bumpUser();
    } catch (e: any) {
      patchError = e?.message ?? "erro";
    } finally {
      patchBusy = false;
    }
  }

  let attrOpen = false;
  let attrName = "";
  let attrParent: number | null = null;
  let attrBusy = false;
  let attrError: string | null = null;

  function openAttr() {
    attrName = "";
    attrParent = null;
    attrError = null;
    attrOpen = true;
  }

  async function submitAttr() {
    if (!attrName.trim() || attrBusy) return;
    attrBusy = true;
    attrError = null;
    try {
      await createUserAttribute(attrName.trim(), attrParent);
      attrOpen = false;
      userAttrs = await fetchUserAttributes();
    } catch (e: any) {
      attrError = e?.message ?? "erro";
    } finally {
      attrBusy = false;
    }
  }
</script>

<section class="page">
  <header class="topbar">
    <span class="title">shop</span>
    <button class="make" on:click={openPatch}>+ patch</button>
    <button class="make" on:click={openAttr}>+ atributo</button>
    <div class="bp-badge">
      <span class="bp-label">build points</span>
      <span class="bp-value">{buildPoints}</span>
    </div>
  </header>

  <div class="search-row">
    <input type="text" placeholder="Buscar ação..." bind:value={query} />
  </div>

  {#if loading}
    <p class="muted">…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if matchCount === 0}
    <p class="muted">nenhuma ação</p>
  {:else}
    <div class="list">
      {#each filteredView as v (v.group.key)}
        {#if v.actions.length > 0}
          {@const open = openSet.has(v.group.key)}
          <button class="pkg-head" on:click={() => toggle(v.group.key)}>
            <span class="caret">{open ? "▾" : "▸"}</span>
            <span class="pkg-name">{v.group.name}</span>
            <span class="pkg-count">{v.actions.length}</span>
          </button>
          {#if open}
            <ul class="actions">
              {#each v.actions as a (a.name)}
                {@const acquired = owned.has(a.name.toUpperCase())}
                <li class:owned={acquired}>
                  <button class="info" on:click={() => (selected = { group: v.group, action: a })}>
                    <span class="a-name">
                      {#if a.code}<span class="a-code">{formatCode(a.code)}</span>{/if}{a.name}
                    </span>
                    <span class="a-meta">
                      {TYPE_LABEL[a.type] ?? a.type} · d{a.diff}{tokenLabel(a)}
                    </span>
                  </button>
                  {#if acquired}
                    <span class="owned-tag">adquirida</span>
                  {:else}
                    <button
                      class="buy"
                      on:click|stopPropagation={() => buy(v.group, a)}
                      disabled={busy === buyKey(v.group.key, a.name) || buildPoints < a.cost}
                    >
                      {busy === buyKey(v.group.key, a.name) ? "..." : priceLabel(a.cost)}
                    </button>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        {/if}
      {/each}
    </div>
  {/if}
</section>

{#if selected}
  {@const selectedAcquired = owned.has(selected.action.name.toUpperCase())}
  <Modal title={selectedAcquired ? "ação" : "adquirir ação"} onClose={() => (selected = null)}>
    <dl class="details">
      <dt>nome</dt><dd class="hl">{selected.action.name}</dd>
      {#if selected.action.code}
        <dt>id</dt><dd class="code">{formatCode(selected.action.code)}</dd>
      {/if}
      <dt>zona</dt><dd>{selected.group.name}</dd>
      <dt>tipo</dt><dd>{TYPE_LABEL[selected.action.type] ?? selected.action.type}</dd>
      <dt>dificuldade</dt><dd>d{selected.action.diff}</dd>
      {#if selected.action.token_gain}
        <dt>rende</dt><dd class="hl">+{selected.action.token_gain} tokens por execução</dd>
      {:else if selected.action.token_cost}
        <dt>consome</dt><dd>{selected.action.token_cost} tokens por execução</dd>
      {/if}
      {#if selectedAcquired}
        <dt>status</dt><dd class="hl">adquirida</dd>
      {:else}
        <dt>custo</dt><dd>{selected.action.cost} bp</dd>
        <dt>saldo</dt><dd>{buildPoints} bp</dd>
      {/if}
    </dl>
    {#if selected.action.leaves && selected.action.leaves.length > 0}
      <div class="leaves-block">
        <div class="leaves-title">estimula</div>
        <ul class="leaves">
          {#each selected.action.leaves as l (l.key)}
            <li><span class="leaf-name">{l.name}</span><span class="leaf-weight">{Math.round(l.weight * 100)}%</span></li>
          {/each}
        </ul>
      </div>
    {/if}
    <div class="confirm-row">
      <button class="ghost" on:click={() => (selected = null)}>fechar</button>
      {#if !selectedAcquired}
        <button
          class="primary"
          on:click={() => buy(selected!.group, selected!.action)}
          disabled={busy !== null || buildPoints < selected.action.cost}
        >
          {busy ? "..." : priceLabel(selected.action.cost)}
        </button>
      {/if}
    </div>
  </Modal>
{/if}

{#if patchOpen}
  <Modal title="novo patch" onClose={() => (patchOpen = false)}>
    <div class="wizard">
      <div class="step">
        <div class="step-title">1 · ação base</div>
        {#if patchBase}
          <div class="chosen">
            <span class="a-code">{formatCode(patchBase.id)}</span>
            <span class="a-name">{patchBase.name}</span>
            <button class="link" on:click={() => (patchBase = null)}>trocar</button>
          </div>
        {:else if baseActions.length === 0}
          <p class="muted small">adquira uma ação na loja primeiro — o patch roda em cima dela</p>
        {:else}
          <input class="field" type="text" placeholder="buscar ação..." bind:value={patchBaseQuery} />
          <ul class="pick-list">
            {#each baseOptions as a (a.id)}
              <li>
                <button class="pick" on:click={() => (patchBase = a)}>
                  <span class="a-code">{formatCode(a.id)}</span>
                  <span class="a-name">{a.name}</span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      {#if patchBase}
        <div class="step">
          <div class="step-title">2 · nome do patch</div>
          <input class="field" type="text" maxlength="48" placeholder="física" bind:value={patchName} />
        </div>
      {/if}

      {#if patchBase && patchName.trim()}
        <div class="step">
          <div class="step-title">3 · atributos</div>
          {#if attrOptions.length > 0}
            <ul class="check-list">
              {#each attrOptions as o (o.id)}
                <li>
                  <label>
                    <input type="checkbox" checked={patchAttrIds.has(o.id)} on:change={() => toggleAttr(o.id)} />
                    <span>{o.path}</span>
                  </label>
                </li>
              {/each}
            </ul>
          {:else if patchNewAttrs.length === 0}
            <p class="muted small">nenhum atributo ainda — crie o primeiro</p>
          {/if}
          {#each patchNewAttrs as n (n)}
            <div class="new-attr">
              <span>+ {n}</span>
              <button class="link" on:click={() => removeNewAttr(n)}>remover</button>
            </div>
          {/each}
          <div class="inline-new">
            <input
              class="field"
              type="text"
              maxlength="64"
              placeholder="novo atributo"
              bind:value={patchNewAttrDraft}
              on:keydown={(e) => e.key === "Enter" && addNewAttr()}
            />
            <button class="ghost" on:click={addNewAttr} disabled={!patchNewAttrDraft.trim()}>criar</button>
          </div>
        </div>
      {/if}
    </div>

    {#if patchBase}
      <dl class="details">
        <dt>id</dt><dd class="code">{nextPatchId ? formatCode(nextPatchId) : "sem ids livres"}</dd>
        <dt>custo</dt><dd>{patchCost} bp</dd>
        <dt>saldo</dt><dd>{buildPoints} bp</dd>
      </dl>
    {/if}
    {#if patchError}<p class="error">{patchError}</p>{/if}
    <div class="confirm-row">
      <button class="ghost" on:click={() => (patchOpen = false)}>cancelar</button>
      <button class="primary" on:click={submitPatch} disabled={!patchReady || patchBusy}>
        {patchBusy ? "..." : patchCost > 0 ? `criar · ${patchCost} bp` : "criar"}
      </button>
    </div>
  </Modal>
{/if}

{#if attrOpen}
  <Modal title="novo atributo" onClose={() => (attrOpen = false)}>
    <div class="wizard">
      <div class="step">
        <div class="step-title">nome</div>
        <input class="field" type="text" maxlength="64" placeholder="física" bind:value={attrName} />
      </div>
      <div class="step">
        <div class="step-title">dentro de (opcional)</div>
        <select class="field" bind:value={attrParent}>
          <option value={null}>nenhum</option>
          {#each attrOptions as o (o.id)}
            <option value={o.id}>{o.path}</option>
          {/each}
        </select>
      </div>
      <p class="muted small">fica fora da árvore padrão e só é treinado por patches</p>
    </div>
    {#if attrError}<p class="error">{attrError}</p>{/if}
    <div class="confirm-row">
      <button class="ghost" on:click={() => (attrOpen = false)}>cancelar</button>
      <button class="primary" on:click={submitAttr} disabled={!attrName.trim() || attrBusy}>
        {attrBusy ? "..." : "criar"}
      </button>
    </div>
  </Modal>
{/if}

<style>
  .page {
    height: 100%;
    box-sizing: border-box;
    padding: 1.5rem 2rem;
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .topbar {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .title {
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 1.05rem;
  }
  .bp-badge {
    margin-left: auto;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    background: #000000;
    border: 1px solid #000000;
    padding: 0.4rem 0.85rem;
    border-radius: 4px;
  }
  .bp-label {
    color: #808080;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .bp-value { color: #00e5ff; font-weight: bold; font-size: 1rem; }
  .search-row { margin-bottom: 0.75rem; }
  .search-row input {
    width: 100%;
    box-sizing: border-box;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #ffffff;
    padding: 0.55rem 0.75rem;
    font: inherit;
    font-size: 0.9rem;
    outline: none;
  }
  .search-row input:focus { border-color: #00e5ff; }

  .list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .pkg-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    width: 100%;
    padding: 0.5rem 0.95rem;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
    text-align: left;
  }
  .pkg-head:hover { background: #000000; }
  .caret {
    color: #808080;
    font-size: 0.75rem;
    width: 1em;
  }
  .pkg-name {
    color: #ffffff;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.88rem;
    flex: 1;
  }
  .pkg-count {
    color: #808080;
    font-size: 0.78rem;
  }
  .actions {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .actions li {
    display: flex;
    align-items: center;
    padding: 0.45rem 0.95rem 0.45rem 2.1rem;
  }
  .actions li.owned { opacity: 0.4; }
  .info {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.15rem;
    flex: 1;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    padding: 0.2rem 0;
  }
  .info:hover .a-name { color: #00e5ff; }
  .a-name { color: #ffffff; font-size: 0.88rem; text-transform: lowercase; }
  .a-meta { color: #808080; font-size: 0.7rem; }
  .a-code {
    color: #808080;
    margin-right: 0.6rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .code { font-variant-numeric: tabular-nums; letter-spacing: 0.04em; }
  .buy {
    background: transparent;
    border: 1px solid #333333;
    color: #808080;
    padding: 0.32rem 0.65rem;
    border-radius: 4px;
    font: inherit;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
    min-width: 72px;
  }
  .buy:hover:not(:disabled) {
    border-color: #00e5ff;
    color: #00e5ff;
  }
  .buy:disabled { opacity: 0.4; cursor: not-allowed; }
  .owned-tag {
    color: #808080;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.3rem 0.5rem;
  }

  .muted { color: #808080; }
  .error { color: #ff4d4d; }

  .details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.5rem 1rem;
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
  .leaves-block {
    margin: 0 0 1.25rem;
    padding: 0.6rem 0.75rem;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 4px;
  }
  .leaves-title {
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.65rem;
    margin-bottom: 0.4rem;
  }
  .leaves {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .leaves li {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
  }
  .leaf-name { color: #cccccc; }
  .leaf-weight { color: #00e5ff; font-variant-numeric: tabular-nums; }
  .confirm-row { display: flex; gap: 0.5rem; justify-content: flex-end; }
  .ghost, .primary {
    padding: 0.5rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .ghost { background: transparent; color: #808080; border-color: #333333; }
  .ghost:hover { color: #cccccc; border-color: #808080; }
  .primary { background: #00e5ff; color: #000000; border-color: #00e5ff; }
  .primary:hover:not(:disabled) { background: #00a3b8; }
  .primary:disabled { opacity: 0.4; cursor: not-allowed; }

  @media (max-width: 768px) {
    .page { padding: 0.75rem 0.9rem; }
    .actions li { padding-left: 1.2rem; }
    .details { grid-template-columns: 1fr; gap: 0.15rem 0; }
    .details dd { margin-bottom: 0.5rem; }
  }

  .make {
    background: transparent;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #ffffff;
    padding: 0.35rem 0.7rem;
    font: inherit;
    font-size: 0.78rem;
    cursor: pointer;
  }
  .make:hover { border-color: #00e5ff; color: #00e5ff; }
  .wizard {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    margin-bottom: 0.9rem;
    min-width: min(26rem, 80vw);
  }
  .step-title {
    color: #808080;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
  }
  .field {
    width: 100%;
    box-sizing: border-box;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #ffffff;
    padding: 0.5rem 0.65rem;
    font: inherit;
    font-size: 0.88rem;
    outline: none;
  }
  .field:focus { border-color: #00e5ff; }
  .pick-list,
  .check-list {
    list-style: none;
    margin: 0.4rem 0 0;
    padding: 0;
    max-height: 12rem;
    overflow-y: auto;
    border: 1px solid #333333;
    border-radius: 4px;
  }
  .pick {
    display: flex;
    gap: 0.6rem;
    width: 100%;
    background: transparent;
    border: none;
    border-bottom: 1px solid #333333;
    color: #ffffff;
    padding: 0.45rem 0.6rem;
    font: inherit;
    font-size: 0.85rem;
    text-align: left;
    cursor: pointer;
  }
  .pick:hover .a-name { color: #00e5ff; }
  .check-list label {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .check-list input { accent-color: #00e5ff; }
  .chosen { display: flex; align-items: baseline; gap: 0.6rem; }
  .link {
    margin-left: auto;
    background: none;
    border: none;
    color: #808080;
    font: inherit;
    font-size: 0.75rem;
    text-decoration: underline;
    cursor: pointer;
  }
  .link:hover { color: #00e5ff; }
  .new-attr { display: flex; align-items: baseline; gap: 0.5rem; margin-top: 0.35rem; color: #00e5ff; font-size: 0.85rem; }
  .inline-new { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
  .small { font-size: 0.72rem; margin: 0; }
</style>
