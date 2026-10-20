<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
  import {
    completeTodo,
    createProject,
    createTodo,
    deleteProject,
    deleteTodo,
    endProject,
    fetchActions,
    fetchAgendaDay,
    fetchJournal,
    fetchProjects,
    fetchTodos,
    setThought,
    updateProject,
    type Action,
    type AgendaDay,
    type DayLog,
    type Project,
    type Todo,
  } from "./api";
  import Icon from "./Icon.svelte";
  import Screen from "./Screen.svelte";
  import { primeAudio } from "./dtmf";
  import { gains as gainsSound, powerOn, tap } from "./sfx";
  import { bumpUser, logsVersion, setBackHandler } from "./store";

  /** Back to the tile home. */
  export let onHome: () => void;
  /** The old month calendar, kept on a page of its own. */
  export let onCalendar: () => void;
  /** The records as a full list, to move, reorder or delete them. */
  export let onLogs: () => void;

  // The agenda in two parts. The first is the day's records, a vertical list of
  // what was done, each waiting for a thought, and at its end the thought of the
  // day: the cycle — act, to-do, a thought on every act, the thought of the day —
  // is complete only when every record carries its thought. The second part holds
  // the to-dos, and below them the projects. Nothing scrolls: lists turn pages.

  const INK = "#00a8e8";
  const ROW = 50;

  type Part = "records" | "plan";
  type Mode =
    | { kind: "list" }
    | { kind: "thought"; log: DayLog | null }
    | { kind: "journal"; text: string }
    | { kind: "todo"; todo: Todo }
    | { kind: "newTodo" }
    | { kind: "project"; project: Project }
    | { kind: "newProject" };

  let part: Part = "records";
  let mode: Mode = { kind: "list" };
  let offset = 0;
  let day: AgendaDay | null = null;
  let todos: Todo[] = [];
  let projects: Project[] = [];
  let actions: Action[] = [];
  let message: string[] = [];
  let busy = false;
  let page = 0;
  let bodyHeight = 0;
  let lastLogs = 0;

  // ---- loading ----
  async function loadDay() {
    try {
      day = await fetchAgendaDay(offset);
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    }
  }
  async function loadPlan() {
    try {
      [todos, projects] = await Promise.all([fetchTodos(), fetchProjects()]);
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    }
  }
  $: if ($logsVersion !== lastLogs) {
    lastLogs = $logsVersion;
    if (lastLogs > 0) loadDay();
  }

  // ---- the records, cut into pages ----
  $: perPage = Math.max(1, Math.floor((bodyHeight - 64) / (ROW + 8)));
  // the list of the part: the records end with the day's thought, the plan is
  // the to-dos then the projects, each list headed by its label
  type Item =
    | { kind: "log"; log: DayLog }
    | { kind: "day" }
    | { kind: "label"; text: string }
    | { kind: "todo"; todo: Todo }
    | { kind: "project"; project: Project }
    | { kind: "add"; what: "todo" | "project" };
  $: items = (part === "records"
    ? [...(day?.logs ?? []).map((log) => ({ kind: "log", log }) as Item), { kind: "day" } as Item]
    : [
        { kind: "label", text: "to-dos" } as Item,
        ...todos.map((todo) => ({ kind: "todo", todo }) as Item),
        { kind: "add", what: "todo" } as Item,
        { kind: "label", text: "projetos" } as Item,
        ...projects.map((project) => ({ kind: "project", project }) as Item),
        { kind: "add", what: "project" } as Item,
      ]) as Item[];
  $: pages = Math.max(1, Math.ceil(items.length / perPage));
  $: if (page >= pages) page = pages - 1;
  $: shown = items.slice(page * perPage, (page + 1) * perPage);

  $: cycle = day?.cycle;
  $: steps = cycle
    ? [
        { id: "act", label: "agir", done: cycle.acted, optional: false },
        { id: "todo", label: "to-do", done: cycle.todo, optional: true },
        { id: "thoughts", label: `${cycle.thoughts}/${cycle.logs}`, done: cycle.logs > 0 && cycle.thoughts === cycle.logs, optional: false },
        { id: "day", label: "dia", done: cycle.day_thought, optional: false },
      ]
    : [];

  const WEEK = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
  function dateLabel(iso: string | undefined): string {
    if (!iso) return "";
    const [y, m, d] = iso.split("-").map(Number);
    return `${WEEK[new Date(y, m - 1, d).getDay()]} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
  }
  const short = (iso: string | null) => (iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) : "");
  function hours(seconds: number): string {
    if (seconds < 3600) return `${Math.floor(seconds / 60)}min`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
    return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
  }

  // ---- moving ----
  function press(n = 0) {
    primeAudio();
    tap(n);
  }
  function setPart(p: Part) {
    press(4);
    part = p;
    page = 0;
    message = [];
    mode = { kind: "list" };
    if (p === "plan") loadPlan();
    powerOn();
  }
  function nextPage() {
    press(2);
    page = (page + 1) % pages;
    powerOn();
  }
  async function shiftDay(delta: number) {
    press(delta < 0 ? 1 : 3);
    offset = Math.min(0, offset + delta);
    page = 0;
    await loadDay();
  }
  function back(): boolean {
    if (mode.kind !== "list") {
      mode = { kind: "list" };
      message = [];
      return true;
    }
    return false;
  }
  function home() {
    press(0);
    onHome();
  }

  // ---- thoughts ----
  let draft = "";
  let field: HTMLTextAreaElement;
  async function openThought(log: DayLog | null) {
    press(6);
    mode = { kind: "thought", log };
    draft = (log ? log.thought?.content : day?.day_thought?.content) ?? "";
    await tick();
    field?.focus();
  }
  async function saveThought() {
    if (!day || mode.kind !== "thought" || busy) return;
    busy = true;
    try {
      await setThought(day.date, draft, mode.log ? mode.log.id : null);
      press(8);
      await loadDay();
      mode = { kind: "list" };
      message = day?.cycle.complete ? ["ciclo completo"] : [];
      if (day?.cycle.complete) gainsSound();
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }

  async function openJournal() {
    if (!day) return;
    press(5);
    try {
      const j = await fetchJournal(day.date);
      mode = { kind: "journal", text: j.text || "nada escrito neste dia" };
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    }
  }

  // ---- to-dos ----
  let title = "";
  let chosen: string[] = [];
  let deadline = "";
  let projectId: string | null = null;
  let pickPage = 0;
  const PICK = 6;
  async function newTodo() {
    press(6);
    title = "";
    chosen = [];
    deadline = "";
    projectId = null;
    pickPage = 0;
    mode = { kind: "newTodo" };
    if (!actions.length) actions = await fetchActions().catch(() => []);
    await tick();
    field?.focus();
  }
  const toggle = (id: string) => {
    press(7);
    chosen = chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id];
  };
  function cycleProject() {
    press(7);
    const open = projects.filter((p) => !p.emblem);
    const i = open.findIndex((p) => p.id === projectId);
    projectId = i + 1 < open.length ? open[i + 1].id : null;
  }
  async function saveTodo() {
    if (busy || !title.trim()) return;
    busy = true;
    try {
      await createTodo({ title, action_ids: chosen, deadline: deadline || null, project_id: projectId });
      press(8);
      await loadPlan();
      mode = { kind: "list" };
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }
  async function finishTodo(t: Todo) {
    if (busy) return;
    busy = true;
    try {
      const r = await completeTodo(t.id);
      gainsSound();
      message = [`+${r.reward} pontos`, r.late ? "concluído com atraso" : "concluído"];
      bumpUser();
      await Promise.all([loadPlan(), loadDay()]);
      mode = { kind: "list" };
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }
  async function dropTodo(t: Todo) {
    press(0);
    await deleteTodo(t.id).catch(() => {});
    await loadPlan();
    mode = { kind: "list" };
  }

  // ---- projects ----
  let name = "";
  async function newProject() {
    press(6);
    name = "";
    deadline = "";
    mode = { kind: "newProject" };
    await tick();
    field?.focus();
  }
  async function saveProject() {
    if (busy || !name.trim()) return;
    busy = true;
    try {
      await createProject(name, deadline || null);
      press(8);
      await loadPlan();
      mode = { kind: "list" };
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }
  async function projectAction(p: Project, what: "toggle" | "end" | "delete") {
    if (busy) return;
    busy = true;
    try {
      if (what === "toggle") mode = { kind: "project", project: await updateProject(p.id, { active: !p.active }) };
      else if (what === "end") {
        const ended = await endProject(p.id);
        gainsSound();
        mode = { kind: "project", project: ended };
        message = ["emblema", ended.outcome === "completed" ? "projeto completado" : "projeto finalizado"];
      } else {
        await deleteProject(p.id);
        mode = { kind: "list" };
      }
      press(5);
      await loadPlan();
    } catch (e: any) {
      message = [e?.message ?? "erro"];
    } finally {
      busy = false;
    }
  }

  function openItem(it: Item) {
    if (it.kind === "log") openThought(it.log);
    else if (it.kind === "day") openThought(null);
    else if (it.kind === "todo") {
      press(6);
      mode = { kind: "todo", todo: it.todo };
    } else if (it.kind === "project") {
      press(6);
      mode = { kind: "project", project: it.project };
    } else if (it.kind === "add") (it.what === "todo" ? newTodo : newProject)();
  }

  onMount(() => {
    setBackHandler(back);
    Promise.all([loadDay(), loadPlan()]).then(() => powerOn());
  });
  onDestroy(() => setBackHandler(null));

  $: pickPages = Math.max(1, Math.ceil(actions.length / PICK));
  $: picking = actions.slice(pickPage * PICK, (pickPage + 1) * PICK);
  $: projectName = projects.find((p) => p.id === projectId)?.name;
</script>

<Screen ink={INK} bind:bodyHeight display="15%">
  <svelte:fragment slot="display">
    {#if message.length}
      {#each message as line, i}<p class={i === 0 ? "big" : "small"}>{line}</p>{/each}
    {:else if mode.kind === "thought"}
      <p class="big">{mode.log ? mode.log.content : "thought do dia"}</p>
      <p class="small">{mode.log ? "o que você pensa disso?" : "feche o ciclo do dia"}</p>
    {:else if mode.kind === "journal"}
      <p class="big">journal</p>
      <p class="small">{dateLabel(day?.date)}</p>
    {:else if mode.kind === "todo"}
      <p class="big">{mode.todo.title}</p>
      <p class="small">
        {mode.todo.done ? `concluído · +${mode.todo.reward} pts` : `${mode.todo.actions.filter((a) => a.acted).length}/${mode.todo.actions.length} ações`}
        {#if mode.todo.deadline} · até {short(mode.todo.deadline)}{/if}
        {#if mode.todo.late} · atrasado{/if}
      </p>
    {:else if mode.kind === "newTodo"}
      <p class="big">novo to-do</p>
      <p class="small">{chosen.length} {chosen.length === 1 ? "ação" : "ações"}{projectName ? ` · ${projectName}` : ""}</p>
    {:else if mode.kind === "project"}
      <p class="big">{mode.project.name}</p>
      <p class="small">
        {mode.project.emblem ? (mode.project.outcome === "completed" ? "emblema · completado" : "emblema · finalizado") : mode.project.active ? "ativo" : "desativado"}
      </p>
    {:else if mode.kind === "newProject"}
      <p class="big">novo projeto</p>
    {:else if part === "records"}
      <p class="big">{offset === 0 ? "hoje" : dateLabel(day?.date)}</p>
      <p class="small">
        {#if cycle}{cycle.complete ? "ciclo completo" : `${cycle.thoughts}/${cycle.logs} thoughts · ${cycle.day_thought ? "dia escrito" : "dia aberto"}`}{/if}
      </p>
    {:else}
      <p class="big">plano</p>
      <p class="small">{todos.filter((t) => !t.done).length} abertos · {projects.filter((p) => !p.emblem).length} projetos</p>
    {/if}
  </svelte:fragment>

  {#if mode.kind === "thought"}
    <textarea bind:this={field} bind:value={draft} class="field grow-field" rows="7" placeholder="escreva…"></textarea>
    <div class="keys">
      <button class="key" aria-label="apagar" on:click={() => (draft = "")}><Icon name="trash" /></button>
      {#if mode.log}
        <button class="key" aria-label="editar registros" on:click={() => { press(1); onLogs(); }}><Icon name="pencil" /></button>
      {/if}
      <button class="key wide" aria-label="salvar" disabled={busy} on:click={saveThought}><Icon name="check" /></button>
    </div>
  {:else if mode.kind === "journal"}
    <pre class="journal">{mode.text}</pre>
  {:else if mode.kind === "todo"}
    {@const t = mode.todo}
    <p class="label">ações</p>
    {#each t.actions as a (a.id)}
      <div class="row static" class:dim={!a.acted}>
        <span class="tick" class:on={a.acted}><Icon name={a.acted ? "check" : "circle"} size={14} /></span>
        <span class="grow">{a.name}</span>
      </div>
    {:else}
      <p class="empty">sem ações</p>
    {/each}
    <div class="keys">
      <button class="key" aria-label="apagar" on:click={() => dropTodo(t)}><Icon name="trash" /></button>
      {#if !t.done}
        <button class="key wide" aria-label="concluir" disabled={busy} on:click={() => finishTodo(t)}><Icon name="check" /> concluir</button>
      {/if}
    </div>
  {:else if mode.kind === "newTodo"}
    <input bind:this={field} bind:value={title} class="field" placeholder="título" maxlength="128" />
    <p class="label">ações · {pickPage + 1}/{pickPages}</p>
    <div class="picks">
      {#each picking as a (a.id)}
        <button class="key pick" class:on={chosen.includes(a.id)} on:click={() => toggle(a.id)}>{a.name}</button>
      {/each}
    </div>
    <div class="keys">
      <button class="key" aria-label="mais ações" on:click={() => { press(2); pickPage = (pickPage + 1) % pickPages; }}><Icon name="right" /></button>
      <label class="key date" aria-label="prazo"><Icon name="flag" size={16} /><input type="date" bind:value={deadline} /></label>
      <button class="key" aria-label="projeto" on:click={cycleProject}><Icon name="list" /></button>
      <button class="key wide" aria-label="salvar" disabled={busy || !title.trim()} on:click={saveTodo}><Icon name="check" /></button>
    </div>
  {:else if mode.kind === "project"}
    {@const p = mode.project}
    <dl class="stats">
      <dt>tempo ativo</dt><dd>{hours(p.stats.active_seconds)}</dd>
      <dt>desativado</dt><dd>{hours(p.stats.inactive_seconds)}</dd>
      <dt>ações</dt><dd>{p.stats.actions}</dd>
      <dt>marcas</dt><dd>{p.stats.marks}</dd>
      <dt>to-dos</dt><dd>{p.stats.todos_done}/{p.stats.todos}</dd>
      {#if p.deadline}<dt>prazo</dt><dd>{short(p.deadline)}</dd>{/if}
    </dl>
    {#if p.emblem}
      <div class="emblem"><Icon name="star" size={40} /></div>
    {/if}
    <div class="keys">
      <button class="key" aria-label="apagar" disabled={busy} on:click={() => projectAction(p, "delete")}><Icon name="trash" /></button>
      {#if !p.emblem}
        <button class="key" aria-label={p.active ? "desativar" : "ativar"} disabled={busy} on:click={() => projectAction(p, "toggle")}>
          <Icon name={p.active ? "pause" : "play"} />
        </button>
        <button class="key wide" aria-label="finalizar" disabled={busy} on:click={() => projectAction(p, "end")}><Icon name="flag" /> emblema</button>
      {/if}
    </div>
  {:else if mode.kind === "newProject"}
    <input bind:this={field} bind:value={name} class="field" placeholder="nome do projeto" maxlength="128" />
    <div class="keys">
      <label class="key date" aria-label="prazo"><Icon name="flag" size={16} /><input type="date" bind:value={deadline} /></label>
      <button class="key wide" aria-label="salvar" disabled={busy || !name.trim()} on:click={saveProject}><Icon name="check" /></button>
    </div>
  {:else}
    {#if part === "records"}
      <!-- the cycle: four steps, the to-do the one that may be skipped -->
      <div class="cycle" class:complete={cycle?.complete}>
        {#each steps as s, i (s.id)}
          {#if i > 0}<span class="link" class:on={s.done}></span>{/if}
          <span class="step" class:on={s.done} class:optional={s.optional}>{s.label}</span>
        {/each}
      </div>
    {/if}
    <div class="list" class:rail={part === "records"}>
      {#each shown as it, i (i + "-" + page)}
        {#if it.kind === "label"}
          <p class="label">{it.text}</p>
        {:else if it.kind === "log"}
          <button class="row rec" class:thought={!!it.log.thought} on:click={() => openItem(it)}>
            <span class="node" class:on={!!it.log.thought}></span>
            <span class="tag">{it.log.period ?? "··"}</span>
            <span class="grow">
              <span class="line">{it.log.content}</span>
              <span class="sub">{it.log.thought ? it.log.thought.content : "sem thought"}</span>
            </span>
          </button>
        {:else if it.kind === "day"}
          <button class="row rec day" class:thought={!!day?.day_thought} on:click={() => openItem(it)}>
            <span class="node diamond" class:on={!!day?.day_thought}></span>
            <span class="grow">
              <span class="line">thought do dia</span>
              <span class="sub">{day?.day_thought ? day.day_thought.content : "toque para escrever"}</span>
            </span>
          </button>
        {:else if it.kind === "todo"}
          <button class="row" class:dim={it.todo.done} on:click={() => openItem(it)}>
            <span class="tick" class:on={it.todo.done}><Icon name={it.todo.done ? "check" : "square"} size={14} /></span>
            <span class="grow">{it.todo.title}</span>
            {#if it.todo.late}<span class="late">atraso</span>{/if}
            <span class="tag">{it.todo.done ? `+${it.todo.reward}` : `${it.todo.actions.filter((a) => a.acted).length}/${it.todo.actions.length}`}</span>
          </button>
        {:else if it.kind === "project"}
          <button class="row" class:dim={!it.project.active && !it.project.emblem} on:click={() => openItem(it)}>
            <span class="tick on"><Icon name={it.project.emblem ? "star" : it.project.active ? "play" : "pause"} size={14} /></span>
            <span class="grow">{it.project.name}</span>
            <span class="tag">{it.project.stats.todos_done}/{it.project.stats.todos}</span>
          </button>
        {:else if it.kind === "add"}
          <button class="row add" aria-label={it.what === "todo" ? "novo to-do" : "novo projeto"} on:click={() => openItem(it)}>
            <Icon name="plus" size={14} /><span class="grow">{it.what === "todo" ? "to-do" : "projeto"}</span>
          </button>
        {/if}
      {/each}
    </div>
  {/if}

  <svelte:fragment slot="bar">
    {#if mode.kind !== "list"}
      <button class="key back-key" aria-label="voltar" on:click={() => { press(0); back(); }}><Icon name="left" /></button>
      <button class="key home" aria-label="início" on:click={home}><Icon name="circle" size={16} /></button>
    {:else if part === "records"}
      <button class="key" aria-label="dia anterior" on:click={() => shiftDay(-1)}><Icon name="left" /></button>
      <button class="key" aria-label="dia seguinte" disabled={offset >= 0} on:click={() => shiftDay(1)}><Icon name="right" /></button>
      <button class="key page-btn" aria-label="próxima página" disabled={pages < 2} on:click={nextPage}><Icon name="down" /></button>
      <button class="key" aria-label="journal" on:click={openJournal}><Icon name="book" /></button>
      <button class="key" aria-label="to-dos e projetos" on:click={() => setPart("plan")}><Icon name="check" /></button>
      <button class="key home" aria-label="início" on:click={home}><Icon name="circle" size={16} /></button>
    {:else}
      <button class="key" aria-label="calendário" on:click={() => { press(1); onCalendar(); }}><Icon name="calendar" /></button>
      <span class="ticks">{#if pages > 1}{#each Array(pages) as _, i}<i class:on={i === page}></i>{/each}{/if}</span>
      <button class="key page-btn" aria-label="próxima página" disabled={pages < 2} on:click={nextPage}><Icon name="down" /></button>
      <button class="key" aria-label="registros" on:click={() => setPart("records")}><Icon name="list" /></button>
      <button class="key home" aria-label="início" on:click={home}><Icon name="circle" size={16} /></button>
    {/if}
  </svelte:fragment>
</Screen>

<style>
  .list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  /* the records hang on a rail: a line through every node, lit where a thought is */
  .list.rail { position: relative; }
  .list.rail::before {
    content: "";
    position: absolute;
    left: calc(0.7rem + 5px);
    top: 0;
    bottom: 0;
    width: 1.5px;
    background: var(--ink);
    opacity: 0.35;
  }
  .rec { position: relative; min-height: 3.1rem; }
  .rec .grow { display: flex; flex-direction: column; gap: 0.15rem; white-space: normal; }
  .line, .sub { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .line { text-transform: uppercase; }
  .sub { font-size: 0.72rem; color: rgba(255, 255, 255, 0.55); }
  .rec.thought .sub { color: var(--ink); }
  .node {
    position: relative;
    z-index: 1;
    flex: none;
    width: 11px;
    height: 11px;
    border: 1.5px solid var(--ink);
    border-radius: 50%;
    background: #000000;
    box-sizing: border-box;
  }
  .node.on { background: var(--ink); box-shadow: 0 0 8px var(--ink); }
  .node.diamond { border-radius: 0; transform: rotate(45deg); }
  .day { border-style: dashed; }
  .day.thought { border-style: solid; }

  /* the four steps of the cycle, linked; closed, they glow */
  .cycle {
    display: flex;
    align-items: center;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 0.66rem;
    text-transform: uppercase;
  }
  .step {
    flex: none;
    padding: 0.25rem 0.45rem;
    border: 1.5px solid var(--ink);
    color: var(--ink);
    opacity: 0.45;
  }
  .step.optional { border-style: dashed; }
  .step.on { opacity: 1; background: color-mix(in srgb, var(--ink) 20%, transparent); }
  .link { flex: 1; height: 1.5px; background: var(--ink); opacity: 0.25; }
  .link.on { opacity: 1; }
  .cycle.complete .step { box-shadow: 0 0 10px var(--ink); color: #ffffff; }

  .row.static { cursor: default; }
  .dim { opacity: 0.55; }
  .tick { flex: none; display: flex; color: rgba(255, 255, 255, 0.5); }
  .tick.on { color: var(--ink); }
  .late {
    flex: none;
    padding: 0.1rem 0.35rem;
    border: 1px solid #ffb347;
    color: #ffb347;
    font-size: 0.62rem;
    text-transform: uppercase;
  }
  .add { border-style: dashed; color: var(--ink); }

  .keys {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
    min-height: 2.8rem;
  }
  .keys .wide { grid-column: span 3; }
  .keys > :global(.key) { min-height: 2.8rem; }
  .date { position: relative; overflow: hidden; }
  .date input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }
  .picks {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  .pick {
    min-height: 2.6rem;
    padding: 0.2rem 0.4rem;
    font-size: 0.68rem;
    overflow: hidden;
  }
  .grow-field { flex: 1; min-height: 6rem; }

  .journal {
    flex: 1;
    min-height: 0;
    margin: 0;
    padding: 0.7rem;
    overflow: hidden;
    border: 1.5px solid var(--ink);
    color: #ffffff;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    line-height: 1.5;
    white-space: pre-wrap;
  }
  .stats {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.45rem 1rem;
    margin: 0;
    padding: 0.8rem;
    border: 1.5px solid var(--ink);
    font-family: var(--font-mono);
    font-size: 0.85rem;
  }
  .stats dt { color: var(--ink); text-transform: uppercase; font-size: 0.7rem; align-self: center; }
  .stats dd { margin: 0; text-align: right; }
  .emblem {
    display: flex;
    justify-content: center;
    color: var(--ink);
    filter: drop-shadow(0 0 8px var(--ink));
  }
  .back-key { grid-column: 1 / 3; }
</style>
