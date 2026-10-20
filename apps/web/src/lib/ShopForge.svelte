<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchShopCatalog,
    fetchUser,
    fetchActions,
    formatCode,
    fetchUserAttributes,
    createUserAttribute,
    createUserAttributePath,
    createPatch,
    flattenUserAttributes,
    sameName,
    fold,
    type CatalogGroup,
    type Action,
    type UserAttribute,
    type NewAttributeSpec,
  } from "./api";
  import { bumpUser } from "./store";
  import Modal from "./Modal.svelte";
  import SuggestionPicker from "./SuggestionPicker.svelte";

  // What the shop makes rather than sells: a patch over an owned action, or an
  // attribute of the profile's own. Opened from the shop's first screen.

  /** Which of the two is being made. */
  export let mode: "patch" | "attr";
  export let onClose: () => void;

  let groups: CatalogGroup[] = [];
  let buildPoints = 0;
  let userActions: Action[] = [];
  let userAttrs: UserAttribute[] = [];

  onMount(async () => {
    const [cat, user, acts, attrs] = await Promise.all([
      fetchShopCatalog().catch(() => []),
      fetchUser().catch(() => null),
      fetchActions().catch(() => []),
      fetchUserAttributes().catch(() => []),
    ]);
    groups = cat;
    buildPoints = user?.build_points ?? 0;
    userActions = acts;
    userAttrs = attrs;
  });

  $: costByName = new Map(
    groups.flatMap((g) => g.actions.map((a) => [a.name.toUpperCase(), a.cost] as [string, number])),
  );
  $: attrOptions = flattenUserAttributes(userAttrs);
  $: baseActions = userActions.filter((a) => !a.base_action_id);

  let patchBase: Action | null = null;
  let patchBaseQuery = "";
  let patchName = "";
  let patchAttrIds: Set<number> = new Set();
  let patchNewAttrs: NewAttributeSpec[] = [];
  let patchPickerOpen = false;
  let patchNewAttrDraft = "";
  let patchBusy = false;
  let patchError: string | null = null;

  $: patchBaseQ = fold(patchBaseQuery.trim());
  $: baseOptions = baseActions.filter((a) => fold(a.name).includes(patchBaseQ));
  $: patchCost = patchBase ? costByName.get(patchBase.name.toUpperCase()) ?? 0 : 0;
  $: nextPatchId = patchBase ? nextFreePatchId(patchBase, userActions) : "";
  // a log action is logged, not trained: its patches only separate entries in
  // the ledger, so they take no attribute and the step is skipped
  $: patchIsLog = !!patchBase?.log_only;
  $: patchReady =
    !!patchBase &&
    !!nextPatchId &&
    patchName.trim().length > 0 &&
    (patchIsLog || patchAttrIds.size + patchNewAttrs.length > 0) &&
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

  function toggleAttr(id: number) {
    const next = new Set(patchAttrIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    patchAttrIds = next;
  }

  /** The name a spec ends up creating — a path trains its leaf. */
  const specLabel = (n: NewAttributeSpec) => (typeof n === "string" ? n : n.path[n.path.length - 1]);

  /** A name the profile already has selects that attribute instead of creating a
   *  twin — the server would refuse the twin anyway, the name is unique. */
  function addAttrNamed(spec: NewAttributeSpec) {
    const label = specLabel(spec);
    const existing = attrOptions.find((o) => sameName(o.name, label));
    if (existing) patchAttrIds = new Set([...patchAttrIds, existing.id]);
    else if (!patchNewAttrs.some((n) => sameName(specLabel(n), label))) patchNewAttrs = [...patchNewAttrs, spec];
  }

  function addNewAttr() {
    const name = patchNewAttrDraft.trim().replace(/\s+/g, " ");
    if (!name) return;
    addAttrNamed(name);
    patchNewAttrDraft = "";
  }

  function removeNewAttr(spec: NewAttributeSpec) {
    patchNewAttrs = patchNewAttrs.filter((n) => n !== spec);
  }

  async function submitPatch() {
    if (!patchReady || !patchBase || patchBusy) return;
    patchBusy = true;
    patchError = null;
    try {
      const res = await createPatch({
        base_action_id: patchBase.id,
        name: patchName.trim(),
        attribute_ids: patchIsLog ? [] : [...patchAttrIds],
        new_attributes: patchIsLog ? [] : patchNewAttrs,
      });
      buildPoints = res.build_points;
      bumpUser();
      onClose();
    } catch (e: any) {
      patchError = e?.message ?? "erro";
    } finally {
      patchBusy = false;
    }
  }

  let attrName = "";
  let attrParent: number | null = null;
  let attrBusy = false;
  let attrError: string | null = null;
  let attrMode: "catalog" | "free" = "catalog";
  /** A suggestion's whole path; the last level is the attribute being created. */
  let attrPath: string[] = [];
  /** Create the levels above it too, or only the one picked. */
  let attrWithParents = true;

  const allUserAttrs = (list: UserAttribute[]): UserAttribute[] =>
    list.flatMap((a) => [a, ...allUserAttrs(a.children)]);

  /** A level of the path the profile already has as a leaf holding marks: taking a
   *  child hands them to it and the level becomes the mean of its children. Nothing
   *  is lost, but the rank moves down a level, so say it before creating. */
  $: attrSwallows =
    attrWithParents && attrPath.length > 1
      ? allUserAttrs(userAttrs).find(
          (a) =>
            a.is_leaf &&
            (a.marks > 0 || a.rank_index > 0) &&
            attrPath.slice(0, -1).some((p) => sameName(a.name, p)),
        ) ?? null
      : null;

  $: attrReady = attrMode === "catalog" ? attrPath.length > 0 : attrName.trim().length > 0;

  async function submitAttr() {
    if (!attrReady || attrBusy) return;
    attrBusy = true;
    attrError = null;
    try {
      if (attrMode === "catalog") {
        await createUserAttributePath(attrWithParents ? attrPath : attrPath.slice(-1));
      } else {
        await createUserAttribute(attrName.trim(), attrParent);
      }
      bumpUser();
      onClose();
    } catch (e: any) {
      attrError = e?.message ?? "erro";
    } finally {
      attrBusy = false;
    }
  }
</script>

{#if mode === "patch"}
  <Modal title="novo patch" onClose={onClose}>
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

      {#if patchBase && patchName.trim() && patchIsLog}
        <div class="step">
          <div class="step-title">3 · atributos</div>
          <p class="muted small">
            {patchBase.name} é registro, não treino: o patch separa as entradas no diário
            e não treina atributo nenhum.
          </p>
        </div>
      {:else if patchBase && patchName.trim()}
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
              <span title={typeof n === "string" ? n : n.path.join(" › ")}>+ {specLabel(n)}</span>
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
          <button class="link" on:click={() => (patchPickerOpen = !patchPickerOpen)}>
            {patchPickerOpen ? "fechar catálogo" : "escolher do catálogo"}
          </button>
          {#if patchPickerOpen}
            <SuggestionPicker
              existing={attrOptions.map((o) => o.name)}
              onPick={(p) => {
                addAttrNamed({ path: p });
                patchPickerOpen = false;
              }}
            />
          {/if}
        </div>
      {/if}
    </div>

    {#if patchBase}
      <dl class="details">
        <dt>id</dt><dd class="code">{nextPatchId ? formatCode(nextPatchId) : "sem ids livres"}</dd>
        <dt>custo</dt><dd>{patchCost} pts</dd>
        <dt>saldo</dt><dd>{buildPoints} pts</dd>
      </dl>
    {/if}
    {#if patchError}<p class="error">{patchError}</p>{/if}
    <div class="confirm-row">
      <button class="ghost" on:click={onClose}>cancelar</button>
      <button class="primary" on:click={submitPatch} disabled={!patchReady || patchBusy}>
        {patchBusy ? "..." : patchCost > 0 ? `criar · ${patchCost} pts` : "criar"}
      </button>
    </div>
  </Modal>
{/if}

{#if mode === "attr"}
  <Modal title="novo atributo" onClose={onClose}>
    <div class="wizard">
      <div class="mode-row">
        <button type="button" class="tab" class:on={attrMode === "catalog"} on:click={() => (attrMode = "catalog")}>
          catálogo
        </button>
        <button type="button" class="tab" class:on={attrMode === "free"} on:click={() => (attrMode = "free")}>
          livre
        </button>
      </div>

      {#if attrMode === "catalog"}
        <div class="step">
          {#if attrPath.length}
            <div class="step-title">escolhido</div>
            <div class="new-attr">
              <span>{attrPath.join(" › ")}</span>
              <button class="link" on:click={() => (attrPath = [])}>trocar</button>
            </div>
            {#if attrPath.length > 1}
              <label class="check-line">
                <input type="checkbox" bind:checked={attrWithParents} />
                <span>criar os níveis acima</span>
              </label>
            {/if}
            {#if attrSwallows}
              <p class="muted small">
                {attrSwallows.name} já existe e guarda marcas: elas passam para o primeiro filho
                e ele vira a média dos filhos.
              </p>
            {/if}
          {:else}
            <div class="step-title">escolher</div>
            <SuggestionPicker existing={attrOptions.map((o) => o.name)} onPick={(p) => (attrPath = p)} />
          {/if}
        </div>
      {:else}
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
      {/if}
      <p class="muted small">fica fora da árvore padrão e só é treinado por patches</p>
    </div>
    {#if attrError}<p class="error">{attrError}</p>{/if}
    <div class="confirm-row">
      <button class="ghost" on:click={onClose}>cancelar</button>
      <button class="primary" on:click={submitAttr} disabled={!attrReady || attrBusy}>
        {attrBusy ? "..." : "criar"}
      </button>
    </div>
  </Modal>
{/if}

<style>
  .a-name { color: #111111; font-size: 0.88rem; text-transform: lowercase; }
  .a-code {
    color: #737373;
    margin-right: 0.6rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .code { font-variant-numeric: tabular-nums; letter-spacing: 0.04em; }
  .muted { color: #737373; }
  .error { color: #d93636; }
  .details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.5rem 1rem;
    margin: 0 0 1.25rem;
  }
  .details dt {
    color: #737373;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
  }
  .details dd { color: #111111; margin: 0; font-size: 0.9rem; }
  .confirm-row { display: flex; gap: 0.5rem; justify-content: flex-end; }
  .ghost, .primary {
    padding: 0.5rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .ghost { background: transparent; color: #737373; border-color: #d4d4d4; }
  .ghost:hover { color: #444444; border-color: #737373; }
  .primary { background: #ffffff; color: #111111; border-color: #111111; }
  .primary:hover:not(:disabled) { background: #111111; color: #ffffff; }
  .primary:disabled { opacity: 0.4; cursor: not-allowed; }
  .wizard {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    margin-bottom: 0.9rem;
    min-width: min(26rem, 80vw);
  }
  .step-title {
    color: #737373;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
  }
  .field {
    width: 100%;
    box-sizing: border-box;
    background: #ffffff;
    border: 1px solid #d4d4d4;
    border-radius: 4px;
    color: #111111;
    padding: 0.5rem 0.65rem;
    font: inherit;
    font-size: 0.88rem;
    outline: none;
  }
  .field:focus { border-color: #00838f; }
  .pick-list,
  .check-list {
    list-style: none;
    margin: 0.4rem 0 0;
    padding: 0;
    max-height: 12rem;
    overflow-y: auto;
    border: 1px solid #d4d4d4;
    border-radius: 4px;
  }
  .pick {
    display: flex;
    gap: 0.6rem;
    width: 100%;
    background: transparent;
    border: none;
    border-bottom: 1px solid #d4d4d4;
    color: #111111;
    padding: 0.45rem 0.6rem;
    font: inherit;
    font-size: 0.85rem;
    text-align: left;
    cursor: pointer;
  }
  .pick:hover .a-name { color: #00838f; }
  .check-list label {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .check-list input { accent-color: #00838f; }
  .chosen { display: flex; align-items: baseline; gap: 0.6rem; }
  .link {
    margin-left: auto;
    background: none;
    border: none;
    color: #737373;
    font: inherit;
    font-size: 0.75rem;
    text-decoration: underline;
    cursor: pointer;
  }
  .link:hover { color: #00838f; }
  .new-attr { display: flex; align-items: baseline; gap: 0.5rem; margin-top: 0.35rem; color: #00838f; font-size: 0.85rem; }
  .inline-new { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
  .small { font-size: 0.72rem; margin: 0; }
  @media (max-width: 768px) {
    .details { grid-template-columns: 1fr; gap: 0.15rem 0; }
    .details dd { margin-bottom: 0.5rem; }
  }
</style>
