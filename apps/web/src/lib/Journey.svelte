<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { fetchJourney, type JourneyState } from "./api";

  let state: JourneyState | null = null;
  // the countdowns run on the phone's clock from the seconds the server sent
  let loadedAt = 0;
  let now = Date.now();
  let loading = true;
  let error: string | null = null;
  let tick: any = null;

  async function load() {
    try {
      state = await fetchJourney();
      loadedAt = Date.now();
      now = loadedAt;
      error = null;
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    load();
    tick = setInterval(() => {
      now = Date.now();
      // a point or the checkpoint just passed: the server pays it on the next load
      // (at most every 5 s, in case the two clocks disagree by a little)
      if (state && !loading && secondsToPoint === 0 && now - loadedAt > 5000) {
        loading = true;
        load();
      }
    }, 1000);
  });
  onDestroy(() => tick && clearInterval(tick));

  $: elapsed = Math.floor((now - loadedAt) / 1000);
  $: secondsLeft = state ? Math.max(0, state.seconds_left - elapsed) : 0;
  $: secondsToPoint = state ? Math.max(0, state.seconds_to_next_point - elapsed) : 0;
  $: nextIsCheckpoint = state ? state.points.every((p) => p.reached) : true;

  function split(total: number) {
    return {
      d: Math.floor(total / 86400),
      h: Math.floor((total % 86400) / 3600),
      m: Math.floor((total % 3600) / 60),
      s: total % 60,
    };
  }
  const pad = (n: number) => n.toString().padStart(2, "0");
  function short(total: number) {
    const t = split(total);
    if (t.d > 0) return `${t.d}d ${t.h}h`;
    if (t.h > 0) return `${t.h}h ${pad(t.m)}m`;
    return `${t.m}m ${pad(t.s)}s`;
  }

  $: left = split(secondsLeft);
  $: stageSeconds = state ? state.stage_days * 86400 : 1;
  $: progress = state ? Math.min(1, Math.max(0, 1 - secondsLeft / stageSeconds)) : 0;
  $: energyPct = state && state.max_energy > 0 ? state.energy / state.max_energy : 0;
  $: actsLeft = state ? Math.ceil(state.energy / Math.max(1, state.energy_penalty)) : 0;
  $: nextReward = (() => {
    if (!state) return "";
    const reached = state.points.filter((p) => p.reached);
    const from = reached.length ? reached[reached.length - 1].day : 0;
    const upcoming = state.points.find((p) => !p.reached);
    const to = upcoming ? upcoming.day : state.stage_days;
    const build = (to - from) * state.build_points_per_day;
    return nextIsCheckpoint
      ? `+${build} build · +${state.checkpoint_skill_points} skill`
      : `+${build} build`;
  })();
  $: unit = state && state.stage_days > 60 ? "mês" : state && state.stage_days > 14 ? "semana" : "dia";
</script>

<section class="page">
  <header class="head">
    <h1>journey</h1>
  </header>

  {#if loading && !state}
    <p class="muted">…</p>
  {:else if error && !state}
    <p class="error">{error}</p>
  {:else if state}
    <div class="stage-line">
      <span class="stage">estágio {state.stage}</span>
      <span class="muted">{state.stage_days} {state.stage_days === 1 ? "dia" : "dias"}</span>
      {#if state.resets > 0}
        <span class="muted resets">{state.resets} {state.resets === 1 ? "reinício" : "reinícios"}</span>
      {/if}
    </div>

    <div class="countdown">
      <span class="label">próximo checkpoint em</span>
      <div class="time">
        {#if left.d > 0}
          <span class="num">{left.d}</span><span class="tag">d</span>
        {/if}
        <span class="num">{pad(left.h)}</span><span class="tag">h</span>
        <span class="num">{pad(left.m)}</span><span class="tag">m</span>
        <span class="num">{pad(left.s)}</span><span class="tag">s</span>
      </div>
    </div>

    <div class="track" aria-label="progresso do estágio">
      <div class="fill" style="width: {progress * 100}%"></div>
      {#each state.points as p (p.day)}
        <span
          class="tick"
          class:reached={p.reached}
          style="left: {(p.day / state.stage_days) * 100}%"
          title="{unit} · dia {p.day}"
        ></span>
      {/each}
    </div>
    <div class="track-legend">
      <span>{state.points.filter((p) => p.reached).length}/{state.points.length} pontos</span>
      <span>
        {nextIsCheckpoint ? "checkpoint" : "próximo ponto"} em {short(secondsToPoint)} · {nextReward}
      </span>
    </div>

    <section class="card">
      <div class="energy-head">
        <span class="label">energia</span>
        <span class="energy-val">{state.energy}/{state.max_energy}</span>
      </div>
      <div class="energy-bar" class:low={energyPct <= 0.2}>
        <div class="energy-fill" style="width: {energyPct * 100}%"></div>
      </div>
      <p class="rule">
        Cada ação fora da agenda do dia custa {state.energy_penalty} de energia — cabem mais
        {actsLeft}. Cada ponto e o checkpoint enchem a energia de novo. Se ela zerar, a
        jornada volta ao estágio 1.
      </p>
    </section>
  {/if}
</section>

<style>
  .page {
    height: 100%;
    box-sizing: border-box;
    padding: 1.5rem 2rem;
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
    overflow-y: auto;
    max-width: 40rem;
  }
  .head { margin-bottom: 1rem; }
  h1 {
    margin: 0;
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 1.05rem;
  }
  .muted { color: #808080; font-size: 0.8rem; }
  .error { color: #ff4d4d; }
  .label {
    color: #808080;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.1em;
  }

  .stage-line {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 1.25rem;
  }
  .stage {
    color: #00e5ff;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .resets { margin-left: auto; }

  .countdown {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-bottom: 1.5rem;
  }
  .time {
    display: flex;
    align-items: baseline;
    gap: 0.2rem;
  }
  .num {
    color: #ffffff;
    font-weight: bold;
    font-size: 2.2rem;
    font-variant-numeric: tabular-nums;
  }
  .tag {
    color: #808080;
    font-size: 0.8rem;
    margin-right: 0.5rem;
  }

  .track {
    position: relative;
    height: 10px;
    border-radius: 999px;
    background: #333333;
  }
  .fill {
    position: absolute;
    inset: 0 auto 0 0;
    border-radius: 999px;
    background: #00e5ff;
  }
  .tick {
    position: absolute;
    top: -3px;
    width: 2px;
    height: 16px;
    margin-left: -1px;
    background: #808080;
  }
  .tick.reached { background: #000000; }
  .track-legend {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin: 0.5rem 0 1.5rem;
    color: #808080;
    font-size: 0.75rem;
  }

  .card {
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0.95rem 1.1rem;
  }
  .energy-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.5rem;
  }
  .energy-val {
    font-variant-numeric: tabular-nums;
    font-size: 0.95rem;
  }
  .energy-bar {
    height: 10px;
    border-radius: 999px;
    background: #333333;
    overflow: hidden;
  }
  .energy-fill {
    height: 100%;
    background: #ffffff;
  }
  .energy-bar.low .energy-fill { background: #ff4d4d; }
  .rule {
    margin: 0.75rem 0 0;
    color: #808080;
    font-size: 0.78rem;
    line-height: 1.45;
  }

  @media (max-width: 768px) {
    .page { padding: 0.75rem 0.9rem; }
    .num { font-size: 1.8rem; }
  }
</style>
