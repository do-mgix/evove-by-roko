<script lang="ts">
  export let widgets: { id: string; label: string; icon: string }[];
  export let onWidgetDragStart: (e: DragEvent, id: string) => void;
</script>

<div class="tray">
  {#if widgets.length === 0}
    <span class="hint">arraste a label de uma janela para mover · arraste daqui para adicionar</span>
  {:else}
    {#each widgets as w (w.id)}
      <div
        class="widget"
        draggable="true"
        on:dragstart={(e) => onWidgetDragStart(e, w.id)}
        title={w.label}
      >
        <span class="icon">{w.icon}</span>
        <span class="label">{w.label}</span>
      </div>
    {/each}
  {/if}
</div>

<style>
  .tray {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: #000000;
    border-top: 1px solid #333333;
    min-height: 56px;
    box-sizing: border-box;
  }
  .widget {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 0.4rem 0.7rem;
    border: 1px solid #333333;
    border-radius: 4px;
    background: #000000;
    cursor: grab;
    transition: all 0.15s;
    min-width: 64px;
  }
  .widget:hover {
    border-color: #00e5ff;
    color: #00e5ff;
  }
  .widget:active {
    cursor: grabbing;
  }
  .icon {
    font-size: 1.1rem;
    color: #808080;
    line-height: 1;
  }
  .widget:hover .icon {
    color: #00e5ff;
  }
  .label {
    color: #808080;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.25rem;
  }
  .widget:hover .label {
    color: #808080;
  }
  .hint {
    color: #808080;
    font-size: 0.75rem;
  }
</style>
