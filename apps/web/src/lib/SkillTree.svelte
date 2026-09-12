<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { fetchSkillTree, acquireSkill, type SkillNode, type SkillTree } from "./api";

  let nodes: SkillNode[] = [];
  let acquired: Set<string> = new Set();
  let sp = 0;
  let loading = true;
  let error: string | null = null;
  let busy: string | null = null;
  let selected: SkillNode | null = null;

  // pan state — viewport center maps to world (panX, panY)
  let panX = 0;
  let panY = 0;
  let viewport: HTMLDivElement;

  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let panStartX = 0;
  let panStartY = 0;
  let movedDuringDrag = false;

  let panTimer: any = null;

  async function load() {
    loading = true;
    try {
      const tree: SkillTree = await fetchSkillTree();
      nodes = tree.nodes;
      acquired = new Set(tree.acquired);
      sp = tree.skill_points;
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  onMount(load);
  onDestroy(() => panTimer && clearInterval(panTimer));

  function nodeById(id: string | null): SkillNode | null {
    if (!id) return null;
    return nodes.find((n) => n.id === id) ?? null;
  }

  function isUnlocked(n: SkillNode): boolean {
    if (n.id === "root") return true;
    if (acquired.has(n.id)) return true;
    return acquired.has(n.parent ?? "") || n.parent === "root";
  }

  function effectLabel(n: SkillNode): string {
    if (!n.effect) return "—";
    const v = n.effect.value;
    switch (n.effect.type) {
      case "max_energy": return `+${v} max energy`;
      case "max_tokens": return `+${v} max tokens`;
      case "xp_multiplier": return `×${v} xp`;
      case "points_multiplier": return `×${v} sp/bp`;
      default: return n.effect.type;
    }
  }

  async function buy(n: SkillNode) {
    if (busy || acquired.has(n.id) || !isUnlocked(n)) return;
    if (sp < n.cost) return;
    busy = n.id;
    try {
      const res = await acquireSkill(n.id);
      acquired = new Set(res.acquired);
      sp = res.skill_points;
      if (selected?.id === n.id) selected = null;
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      busy = null;
    }
  }

  // Pan via drag on background
  function onPointerDown(e: PointerEvent) {
    if ((e.target as HTMLElement).closest(".skill-node")) return;
    dragging = true;
    movedDuringDrag = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    panStartX = panX;
    panStartY = panY;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: PointerEvent) {
    if (!dragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    if (Math.abs(dx) + Math.abs(dy) > 4) movedDuringDrag = true;
    panX = panStartX - dx;
    panY = panStartY - dy;
  }
  function onPointerUp(e: PointerEvent) {
    if (!dragging) return;
    dragging = false;
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  }

  // Edge arrow navigation
  const PAN_STEP = 8;
  function startPan(dx: number, dy: number) {
    if (panTimer) clearInterval(panTimer);
    panTimer = setInterval(() => {
      panX += dx * PAN_STEP;
      panY += dy * PAN_STEP;
    }, 16);
  }
  function stopPan() {
    if (panTimer) {
      clearInterval(panTimer);
      panTimer = null;
    }
  }

  function recenter() {
    panX = 0;
    panY = 0;
  }
</script>

<section class="page" on:pointerleave={stopPan}>
  <header class="topbar">
    <span class="title">skill tree</span>
    <button class="recenter" on:click={recenter} title="recentralizar">◎</button>
    <div class="sp-badge">
      <span class="sp-label">skill points</span>
      <span class="sp-value">{sp}</span>
    </div>
  </header>

  {#if loading}
    <p class="status">…</p>
  {:else if error}
    <p class="status err">{error}</p>
  {:else}
    <div
      class="viewport"
      bind:this={viewport}
      on:pointerdown={onPointerDown}
      on:pointermove={onPointerMove}
      on:pointerup={onPointerUp}
      on:pointercancel={onPointerUp}
    >
      <div class="canvas" style="transform: translate(calc(50% + {-panX}px), calc(50% + {-panY}px));">
        <svg class="connections" width="4000" height="4000" style="left: -2000px; top: -2000px;">
          {#each nodes.filter((n) => n.parent) as n (n.id + ':line')}
            {@const p = nodeById(n.parent)}
            {#if p}
              <line
                x1={2000 + p.x}
                y1={2000 + p.y}
                x2={2000 + n.x}
                y2={2000 + n.y}
                stroke={acquired.has(n.id) ? "#00e5ff" : "#333333"}
                stroke-width="2"
              />
            {/if}
          {/each}
        </svg>

        {#each nodes as n (n.id)}
          {@const owned = acquired.has(n.id) || n.id === "root"}
          {@const unlocked = isUnlocked(n)}
          {@const affordable = sp >= n.cost}
          <button
            class="skill-node"
            class:owned
            class:locked={!unlocked && !owned}
            class:cant-afford={unlocked && !owned && !affordable}
            style="left: {n.x}px; top: {n.y}px;"
            on:click={() => (selected = n)}
            disabled={!unlocked && !owned}
          >
            <span class="node-label">{n.label}</span>
            {#if n.id !== "root"}
              <span class="node-cost">{owned ? "✓" : `${n.cost} sp`}</span>
            {/if}
          </button>
        {/each}
      </div>

      <button class="edge top" on:pointerdown={() => startPan(0, -1)} on:pointerup={stopPan} on:pointerleave={stopPan} aria-label="up">▲</button>
      <button class="edge bottom" on:pointerdown={() => startPan(0, 1)} on:pointerup={stopPan} on:pointerleave={stopPan} aria-label="down">▼</button>
      <button class="edge left" on:pointerdown={() => startPan(-1, 0)} on:pointerup={stopPan} on:pointerleave={stopPan} aria-label="left">◀</button>
      <button class="edge right" on:pointerdown={() => startPan(1, 0)} on:pointerup={stopPan} on:pointerleave={stopPan} aria-label="right">▶</button>
    </div>
  {/if}
</section>

{#if selected}
  <div class="modal-backdrop" on:click={() => (selected = null)}></div>
  <div class="modal">
    <header class="m-head">
      <span class="m-title">{selected.label}</span>
      <button class="m-close" on:click={() => (selected = null)}>×</button>
    </header>
    <dl class="m-body">
      <dt>efeito</dt><dd>{effectLabel(selected)}</dd>
      <dt>custo</dt><dd>{selected.cost} sp</dd>
      <dt>status</dt>
      <dd>
        {#if acquired.has(selected.id)}adquirida
        {:else if !isUnlocked(selected)}bloqueada
        {:else if sp < selected.cost}sem skill points
        {:else}disponível{/if}
      </dd>
    </dl>
    <div class="m-actions">
      <button class="ghost" on:click={() => (selected = null)}>fechar</button>
      <button
        class="primary"
        on:click={() => selected && buy(selected)}
        disabled={!selected || acquired.has(selected.id) || !isUnlocked(selected) || sp < selected.cost || busy !== null}
      >
        {busy ? "..." : "adquirir"}
      </button>
    </div>
  </div>
{/if}

<style>
  .page {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
  }
  :global(body) { overflow: hidden; }
  .topbar {
    position: absolute;
    top: 1rem;
    left: 1.5rem;
    right: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    z-index: 10;
  }
  .title {
    color: #808080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.85rem;
  }
  .recenter {
    background: #000000;
    border: 1px solid #333333;
    color: #808080;
    padding: 0.3rem 0.55rem;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
  }
  .recenter:hover { color: #00e5ff; border-color: #00e5ff; }
  .sp-badge {
    margin-left: auto;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    background: #000000;
    border: 1px solid #000000;
    padding: 0.4rem 0.85rem;
    border-radius: 4px;
  }
  .sp-label {
    color: #808080;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .sp-value {
    color: #00e5ff;
    font-weight: bold;
    font-size: 1rem;
  }
  .status { color: #808080; padding: 2rem; }
  .status.err { color: #ff4d4d; }
  .viewport {
    position: absolute;
    inset: 0;
    overflow: hidden;
    cursor: grab;
    user-select: none;
    touch-action: none;
  }
  .viewport:active { cursor: grabbing; }
  .canvas {
    position: absolute;
    width: 0;
    height: 0;
    transform-origin: 0 0;
  }
  .connections {
    position: absolute;
    pointer-events: none;
  }
  .skill-node {
    position: absolute;
    transform: translate(-50%, -50%);
    width: 130px;
    background: #000000;
    border: 2px solid #333333;
    border-radius: 6px;
    padding: 0.55rem 0.7rem;
    color: #cccccc;
    font: inherit;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.2rem;
  }
  .skill-node:hover:not(:disabled) {
    border-color: #00e5ff;
    background: #000000;
  }
  .skill-node.owned {
    border-color: #00e5ff;
    background: #000000;
  }
  .skill-node.owned .node-label { color: #00e5ff; }
  .skill-node.locked {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .skill-node.cant-afford {
    opacity: 0.65;
  }
  .node-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .node-cost {
    color: #808080;
    font-size: 0.7rem;
  }
  .skill-node.owned .node-cost { color: #00e5ff; }

  .edge {
    position: absolute;
    background: rgba(0, 0, 0, 0.85);
    border: 1px solid #333333;
    color: #808080;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    cursor: pointer;
    font: inherit;
    font-size: 0.75rem;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.15s, border-color 0.15s, transform 0.1s;
  }
  .edge:hover { color: #00e5ff; border-color: #00e5ff; }
  .edge:active { transform: scale(0.92); }
  .edge.top { top: 4rem; left: 50%; transform: translateX(-50%); }
  .edge.bottom { bottom: 1rem; left: 50%; transform: translateX(-50%); }
  .edge.left { left: 1rem; top: 50%; transform: translateY(-50%); }
  .edge.right { right: 1rem; top: 50%; transform: translateY(-50%); }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    z-index: 99;
  }
  .modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: #000000;
    border: 1px solid #333333;
    border-radius: 8px;
    min-width: 320px;
    z-index: 100;
    overflow: hidden;
  }
  .m-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #333333;
  }
  .m-title {
    color: #00e5ff;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
  }
  .m-close {
    background: transparent;
    border: none;
    color: #808080;
    font-size: 1.4rem;
    line-height: 1;
    cursor: pointer;
  }
  .m-close:hover { color: #ff4d4d; }
  .m-body {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.5rem 1rem;
    padding: 1rem 1.25rem;
    margin: 0;
  }
  .m-body dt {
    color: #808080;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
  }
  .m-body dd {
    color: #ffffff;
    margin: 0;
    font-size: 0.9rem;
  }
  .m-actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
    padding: 0 1.25rem 1rem;
  }
  .ghost, .primary {
    padding: 0.5rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .ghost { background: transparent; color: #808080; border-color: #333333; }
  .ghost:hover { color: #cccccc; border-color: #808080; }
  .primary { background: #00e5ff; color: #000000; border-color: #00e5ff; }
  .primary:hover:not(:disabled) { background: #00a3b8; }
  .primary:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
