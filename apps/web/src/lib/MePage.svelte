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
  import AttrTree from "./AttrTree.svelte";
  import MarkBar from "./MarkBar.svelte";

  type Group<T> = { key: string; title: string; items: T[] };
  type AttrView = 1 | 2 | 3 | "custom";
  type ActView = 1 | 2 | "patches";

  const ATTR_VIEWS: { id: AttrView; label: string }[] = [
    { id: 1, label: "grau 1" },
    { id: 2, label: "grau 2" },
    { id: 3, label: "grau 3" },
    { id: "custom", label: "custom" },
  ];
  const ACT_VIEWS: { id: ActView; label: string }[] = [
    { id: 1, label: "grau 1" },
    { id: 2, label: "grau 2" },
    { id: "patches", label: "patches" },
  ];
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

  const byTitle = <T,>(a: Group<T>, b: Group<T>) => a.title.localeCompare(b.title, "pt");

  /** The attributes of one degree, grouped under the path to their parent. Follows
   *  primary links only, so a node with several parents is listed once, where it
   *  lives; its subtree still opens with every link. */
  function attributesOfDegree(list: AttrNode[], degree: number): Group<AttrNode>[] {
    const groups = new Map<string, Group<AttrNode>>();
    const seen = new Set<string>();
    const walk = (n: AttrNode, path: AttrNode[]) => {
      if (n.degree === degree) {
        if (seen.has(n.key)) return;
        seen.add(n.key);
        const key = path.at(-1)?.key ?? "";
        if (!groups.has(key)) groups.set(key, { key, title: path.map((p) => p.name).join(" › "), items: [] });
        groups.get(key)!.items.push(n);
        return;
      }
      for (const c of n.children ?? []) if (c.primary !== false) walk(c, [...path, n]);
    };
    for (const r of list) walk(r, []);
    return [...groups.values()];
  }

  /** Catalog actions under their ancestor of `degree`, on the way to the attribute
   *  they are registered under. Patches have their own view. */
  function actionsOfDegree(list: Action[], degree: number): Group<Action>[] {
    const groups = new Map<string, Group<Action>>();
    const loose: Group<Action> = { key: "", title: "sem registro", items: [] };
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

  function patchesByBase(list: Action[]): Group<Action>[] {
    const names = new Map(list.map((a) => [a.id, a.name]));
    const groups = new Map<string, Group<Action>>();
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

  $: half = Math.ceil(recent.length / 2);
  $: recentColumns = [recent.slice(0, half), recent.slice(half)];
  $: attrGroups = attrView === "custom" ? [] : attributesOfDegree(roots, attrView);
  $: actGroups = actView === "patches" ? patchesByBase(actions) : actionsOfDegree(actions, actView);
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
        <span class="muted">· nível {user.local_level_roman}: {user.level_marks}/{user.level_cost}</span>
      </div>
      <MarkBar marks={user.level_marks} need={user.level_cost} size="lg" />
    </section>

    <section class="card">
      <h2>atualizados recentemente</h2>
      {#if recent.length > 0}
        <div class="duo">
          {#each recentColumns as column, i (i)}
            <ul class="recent">
              {#each column as r (r.key)}
                <li class:custom={r.custom}>
                  <div class="rec-row">
                    <span class="rec-name">{r.name}</span>
                    <span class="rank">{r.rank}</span>
                    <span class="meta">{r.max ? "máx" : `${r.marks}/${r.need}`}</span>
                  </div>
                  <MarkBar marks={r.max ? r.need : r.marks} need={r.need} size="md" />
                  <div class="rec-sub">{r.parent ?? (r.custom ? "custom" : "")} · {ago(r.seconds_ago)}</div>
                </li>
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
        <div class="switch">
          {#each ATTR_VIEWS as v (v.id)}
            <button aria-pressed={attrView === v.id} class:on={attrView === v.id} on:click={() => (attrView = v.id)}>
              {v.label}
            </button>
          {/each}
        </div>
      </div>
      {#if attrView === "custom"}
        {#if custom.length > 0}
          <ul class="tree">
            {#each custom as a (a.id)}
              <AttrTree node={userAttrAsNode(a)} />
            {/each}
          </ul>
        {:else}
          <p class="empty-note">nenhum ainda — crie na loja, em “+ atributo” ou ao montar um patch</p>
        {/if}
      {:else}
        {#each attrGroups as g (g.key)}
          <div class="group">
            {#if g.title}<h3>{g.title}</h3>{/if}
            <ul class="tree">
              {#each g.items as n (n.key)}
                <AttrTree node={n} />
              {/each}
            </ul>
          </div>
        {:else}
          <p class="empty-note">nenhum atributo de grau {attrView}</p>
        {/each}
      {/if}
    </section>

    <section class="card">
      <div class="card-head">
        <h2>ações</h2>
        <div class="switch">
          {#each ACT_VIEWS as v (v.id)}
            <button aria-pressed={actView === v.id} class:on={actView === v.id} on:click={() => (actView = v.id)}>
              {v.label}
            </button>
          {/each}
        </div>
      </div>
      {#if actGroups.length > 0}
        <div class="act-groups">
          {#each actGroups as g (g.key)}
            <div class="group">
              <h3>{g.title}</h3>
              <ul class="acts">
                {#each g.items as a (a.id)}
                  <li>
                    <div class="act-row">
                      <span class="code">{formatCode(a.id)}</span>
                      <span class="a-name">{actView === "patches" ? patchLabel(a) : a.name}</span>
                      <span class="meta">{a.value ?? 0}× · {Math.floor(a.score ?? 0)} marcas</span>
                    </div>
                    {#if actView === "patches" && a.attributes?.length}
                      <div class="a-attrs">{a.attributes.map((x) => x.name).join(", ")}</div>
                    {/if}
                  </li>
                {/each}
              </ul>
            </div>
          {/each}
        </div>
      {:else}
        <p class="empty-note">
          {actView === "patches" ? "nenhum patch ainda — monte um na loja, em “+ patch”" : "nenhuma ação ainda — adquira na loja"}
        </p>
      {/if}
    </section>
  {/if}
</section>

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
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem 1rem;
    margin-bottom: 0.75rem;
  }
  .card-head h2 { margin: 0; }

  .switch {
    display: flex;
    border: 1px solid #333333;
    border-radius: 4px;
    overflow: hidden;
  }
  .switch button {
    padding: 0.3rem 0.7rem;
    background: #000000;
    border: none;
    border-left: 1px solid #333333;
    color: #808080;
    font: inherit;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    cursor: pointer;
    white-space: nowrap;
  }
  .switch button:first-child { border-left: none; }
  .switch button:hover { color: #cccccc; }
  .switch button.on { color: #000000; background: #00e5ff; }

  .duo {
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 2rem;
  }
  .recent {
    list-style: none;
    margin: 0;
    padding: 0;
    min-width: 0;
  }
  .recent li { padding: 0.3rem 0 0.45rem; }
  .rec-row {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin-bottom: 0.15rem;
  }
  .rec-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.85rem;
  }
  .recent li.custom .rec-name { color: #00e5ff; }
  .rec-sub {
    margin-top: 0.2rem;
    color: #808080;
    font-size: 0.68rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rank { color: #00e5ff; font-weight: bold; font-size: 0.8rem; }
  .meta {
    color: #808080;
    font-size: 0.72rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .group { margin-bottom: 0.9rem; }
  .group:last-child { margin-bottom: 0; }

  /* Grid, not columns: an expanded attribute grows its own cell downward instead
     of reflowing every one after it into the next column. */
  .tree {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr));
    align-items: start;
    column-gap: 2rem;
  }

  .act-groups {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr));
    align-items: start;
    gap: 0.9rem 2rem;
  }
  .act-groups .group { margin: 0; }
  .acts {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .acts li { padding: 0.3rem 0; border-bottom: 1px solid #1a1a1a; }
  .acts li:last-child { border-bottom: none; }
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
  .a-attrs {
    margin: 0.15rem 0 0 0;
    color: #00e5ff;
    font-size: 0.72rem;
  }

  @media (max-width: 768px) {
    .page { padding: 0.75rem 0.9rem; }
    .duo { column-gap: 1rem; }
    .tree,
    .act-groups { grid-template-columns: 1fr; }
  }
</style>
