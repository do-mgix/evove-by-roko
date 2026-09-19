<script lang="ts">
  import { onMount, onDestroy } from "svelte";

  // five columns shrink to unreadable circles at phone width; three stay legible
  const NARROW_QUERY = "(max-width: 520px)";
  let narrow = false;
  onMount(() => {
    const mq = window.matchMedia(NARROW_QUERY);
    const apply = () => (narrow = mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  });
  import { fetchJourney, type JourneyState } from "./api";

  let state: JourneyState | null = null;
  let nextAt: number | null = null;
  let now = Date.now();
  let loading = true;
  let error: string | null = null;
  let tick: any = null;

  async function load() {
    try {
      state = await fetchJourney();
      nextAt = new Date(state.next_checkpoint_at).getTime();
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    load();
    tick = setInterval(() => (now = Date.now()), 1000);
  });
  onDestroy(() => tick && clearInterval(tick));

  $: secondsLeft = nextAt ? Math.max(0, Math.floor((nextAt - now) / 1000)) : 0;
  $: hh = Math.floor(secondsLeft / 3600);
  $: mm = Math.floor((secondsLeft % 3600) / 60);
  $: ss = secondsLeft % 60;
  $: pad = (n: number) => n.toString().padStart(2, "0");

  // Path map: zigzag layout of stages around current
  const SHOW_BEFORE = 4;
  const SHOW_AFTER = 8;
  $: COLS = narrow ? 3 : 5;

  $: stages = (() => {
    if (!state) return [] as { n: number; x: number; y: number; status: "done" | "current" | "future" }[];
    const cur = state.stage;
    const start = Math.max(1, cur - SHOW_BEFORE);
    const end = cur + SHOW_AFTER;
    const out = [];
    for (let n = start; n <= end; n++) {
      const idx = n - start;
      const row = Math.floor(idx / COLS);
      const colInRow = idx % COLS;
      // Zigzag: even rows left-to-right, odd rows right-to-left
      const col = row % 2 === 0 ? colInRow : COLS - 1 - colInRow;
      out.push({
        n,
        x: 80 + col * 130,
        y: 80 + row * 130,
        status: n < cur ? "done" : n === cur ? "current" : "future",
      });
    }
    return out;
  })();

  // the same 80 of margin on both sides of the outer columns
  $: viewW = 160 + (COLS - 1) * 130;
  $: viewH = stages.length > 0 ? stages[stages.length - 1].y + 80 : 200;
</script>

<section class="page">
  <header class="head">
    <h1>journey</h1>
  </header>

  {#if loading}
    <p class="muted">…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if state}
    <div class="countdown-card">
      <div class="cd-block">
        <span class="cd-label">próximo checkpoint em</span>
        <div class="cd-time">
          <div class="cd-unit">
            <span class="cd-num">{pad(hh)}</span>
            <span class="cd-tag">h</span>
          </div>
          <span class="cd-sep">:</span>
          <div class="cd-unit">
            <span class="cd-num">{pad(mm)}</span>
            <span class="cd-tag">m</span>
          </div>
          <span class="cd-sep">:</span>
          <div class="cd-unit">
            <span class="cd-num">{pad(ss)}</span>
            <span class="cd-tag">s</span>
          </div>
        </div>
        <span class="cd-sub">
          {state.days_until_next_checkpoint} dias · stage {state.stage} (intervalo {state.interval_for_current_stage}d)
        </span>
      </div>
    </div>

    <div class="map-wrap">
      <svg viewBox="0 0 {viewW} {viewH}" preserveAspectRatio="xMidYMid meet" class="map">
        <!-- Path lines connecting stages in order -->
        {#each stages as s, i (s.n)}
          {#if i < stages.length - 1}
            {@const next = stages[i + 1]}
            <path
              d="M {s.x} {s.y} Q {(s.x + next.x) / 2} {s.y} {(s.x + next.x) / 2} {(s.y + next.y) / 2} T {next.x} {next.y}"
              stroke={s.status === "done" || s.status === "current" ? "#00e5ff" : "#333333"}
              stroke-width="2"
              fill="none"
              stroke-dasharray={s.status === "future" ? "6 5" : "0"}
            />
          {/if}
        {/each}

        <!-- Stage nodes -->
        {#each stages as s (s.n)}
          <g class="stage-node {s.status}">
            <circle cx={s.x} cy={s.y} r="28"
              fill={s.status === "current" ? "#000000" : s.status === "done" ? "#000000" : "#000000"}
              stroke={s.status === "current" ? "#00e5ff" : s.status === "done" ? "#000000" : "#333333"}
              stroke-width={s.status === "current" ? 3 : 2}
            />
            <text x={s.x} y={s.y + 5}
              text-anchor="middle"
              fill={s.status === "current" ? "#00e5ff" : s.status === "done" ? "#00e5ff" : "#808080"}
              font-family="Arial, Helvetica, sans-serif"
              font-size="14"
              font-weight={s.status === "current" ? "bold" : "normal"}
            >{s.n}</text>
          </g>
        {/each}
      </svg>
    </div>
  {/if}
</section>

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
  .head {
    margin-bottom: 1rem;
  }
  h1 {
    margin: 0;
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 1.05rem;
  }
  .muted { color: #808080; }
  .error { color: #ff4d4d; }

  .countdown-card {
    background: #000000;
    border: 1px solid #000000;
    border-radius: 6px;
    padding: 1rem 1.5rem;
    margin-bottom: 1.25rem;
    background: linear-gradient(135deg, #000000, #000000 70%);
  }
  .cd-block {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-start;
  }
  .cd-label {
    color: #808080;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.1em;
  }
  .cd-time {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
  }
  .cd-unit {
    display: flex;
    align-items: baseline;
    gap: 0.15rem;
  }
  .cd-num {
    color: #00e5ff;
    font-weight: bold;
    font-size: 2rem;
    font-variant-numeric: tabular-nums;
  }
  .cd-tag {
    color: #808080;
    font-size: 0.75rem;
  }
  .cd-sep {
    color: #000000;
    font-size: 1.4rem;
  }
  .cd-sub {
    color: #808080;
    font-size: 0.8rem;
  }

  .map-wrap {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    background: #000000;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0.5rem;
  }
  .map {
    width: 100%;
    height: auto;
  }
  .stage-node.current circle {
    filter: drop-shadow(0 0 8px rgba(0, 229, 255, 0.5));
  }

  @media (max-width: 768px) {
    .page { padding: 0.75rem 0.9rem; }
    .countdown-card { padding: 0.5rem 0.25rem; margin-bottom: 0.75rem; }
  }
</style>
