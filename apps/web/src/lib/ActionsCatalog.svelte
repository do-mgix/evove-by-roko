<script lang="ts">
  import { onMount } from "svelte";
  import { fetchPackages, fetchUser, fetchActions, buyPackageAction, type Package, type PackageAction } from "./api";
  import Modal from "./Modal.svelte";

  export let filter: string | null = null;

  let packages: Package[] = [];
  let buildPoints = 0;
  let owned: Set<string> = new Set();
  let loading = true;
  let error: string | null = null;
  let busy: string | null = null;
  let selected: { pkg: Package; action: PackageAction } | null = null;

  $: filteredPackages = filter
    ? packages.filter((p) => p.attribute === filter)
    : packages;

  const TYPE_LABEL: Record<number, string> = {
    0: "session",
    1: "reps",
    2: "seconds",
    3: "minutes",
    4: "hours",
    5: "letters",
    6: "lines",
    7: "words",
    8: "group",
  };

  async function refresh() {
    loading = true;
    error = null;
    try {
      const [pkgs, user, userActions] = await Promise.all([
        fetchPackages(),
        fetchUser().catch(() => null),
        fetchActions().catch(() => []),
      ]);
      packages = pkgs;
      buildPoints = user?.build_points ?? 0;
      owned = new Set(userActions.map((a) => a.name.toUpperCase()));
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      loading = false;
    }
  }

  async function buy(pkg: Package, action: PackageAction) {
    if (busy) return;
    busy = `${pkg.attribute}:${action.name}`;
    error = null;
    try {
      const res = await buyPackageAction(pkg.attribute, action.name);
      buildPoints = res.build_points;
      owned = new Set([...owned, action.name.toUpperCase()]);
      if (selected && selected.action.name === action.name && selected.pkg.attribute === pkg.attribute) {
        selected = null;
      }
    } catch (e: any) {
      error = e?.message ?? "erro";
    } finally {
      busy = null;
    }
  }

  onMount(refresh);
</script>

<section class="catalog">
  {#if loading}
    <p class="muted">…</p>
  {:else if error}
    <p class="error">{error}</p>
  {/if}

  <div class="packages">
    {#each filteredPackages as pkg (pkg.attribute)}
      <div class="package">
        <div class="package-title">{pkg.attribute}</div>
        <ul>
          {#each pkg.actions as a (a.name)}
            {@const acquired = owned.has(a.name.toUpperCase())}
            <li class:owned={acquired}>
              <button class="info-btn" on:click={() => (selected = { pkg, action: a })} disabled={acquired}>
                <span class="name">{a.name}</span>
                <span class="meta">{TYPE_LABEL[a.type] ?? a.type} · d{a.diff}</span>
              </button>
              {#if acquired}
                <span class="owned-tag">owned</span>
              {:else}
                <button
                  class="buy"
                  on:click|stopPropagation={() => buy(pkg, a)}
                  disabled={busy === `${pkg.attribute}:${a.name}` || buildPoints < a.cost}
                  title="comprar diretamente"
                >
                  {busy === `${pkg.attribute}:${a.name}` ? "..." : `${a.cost} bp`}
                </button>
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </div>
</section>

{#if selected}
  <Modal title="comprar ação" onClose={() => (selected = null)}>
    <dl class="details">
      <dt>nome</dt><dd class="hl">{selected.action.name}</dd>
      <dt>atributo</dt><dd>{selected.pkg.attribute}</dd>
      <dt>tipo</dt><dd>{TYPE_LABEL[selected.action.type] ?? selected.action.type}</dd>
      <dt>dificuldade</dt><dd>d{selected.action.diff}</dd>
      <dt>custo</dt><dd>{selected.action.cost} bp</dd>
      <dt>saldo</dt><dd>{buildPoints} bp</dd>
    </dl>
    <div class="confirm-row">
      <button class="ghost" on:click={() => (selected = null)}>cancelar</button>
      <button
        class="primary"
        on:click={() => buy(selected!.pkg, selected!.action)}
        disabled={busy !== null || buildPoints < selected.action.cost}
      >
        {busy ? "..." : "confirmar compra"}
      </button>
    </div>
  </Modal>
{/if}

<style>
  .catalog {
    color: #e5e5e5;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    box-sizing: border-box;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 1.25rem;
  }
  h2 {
    margin: 0;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 1rem;
  }
  .bp {
    color: #888;
    font-size: 0.85rem;
  }
  .bp b {
    color: #6cf;
  }
  .packages {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1rem;
  }
  .package {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    padding: 0.85rem 1rem;
  }
  .package-title {
    color: #6cf;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.8rem;
    margin-bottom: 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #1f1f1f;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.4rem 0;
    border-bottom: 1px solid #161616;
  }
  li:last-child {
    border-bottom: none;
  }
  li.owned {
    opacity: 0.4;
  }
  .owned-tag {
    color: #555;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.3rem 0.5rem;
  }
  .info-btn:disabled {
    cursor: default;
  }
  .info-btn:disabled:hover .name {
    color: inherit;
  }
  .info-btn {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.15rem;
    flex: 1;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    padding: 0.2rem 0;
  }
  .info-btn:hover .name {
    color: #6cf;
  }
  .name {
    color: #ddd;
    font-size: 0.85rem;
  }
  .meta {
    color: #555;
    font-size: 0.7rem;
  }
  .buy {
    background: transparent;
    border: 1px solid #2a2a2a;
    color: #888;
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    font: inherit;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
    min-width: 56px;
  }
  .buy:hover:not(:disabled) {
    border-color: #6cf;
    color: #6cf;
  }
  .buy:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .muted {
    color: #555;
  }
  .error {
    color: #f66;
    margin-bottom: 1rem;
  }
  .details {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.5rem 1rem;
    margin: 0 0 1.25rem;
  }
  .details dt {
    color: #555;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.05em;
  }
  .details dd {
    color: #ddd;
    margin: 0;
    font-size: 0.9rem;
  }
  .hl {
    color: #6cf;
  }
  .confirm-row {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
  }
  .ghost,
  .primary {
    padding: 0.5rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.15s;
  }
  .ghost {
    background: transparent;
    color: #888;
    border-color: #333;
  }
  .ghost:hover {
    color: #ccc;
    border-color: #555;
  }
  .primary {
    background: #6cf;
    color: #0a0a0a;
    border-color: #6cf;
  }
  .primary:hover:not(:disabled) {
    background: #4ad;
  }
  .primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
</style>
