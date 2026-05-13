<script lang="ts">
  import type { UserState, AttrTag } from "./api";
  export let user: UserState;
  export let tags: AttrTag[] = [];

  $: xpProgress =
    user.xp_cost > 0
      ? Math.max(0, Math.min(100, ((user.xp_cost - user.next_xp) / user.xp_cost) * 100))
      : 100;

  $: maxTagScore = tags.reduce((m, t) => Math.max(m, t.score), 1) || 1;

  $: tagsByCategory = (() => {
    const groups: Record<string, AttrTag[]> = {};
    for (const t of tags) {
      (groups[t.category] ||= []).push(t);
    }
    return groups;
  })();

  $: categoryOrder = ["Físico", "Mental"].filter((c) => tagsByCategory[c]?.length);
</script>

<aside class="user-panel">
  <div class="rank-line">
    <span class="rank">{user.rank_symbol}</span>
    <span class="rank-letter">{user.rank_letter}</span>
    <span class="local">{user.local_level_roman}/{user.local_levels_total}</span>
  </div>

  <div class="row">
    <span class="label">level</span>
    <span class="value">{user.level}</span>
  </div>

  <div class="xp-bar" title="{user.xp.toLocaleString()} xp · faltam {user.next_xp.toLocaleString()}">
    <div class="fill" style="width: {xpProgress}%"></div>
  </div>

  <div class="day-block">
    <span class="day-label">day</span>
    <span class="day-value">{user.day}</span>
  </div>

  <div class="bp">
    <span class="label">build points</span>
    <span class="bp-value">{user.build_points}</span>
  </div>

  <div class="grid">
    <div><span class="label">streak</span><span class="value">{user.consecutive_days}</span></div>
    <div><span class="label">stage</span><span class="value">{user.stage}</span></div>
    <div><span class="label">energy</span><span class="value">{user.energy}</span></div>
    <div><span class="label">attrs</span><span class="value">{user.attributes_count}</span></div>
    <div class="span-2"><span class="label">tokens</span><span class="value">{user.tokens}/{user.max_tokens}</span></div>
    <div class="span-2"><span class="label">checkpoint</span><span class="value">{user.days_until_next_checkpoint}d</span></div>
    <div class="span-2"><span class="label">today</span><span class="value">{new Date(user.date + 'T00:00:00').toLocaleDateString('pt-BR')}</span></div>
    <div class="span-2"><span class="label">skill points</span><span class="value">{user.skill_points}</span></div>
  </div>

  {#each categoryOrder as cat (cat)}
    <div class="attrs-title">{cat}</div>
    <ul class="attrs">
      {#each tagsByCategory[cat] as t (t.key)}
        <li>
          <div class="attr-row">
            <span class="attr-name">{t.name}</span>
            {#if t.level != null && t.max_level != null}
              <span class="attr-score">lvl {t.level.toFixed(1)}/{t.max_level}</span>
            {:else}
              <span class="attr-score">{Math.round(t.score).toLocaleString()}</span>
            {/if}
          </div>
          <div class="attr-bar">
            {#if t.progress_to_next != null}
              <div class="attr-fill" style="width: {t.progress_to_next * 100}%"></div>
            {:else}
              <div class="attr-fill" style="width: {(t.score / maxTagScore) * 100}%"></div>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/each}

  <div class="user-name">{user.username}</div>
</aside>

<style>
  .user-panel {
    background: #111;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    color: #ccc;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.82rem;
    height: 100%;
    box-sizing: border-box;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .rank-line {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #1f1f1f;
    margin-bottom: 0.6rem;
  }
  .rank { color: #6cf; font-size: 1.4rem; }
  .rank-letter { color: #888; font-weight: bold; }
  .local { color: #666; font-size: 0.75rem; margin-left: auto; }

  .row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin: 0.2rem 0;
  }
  .label {
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.7rem;
  }
  .value {
    color: #e5e5e5;
  }

  .xp-bar {
    height: 4px;
    background: #1a1a1a;
    border-radius: 2px;
    overflow: hidden;
    margin: 0.4rem 0 0.85rem;
  }
  .fill {
    height: 100%;
    background: #6cf;
    transition: width 0.3s ease;
  }

  .day-block {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.55rem 0.7rem;
    background: #0a1820;
    border: 1px solid #2a4a5a;
    border-radius: 4px;
    margin-bottom: 0.5rem;
  }
  .day-label {
    color: #6cf;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.1em;
  }
  .day-value {
    color: #6cf;
    font-weight: bold;
    font-size: 1.25rem;
  }

  .bp {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin: 0.5rem 0;
    padding: 0.4rem 0.6rem;
    background: #0a1418;
    border: 1px solid #1d3340;
    border-radius: 4px;
  }
  .bp-value {
    color: #6cf;
    font-weight: bold;
    font-size: 1rem;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem 0.8rem;
    margin-top: 0.5rem;
  }
  .grid > div {
    display: flex;
    justify-content: space-between;
  }
  .span-2 {
    grid-column: span 2;
  }

  .attrs-title {
    margin-top: 0.85rem;
    padding-top: 0.5rem;
    border-top: 1px solid #1f1f1f;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.7rem;
  }
  .attrs {
    list-style: none;
    padding: 0;
    margin: 0.4rem 0 0 0;
  }
  .attrs li {
    margin-bottom: 0.4rem;
  }
  .attr-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.78rem;
  }
  .attr-name { color: #cfcfcf; }
  .attr-score { color: #777; font-size: 0.72rem; }
  .attr-bar {
    height: 3px;
    background: #1a1a1a;
    border-radius: 2px;
    overflow: hidden;
    margin-top: 0.15rem;
  }
  .attr-fill {
    height: 100%;
    background: #6cf;
    opacity: 0.6;
  }

  .user-name {
    margin-top: 0.7rem;
    padding-top: 0.5rem;
    border-top: 1px solid #1f1f1f;
    color: #555;
    font-size: 0.7rem;
    text-align: right;
  }
</style>
