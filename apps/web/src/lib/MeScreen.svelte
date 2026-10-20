<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import {
    claimRank,
    fetchAttributeTree,
    fetchAttributeUsage,
    fetchUser,
    type AttrNode,
    type UsedAttribute,
    type UserState,
  } from "./api";
  import Icon from "./Icon.svelte";
  import MarkBar from "./MarkBar.svelte";
  import Screen from "./Screen.svelte";
  import { primeAudio } from "./dtmf";
  import { gains as gainsSound, powerOn, tap } from "./sfx";
  import { bumpUser, setBackHandler, userVersion } from "./store";

  /** Back to the tile home. */
  export let onHome: () => void;
  export let onProfile: () => void;
  /** The long lists of attributes and actions, patches included. */
  export let onDetails: () => void;

  // The profile's attributes. The ones used most come first; "all" walks the
  // graph, an attribute opening onto its children; and every attribute of one
  // star level can be listed together — the star level being how many levels an
  // attribute gathers, a leaf ★1, Físico far above.

  const INK = "#00c8ff";
  const ROW = 46;

  type View = "used" | "all" | "star";
  const VIEWS: View[] = ["used", "all", "star"];
  const VIEW_ICON = { used: "eye", all: "tree", star: "star" } as const;
  const VIEW_LABEL = { used: "mais usados", all: "todos", star: "por estrela" };

  let user: UserState | null = null;
  let roots: AttrNode[] = [];
  let used: UsedAttribute[] = [];
  let view: View = "used";
  let path: AttrNode[] = [];
  let star = 1;
  let page = 0;
  let detail: AttrNode | null = null;
  let message: string[] = [];
  let bodyHeight = 0;
  let busy = false;
  let lastVersion = 0;

  async function load() {
    try {
      const [u, tree, use] = await Promise.all([fetchUser(), fetchAttributeTree(), fetchAttributeUsage(30, 24)]);
      user = u;
      roots = tree.roots;
      used = use;
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    }
  }
  $: if ($userVersion !== lastVersion) {
    lastVersion = $userVersion;
    if (lastVersion > 0) load();
  }

  /** Every attribute once, by its primary place, keyed. */
  function flatten(list: AttrNode[]): Map<string, AttrNode> {
    const out = new Map<string, AttrNode>();
    const walk = (n: AttrNode) => {
      if (!out.has(n.key)) out.set(n.key, n);
      for (const c of n.children ?? []) if (c.primary !== false) walk(c);
    };
    list.forEach(walk);
    return out;
  }
  $: all = flatten(roots);
  $: maxStar = Math.max(1, ...[...all.values()].map((n) => n.star ?? 1));
  const kids = (n: AttrNode) => (n.children ?? []).filter((c) => c.primary !== false);

  // what the current view lists
  $: listed = (view === "used"
    ? used.map((u) => all.get(u.key) ?? u)
    : view === "all"
      ? path.length ? kids(path[path.length - 1]) : roots
      : [...all.values()].filter((n) => (n.star ?? 1) === star).sort((a, b) => b.total_marks - a.total_marks || a.name.localeCompare(b.name, "pt"))) as AttrNode[];
  $: usesOf = new Map(used.map((u) => [u.key, u.uses]));
  $: perPage = Math.max(1, Math.floor((bodyHeight - 30) / (ROW + 8)));
  $: pages = Math.max(1, Math.ceil(listed.length / perPage));
  $: if (page >= pages) page = pages - 1;
  $: shown = listed.slice(page * perPage, (page + 1) * perPage);

  function press(n = 0) {
    primeAudio();
    tap(n);
  }
  function cycleView() {
    press(4);
    view = VIEWS[(VIEWS.indexOf(view) + 1) % VIEWS.length];
    page = 0;
    detail = null;
    message = [];
    powerOn();
  }
  function cycleStar() {
    press(6);
    star = (star % maxStar) + 1;
    page = 0;
  }
  function up() {
    press(1);
    path = path.slice(0, -1);
    page = 0;
  }
  function open(n: AttrNode) {
    press(7);
    message = [];
    if (view === "all" && kids(n).length) {
      path = [...path, n];
      page = 0;
      return;
    }
    detail = n;
  }
  function back(): boolean {
    if (detail) {
      detail = null;
      return true;
    }
    if (view === "all" && path.length) {
      up();
      return true;
    }
    return false;
  }

  async function claim(n: AttrNode) {
    if (busy || !n.claim) return;
    busy = true;
    try {
      const r = await claimRank(n.key);
      gainsSound();
      message = [`${r.ranks} ${r.ranks === 1 ? "rank" : "ranks"}`, `+${r.points_gained ?? 0} pts · +${r.tokens_gained}t · +${r.skill_points_gained} skill`];
      bumpUser();
      detail = { ...n, claim: undefined };
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }

  onMount(() => {
    setBackHandler(back);
    load().then(() => powerOn());
  });
  onDestroy(() => setBackHandler(null));
</script>

<Screen ink={INK} bind:bodyHeight display="17%">
  <svelte:fragment slot="display">
    {#if message.length}
      {#each message as line, i}<p class={i === 0 ? "big" : "small"}>{line}</p>{/each}
    {:else if detail}
      <p class="big">{detail.name}</p>
      <p class="small">{detail.rank} {detail.rank_name ?? ""} · ★{detail.star ?? 1} · grau {detail.degree}</p>
    {:else if user}
      <p class="rank">{user.rank_symbol}<span>{user.rank_name ?? ""}</span></p>
      <p class="small">{user.nickname ?? user.username} · nível {user.level} · {user.local_level_roman}/{user.local_levels_total}</p>
      <div class="bar-wrap"><MarkBar marks={user.level_marks} need={user.level_cost} size="md" /></div>
    {/if}
  </svelte:fragment>

  {#if detail}
    {@const d = detail}
    <dl class="stats">
      <dt>rank</dt><dd>{d.rank} · {d.rank_name ?? ""}</dd>
      <dt>marcas</dt><dd>{d.marks}/{d.need}</dd>
      <dt>total</dt><dd>{d.total_marks}</dd>
      <dt>estrela</dt><dd>★{d.star ?? 1}</dd>
      <dt>grau</dt><dd>{d.degree}</dd>
      <dt>filhos</dt><dd>{kids(d).length}</dd>
      {#if usesOf.get(d.key)}<dt>usos em 30 dias</dt><dd>{usesOf.get(d.key)}</dd>{/if}
    </dl>
    <MarkBar marks={d.marks} need={d.need} size="md" tone="gold" />
    {#if d.claim}
      <button class="key claim" disabled={busy} on:click={() => claim(d)}>
        <Icon name="star" size={16} /> reclamar {d.claim.ranks} · +{d.claim.points ?? 0} pts
      </button>
    {/if}
    {#if kids(d).length}
      <button class="key claim" on:click={() => { press(7); view = "all"; path = [...(path.length ? path : []), d]; detail = null; page = 0; }}>
        <Icon name="tree" size={16} /> ver filhos
      </button>
    {/if}
  {:else}
    <p class="label">
      {VIEW_LABEL[view]}{#if view === "all" && path.length} · {path.map((p) => p.name).join(" › ")}{/if}{#if view === "star"} · ★{star}{/if}
      {#if pages > 1} · {page + 1}/{pages}{/if}
    </p>
    {#each shown as n (n.key)}
      <button class="row attr" on:click={() => open(n)}>
        <span class="r">{n.rank}</span>
        <span class="grow">{n.name}</span>
        {#if n.claim}<span class="claim-dot" aria-label="rank a reclamar"><Icon name="star" size={12} /></span>{/if}
        <span class="tag">
          {#if view === "used"}{usesOf.get(n.key) ?? 0}×{:else}{n.marks}/{n.need}{/if}
        </span>
        {#if view === "all" && kids(n).length}<span class="tag">›</span>{/if}
      </button>
    {:else}
      <p class="empty">{view === "used" ? "nada usado nos últimos 30 dias — aja" : "nenhum atributo aqui"}</p>
    {/each}
  {/if}

  <svelte:fragment slot="bar">
    {#if detail}
      <button class="key back-key" aria-label="voltar" on:click={() => { press(0); back(); }}><Icon name="left" /></button>
      <button class="key home" aria-label="início" on:click={() => { press(0); onHome(); }}><Icon name="circle" size={16} /></button>
    {:else}
      <button class="key" aria-label="trocar visão: {VIEW_LABEL[view]}" on:click={cycleView}><Icon name={VIEW_ICON[view]} /></button>
      {#if view === "star"}
        <button class="key" aria-label="nível estrela" on:click={cycleStar}>★{star}</button>
      {:else if view === "all"}
        <button class="key" aria-label="subir" disabled={!path.length} on:click={up}><Icon name="up" /></button>
      {:else}
        <span></span>
      {/if}
      <button class="key page-btn" aria-label="próxima página" disabled={pages < 2} on:click={() => { press(2); page = (page + 1) % pages; }}><Icon name="down" /></button>
      <button class="key" aria-label="listas completas" on:click={() => { press(3); onDetails(); }}><Icon name="list" /></button>
      <button class="key" aria-label="perfil" on:click={() => { press(5); onProfile(); }}><Icon name="user" /></button>
      <button class="key home" aria-label="início" on:click={() => { press(0); onHome(); }}><Icon name="circle" size={16} /></button>
    {/if}
  </svelte:fragment>
</Screen>

<style>
  .rank {
    margin: 0;
    font-family: var(--font-display);
    font-size: 2.6rem;
    line-height: 1;
    color: var(--ink);
  }
  .rank span {
    margin-left: 0.5rem;
    font-size: 0.8rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #ffffff;
  }
  .bar-wrap { width: min(16rem, 100%); }
  .attr { min-height: 2.9rem; }
  .attr .grow { text-transform: uppercase; }
  .r {
    flex: none;
    width: 1.4rem;
    color: var(--ink);
    font-family: var(--font-display);
    font-size: 1.05rem;
    text-align: center;
  }
  .claim-dot { flex: none; display: flex; color: #ffd166; }
  .stats {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.45rem 1rem;
    margin: 0;
    padding: 0.8rem;
    border: 1.5px solid var(--ink);
    font-family: var(--font-mono);
    font-size: 0.85rem;
  }
  .stats dt { color: var(--ink); text-transform: uppercase; font-size: 0.7rem; align-self: center; }
  .stats dd { margin: 0; text-align: right; }
  .claim { min-height: 2.8rem; }
  .back-key { grid-column: 1 / 3; }
</style>
