<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import {
    buyEquipment,
    fetchBoss,
    fetchEquipment,
    fetchJourney,
    fetchJourneyStats,
    fightBoss,
    recover,
    wearEquipment,
    type BossState,
    type Equipment,
    type EquipmentItem,
    type FightResult,
    type JourneyState,
    type JourneyStats,
    type Recovery,
  } from "./api";
  import Icon from "./Icon.svelte";
  import Screen from "./Screen.svelte";
  import { caps } from "./text";
  import { primeAudio } from "./dtmf";
  import { gains as gainsSound, powerOn, tap } from "./sfx";
  import { bumpUser, setBackHandler } from "./store";

  /** Back to the tile home. */
  export let onHome: () => void;

  // The journey: survive from one checkpoint to the next on an hp of 25, every
  // act costing one. Tokens buy hp back. Between the points stand the bosses: the
  // autobattler picks the lineup and the fight plays out in text, line by line.

  const INK = "#00ffd0";
  const LINE_MS = 520;

  type Mode = "main" | "boss" | "fight" | "stats" | "equip";
  let mode: Mode = "main";
  let state: JourneyState | null = null;
  let boss: BossState | null = null;
  let stats: JourneyStats | null = null;
  let gear: Equipment | null = null;
  let fight: FightResult | null = null;
  let shown = 0;
  let message: string[] = [];
  let busy = false;
  let loadedAt = Date.now();
  let now = Date.now();
  let timer: any = null;
  let player: any = null;

  async function load() {
    try {
      [state, boss] = await Promise.all([fetchJourney(), fetchBoss()]);
      loadedAt = Date.now();
      now = loadedAt;
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    }
  }

  $: elapsed = Math.floor((now - loadedAt) / 1000);
  $: secondsLeft = state ? Math.max(0, state.seconds_left - elapsed) : 0;
  $: toPoint = state ? Math.max(0, state.seconds_to_next_point - elapsed) : 0;
  $: progress = state ? Math.min(1, Math.max(0, 1 - secondsLeft / (state.stage_days * 86400))) : 0;

  function clock(total: number): string {
    const d = Math.floor(total / 86400);
    const h = Math.floor((total % 86400) / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const p = (n: number) => String(n).padStart(2, "0");
    return d > 0 ? `${d}d ${p(h)}h` : h > 0 ? `${h}h ${p(m)}m` : `${m}m ${p(s)}s`;
  }

  function press(n = 0) {
    primeAudio();
    tap(n);
  }

  function go(m: Mode) {
    press(m === "main" ? 0 : 4);
    mode = m;
    message = [];
    if (m === "stats") fetchJourneyStats().then((s) => (stats = s)).catch(() => {});
    if (m === "equip") fetchEquipment().then((g) => (gear = g)).catch(() => {});
    powerOn();
  }

  function back(): boolean {
    if (mode === "fight") {
      skip();
      if (fight && shown >= fight.log.length) {
        mode = "main";
        fight = null;
      }
      return true;
    }
    if (mode !== "main") {
      mode = "main";
      message = [];
      return true;
    }
    return false;
  }

  async function heal(r: Recovery) {
    if (busy || !r.ready) return;
    busy = true;
    try {
      const res = await recover(r.kind);
      gainsSound();
      message = [`+${res.healed} hp`, `−${r.cost} tokens`];
      bumpUser();
      await load();
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }

  async function startFight() {
    if (busy) return;
    busy = true;
    press(9);
    try {
      fight = await fightBoss();
      shown = 0;
      mode = "fight";
      message = [];
      player = setInterval(() => {
        if (!fight) return;
        shown += 1;
        tap(fight.log[shown - 1]?.who === "you" ? 3 : 1);
        if (shown >= fight.log.length) finish();
      }, LINE_MS);
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }

  function finish() {
    if (player) clearInterval(player);
    player = null;
    if (!fight) return;
    shown = fight.log.length;
    if (fight.won) gainsSound();
    bumpUser();
    load();
  }

  function skip() {
    if (fight && shown < fight.log.length) finish();
  }

  $: last = fight && shown > 0 ? fight.log[Math.min(shown, fight.log.length) - 1] : null;
  $: bossHp = fight ? (last ? last.boss_hp : fight.boss.hp) : 0;
  $: myHp = fight ? (last ? last.hp : (state?.energy ?? 0)) : 0;
  $: over = !!fight && shown >= fight.log.length;
  $: visible = fight ? fight.log.slice(Math.max(0, Math.min(shown, fight.log.length) - 7), shown) : [];

  async function useItem(item: EquipmentItem) {
    if (busy) return;
    busy = true;
    try {
      gear = item.owned ? await wearEquipment(item.id, !item.worn) : await buyEquipment(item.id);
      press(item.owned ? 5 : 8);
      if (!item.owned) gainsSound();
      bumpUser();
      await load();
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }

  const SLOT_ICON: Record<string, "sword" | "shield" | "amulet"> = { arma: "sword", armadura: "shield", amuleto: "amulet" };
  const LABEL: Record<string, string> = { small: "pequena", large: "grande" };

  onMount(() => {
    setBackHandler(back);
    load().then(() => powerOn());
    timer = setInterval(() => {
      now = Date.now();
      if (state && toPoint === 0 && now - loadedAt > 5000) load();
    }, 1000);
  });
  onDestroy(() => {
    setBackHandler(null);
    clearInterval(timer);
    if (player) clearInterval(player);
  });
</script>

<Screen ink={INK} display="15%">
  <svelte:fragment slot="display">
    {#if message.length}
      {#each message as line, i}<p class={i === 0 ? "big" : "small"}>{line}</p>{/each}
    {:else if mode === "boss" && boss}
      <p class="big keep">{caps(`${boss.boss.name} (${boss.boss.rank})`)}</p>
      <p class="small">{boss.boss.type}</p>
    {:else if mode === "fight" && fight}
      <p class="big">{over ? (fight.won ? "vitória" : "derrota") : fight.boss.name}</p>
      <p class="small">
        {#if over}{fight.won ? `+${fight.points} pontos` : `−${fight.taken} hp${fight.journey_reset ? " · a jornada recomeçou" : ""}`}{:else}toque para pular{/if}
      </p>
    {:else if mode === "stats"}
      <p class="big">stats</p>
      <p class="small">da jornada</p>
    {:else if mode === "equip"}
      <p class="big">equipamento</p>
      <p class="small">{gear ? `${gear.points} pontos` : "…"}</p>
    {:else if state}
      <p class="big">estágio {state.stage}</p>
      <p class="small">checkpoint em {clock(secondsLeft)}{state.resets ? ` · ${state.resets} reinícios` : ""}</p>
    {:else}
      <p class="small">…</p>
    {/if}
  </svelte:fragment>

  {#if mode === "main" && state}
    <!-- the hp: one segment each, as the acts spend them -->
    <div class="meter">
      <p class="label">hp {state.energy}/{state.max_energy}</p>
      <div class="hp" class:low={state.energy <= state.max_energy * 0.3}>
        {#each Array(state.max_energy) as _, i}<i class:on={i < state.energy}></i>{/each}
      </div>
    </div>
    <div class="meter">
      <p class="label">estágio · {state.points.filter((p) => p.reached).length}/{state.points.length} pontos · próximo em {clock(toPoint)}</p>
      <div class="track">
        <div class="fill" style="width: {progress * 100}%"></div>
        {#each state.points as p (p.day)}<span class="pt" class:on={p.reached} style="left: {(p.day / state.stage_days) * 100}%"></span>{/each}
      </div>
    </div>
    <p class="label">recuperar · {state.tokens} tokens</p>
    <div class="keys two">
      {#each state.recover as r (r.kind)}
        <button class="key heal" disabled={busy || !r.ready} on:click={() => heal(r)}>
          <Icon name="heart" size={16} />
          <span>+{r.heal} · {r.cost}t</span>
          <span class="sub">{r.blocked === "cooldown" ? clock(Math.max(0, r.seconds_left - elapsed)) : r.blocked === "full" ? "cheio" : r.blocked === "tokens" ? "sem tokens" : LABEL[r.kind]}</span>
        </button>
      {/each}
    </div>
    {#if boss}
      <p class="label">chefe do trecho</p>
      <button class="row boss-row" class:dim={boss.beaten} on:click={() => go("boss")}>
        <Icon name={boss.beaten ? "check" : "bolt"} size={16} />
        <span class="grow">{caps(`${boss.boss.name} (${boss.boss.rank}) · ${boss.boss.type}`)}</span>
        <span class="tag">{boss.beaten ? "vencido" : `${boss.boss.hp} hp`}</span>
      </button>
    {/if}
  {:else if mode === "boss" && boss}
    {@const b = boss.boss}
    <dl class="stats five">
      <dt>hp</dt><dd>{b.hp}</dd>
      <dt>mp</dt><dd>{b.mp}</dd>
      <dt>ataque</dt><dd>{b.attack}</dd>
      <dt>especial</dt><dd>{b.special}</dd>
      <dt>defesa</dt><dd>{b.defense}%</dd>
    </dl>
    <p class="label">habilidades</p>
    {#each b.abilities as a (a.name)}
      <div class="text-line">{caps(a.name)} <span class="tag">· {a.power}</span></div>
    {/each}
    <p class="label">escalação · fraco contra {b.types.map((t) => t.name.toLowerCase()).join(", ")}</p>
    {#each boss.lineup as m (m.action_id)}
      <div class="text-line">
        {caps(m.name)}{#if m.multiplier > 1}<span class="mult"> ×{m.multiplier} {caps(m.kinship)}</span>{/if}
        <span class="tag">→ {m.damage}</span>
      </div>
    {:else}
      <p class="empty">nenhuma ação para lutar — adquira no shop</p>
    {/each}
    <div class="keys">
      <button class="key fight" disabled={busy || boss.beaten || !boss.lineup.length || boss.hp <= 0} on:click={startFight}>
        <Icon name="bolt" /> {boss.beaten ? "vencido" : `lutar · +${boss.reward}`}
      </button>
    </div>
  {:else if mode === "fight" && fight}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="arena" on:click={skip}>
      <div class="versus">
        <span>VOCÊ {myHp}</span>
        <span>{fight.boss.name} {bossHp}/{fight.boss.hp}</span>
      </div>
      <div class="bossbar"><div style="width: {(bossHp / fight.boss.hp) * 100}%"></div></div>
      <div class="log">
        {#each visible as l, i (shown - visible.length + i)}
          <p class="fl" class:you={l.who === "you"}>{l.text} <span>{l.who === "you" ? `−${l.damage}` : `−${l.damage} hp`}</span></p>
        {/each}
        {#if over}
          <p class="fl end">{fight.won ? `${fight.boss.name} CAIU.` : "VOCÊ RECUOU."}</p>
        {/if}
      </div>
    </div>
  {:else if mode === "stats"}
    {#if stats}
      <dl class="stats">
        <dt>lutas</dt><dd>{stats.fights}</dd>
        <dt>vitórias</dt><dd>{stats.wins}</dd>
        <dt>derrotas</dt><dd>{stats.losses}</dd>
        <dt>chefes vencidos</dt><dd>{stats.bosses}</dd>
        <dt>dano causado</dt><dd>{stats.dealt}</dd>
        <dt>dano recebido</dt><dd>{stats.taken}</dd>
        <dt>maior golpe</dt><dd>{stats.best_hit}</dd>
        <dt>pontos ganhos</dt><dd>{stats.points_won}</dd>
        <dt>maior estágio</dt><dd>{stats.highest_stage}</dd>
        <dt>reinícios</dt><dd>{stats.resets}</dd>
        <dt>recuperações</dt><dd>{stats.recover_uses}</dd>
      </dl>
    {:else}
      <p class="empty">…</p>
    {/if}
  {:else if mode === "equip"}
    {#if gear}
      {#each gear.slots as slot (slot)}
        <p class="label">{slot}</p>
        {#each gear.items.filter((i) => i.slot === slot) as item (item.id)}
          <button class="row" class:on-row={item.worn} disabled={busy || (!item.owned && gear.points < item.price)} on:click={() => useItem(item)}>
            <Icon name={SLOT_ICON[slot]} size={16} />
            <span class="grow">{item.name}<span class="sub"> · {item.text}</span></span>
            <span class="tag">{item.worn ? "em uso" : item.owned ? "vestir" : `${item.price} pts`}</span>
          </button>
        {/each}
      {/each}
    {:else}
      <p class="empty">…</p>
    {/if}
  {/if}

  <svelte:fragment slot="bar">
    {#if mode === "main"}
      <button class="key" aria-label="chefe" on:click={() => go("boss")}><Icon name="bolt" /></button>
      <button class="key" aria-label="equipamento" on:click={() => go("equip")}><Icon name="shield" /></button>
      <button class="key" aria-label="stats" on:click={() => go("stats")}><Icon name="bars" /></button>
      <span></span><span></span>
      <button class="key home" aria-label="início" on:click={() => { press(0); onHome(); }}><Icon name="circle" size={16} /></button>
    {:else}
      <button class="key back-key" aria-label="voltar" on:click={() => { press(0); back(); }}><Icon name="left" /></button>
      <button class="key home" aria-label="início" on:click={() => { press(0); onHome(); }}><Icon name="circle" size={16} /></button>
    {/if}
  </svelte:fragment>
</Screen>

<style>
  .meter { display: flex; flex-direction: column; gap: 6px; }
  .hp { display: flex; gap: 2px; height: 18px; }
  .hp i { flex: 1; border: 1px solid var(--ink); opacity: 0.35; }
  .hp i.on { background: var(--ink); opacity: 1; }
  .hp.low i.on { background: #ff5c7a; border-color: #ff5c7a; }
  .track { position: relative; height: 10px; border: 1.5px solid var(--ink); }
  .fill { position: absolute; inset: 0 auto 0 0; background: color-mix(in srgb, var(--ink) 45%, transparent); }
  .pt { position: absolute; top: -4px; width: 2px; height: 14px; background: #ffffff; opacity: 0.4; transform: translateX(-1px); }
  .pt.on { opacity: 1; }

  .keys { display: grid; grid-template-columns: 1fr; gap: 8px; }
  .keys.two { grid-template-columns: 1fr 1fr; }
  .heal { flex-direction: column; min-height: 4rem; gap: 0.2rem; }
  .heal .sub { font-size: 0.62rem; opacity: 0.7; }
  .fight { min-height: 3rem; font-size: 0.9rem; }
  .dim { opacity: 0.55; }
  .on-row { background: color-mix(in srgb, var(--ink) 22%, transparent); }
  .sub { color: rgba(255, 255, 255, 0.55); font-size: 0.68rem; }

  .stats {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.4rem 1rem;
    margin: 0;
    padding: 0.8rem;
    border: 1.5px solid var(--ink);
    font-family: var(--font-mono);
    font-size: 0.85rem;
  }
  .stats dt { color: var(--ink); text-transform: uppercase; font-size: 0.7rem; align-self: center; }
  .stats dd { margin: 0; text-align: right; }
  .text-line {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: #ffffff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .text-line .tag, .text-line .mult { color: var(--ink); }

  /* the fight: text, the autobattler reading itself aloud */
  .arena {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 0.8rem;
    border: 1.5px solid var(--ink);
    cursor: pointer;
    font-family: var(--font-display);
  }
  .versus { display: flex; justify-content: space-between; font-size: 0.72rem; letter-spacing: 0.08em; color: var(--ink); }
  .bossbar { height: 6px; border: 1px solid var(--ink); }
  .bossbar div { height: 100%; background: var(--ink); transition: width 0.3s; }
  .log { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; gap: 0.55rem; overflow: hidden; }
  .fl { margin: 0; font-size: 0.8rem; letter-spacing: 0.06em; color: #ff8fa3; animation: arrive 0.3s ease-out; }
  .fl.you { color: #ffffff; }
  .fl span { color: var(--ink); }
  .fl.end { color: var(--ink); font-size: 1rem; font-weight: 600; }
  @keyframes arrive {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: none; }
  }
  .back-key { grid-column: 1 / 3; }
</style>
