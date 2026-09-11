# EVOVE

Personal progression tracking system. Actions you log daily turn into experience, levels
and scores spread across a tree of attributes.

The repository is a monorepo with three applications sharing one domain layer and one
database:

| Application | Path | Stack |
| --- | --- | --- |
| HTTP API | `backend/` | FastAPI · SQLAlchemy 2 · Alembic · MySQL 8.4 |
| Web client | `apps/web/` | Svelte 5 · TypeScript · Vite |
| Terminal client | `apps/cli/` | Rich · readchar |

---

## Running the project

Requirements: Docker with Compose, Node 20+ and Python 3.10+ if you want to run anything
outside the containers.

### 1. Backend stack

```bash
docker compose up -d db adminer backend
docker compose exec backend alembic upgrade head   # the container does not migrate itself
```

| Service | URL | Notes |
| --- | --- | --- |
| API | `http://localhost:8000` | interactive docs at `/docs` |
| Adminer | `http://localhost:8080` | server `db`, user `roko`, password `rokopass` |
| MySQL | `localhost:3306` | database `roko` |

The migration step is not optional on a fresh database: nine of the revisions also seed
the attribute tree, the tags and the shop catalog that the API reads on every request.

### 2. Web client

```bash
cd apps/web
npm install
npm run dev        # http://localhost:5173
```

It talks to `http://localhost:8000` by default — set `VITE_API_BASE` to point somewhere
else. `npm run build` writes `dist/`, `npm run check` runs `svelte-check` and `tsc`.

The first screen is a login. Register a profile with a username and a password of at
least 8 characters; the session token that comes back is kept in `localStorage` and sent
as `Authorization: Bearer`.

### 3. Terminal client

```bash
docker compose run --rm cli
```

Or on the host, against the same database:

```bash
export DATABASE_URL='mysql+pymysql://roko:rokopass@127.0.0.1:3306/roko?charset=utf8mb4'
python apps/cli/main.py
```

That needs `rich` and `readchar` (`pip install -r apps/cli/requirements.txt`) plus the
backend requirements, since it imports the same domain code.

### Development loop

Editing source is enough — nothing needs a rebuild:

| You changed | What picks it up |
| --- | --- |
| `apps/web/src/**` | Vite |
| `backend/**` | uvicorn `--reload`, inside the container |
| `backend/alembic/versions/**` | `docker compose exec backend alembic …`, right away |

That comes from `docker-compose.override.yml`, which Compose merges into
`docker-compose.yml` on its own — plain `docker compose up -d` already applies it. It
mounts `./backend` over `/app` and replaces the command with `uvicorn --reload`, so the
container reads your working tree instead of the copy `backend/Dockerfile` took at build
time. The `cli` service gets the same for `backend/src` and `apps/cli`.

Dependencies are the exception: `requirements.txt` is installed into the image, so a new
package still means

```bash
docker compose up -d --build backend
```

**Running the images as built.** Name only the base file and the override is skipped,
which is worth doing before you ship anything, since that is what a deploy would serve:

```bash
docker compose -f docker-compose.yml up -d --build backend
```

In that mode a forgotten `--build` comes back, and it shows up in two ways that do not
point at the image:

- **The API answers fine, with old values.** Migrations run against MySQL directly, not
  through the application, so the database has your new rows while the Python reading them
  is the version in the image. A seed you just added shows up in Adminer and not in the
  API.
- **`alembic: Can't locate revision identified by '<hash>'`.** You migrated from the host,
  so `alembic_version` names a revision whose file only exists in your working tree.
  Rebuild and it reappears; the database is already at head, so the upgrade then does
  nothing.

Migrating from the host works in either mode and hits the same database:

```bash
cd backend
DATABASE_URL='mysql+pymysql://roko:rokopass@127.0.0.1:3306/roko?charset=utf8mb4' \
  alembic upgrade head
```

### Restarting the backend

| Situation | Command |
| --- | --- |
| a code change did not show up | `docker compose restart backend` |
| `requirements.txt` changed | `docker compose up -d --build backend` |
| `docker-compose*.yml` or an env var changed | `docker compose up -d backend` |
| there is a new migration | `docker compose exec backend alembic upgrade head` |
| it will not come up | `docker compose logs -f backend` |
| stop it | `docker compose stop backend` |

They are not interchangeable. `restart` reuses the same container and the same image, so
it picks up neither a new package nor a compose change. `up -d` recreates the container
from the current compose files but keeps the image. `--build` also rebuilds the image —
the only one of the three that installs a dependency.

Docker needs `sudo` unless your user is in the `docker` group
(`sudo usermod -aG docker $USER`, then log in again).

### Backend outside Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

export DATABASE_URL='mysql+pymysql://roko:rokopass@127.0.0.1:3306/roko?charset=utf8mb4'
cd backend
alembic upgrade head
uvicorn main:app --reload --port 8000
```

Both `alembic` and `uvicorn` expect to be run from inside `backend/`.

### Importing legacy JSON data

```bash
DATABASE_URL='mysql+pymysql://...' python backend/scripts/migrate_json_to_db.py [user ...]
```

Reads `~/.local/share/evove/<user>/{user,logs,agenda,sequences,projects}.json` and upserts
by username. Idempotent: running it again replaces that user's state with whatever is in
the files.

### Environment variables

| Variable | Used by | Default | Purpose |
| --- | --- | --- | --- |
| `MYSQL_ROOT_PASSWORD` | compose | `rokoroot` | MySQL root password |
| `MYSQL_DATABASE` | compose | `roko` | database name |
| `MYSQL_USER` / `MYSQL_PASSWORD` | compose | `roko` / `rokopass` | application user |
| `DATABASE_URL` | backend, CLI, alembic, importer | `mysql+pymysql://roko:rokopass@127.0.0.1:3306/roko?charset=utf8mb4` | SQLAlchemy connection |
| `EVOVE_USERNAME` | CLI | `default` | profile the CLI opens with |
| `EVOVE_DATA_DIR` | backend | `~/.local/share/evove` | on-disk data root (legacy) |
| `TZ` | containers | `America/Sao_Paulo` | timezone |
| `VITE_API_BASE` | web (build time) | `http://localhost:8000` | API base URL |

---

## Repository structure

```
backend/
  main.py                      the whole FastAPI app (routes + presentation rules)
  src/domain/                  pure rules, no I/O — shared with the CLI
    action.py                  the Action class and the score formula
    act.py                     the "execute an action" flow (single source of truth)
    agenda.py                  matching an action against the day's agenda
    attributes.py              the attribute graph: power, levels, degree, registration rules
    contributions.py           applies an action's stimulus to the leaves
    daily.py                   daily tick (token refill, checkpoint countdown)
    skills.py                  skill tree rules and bonus aggregation
    ports.py                   WebInputInterrupt — how the domain asks the host for input
  src/infrastructure/
    db.py                      SQLAlchemy engine, session and Base
    orm.py                     table models
    repos.py                   repositories: dicts in, dicts out — never ORM entities
    storage.py                 per-user directory under ~/.local/share/evove (legacy)
    static_data.py             skill tree hardcoded in Python
  data/                        live seed: the attribute graph and the catalog
  alembic/                     migrations
  alembic/seeds/               frozen seed copies the older migrations read
  scripts/attributes.py        register attributes (subdivide, add, link…)
  scripts/migrate_json_to_db.py  legacy JSON importer
apps/web/src/
  App.svelte                   screen switching by state, no router
  lib/api.ts                   HTTP client and API types
  lib/*.svelte                 screens and panels
apps/cli/
  main.py                      single-key menu
  user_selector.py             profile picker (up to 4)
docker-compose.yml             MySQL + Adminer + backend + CLI
docker-compose.override.yml    dev bind mounts + uvicorn --reload (auto-merged)
CHANGELOG.md                   release history (conventional commits)
```

The CLI imports `backend/src/domain` directly — through `sys.path` in `apps/cli/main.py`
and `PYTHONPATH` in `apps/cli/Dockerfile`. That is why scoring, token cost and energy
penalties behave identically in both clients: there is only one implementation.

---

## Concepts

Enough vocabulary to read the code:

| Term | What it is |
| --- | --- |
| **action** | something you log, with a unit type and a difficulty; executing it is called an *act* |
| **attribute** | anything that can be trained, at any grain: Corpo, Bíceps, Força, Leitura. All the same kind of thing |
| **leaf** | an attribute with no children — the only kind that stores a per-user score, which decays unless converted into a permanent level |
| **power** | a leaf's score, or for any other attribute the weighted mean of its children |
| **degree** | depth along primary parents, the root being 1 |
| **tokens** | earned by executing productivity actions, spent on leisure ones, capped in stock |
| **energy** | drained by acting outside today's agenda, refilled at each checkpoint |
| **build points / skill points** | currencies for buying actions in the shop and nodes in the skill tree; both are paid out at checkpoints |
| **stage / checkpoint** | a countdown that advances the profile and hands out rewards |

The numbers behind all of this (score formula, decay half-lives, level thresholds,
progression curve) live in `backend/src/domain/` and in `backend/data/*.json`.

---

## Backend

### Layers

`src/domain` imports nothing outside the standard library, except `contributions.py`,
which needs the repositories. When the domain needs interactive input it raises
`WebInputInterrupt` and lets the host decide how to ask.

`src/infrastructure/repos.py` is the boundary: it takes and returns dicts shaped like the
JSON files that predated the database, so `main.py` never sees an ORM object. Each
function opens and closes its own session.

### Authentication

A profile is a username plus a bcrypt hash in `users.password_hash`. `POST /auth/register`
and `POST /auth/login` return an opaque token; every other user route depends on
`current_username`, which resolves `Authorization: Bearer <token>` through the `sessions`
table. An endpoint therefore cannot be left open by accident — without a valid session
there is no username to act as.

Sessions are server-side and revocable: `POST /auth/logout` deletes the row and the token
dies with it. Only the SHA-256 of the token is stored, so a dump of `sessions` hands out
nothing usable. Tokens last 30 days (`auth.SESSION_TTL`) and expired rows are cleared on
the next login.

Login answers the same 401 for a wrong password and for a username that does not exist, so
the response does not enumerate profiles. There is no endpoint that lists usernames.

**Two things remain open, on purpose, for local use:** CORS still accepts every origin —
tightening it would break reaching the dev server from a phone on the LAN — and the CLI
talks straight to MySQL with no password, since whoever runs it already holds
`DATABASE_URL` and could read every profile anyway. The password protects the API, which
is the part exposed on a network.

### Database

Twenty-one tables. Profile and content tables have an FK to `users` with delete cascade; the
attribute graph and the catalog are global and shared by everyone:

- profile — `users`, `user_state`, `user_tutorial`, `sequences_state`, `sessions`
- user content — `actions`, `attributes`, `attribute_actions`, `skills_acquired`,
  `agenda_items`, `logs`, `projects`, `project_actions`, `project_attributes`
- attribute graph — `attr_nodes`, `attr_edges`, `action_contributions`
- catalog — `action_templates`, `id_class1`, `id_class2`
- per-user derived data — `user_leaf_scores`

Content tables also keep the logical id from the JSON era (`action_id`, `attr_id`,
`item_id`), preserved so ids already used by the front end keep working.

### Migrations

Sixteen revisions in a chain:

```
5638fb2a1810  initial schema
a844b8c6e2c0  add date to user_state
b7c1d4e3f2a9  attribute tree (anatomy + neurology) with decay
c8d2e5f7a3b1  attribute tags
d3f9a8b4c6e2  permanent level
e5a1c9d8b2f4  programming actions contributions
f7b3e9c1d4a8  conceptual attribute tree
b2e7d9c4a6f1  routine actions contributions
c4a8e2f6b9d3  action templates (unit, difficulty and prices)
d6b1f4a9c8e2  token economy: earned by productivity, spent on leisure
e8c2a5d7b1f3  raise the token stock cap to 100
f9d3b6e8a2c4  record the token delta on each log
a1e5c9b3d7f2  conceptual themes for the actions that had none
b4f7d2a9e6c3  passwords and sessions
c7a3e9f1b5d8  memorable action ids: 5aa-aa-ii
d8e4b2c6f1a3  attribute engine: one graph, no kinds
```

Nine of them (`b7c1`, `c8d2`, `e5a1`, `f7b3`, `b2e7`, `c4a8`, `d6b1`, `a1e5`, `c7a3`) seed
from **frozen copies** in `backend/alembic/seeds/`, not from `backend/data/`. They used to
re-read the live seed, so every later edit changed what a fresh install built — which is
how 17 leaves ended up with a null `max_level`. `d8e4` is the one that reads the live seed:
it brings nodes, links, their settings, contributions and templates in line with it, so a
fresh install always ends where the seed says.

### The attribute engine

There is one kind of attribute. Any attribute can have weighted children, depth has no
limit, and a parent is worth the weighted mean of its children — `braço = antebraço·½ +
braço·½`. A leaf is simply an attribute without children; only leaves store a score, and
everything above them is computed on read (`compute_node_score`, memoized per request).

**Several parents, one primary.** Força draws on peitoral, dorsal and more, while peitoral
also sits under Tronco. Each attribute has at most one *primary* parent, and the primary
chain alone defines its **degree** — its depth, root = 1 — which is what action ids use.
Other parents are ordinary links: Físico and Mental are roots whose children are the old
tags, and each tag reaches its leaves through non-primary links with the weights it
always had, so every tag kept its value.

**Levels.** A leaf levels up through its own `max_level`. Any other attribute shows the
weighted mean of the levels of the leveled leaves under it, provided they carry at least
80% of its weight (`LEVELED_SHARE`); otherwise it shows its power and no level.

### Registering attributes

Registration is always of children. `backend/scripts/attributes.py` applies each change
to the database **and** writes it into `backend/data/attributes_tree.json`, so a fresh
install builds the same graph:

```bash
export DATABASE_URL='mysql+pymysql://roko:rokopass@127.0.0.1:3306/roko?charset=utf8mb4'
python backend/scripts/attributes.py subdivide biceps \
  c_longa="Cabeça longa":0.6 c_curta="Cabeça curta":0.4
python backend/scripts/attributes.py show c_longa
```

| Command | What it does |
| --- | --- |
| `subdivide PARENT KEY=Name:w …` | a leaf gets children, weights summing to 1 |
| `add PARENT KEY=Name:w …` | more children for a node that already has some |
| `link PARENT CHILD w` | a non-primary link, how an aggregate like Força is assembled |
| `reweight PARENT CHILD=w …` | set every child's weight |
| `root KEY Name` | a parentless attribute to hang an aggregate on |
| `code-for PARENT` | the code a new action under `PARENT` would get |
| `show KEY` | degree, primary path, parents and children |

The rule behind `subdivide` and `add`: **registering children never changes what a
parent is worth at that moment.** On `subdivide`, every child inherits the leaf whole —
each user's score and permanent level, and every action contribution at the same weight.
That is not a split: since the parent is a weighted *mean*, `0.6·100 + 0.4·100 = 100`,
and each act keeps moving it exactly as before. The children start identical and
diverge once you tune which actions feed which. On `add`, existing links are scaled by
what the new weights leave, and each new child starts at the parent's current value.

`reweight` is the exception, on purpose: it moves the parent. Links that would close a
cycle are refused, and so is linking children onto a leaf that already holds scores —
subdivide it instead.

### Adding actions to the catalog

The shop has no admin screen. `/shop/packages` and `/shop/catalog` are assembled from
`action_contributions` (which attributes an action feeds) joined with `action_templates`
(its unit, difficulty and prices), so adding a shop item means rows in both — and for now
a migration is how you add them. Both blocks live in
`backend/data/attributes_tree.json`:

1. `contributions` — one entry per leaf the action feeds, name in caps. By convention an
   action carries two budgets that each sum to `1.0`: its leaves under the practice roots
   (the ones marked `shop_group`) and all the others. The practice leaf is what files it
   in the shop — see below.
2. `action_templates` — one entry per action: its `parent` (the attribute it is
   registered under), its `code` (from `attributes.py code-for PARENT`), `type` (the unit,
   see `Action._TYPE_MAP`), `diff` 0–5, `cost` in build points to acquire it, and either
   `token_gain` or `token_cost` — never both. An action with contributions but no
   template still shows in the shop, but cannot be bought: with no code there is no id.
3. Write a migration that inserts the contributions and the template, and records the
   class numbers `code-for` reported as new in `id_class1` / `id_class2`. A fresh install
   does not need it — `d8e4` brings everything in line with the seed — but the database
   you already have does.
4. Migrating through a container started with `-f docker-compose.yml`? Run
   `docker compose build backend` first — without the override the image carries a copy
   of `backend/data/` from build time, not the file in your working tree.

### Action ids

An action's id is seven digits, the same for every profile:

```
5  01  03  01      FLEXÃO
│   │   │   └─ position among actions with the same two classes, 01–99
│   │   └───── class 2: the action's parent — Peitoral
│   └───────── class 1: the ancestor at degree max(2, ⌈N/2⌉) — Musculatura
└───────────── always 5 — it is an action
```

Every action is **registered** under a parent attribute (`action_templates.parent_node_id`).
With N the parent's degree, the first class is the ancestor halfway down its primary path
— never the root, which contains everything and says nothing — and the second is the
parent itself, or `00` when the two coincide. FLEXÃO hangs from Peitoral, degree 4 on
Corpo → Musculatura → Tronco → Peitoral, so its classes are Musculatura and Peitoral.

The class numbers are registered too: `id_class1` gives each first-class attribute two
global digits, `id_class2` gives each second class two digits under its first. Both are
numbered the first time an action needs them. `00` is reserved at every level.

**Ids never move.** The parent, the class numbers and the code are all stored rather than
derived: if they were computed, a weight change could re-pick the parent, or an attribute
inserted mid-path could shift every degree below it, and ids would change. After an
action is registered, its id is data. The initial parents were the heaviest leaf of the
body/mind branch; four ties (BURPEE, INSTAGRAM, TEA, AQUECIMENTO) went to the first leaf
in the seed, and any parent can be changed with a migration.

To add an action, `attributes.py code-for PARENT` names the next free code and says
whether it opens a new class.

The web client shows ids grouped (`5 01 03 01`) and the dial filters by prefix as you
type, so `501` narrows the list to your Musculatura actions and `50103` to the ones on
Peitoral before the seventh digit picks one.

### How the shop groups actions

The shop groups by **practice** — Treino, Programação, Escrita, Literacia, Alimentação,
Consumo, Prática Mental — while ids classify by body and mind region. The same action is
filed two ways on purpose.

The engine has no notion of kinds, so the six practice roots carry a display mark,
`attr_nodes.shop_group`, and `_theme_for` in `backend/main.py` is its only reader: an
action goes under the primary parent of its heaviest leaf below a marked root. Scores,
degrees and ids never look at the mark. Marked leaves are preferred explicitly rather
than by weight — `WATER` feeds `hidratacao` and `c_bebida` both at `1.0`, and a tie would
otherwise be settled by row order.

### Catalog balance

Score is `value × type factor × difficulty multiplier`, and the difficulty multipliers
jump hard (`1, 30, 120, 400, 1000, 2500`). The catalog leans on that: almost everything is
a `session` whose value is 1 per act, so the difficulty alone sets the reward — d1 is 90
xp, d2 is 360, d3 is 1200. Only `WATER`, `COFFEE` and `TEA` use a counted unit, where you
log how many.

A note on an act is an annotation, not a quantity: free text always adds one execution,
and only a numeric note adds volume (`3` on a session action counts as three of them).

Prices assume build points stay scarce: 100 at profile creation plus
`BUILD_POINTS_PER_CHECKPOINT` (10) every checkpoint, against 240 bp to own the whole
catalog.

### The token economy

Tokens are not handed out over time — there is no daily refill. An action either releases
them or consumes them, flat per execution, and the note never multiplies either side:

| `token_gain` | who |
| --- | --- |
| 30 | escalada, surf, architecture |
| 25 | endurance, team sports, feature, refactor |
| 20 | heavy lifts, the dev routine, the writing actions |
| 15 | standard training, read, estudo |
| 10 | caminhada, meditação, core work, board game |
| 5 | alongamento, mobilidade, respiração, diário, podcast |

| `token_cost` | who |
| --- | --- |
| 20 | video games |
| 15 | watch film, tiktok |
| 12 | youtube, watch series, instagram |
| 10 | twitter, guloseima |

Nutrition sits at zero on both sides: eating is maintenance, not production. A profile
starts with an empty stock, so the first leisure act runs a debt — spending is never
blocked, the balance simply goes negative until productivity covers it.

The stock caps at `max_tokens` (100, plus 5 per Tokens node in the skill tree) and
anything past the cap is dropped. A productive day releases around 70, so a good day lands
whole and roughly a day and a half can be banked, but a run of them still overflows.
`ActOutcome.tokens_wasted` reports how much a given act threw away, and both clients show
it.

Every log carries the signed delta the act produced in `logs.tokens` — positive for what
was released after the cap took its cut, negative for what was spent — so the day's ledger
reads back from the logs panel without recomputing anything. Entries written before that
column existed sit at 0.

### API

Every user route requires `Authorization: Bearer <token>` and answers 401 without one.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | ping |
| POST | `/auth/register` | create a profile and sign in (`{username, password}`) |
| POST | `/auth/login` | sign in (`{username, password}`) |
| POST | `/auth/logout` | revoke the current session |
| GET | `/auth/me` | the username behind the token |
| GET | `/user` | full state: xp, level, rank, resources, bonuses |
| GET | `/journey` | stage and time left until the next checkpoint |
| GET | `/actions` | the profile's actions |
| POST | `/actions/{id}/act` | execute an action (`{note}` or `{value}`) |
| GET | `/attributes` | every leaf with its power and level |
| GET | `/attributes/roots` | every root with power and aggregated level |
| GET | `/attributes/tree` | the whole graph; each child link says its `weight` and whether it is `primary` |
| GET | `/shop/packages` | available actions grouped by theme |
| GET | `/shop/catalog` | the same, with each action's leaves and weights |
| POST | `/shop/actions/buy` | buy an action (`{attribute, name}`) |
| GET | `/skills/tree` | nodes, acquired ids, skill point balance and bonuses |
| POST | `/skills/{id}/acquire` | acquire a node |
| GET | `/logs` | logs for one day — `?offset=0` today, `-1` yesterday, `+1` tomorrow |
| GET | `/logs/by-date` | logs for a date (`?date=YYYY-MM-DD`) |
| PATCH | `/logs/{id}` | edit the note (`{note}`) or move it across days (`{day_delta}`) |
| DELETE | `/logs/{id}` | delete |
| POST | `/logs/reorder` | reorder within a day (`{day, ids}`) |
| GET | `/agenda` · `/agenda/today` | full agenda · today's agenda |
| POST | `/agenda` | create an item |
| PATCH · DELETE | `/agenda/{id}` | edit · remove |
| GET | `/calendar` | month view with log counts and events (`?year=&month=`) |
| GET · POST | `/projects` | list · create |
| PATCH · DELETE | `/projects/{id}` | edit · remove |

---

## Web client

Svelte 5 with TypeScript and no router: `App.svelte` keeps the current screen in a
variable and the sidebar switches between `home`, `agenda`, `journey`, `shop`, `skills`
and `user`. The theme is dark and monospaced.

The home screen is a grid of windows you can drag between slots and the bottom tray —
`actions`, `agenda`, `logs` and `projects`. The profile name lives in `localStorage` under
the key `roko_username`; without it the user picker takes over. Two stores (`logsVersion`,
`userVersion`) act as signals telling panels to refetch after an act.

## Terminal client

A single-key menu over the same database: `l` lists actions, `a` executes one, `g` shows
today's logs, `s` shows status, `u` switches profile, `q` quits. The profile picker holds
up to four users and can create and delete them.

---

## Current state

Known rough edges, for whoever touches this next:

- **The root `.env` is stale.** It still describes Postgres (`POSTGRES_*` and a
  `DATABASE_URL` pointing at `postgresql://…`), while `docker-compose.yml` brings up MySQL
  and sets `DATABASE_URL` on both services itself. Its `JWT_SECRET` is stale too: sessions
  are opaque tokens in a table, not signed ones. Nothing on the current path reads that
  file.
- **`npm run check` reports 4 type errors** under `apps/web/src/lib/` — `api.ts:105`
  (`stringfalso`), `api.ts:344` (`ProjectItem` does not exist; the declared type is
  `Project`, and `/projects` returns `{items: [...]}` rather than an array), and
  `ProjectsPanel.svelte:16` and `:44` following from it. The app still runs — Vite does
  not type-check in `dev` — but `check` is red.
- **A fourth, dead notion of attribute.** The per-user tables `attributes`,
  `attribute_actions` and `project_attributes` are still loaded and saved with every
  profile, and the legacy branch of agenda matching reads them, but nothing has filled them
  since `b7c1`. Attribute scoring is the graph. Removing them touches projects and the old
  agenda path.
- Three attributes are named "Mobilidade" (`mobilidade`, `c_mobilidade`, `t_mobilidade`).
  The keys differ, but in the unified tree they sit side by side.
- `storage.py` and `EVOVE_DATA_DIR` are leftovers from the JSON era. State lives in the
  database; the per-user directory is only used to locate legacy files.
