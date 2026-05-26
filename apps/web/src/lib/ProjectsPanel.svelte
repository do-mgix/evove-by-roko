<script lang="ts">
  import {onMount} from "svelte";
  import{
      type Project,
      fetchProjects,
  } from "./api";

  let projects: Project[] = [];
  let loading = true;
  let error: string | null = null;
  let showForm = false;
  
  async function load() {
    try {
      const res =  await fetchProjects();
      projects = res.items ?? [];
    } catch (e: any) {
      error = e?.message ?? "erro";
      projects = [];
    } finally {
      loading = false;
    }
  }

  onMount(load);

</script>

<div class="panel">
    <header class="head">
        <span class="panel-title">projetos</span>
        <button class="add-btn" on:click={() => (showForm = true)} title="adicionar-item">+</button>
    </header>
    {#if loading}
        <p class="empty">carregando...</p>
    {:else if error}
        <p class="empty">{error}</p>
    {:else if projects.length === 0 }
        <p class="empty">sem projetos</p>
    {:else}         
        <ul>            
           {#each projects as p}               
                <li>
                  <span class="label">{p.name}</span>                 
                </li>
           {/each}            
        </ul>
    {/if}
</div>

<style>
  .panel {
    background: #0d0d0d;
    border: 1px solid #1f1f1f;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    overflow: auto;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.6rem;
  }
  .add-btn {
    background: transparent;
    border: 1px solid #2a2a2a;
    color: #888;
    width: 22px;
    height: 22px;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
    line-height: 1;
    padding: 0;
  }
  .add-btn:hover {
    border-color: #6cf;
    color: #6cf;
  }
  .panel-title {
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.7rem;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  li {
    border-bottom: 1px solid #161616;
  }
  .empty {
    color: #555;
    font-size: 0.85rem;
  }
  .row {
    display: grid;
    grid-template-columns: 6.5rem 1fr auto;
    gap: 0.6rem;
    align-items: baseline;
    width: 100%;
    padding: 0.35rem 0.3rem;
    background: transparent;
    border: none;
    font: inherit;
    font-size: 0.82rem;
    color: #888;
    text-align: left;
    cursor: pointer;
  }
  .row:hover {
    background: #141414;
  }  
</style>
