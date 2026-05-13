<script lang="ts">
  import { onMount } from "svelte";
  import { fetchUser, fetchAttributes, type UserState, type Attribute } from "./api";
  import { userVersion } from "./store";

  let user: UserState | null = null;
  let attributes: Attribute[] = [];
  let loading = true;
  let error: string | null = null;
  let lastVersion = 0;

  async function load() {
    try {
      const [u, a] = await Promise.all([fetchUser(), fetchAttributes()]);
      user = u;
      attributes = a;
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

  $: maxAttrScore = attributes.reduce((m, a) => Math.max(m, a.score), 1) || 1;
  $: xpProgress = user && user.xp_cost > 0
    ? Math.max(0, Math.min(100, ((user.xp_cost - user.next_xp) / user.xp_cost) * 100))
    : 100;
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
        <span class="muted">xp</span>
        <span class="xp-val">{user.xp.toLocaleString()}</span>
        <span class="muted">→ próximo: {user.next_xp.toLocaleString()}</span>
      </div>
      <div class="xp-bar">
        <div class="fill" style="width: {xpProgress}%"></div>
      </div>
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

    {#if attributes.length > 0}
      <section class="attrs-section">
        <h2>atributos</h2>
        <ul class="attrs">
          {#each attributes as a (a.key)}
            <li>
              <div class="attr-row">
                <span class="attr-name">{a.name}</span>
                <span class="attr-score">{Math.round(a.score).toLocaleString()}</span>
              </div>
              <div class="attr-bar">
                <div class="attr-fill" style="width: {(a.score / maxAttrScore) * 100}%"></div>
              </div>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</section>

<style>
  .page {
    padding: 1.75rem 2rem;
    color: #e5e5e5;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
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
    color: #ddd;
    font-size: 1.4rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  h2 {
    margin: 0 0 0.75rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
  }
  .muted { color: #555; font-size: 0.78rem; }
  .muted-sub { color: #555; font-size: 0.7rem; }
  .error { color: #f66; }

  .rank-large {
    display: flex;
    gap: 0.85rem;
    align-items: center;
    background: #0a1418;
    border: 1px solid #1d3340;
    border-radius: 6px;
    padding: 0.6rem 0.95rem;
  }
  .rank-sym {
    color: #6cf;
    font-size: 2.2rem;
    line-height: 1;
  }
  .rank-letter {
    color: #6cf;
    font-weight: bold;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .local-level { color: #888; font-size: 0.75rem; }

  .xp-card {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
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
    color: #6cf;
    font-weight: bold;
    font-size: 1.1rem;
  }
  .xp-bar {
    height: 5px;
    background: #1a1a1a;
    border-radius: 2px;
    overflow: hidden;
  }
  .fill {
    height: 100%;
    background: #6cf;
    transition: width 0.3s ease;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1.75rem;
  }
  .stat {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    padding: 0.7rem 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .stat-label {
    color: #555;
    text-transform: uppercase;
    font-size: 0.65rem;
    letter-spacing: 0.08em;
  }
  .stat-value {
    color: #ddd;
    font-size: 1.15rem;
    font-weight: bold;
  }

  .attrs-section {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    padding: 0.95rem 1.1rem;
  }
  .attrs {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.85rem;
  }
  .attr-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.85rem;
  }
  .attr-name { color: #ddd; }
  .attr-score { color: #777; font-size: 0.78rem; }
  .attr-bar {
    height: 3px;
    background: #1a1a1a;
    border-radius: 2px;
    margin-top: 0.2rem;
    overflow: hidden;
  }
  .attr-fill {
    height: 100%;
    background: #6cf;
    opacity: 0.6;
  }
</style>
