<script lang="ts">
  export let dragOver = false;
</script>

<div class="empty-slot" class:drag-over={dragOver}>
  <span class="plus">+</span>
</div>

<style>
  .empty-slot {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    border: 1px dashed #333333;
    border-radius: 6px;
    background: transparent;
    transition: all 0.15s;
  }
  .empty-slot.drag-over {
    border-color: #00e5ff;
    background: #000000;
  }
  .plus {
    color: #333333;
    font-size: 2rem;
    font-weight: 200;
    transition: color 0.15s;
  }
  .drag-over .plus {
    color: #00e5ff;
  }
</style>
