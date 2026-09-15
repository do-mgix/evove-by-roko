<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchUser,
    fetchAttributeTree,
    fetchUserAttributes,
    fetchActions,
    fetchRecentAttributes,
    formatCode,
    userAttrAsNode,
    type UserState,
    type AttrNode,
    type UserAttribute,
    type Action,
    type RecentAttribute,
  } from "./api";
  import { userVersion } from "./store";
  import AttrRow from "./AttrRow.svelte";
  import MarkBar from "./MarkBar.svelte";
  import DetailModal, { type Subject } from "./DetailModal.svelte";

  type Group = { key: string; title: string; items: Action[] };
  // a degree, or "p": the custom attributes, or the patches
  type AttrView = 1 | 2 | 3 | "p";
  type ActView = 1 | 2 | "p";

  const ATTR_VIEWS: AttrView[] = [1, 2, 3, "p"];
  const ACT_VIEWS: ActView[] = [1, 2, "p"];
  const SEPARATOR = " · ";

  let user: UserState | null = null;
  let roots: AttrNode[] = [];
  let custom: UserAttribute[] = [];
  let actions: Action[] = [];
  let recent: RecentAttribute[] = [];
  let loading = true;
  let error: string | null = null;
  let lastVersion = 0;
  let attrView: AttrView = 1;
  let actView: ActView = 1;
  // what the detail modal shows; the recent list opens nothing
  let subject: Subject | null = null;

  async function load() {
    try {
      const [u, tree, ua, acts, rec] = await Promise.all([
        fetchUser(),
        fetchAttributeTree(),
        fetchUserAttributes().catch(() => []),
        fetchActions(),
        fetchRecentAttributes(10),
      ]);
      user = u;
      roots = tree.roots;
      custom = ua;
      actions = acts;
      recent = rec;
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(load);

  $: if ($userVersion !== lastVersion) {
    lastVersion = $userVersion;
    if (lastVersion > 0) load();
  }

  const cycle = <T,>(views: T[], current: T): T => views[(views.indexOf(current) + 1) % views.length];
  const byTitle = (a: Group, b: Group) => a.title.localeCompare(b.title, "pt");

  /** The attributes of one degree, in graph order. Follows primary links only, so a
   *  node with several parents is listed once, where it lives. */
  function attributesOfDegree(list: AttrNode[], degree: number): AttrNode[] {
    const out: AttrNode[] = [];
    const seen = new Set<string>();
    const walk = (n: AttrNode) => {
      if (n.degree === degree) {
        if (!seen.has(n.key)) {
          seen.add(n.key);
          out.push(n);
        }
        return;
      }
      for (const c of n.children ?? []) if (c.primary !== false) walk(c);
    };
    for (const r of list) walk(r);
    return out;
  }

  // nothing opens in place, so every custom attribute is listed, each parent before its children
  const flattenCustom = (list: UserAttribute[]): UserAttribute[] => list.flatMap((a) => [a, ...flattenCustom(a.children)]);

  /** Catalog actions under their ancestor of `degree`, on the way to the attribute
   *  they are registered under. Patches have their own view. */
  function actionsOfDegree(list: Action[], degree: number): Group[] {
    const groups = new Map<string, Group>();
    const loose: Group = { key: "", title: "sem registro", items: [] };
    for (const a of list) {
      if (a.base_action_id) continue;
      const path = a.path ?? [];
      const at = path[degree - 1];
      if (!at) {
        loose.items.push(a);
        continue;
      }
      if (!groups.has(at.key)) {
        groups.set(at.key, { key: at.key, title: path.slice(0, degree).map((p) => p.name).join(" › "), items: [] });
      }
      groups.get(at.key)!.items.push(a);
    }
    const out = [...groups.values()].sort(byTitle);
    if (loose.items.length) out.push(loose);
    for (const g of out) g.items.sort((x, y) => x.id.localeCompare(y.id));
    return out;
  }

  function patchesByBase(list: Action[]): Group[] {
    const names = new Map(list.map((a) => [a.id, a.name]));
    const groups = new Map<string, Group>();
    for (const a of list) {
      if (!a.base_action_id) continue;
      const key = a.base_action_id;
      if (!groups.has(key)) groups.set(key, { key, title: names.get(key) ?? key, items: [] });
      groups.get(key)!.items.push(a);
    }
    const out = [...groups.values()].sort(byTitle);
    for (const g of out) g.items.sort((x, y) => x.id.localeCompare(y.id));
    return out;
  }

  // "ESTUDO · FÍSICA" under the ESTUDO heading reads as "física"
  const patchLabel = (a: Action) => a.name.split(SEPARATOR).slice(1).join(SEPARATOR) || a.name;

  function ago(seconds: number): string {
    if (seconds < 60) return "agora";
    if (seconds < 3600) return `há ${Math.floor(seconds / 60)} min`;
    if (seconds < 86400) return `há ${Math.floor(seconds / 3600)} h`;
    return `há ${Math.floor(seconds / 86400)} d`;
  }

  const recentNote = (r: RecentAttribute) =>
    [r.parent ?? (r.custom ? "custom" : null), ago(r.seconds_ago)].filter(Boolean).join(" · ");

  $: half = Math.ceil(recent.length / 2);
  $: recentColumns = [recent.slice(0, half), recent.slice(half)];
  $: attrItems =
    attrView === "p"
      ? flattenCustom(custom).map((a) => ({ node: userAttrAsNode(a), subject: { kind: "custom", id: a.id } as Subject }))
      : attributesOfDegree(roots, attrView).map((n) => ({ node: n, subject: { kind: "attribute", key: n.key } as Subject }));
  $: actGroups = actView === "p" ? patchesByBase(actions) : actionsOfDegree(actions, actView);
</script>

<section class="page">
  {#if loading}
    <p class="muted">carregando...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if user}
    <header class="head">
      <h1>me</h1>
      <div class="rank-large">
        <span class="rank-sym">{user.rank_symbol}</span>
        <div>
          <div class="rank-letter">rank {user.rank_letter}</div>
          <div class="local-level">level {user.level} · {user.local_level_roman}/{user.local_levels_total}</div>
        </div>
      </div>
    </header>

    <section class="xp-card">
      <div class="xp-row">
        <span class="muted">marcas</span>
        <span class="xp-val">{user.marks.toLocaleString()}</span>
        <span class="muted">· nível {user.local_level_roman}</span>
      </div>
      <MarkBar marks={user.level_marks} need={user.level_cost} size="lg" />
    </section>

    <section class="card">
      <h2>atualizados recentemente</h2>
      {#if recent.length > 0}
        <div class="duo">
          {#each recentColumns as column, i (i)}
            <ul class="list">
              {#each column as r (r.key)}
                <AttrRow node={r} note={recentNote(r)} />
              {/each}
            </ul>
          {/each}
        </div>
      {:else}
        <p class="empty-note">nenhum atributo ganhou marcas ainda</p>
      {/if}
    </section>

    <section class="card">
      <div class="card-head">
        <h2>atributos</h2>
        <button
          class="degree"
          title={attrView === "p" ? "atributos custom" : `atributos de grau ${attrView}`}
          on:click={() => (attrView = cycle(ATTR_VIEWS, attrView))}
        >
          <span class="star">★</span>{attrView}
        </button>
      </div>
      {#if attrItems.length > 0}
        <ul class="list grid">
          {#each attrItems as item (item.node.key)}
            <AttrRow node={item.node} onOpen={() => (subject = item.subject)} />
          {/each}
        </ul>
      {:else}
        <p class="empty-note">
          {attrView === "p" ? "nenhum ainda — crie na loja, em “+ atributo” ou ao montar um patch" : `nenhum atributo de grau ${attrView}`}
        </p>
      {/if}
    </section>

    <section class="card">
      <div class="card-head">
        <h2>ações</h2>
        <button
          class="degree"
          title={actView === "p" ? "patches" : `ações por atributo de grau ${actView}`}
          on:click={() => (actView = cycle(ACT_VIEWS, actView))}
        >
          <span class="star">★</span>{actView}
        </button>
      </div>
      {#if actGroups.length > 0}
        <div class="act-groups">
          {#each actGroups as g (g.key)}
            <div>
              <h3>{g.title}</h3>
              <ul class="list">
                {#each g.items as a (a.id)}
                  <li class="act">
                    <button
                      type="button"
                      class="act-hit"
                      on:click={() => (subject = a.base_action_id ? { kind: "patch", id: a.id } : { kind: "action", id: a.id })}
                    >
                      <span class="act-row">
                        <span class="code">{formatCode(a.id)}</span>
                        <span class="a-name">{actView === "p" ? patchLabel(a) : a.name}</span>
                        <span class="meta">{a.value ?? 0}× · {Math.floor(a.score ?? 0)} marcas</span>
                      </span>
                      {#if actView === "p" && a.attributes?.length}
                        <span class="a-attrs">{a.attributes.map((x) => x.name).join(", ")}</span>
                      {/if}
                    </button>
                  </li>
                {/each}
              </ul>
            </div>
          {/each}
        </div>
      {:else}
        <p class="empty-note">
          {actView === "p" ? "nenhum patch ainda — monte um na loja, em “+ patch”" : "nenhuma ação ainda — adquira na loja"}
        </p>
      {/if}
    </section>
  {/if}
</section>

{#if subject}
  <DetailModal {subject} {roots} {custom} {actions} onClose={() => (subject = null)} onChanged={load} />
{/if}

<style>
  .page {
    padding: 1.75rem 2rem;
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
    height: 100%;
    overflow-y: auto;
    box-sizing: border-box;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1.5rem;
  }
  h1 {
    margin: 0;
    color: #ffffff;
    font-size: 1.4rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  h2 {
    margin: 0 0 0.75rem;
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
  }
  h3 {
    margin: 0 0 0.35rem;
    color: #00e5ff;
    font-size: 0.72rem;
    font-weight: normal;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .muted { color: #808080; font-size: 0.78rem; }
  .error { color: #ff4d4d; }
  .empty-note { color: #808080; font-size: 0.8rem; margin: 0; }

  .rank-large {
    display: flex;
    gap: 0.85rem;
    align-items: center;
    background: #000000;
    border: 1px solid #000000;
    border-radius: 6px;
    padding: 0.6rem 0.95rem;
  }
  .rank-sym {
    color: #00e5ff;
    font-size: 2.2rem;
    line-height: 1;
  }
  .rank-letter {
    color: #00e5ff;
    font-weight: bold;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .local-level { color: #808080; font-size: 0.75rem; }

  .xp-card {
    background: #000000;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
  }
  .xp-row {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    margin-bottom: 0.5rem;
  }
  .xp-val {
    color: #00e5ff;
    font-weight: bold;
    font-size: 1.1rem;
  }

  .card {
    background: #000000;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0.95rem 1.1rem;
    margin-bottom: 1rem;
  }
  .card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.75rem;
  }
  .card-head h2 { margin: 0; }

  /* one button cycles the views; a fixed width keeps it still between "1" and "p" */
  .degree {
    display: inline-flex;
    align-items: baseline;
    justify-content: center;
    gap: 0.3rem;
    min-width: 3.2rem;
    padding: 0.3rem 0.65rem;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #ffffff;
    font: inherit;
    font-size: 0.85rem;
    font-variant-numeric: tabular-nums;
    cursor: pointer;
  }
  .degree:hover { border-color: #00e5ff; }
  .star { color: #00e5ff; }

  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    min-width: 0;
  }
  .duo {
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 2rem;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr));
    column-gap: 2rem;
  }

  .act-groups {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr));
    align-items: start;
    gap: 0.9rem 2rem;
  }
  .act { padding: 0.3rem 0; border-bottom: 1px solid #1a1a1a; }
  .act:last-child { border-bottom: none; }
  .act-hit {
    display: block;
    width: 100%;
    padding: 0;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .act-hit:hover .a-name { color: #00e5ff; }
  .act-row {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
  }
  .code {
    color: #808080;
    font-size: 0.72rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .a-name {
    flex: 1;
    min-width: 0;
    font-size: 0.85rem;
    text-transform: lowercase;
    overflow-wrap: anywhere;
  }
  .meta {
    color: #808080;
    font-size: 0.72rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .a-attrs {
    display: block;
    margin-top: 0.15rem;
    color: #00e5ff;
    font-size: 0.72rem;
  }

  @media (max-width: 768px) {
    .page { padding: 0.75rem 0.9rem; }
    .duo { column-gap: 1rem; }
    .grid,
    .act-groups { grid-template-columns: 1fr; }
  }
</style>
