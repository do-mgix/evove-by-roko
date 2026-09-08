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

The migration step is not optional on a fresh database: seven of the revisions also seed
the attribute tree, the tags and the shop catalog that the API reads on every request.

### 2. Web client

```bash
cd apps/web
npm install
npm run dev        # http://localhost:5173
```

It talks to `http://localhost:8000` by default — set `VITE_API_BASE` to point somewhere
else. `npm run build` writes `dist/`, `npm run check` runs `svelte-check` and `tsc`.

There is no login. The first screen asks for a profile name, which is stored in
`localStorage` and sent on every request as the `X-Evove-Username` header.

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
| `EVOVE_USERNAME` | backend, CLI | `default` | profile used when no header is sent |
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
    attributes.py              decay, levels and aggregated tree scores
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
  data/                        migration seeds (never read at runtime)
  alembic/                     migrations
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
| **attribute tree** | a static weighted tree; each action feeds a set of leaves |
| **leaf score** | per-user score on a leaf, decaying over time unless it is converted into a permanent level |
| **tag** | a curated combination of leaves, shown as a single bar |
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

### User identification

There is no authentication. The user comes in the `X-Evove-Username` header, validated
against `^[A-Za-z0-9_-]{1,24}$`; without it the request falls back to `EVOVE_USERNAME` or
to `default`. CORS is open to every origin. **This is meant for local use — do not expose
this API to a network.**

### Database

Twenty tables. Profile and content tables have an FK to `users` with delete cascade; the
attribute tree, the catalog and the tags are global and shared by everyone:

- profile — `users`, `user_state`, `user_tutorial`, `sequences_state`
- user content — `actions`, `attributes`, `attribute_actions`, `skills_acquired`,
  `agenda_items`, `logs`, `projects`, `project_actions`, `project_attributes`
- static tree — `attr_nodes`, `attr_edges`, `action_contributions`
- catalog metadata — `action_templates`
- per-user derived data — `user_leaf_scores`
- tags — `attribute_tags`, `attribute_tag_sources`

Content tables also keep the logical id from the JSON era (`action_id`, `attr_id`,
`item_id`), preserved so ids already used by the front end keep working.

### Migrations

Eleven revisions in a chain:

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
```

Seven of them (`b7c1`, `c8d2`, `e5a1`, `f7b3`, `b2e7`, `c4a8`, `d6b1`) read
`backend/data/*.json` to seed. Those files exist only for that: nothing opens them at runtime.

### Adding actions to the catalog

The shop has no admin screen. `/shop/packages` and `/shop/catalog` are assembled from
`action_contributions` (which attributes an action feeds) joined with `action_templates`
(its unit, difficulty and prices), so adding a shop item means rows in both — and for now
a migration is how you add them. Both blocks live in
`backend/data/attributes_tree.json`:

1. `contributions` — one entry per leaf, action name in caps. Anatomical weights sum to
   `1.0` per action and conceptual weights sum to `1.0` separately; an action with neither
   never reaches an attribute.
2. `action_templates` — one entry per action: `type` (the unit, see `Action._TYPE_MAP`),
   `diff` 0–5, `cost` in build points to acquire it, and then either `token_gain` or
   `token_cost` — never both. An action with contributions but no template falls back to
   `repos.TEMPLATE_FALLBACK`.
3. Copy `b2e7d9c4a6f1_routine_actions.py` for the contributions and
   `c4a8e2f6b9d3_action_templates.py` for the templates, put the new names in
   `NEW_ACTIONS` and chain `down_revision` to the current head. Keep the guard against
   rows that already exist: on a fresh database `b7c1` seeds the whole file, so without it
   the migration hits the unique constraint on `(action_name, leaf_id)`.
4. Migrating through the container? Run `docker compose build backend` first. The image
   carries a copy of `backend/data/` from build time, not the file in your working tree.

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

### API

Every user route reads the `X-Evove-Username` header.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | ping |
| GET | `/users` | list profiles |
| POST | `/users` | create a profile (`{name}`) |
| GET | `/user` | full state: xp, level, rank, resources, bonuses |
| GET | `/journey` | stage and time left until the next checkpoint |
| GET | `/actions` | the profile's actions |
| POST | `/actions/{id}/act` | execute an action (`{note}` or `{value}`) |
| GET | `/attributes` | leaves with score and level — filter with `?tree=anatomical\|conceptual` |
| GET | `/attributes/tags` | the composite tags |
| GET | `/attributes/tree` | hierarchical tree with a computed score on every node |
| GET | `/attributes/conceptual/roots` | conceptual roots with aggregated level |
| GET | `/shop/packages` | available actions grouped by attribute |
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
  and sets `DATABASE_URL` on both services itself. Nothing on the current path reads that
  file.
- **`npm run check` reports 5 type errors** under `apps/web/src/lib/` — `api.ts:40`
  (`stringfalso`), `api.ts:274` (`ProjectItem` does not exist; the declared type is
  `Project`, and `/projects` returns `{items: [...]}` rather than an array),
  `UserPanel.svelte:58`, `ProjectsPanel.svelte:16` and `:44`. The app still runs — Vite
  does not type-check in `dev` — but `check` is red.
- `attribute_actions`, `project_actions` and `project_attributes` exist in the ORM and are
  marked as unimplemented; attribute scoring currently comes from the contribution tree,
  not from the per-user `attributes` table.
- `storage.py` and `EVOVE_DATA_DIR` are leftovers from the JSON era. State lives in the
  database; the per-user directory is only used to locate legacy files.
