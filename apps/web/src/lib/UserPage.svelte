<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchUser,
    fetchAttributeTree,
    fetchUserAttributes,
    userAttrAsNode,
    type UserState,
    type AttrNode,
    type UserAttribute,
  } from "./api";
  import { userVersion } from "./store";
  import AttrTree from "./AttrTree.svelte";
  import MarkBar from "./MarkBar.svelte";

  let user: UserState | null = null;
  let roots: AttrNode[] = [];
  let custom: UserAttribute[] = [];
  let loading = true;
  let error: string | null = null;
  let lastVersion = 0;

  async function load() {
    try {
      const [u, tree, ua] = await Promise.all([
        fetchUser(),
        fetchAttributeTree(),
        fetchUserAttributes().catch(() => []),
      ]);
      user = u;
      roots = tree.roots;
      custom = ua;
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

</script>

<section class="page">
  {#if loading}
    <p class="muted">carregando...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if user}
    <header class="head">
      <div>
        <h1>{user.username}</h1>
        <span class="muted">user</span>
      </div>
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

    <section class="grid">
      <div class="stat">
        <span class="stat-label">day</span>
        <span class="stat-value">{user.day}</span>
        <span class="muted-sub">desde primeiro login</span>
      </div>
      <div class="stat">
        <span class="stat-label">streak</span>
        <span class="stat-value">{user.consecutive_days}</span>
        <span class="muted-sub">dias consecutivos</span>
      </div>
      <div class="stat">
        <span class="stat-label">stage</span>
        <span class="stat-value">{user.stage}</span>
        <span class="muted-sub">checkpoint em {user.days_until_next_checkpoint}d</span>
      </div>
      <div class="stat">
        <span class="stat-label">energy</span>
        <span class="stat-value">{user.energy}{user.max_energy ? `/${user.max_energy}` : ""}</span>
        <span class="muted-sub">{user.bonuses?.max_energy ? `+${user.bonuses.max_energy} skills` : "base"}</span>
      </div>
      <div class="stat">
        <span class="stat-label">tokens</span>
        <span class="stat-value">{user.tokens}/{user.max_tokens}</span>
        <span class="muted-sub">{user.bonuses?.max_tokens ? `+${user.bonuses.max_tokens} skills` : "base"}</span>
      </div>
      <div class="stat">
        <span class="stat-label">build points</span>
        <span class="stat-value">{user.build_points}</span>
        <span class="muted-sub">para criar ações</span>
      </div>
      <div class="stat">
        <span class="stat-label">skill points</span>
        <span class="stat-value">{user.skill_points}</span>
        <span class="muted-sub">para skill tree</span>
      </div>
      <div class="stat">
        <span class="stat-label">attributes</span>
        <span class="stat-value">{user.attributes_count}</span>
        <span class="muted-sub">ativos</span>
      </div>
    </section>

    {#if roots.length > 0}
      <section class="attrs-section">
        <h2>atributos</h2>
        <ul class="tree">
          {#each roots as r (r.key)}
            <AttrTree node={r} />
          {/each}
        </ul>
      </section>
    {/if}

    <section class="attrs-section">
      <h2>customizados</h2>
      {#if custom.length > 0}
        <ul class="tree">
          {#each custom as a (a.id)}
            <AttrTree node={userAttrAsNode(a)} />
          {/each}
        </ul>
      {:else}
        <p class="empty-note">nenhum ainda — crie na loja, em “+ atributo” ou ao montar um patch</p>
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
  .muted { color: #808080; font-size: 0.78rem; }
  .muted-sub { color: #808080; font-size: 0.7rem; }
  .error { color: #ff4d4d; }

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
    margin-bottom: 1.5rem;
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

  .fill {
    height: 100%;
    background: #00e5ff;
    transition: width 0.3s ease;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1.75rem;
  }
  .stat {
    background: #000000;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0.7rem 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .stat-label {
    color: #808080;
    text-transform: uppercase;
    font-size: 0.65rem;
    letter-spacing: 0.08em;
  }
  .stat-value {
    color: #ffffff;
    font-size: 1.15rem;
    font-weight: bold;
  }

  .attrs-section {
    background: #000000;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0.95rem 1.1rem;
    margin-bottom: 1rem;
  }
  /* Grid, not columns: an expanded root grows its own cell downward instead of
     reflowing every root after it into the next column. */
  .tree {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr));
    align-items: start;
    column-gap: 2rem;
  }

  @media (max-width: 768px) {
    .page { padding: 0.75rem 0.9rem; }
  }
  .empty-note { color: #808080; font-size: 0.8rem; margin: 0; }
</style>
