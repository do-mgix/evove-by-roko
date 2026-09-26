# EVOVE

Personal progression tracking system. Every act you log earns marks — up to five for a
real session — and marks move you and a tree of attributes through ranks.

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

### 4. Android client

The web client also ships as an APK: the same `dist/` bundle inside a WebView. It needs a
JDK 21 and the Android SDK (platform 36, build-tools 36) reachable through `JAVA_HOME` and
`ANDROID_HOME` — no Android Studio.

```bash
cd apps/web
echo 'VITE_API_BASE=http://<lan-ip>:8000' > .env.local   # the phone is not localhost
npm run apk          # build + cap sync + gradlew assembleDebug
npm run apk:install  # the same, then adb install -r on the connected device
npm run apk:release  # signed release APK, if android/keystore.properties is there
```

The APK lands in `apps/web/android/app/build/outputs/apk/debug/`. The first build downloads
Gradle and the AndroidX dependencies and takes a few minutes; after that it is seconds.
"Android client" below says what the native shell adds.

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
    action.py                  the Action class (its score formula no longer pays anything)
    marks.py                   tiers, the 6-hour window, how many marks an act yields
    act.py                     what an act changes in the user aggregate
    acting.py                  one act end to end — shared by the API and the CLI
    agenda.py                  matching an action against the day's agenda
    attributes.py              the attribute graph: marks, ranks, degree, registration rules
    user_attributes.py         patches and the attributes users create for them
    contributions.py           marks reaching the leaves
    daily.py                   daily tick (token refill, checkpoint countdown)
    skills.py                  skill tree rules and bonus aggregation
    ports.py                   WebInputInterrupt — how the domain asks the host for input
  src/infrastructure/
    db.py                      SQLAlchemy engine, session and Base
    orm.py                     table models
    repos.py                   repositories: dicts in, dicts out — never ORM entities
    storage.py                 per-user directory under ~/.local/share/evove (legacy)
    static_data.py             skill tree, and the attribute suggestion catalog
  data/attributes_tree.json    live seed: the attribute graph and the catalog
  data/attribute_suggestions.json  names offered when a user creates an attribute
  alembic/                     migrations
  alembic/seeds/               frozen seed copies the migrations read
  scripts/attributes.py        register attributes (subdivide, add, link…)
  scripts/migrate_json_to_db.py  legacy JSON importer
apps/web/src/
  App.svelte                   screen switching by state, no router
  lib/api.ts                   HTTP client and API types
  lib/*.svelte                 screens and panels
apps/web/capacitor.config.ts   app id, app name and WebView settings for the APK
apps/web/android/              Capacitor shell: Gradle project, black theme, debug cleartext
apps/web/scripts/android-icon.sh    launcher icons, cut from the wordmark
apps/web/scripts/android-splash.sh  launch screen wordmark, cut from the load screen
apps/cli/
  main.py                      single-key menu
  user_selector.py             profile picker (up to 4)
docker-compose.yml             MySQL + Adminer + backend + CLI
docker-compose.override.yml    dev bind mounts + uvicorn --reload (auto-merged)
CHANGELOG.md                   release history (conventional commits)
```

The CLI imports `backend/src/domain` directly — through `sys.path` in `apps/cli/main.py`
and `PYTHONPATH` in `apps/cli/Dockerfile`. That is why scoring, token cost and energy
penalties behave identically in both clients: `src/domain/acting.py` is the only
implementation of an act.

---

## Concepts

Enough vocabulary to read the code:

| Term | What it is |
| --- | --- |
| **action** | something you log, with a unit type and a difficulty; executing it is called an *act* |
| **attribute** | anything that can be trained, at any grain: Corpo, Bíceps, Força, Leitura. All the same kind of thing |
| **mark** | the unit of progress: an act picks one of its action's six tiers, worth 0–5 marks, and an action yields at most 5 every 6 hours |
| **rank** | A→Z. Each rank asks for more marks than the last (A 3, B 4 … Z 28); reaching one is permanent |
| **leaf** | an attribute with no children — the only kind that stores marks; any other attribute is the weighted mean of its children, rounded down |
| **degree** | depth along primary parents, the root being 1 |
| **patch** | a user's specialization of an owned action (*estudo → física*): acts like the base and also trains the user's own attributes |
| **user attribute** | an attribute a user created, outside the default graph, trained only by patches |
| **log action** | an action logged for monitoring only (leisure): `log_only`, spends tokens, feeds no attribute — its marks stay on the action |
| **tokens** | earned by executing productivity actions, spent on leisure ones, capped in stock |
| **energy** | drained by acting outside today's agenda, refilled at each checkpoint |
| **build points / skill points** | currencies for buying actions in the shop and nodes in the skill tree; both are paid out at checkpoints |
| **stage / checkpoint** | a countdown that advances the profile and hands out rewards |

The numbers behind all of this (tiers, the marks window, the rank table, the progression
curve) live in `backend/src/domain/` and in `backend/data/*.json`.

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
dies with it, and `POST /auth/logout-all` deletes every row of the profile, signing it out
on every device. Only the SHA-256 of the token is stored, so a dump of `sessions` hands out
nothing usable. Tokens last 30 days (`auth.SESSION_TTL`) and expired rows are cleared on
the next login.

Login answers the same 401 for a wrong password and for a username that does not exist, so
the response does not enumerate profiles. There is no endpoint that lists usernames.

`DELETE /auth/me` deletes the profile, and the foreign keys cascade to everything it owns —
state, actions, attributes, patches, marks, logs, agenda, projects and sessions. It asks for
the password again (`{password}`), so a session left open on another device is not enough;
a wrong one is 403 rather than 401, because the session is still valid and the web client
drops to login on any 401. The profile page offers it, and `GET /excluir-conta` serves a
plain page (`backend/pages/excluir-conta.html`) that does the same without the app — the
public deletion URL the Play Store asks for, at `https://api.voide.shop/excluir-conta`.

A profile may carry an e-mail address (`users.email`, optional, lower-cased, unique), set
at registration or from the profile page with the password (`PATCH /auth/me`). It exists
only for recovery: `POST /auth/forgot` takes a username or an address, and when the profile
has one it records a link in `password_resets` — a SHA-256 digest, 60 minutes, one per
minute at most — and mails it after answering. The answer is the same `{ok: true}` either
way, so it tells nothing about which profiles exist. The link opens `GET /redefinir-senha`
(`backend/pages/redefinir-senha.html`) with the token in the URL fragment, which never
reaches a server log; `POST /auth/reset` sets the new password, spends every open link of
the profile and ends all its sessions.

Mail goes out over SMTP configured by `mail.env` at the repository root, which Compose
loads into the backend and git ignores (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASSWORD`, `MAIL_FROM`). Without `SMTP_HOST` the backend prints the message, link
included, to its log instead. Links point at `PUBLIC_BASE_URL`, `https://api.voide.shop`
by default.

**Two things remain open, on purpose, for local use:** CORS still accepts every origin —
tightening it would break reaching the dev server from a phone on the LAN — and the CLI
talks straight to MySQL with no password, since whoever runs it already holds
`DATABASE_URL` and could read every profile anyway. The password protects the API, which
is the part exposed on a network.

### Database

Twenty-four tables. Profile and content tables have an FK to `users` with delete cascade; the
attribute graph and the catalog are global and shared by everyone:

- profile — `users`, `user_state`, `user_tutorial`, `sequences_state`, `sessions`
- patches — `user_attributes`, `patch_attributes` (a patch itself is a row in `actions`)
- user content — `actions`, `attributes`, `attribute_actions`, `skills_acquired`,
  `agenda_items`, `logs`, `projects`, `project_actions`, `project_attributes`
- attribute graph — `attr_nodes`, `attr_edges`, `action_contributions`
- catalog — `action_templates`, `id_class1`, `id_class2`
- per-user progress — `user_leaf_scores`, `mark_events`

Content tables also keep the logical id from the JSON era (`action_id`, `attr_id`,
`item_id`), preserved so ids already used by the front end keep working.

### Migrations

Twenty-one revisions in a chain:

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
e2c7a9d4f6b1  patches and user attributes
f3b8d1e7a4c2  marks and ranks replace scores, levels and xp
a3c9e5f1b7d2  patch link weights
b9f4c2e7a1d6  population: diet out, one action per practice, log actions
c1a7e4b9d2f6  anatomical weights from published muscle volumes
```

**No revision reads `backend/data/attributes_tree.json` any more.** Every one that seeds
reads a **frozen copy** in `backend/alembic/seeds/`: `*.pre_engine.json` for the nine older
ones (`b7c1`, `c8d2`, `e5a1`, `f7b3`, `b2e7`, `c4a8`, `d6b1`, `a1e5`, `c7a3`), and
`attributes_tree.engine.json` for `d8e4` and `f3b8`. Those two used to re-read the live
seed, so every later edit changed what a fresh install built — which is how 17 leaves ended
up with a null `max_level`, and `d8e4` validates every action code against its parent's
chain, so the first action added to the live seed would have broken fresh installs
outright.

The live seed is therefore the *end state*, not an input: a fresh install replays the
history and lands on it, and `scripts/attributes.py check` is what says whether the
database and the seed still agree.

### The attribute engine

There is one kind of attribute. Any attribute can have weighted children, depth has no
limit, and a parent's marks are the weighted mean of its children's, rounded down —
`braço = ⌊antebraço·½ + braço·½⌋`. A leaf is simply an attribute without children; only
leaves store marks, and everything above them is computed on read (`node_total`, memoized
per request).

**Several parents, one primary.** Força draws on peitoral, dorsal and more, while peitoral
also sits under Tronco. Each attribute has at most one *primary* parent, and the primary
chain alone defines its **degree** — its depth, root = 1 — which is what action ids use.
Other parents are ordinary links: Físico and Mental are roots whose children are the old
tags, and each tag reaches its leaves through non-primary links with the weights it
always had, so every tag kept its value.

**Marks and ranks.** An act's marks reach each leaf the action feeds multiplied by the
contribution weight — a 4-mark push-up session gives Calistenia (100%) 4 and Tríceps (30%)
1.2. Fractions accumulate; the interface shows whole marks. Marks buy ranks A→Z, rank
index *i* asking for `3 + i` (`rank_need`), 403 to finish Z, where progress stops at 28/28.
A leaf stores its `rank_index` and the `marks` above it; any other attribute derives both
from its total with the same table (`rank_view`). The `me` page draws every attribute as
a thick white bar cut into one segment per mark, rounded only at its ends, with the count
floating in the middle (`MarkBar.svelte`).

**Losing marks.** Nothing decays continuously any more. A rank is a permanent checkpoint;
the marks above it are progress that a trigger will be able to take away — the end of a
journey stage, a soft reset, time passing — none of which exists yet. The hook does:
`repos.lose_marks(username, rule)` with `{"kind": "all"}`, `{"kind": "fraction", …}` or
`{"kind": "half_life"}` (using `attr_nodes.half_life_hours`, kept for this), and it never
touches a rank.

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
| `check` | every difference between the seed and the database; exits 1 if there is one |

The rule behind `subdivide` and `add`: **registering children never changes what a
parent is worth at that moment.** On `subdivide`, every child inherits the leaf whole —
each user's marks and rank, and every action contribution at the same weight.
That is not a split: since the parent is a weighted *mean*, `0.6·100 + 0.4·100 = 100`,
and each act keeps moving it exactly as before. The children start identical and
diverge once you tune which actions feed which. On `add`, existing links are scaled by
what the new weights leave, and each new child starts at the parent's current total.
Because a parent rounds down, subdividing a leaf that holds a fraction (14.5 marks) leaves
the parent at 14 — its rank and whole marks on screen stay exactly the same, and the
fraction stays in the children.

`reweight` is the exception, on purpose: it moves the parent. Links that would close a
cycle are refused, and so is linking children onto a leaf that already holds marks —
subdivide it instead.

### What deserves an attribute

The engine takes any grain, which is exactly why the tree needs a policy — nothing in the
code stops someone from registering *surf* next to *bíceps*. One question decides it:

> **Is this, in practice, completely different from what is already there — or does it name
> a part of the body?** If neither, it is not a new attribute.

Surf is not, in practice, different from a sport: it is Esporte. So is chess, if the user
wants it there — the tree is not a taxonomy of the world, it is the set of things that can
be trained, and the system is not trying to model reality closely. Training and sport, on
the other hand, *are* different enough to stay apart: the anatomical branch already covers
what a training session moves, muscle by muscle, while a sport is one activity with a
progression of its own.

So the seed stays coarse and generic:

| Not an attribute | Where it goes |
| --- | --- |
| Surf, futebol, basquete, vôlei, tênis, xadrez | Esporte — one attribute, one action, a patch per sport |
| Instagram, TikTok, Twitter | Redes sociais — one action, no brands |
| A single exercise | The muscles it moves, through `action_contributions` |

**Brand names never enter the seed.** They date, they multiply, and whoever wants to
separate them already has patches. The catalog carries *Redes sociais*, *Vídeo*, *Jogos*;
a user who cares about the distinction carries *Redes sociais · Instagram*.

**Patches absorb the specificity.** A patch keeps everything its base pays and adds the
user's own attributes, so *Esporte · Basquete*, *Treino · Arremesso de 3* and *Treino ·
Velocidade* are all things a user builds on top of two catalog actions, each feeding
whatever user attributes they created. That is where realism belongs — the seed only has
to be right about what is *different*.

**Food and diet are out.** `nutricao` (`macros`, `hidratacao`, `estimulantes`), the
`c_alimentacao` practice (`c_refeicao`, `c_bebida`) and the seven actions that fed them —
WATER, COFFEE, TEA, BREAKFAST, LUNCH, DINNER, SNACK — left the seed in `b9f4`. Tying an
achievement to what someone ate is not a progression worth rewarding here, and ranks
pointed at meals push in the direction of several eating disorders whether or not the app
intends it. Hydration and caffeine went with it rather than surviving as a smaller version
of the same idea. Two weights moved with them: `corpo` lost a child worth `0.2` and is
`0.5 / 0.3 / 0.2` now, and `t_saude`, which was mostly nutrition, is rebuilt on aerobico
`0.5`, flexibilidade `0.2`, estabilidade `0.15` and core `0.15`.

**What that left.** Five ball sports became one ESPORTE with the athletic profile they
shared (aerobico `.25`, anaerobico `.2`, coordenacao `.2`, equilibrio `.1`, quadriceps
`.1`, core `.1`, panturrilha `.05`); the ones that are anatomically their own thing stayed
— CORRIDA, CICLISMO, NATAÇÃO, CAMINHADA, ESCALADA. Nine leisure actions became five log
actions. The catalog went from 61 actions to 46, the graph from 92 attributes to 79.

### Log actions

Leisure is *logged*, not trained. Watching a film or scrolling a feed belongs in the day's
ledger and in the token balance, and should not raise an attribute — there is no level of
watching films worth having. For these the **action is the attribute**: marks accumulate on
the action row itself (`actions.score`, plus `logs.marks` and `mark_events`, all of which
already exist) and reach no leaf.

They are marked with a boolean on the template, `action_templates.log_only`, because they
share one shape: they charge `token_cost` instead of releasing `token_gain`, they carry six
tiers like any action, and they have no contributions at all. The catalog has five —
REDES SOCIAIS, VÍDEO, JOGOS, MÚSICA, GULOSEIMA — where it used to carry a brand per feed.

What an act on one does, and does not do:

| | |
| --- | --- |
| the action's own marks (`actions.score`) | grow, as for any action |
| the marks window | applies, so a split session pays no more |
| `logs` and `mark_events` | written, as for any action |
| tokens and the energy penalty | charged, as for any action |
| the profile's total (`user_state.marks`) | **untouched** — the marks stay on the action |
| attributes, through contributions or a patch | **untouched** — it feeds none |

`perform_act` reads `log_only` from the template behind the action — a patch's is its
base's — passes it to `apply_act`, which then skips the profile's total, and returns before
`apply_action_contributions`. The act's response carries `log_only`, so a client can say
why the total did not move.

**Registration and the id.** A log action is registered under no attribute:
`action_templates.parent_node_id` is NULL and the id takes the reserved class, `5 00 00 ii`
— an action with no attribute has no class to name. That is why `/actions` returns an empty
`path` for one, and why the `me` page files them under *registro* rather than under an
attribute.

**Patches.** A patch on a log action is allowed and costs the base's `cost` like any other
patch, but it takes no attributes: `POST /patches` refuses `attribute_ids` on a log base
instead of accepting links that would never pay, and the shop skips the attribute step. It
is there to separate entries in the ledger — *REDES SOCIAIS · TRABALHO* apart from
*REDES SOCIAIS · ROLAGEM* — without either becoming progression.

### Naming and language

Schema in English, visible text translatable, user text untouched:

| Layer | Language | Example |
| --- | --- | --- |
| Tables, columns, enums, `attr_nodes.key`, action names | English | `arm_strength`, `log_only` |
| Labels the interface shows for seeded content | a translation keyed by the technical key | `arm_strength` → "Força de Braço" |
| Anything the user typed — patch names, user attributes | free text, stored as written, never keyed | "Ler Ficção" |

Identifiers in Portuguese cost more than they look: accents rub against ORMs, migrations,
query caches and logs, every error message and every library around them is in English
already, and a mixed-language schema is the first thing a second pair of hands trips over.
Content is the opposite — it has to be in the user's language, so it lives as data and not
as an identifier, either as a `label_pt` column beside the key or, better, in an i18n file
the front end reads by key without touching the database.

User-created content is a third case and takes no key at all. A patch called "Ler Ficção"
has no English name to map to and never gets one; it is stored in the language it was typed
in, and only the closed set of seeded attributes and actions gets the key plus translation
treatment.

**This is the convention, not yet the code.** The seed still mixes the two (`biceps` and
`c_leitura` next to `FLEXÃO` and `ESCREVER DIÁLOGOS`), and the new actions follow the
catalog as it reads today — ESPORTE, REDES SOCIAIS, VÍDEO. The rename needs the label layer
in the same pass, or the interface starts showing SPORT and SOCIAL MEDIA to a Portuguese
reader, and that crosses the API and the web client. Node keys are cheap to rename:
`attr_edges`, `action_contributions` and `action_templates` all point at node **ids**, no
client stores a key, and the only files that spell them out are `backend/data/attributes_tree.json`
and `scripts/attributes.py` — the frozen `*.pre_engine.json` seeds keep the old keys, and the
rename migration maps them forward the way `d8e4` already realigns the graph. Action names
are not cheap: `action_contributions.action_name`, `action_templates.action_name` and
`actions.name` join on the string itself, and `engine_name` resolves a patch through its
base's name, so renaming one action touches all of them at once.

### Where the weights come from

The weights inside the two limbs are the fraction of that limb's muscle volume each
group holds, taken from the tables named below rather than picked by hand — `c1a7`.
Everything else in the graph is still a judgement call.

| leaf | weight | leaf | weight |
| --- | --- | --- | --- |
| `deltoide` | 0.24 | `quadriceps` | 0.35 |
| `triceps` | 0.24 | `gluteo` | 0.32 |
| `biceps` | 0.18 | `panturrilha` | 0.17 |
| `antebraco` | 0.34 | `posterior_coxa` | 0.16 |

**Upper limb — Holzbaur, Murray, Gold & Delp 2007**, "Upper limb muscle volumes in adult
subjects", *J Biomech* 40:742-749, Table 2: 10 subjects, 32 muscles, 2554 cm³ of muscle in
the limb, and the volume fraction of each. Deltoid 15.2%, triceps 14.5, anconeus 0.4,
biceps 5.6, brachialis 5.7, brachioradialis 2.5, the eighteen forearm muscles 19.0
together. The tree has four leaves, so the muscles are grouped onto them: `triceps` takes
the elbow extensors, `biceps` the elbow flexors (brachialis with it), `antebraco` the
brachioradialis and the forearm, `deltoide` the deltoid **alone** — the rotator cuff's
16.7% is left out, because the leaf is Deltoide and not Ombro. Pectoralis and latissimus
are in Holzbaur's total but sit under `tronco` here, so they leave the sum too. The four
hold 62.9% of the limb and are renormalised over that.

**Lower limb — Ward, Eng, Smallwood & Lieber 2009**, "Are current measurements of lower
extremity muscle architecture accurate?", *Clin Orthop Relat Res*, Table 3: 21 cadaver
limbs, 83 ± 9 years. Masses in grams — quadriceps 897.8, gluteals 820.7, hamstrings 407.2,
triceps surae 451.5 — over their 2577.2 g.

**The caveat, in full.** Handsfield et al. 2014 is the in vivo source and was the first
one reached for, but it publishes its fractions as Fig. 2A, a figure: the body of the paper
carries none of the numbers. It does compare itself against Ward and finds the cadaver
fractions consistent *"with a few exceptions"* — gluteus medius, psoas and vastus lateralis
differ significantly — and two of those fall in the groups that rise here. Ward is the best
source available as text, and that is what these weights rest on.

`tronco` and `musculatura` are **not** touched: neither paper covers the abdominals or the
erectors, and comparing Holzbaur's in vivo total against Ward's cadaver total would not
mean anything. Nor is the `mente` branch: Penfield and Fedorenko were on the list for
linking cortical weight to attributes, and that is still ahead, as is calibrating each
action's contribution per exercise from the EMG work.

### The suggestion catalog

Nobody should have to invent the subdivisions of "what I study" from a blank text field, so
the interface offers a ready-made list: `backend/data/attribute_suggestions.json`, served
by `GET /attribute-suggestions` and rendered by `SuggestionPicker.svelte` in both places
where an attribute is created.

**It is not the attribute graph and never becomes it.** Nothing user-created can feed
`attr_nodes` — `patch_attributes` references `user_attributes.id` and nothing else — so a
taxonomy seeded as nodes would have no way to receive a mark, and since a parent is the
weighted sum of its children, a branch of permanent zeros would drag its ancestors down.
The catalog is therefore **text**: picking *Ciências naturais e matemática › Ciências
físicas › Física* creates ordinary user attributes with those names. Only the label is
copied, so renaming one in the JSON later renames nobody's attribute — there is no link
back, and that is deliberate.

Two catalogs, 128 entries, at most three levels:

| catalog | what | source |
| --- | --- | --- |
| Matérias | 11 broad fields, 30 narrow, 43 detailed | UNESCO ISCED-F 2013 |
| Competências | Essential and Transferable Skills, their 7 groups and 35 skills | O*NET Content Model |

Every node keeps the official code (ISCED) and the official English title in
`source_label`, next to the Portuguese `label` shown on screen. The labels are an
**adaptation**, not an official translation: several ISCED names run past the 64 characters
`user_attributes.name` holds, and the loader refuses the file if one does, so a bad edit
fails at boot instead of as a 400 when somebody picks it. ISCED repeats a broad field's own
name at the narrow level when a broad has a single narrow (011 Education, 061 ICTs); those
are left out and their children attach to the broad field.

**Picking a path.** `POST /user-attributes` takes `{"path": [...]}` besides
`{name, parent_id?}`, and `new_attributes` in `POST /patches` takes `{"path": [...]}`
besides a name — the same helper, in the patch's own transaction, so a patch that fails on
build points leaves no attribute behind. Two rules decide what it creates:

- **a level the profile already has by that name is reused where it sits, never moved.**
  Names are unique per profile and the column is `utf8mb4_unicode_ci`, so "Física",
  "FÍSICA" and "fisica" are one attribute — the column's collation decides, not a
  comparison in Python, which would miss the accent. If Física was already a root, picking
  the full path reuses the root and the chain is not formed: moving an attribute carries
  its marks and changes what its old parent is worth, which stays the user's own
  `PATCH /user-attributes/{id}`;
- **an ancestor is created only when something below it has to be.** Picking a field the
  profile already has creates nothing at all, rather than leaving an empty branch above it.

The answer's `chain` says which levels were created and which were reused. And because a
reused level may be a leaf holding marks, taking a child hands them down —
`new_child_start`, the rule for every user attribute — so the shop says so before creating.

### Adding actions to the catalog

The shop has no admin screen. `/shop/packages` and `/shop/catalog` are assembled from
`action_templates` (unit, difficulty, prices, `log_only`), with `action_contributions`
saying which attributes each one feeds and, through them, which practice it is filed
under. The catalog is therefore the set of templates: a template is what carries the code
an id comes from, so nothing listed in the shop is unbuyable, and a log action with no
contributions at all still appears. Adding a shop item means a migration; both blocks live
in `backend/data/attributes_tree.json`:

1. `contributions` — one entry per leaf the action feeds, name in caps. By convention an
   action carries two budgets that each sum to `1.0`: its leaves under the practice roots
   (the ones marked `shop_group`) and all the others. The practice leaf is what files it
   in the shop — see below.
2. `action_templates` — one entry per action: its `parent` (the attribute it is
   registered under), its `code` (from `attributes.py code-for PARENT`), `type` (the unit,
   see `Action._TYPE_MAP`), `diff` 0–5, `cost` in build points to acquire it, either
   `token_gain` or `token_cost` — never both — and its six `tiers` (see "Marks and
   tiers"). A log action skips step 1 entirely and its entry here carries
   `"log_only": true` with `"parent": null` and the next free `5 00 00 ii` code.
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

**`5 00 00 ii` is the log class.** A log action is registered under no attribute, so it has
no class to name and takes the reserved one: `00` at both levels, which was already
reserved everywhere, and the position among log actions. REDES SOCIAIS is `5 00 00 01`. It
is the only shape whose `parent_node_id` is NULL, and `code-for` is not involved — there is
no parent to ask about.

**Ids never move.** The parent, the class numbers and the code are all stored rather than
derived: if they were computed, a weight change could re-pick the parent, or an attribute
inserted mid-path could shift every degree below it, and ids would change. After an
action is registered, its id is data. The initial parents were the heaviest leaf of the
body/mind branch; ties went to the first leaf in the seed, and any parent can be changed
with a migration. A freed code is not reused either: ESPORTE took `5 02 01 07` and not the
`01` and `05` BASQUETE and FUTEBOL left behind, since a reused code would inherit their
mark events.

To add an action, `attributes.py code-for PARENT` names the next free code and says
whether it opens a new class.

The web client shows ids grouped (`5 01 03 01`) and the dial filters by prefix as you
type, so `501` narrows the list to your Musculatura actions and `50103` to the ones on
Peitoral before the seventh digit picks one.

### Marks and tiers

A mark is the smallest execution that counts as a real achievement. Acting means picking
one of the action's six tiers instead of counting exactly — estudo is
`<10m · 10–30m · 30m–1h · 1–2h · 2–3h · >3h`, worth 0 to 5 marks. Each template carries
them in `tiers`:

```json
{ "unit": "min", "bounds": [10, 30, 60, 120, 180] }
{ "mode": "max", "labels": ["ultraprocessado", "rápido", "simples", "caseiro", "equilibrado", "equilibrado com vegetais"] }
```

Five bounds define the six tiers and the labels are generated from the unit (`min`, `reps`,
`km`, `m`, or any word). The 46 catalog actions carry tiers — repetitions for calisthenics,
km or minutes for cardio, minutes for study, dev work and leisure, portions for
GULOSEIMA — meant to be tuned. `max` mode still works and nothing uses it since the meals
left: it was for events that do not add up.

**The window.** An action yields at most `MARKS_PER_WINDOW` (5) marks every
`MARK_WINDOW_HOURS` (6), counted in `mark_events`. The window is cumulative, so splitting a
session pays nothing extra: in `sum` mode a choice is worth the lower bound of its tier,
and the window pays the tier the total falls in minus what it already paid. Five
"20–50" push-up records add up to 100, the 100–150 tier: +1, +0, +1, +0, +1 — 3 marks,
not 5. One ">200" pays 5 and the action pays nothing more until the window frees up. `max`
mode is for events that do not add up: the window pays the best tier chosen.
A patch counts against its base's window, or two patches of one action would each get 5 —
a log action included, since it runs the same window.

**One act, end to end,** is `perform_act` in `src/domain/acting.py`, used by the API and
the CLI alike: tiers (the base's, for a patch) → window → marks (`marks_for`) → the act on
the aggregate (executions, marks, tokens, energy, log line `FLEXÃO [20–50] : note`) →
save → mark event → default-graph contributions → the patch's own attributes. An invalid
tier is refused before anything changes.

**Xp is gone.** The user's progression keeps its shape — rank letters with roman levels —
but every level costs marks: the old xp curve divided by 70, so A·I costs 3 and the whole
of rank A about 169. `user_state.marks` holds the total and `logs.marks` what each act
earned; the `xp` and `score` columns stay as legacy and are no longer written. The five
"XP I–V" skills multiplied xp and have no effect until they get a new one.

In the web client the act modal shows the six tiers and how many marks the window already
holds; after dialing an id, keys 1–6 pick the tier and `Enter` acts.

### Patches and user attributes

Catalog actions are engines. A **patch** specializes one the user owns without asking
them to pick anatomical leaves: *estudo → física* keeps everything estudo pays and also
trains "Física", an attribute the user created. The flow is all in the shop — buy the
action, then "+ patch": base action → name → attributes, creating them on the spot if
there are none. The patch then lists right under its base and acts like any action.

**What an act on a patch does.** It is a row in `actions` with `base_action_id` set,
carrying the base's `type`, `diff` and tokens. Its tiers, its marks window, its contributions
to the default graph and its agenda matching all come from the base (`engine_name`), so a
patch moves exactly the leaves its base would; its name is stored as `ESTUDO · FÍSICA`, which
keeps logs readable and sorts it under the base. Then `apply_patch_attributes` trains the
patch's attributes, inside the same `perform_act` both clients use.

**Price and ids.** A patch costs the base's `cost` in build points; creating an attribute
is free. The id is the base's seven digits plus the lowest free two, so one action takes
up to 99 patches — `5 06 01 01 · 01`. The dial needs no new rule: a base with patches no
longer fires at seven digits, because a longer id shares the prefix; `Enter` fires the
base and the ninth digit fires the patch.

**User attributes** live in `user_attributes`, per user, and follow the engine's rules with
equal weights:

- only a leaf (no children) holds marks; a parent is the mean of its children, rounded down;
- creating a child never moves the parent at that moment — the first child of a leaf
  inherits its marks and rank, and a later child starts at the parent's current total;
- a patch may point at any attribute, each link with a weight above 0 and at most 1 (new
  links start at 1): on each act every leaf reached gets the act's marks times that
  weight, once, through the heaviest link when several reach it — a patch on "Ciências"
  at 100% trains Física and Química fully;
- moving an attribute takes its marks along; a parent it leaves without children becomes
  a leaf again at the total it had, and a leaf holding marks takes no children, since its
  own marks would vanish behind the mean;
- they rank A→Z like any attribute.

**In the tree** a patch sits where its base action would, under the base's registered
parent: `/attributes/tree` lists it in that node's `patches`, display only — it never
enters the node's marks, and the web client no longer draws it there. The `me` page lists
every user attribute under the attributes' ★p and every patch, by base action, under the
actions' ★p.

**Why links go by text.** `repos._write_actions` deletes and reinserts every action row on
each save, so `actions.id` changes all the time. `patch_attributes` references the patch by
`(user_id, action_id)`, and `POST /patches` writes the whole patch in one transaction
instead of going through `save_user`. The dead per-user `attributes` table was not an
option for the same reason — every save wipes it.

**Where they come from.** The shop's "+ atributo" and the patch wizard both offer the
suggestion catalog next to the free-text field — see "The suggestion catalog".

**Editing.** The `me` page opens any attribute or action in a page-sized modal — its marks
and rank, what computes it and what it computes. Only what the user created changes there:
a patch or a user attribute can be renamed and re-parented, and a user attribute's
children re-weighted (patches, in tenths) or removed — a child attribute becomes a root
with its marks, a patch simply stops training it. Anything that makes an attribute stop
counting marks asks for confirmation first. Deleting patches and user attributes is not
built yet.

### How the shop groups actions

The shop groups by **practice** — Treino, Escrita, Literacia, Programação, Prática
Mental — while ids classify by body and mind region. The same action is filed two ways on
purpose.

The engine has no notion of kinds, so the practice roots carry a display mark,
`attr_nodes.shop_group`, and `_theme_for` in `backend/main.py` is its only reader: an
action goes under the primary parent of its heaviest leaf below a marked root. Scores,
degrees and ids never look at the mark. Marked leaves are preferred explicitly rather
than by weight — `ESPORTE` feeds `aerobico` and `c_esportes` both at `1.0`, and a tie would
otherwise be settled by row order.

**Consumo is the exception, and not a practice.** Log actions feed no leaf, so there is
nothing to group them by; they go in a section of their own keyed `_log`, which is not an
attribute. `Alimentação` and `Consumo` used to be practice roots in the graph and are gone
with the attributes under them — the shop section survived the attributes it was named
after, because the shop needs somewhere to put five actions and the graph does not.

### Catalog balance

What an act pays is decided by its tier — see "Marks and tiers". `type` and `diff` are
still stored on every template and every action, but since xp became marks they no longer
move anything: the old `value × type factor × difficulty multiplier` formula in
`Action` is not called by acting. A note on an act is text only.

Prices assume build points stay scarce: 100 at profile creation plus
`BUILD_POINTS_PER_CHECKPOINT` (10) every checkpoint, against 204 bp to own the whole
catalog. Log actions are free to acquire, as the leisure actions they replace were.

### The token economy

Tokens are not handed out over time — there is no daily refill. An action either releases
them or consumes them, flat per execution whatever the tier — even an act worth 0 marks —
and the note never multiplies either side:

| `token_gain` | who |
| --- | --- |
| 30 | escalada, architecture |
| 25 | endurance, esporte, feature, refactor |
| 20 | heavy lifts, the dev routine, the writing actions |
| 15 | standard training, read, estudo |
| 10 | caminhada, meditação, core work, board game |
| 5 | alongamento, mobilidade, respiração, diário, podcast |

| `token_cost` | who |
| --- | --- |
| 20 | jogos |
| 12 | redes sociais, vídeo |
| 10 | guloseima |
| 0 | música |

Every action that spends is a log action, which is the shape the pattern had all along:
what costs tokens is consumption, and consumption is logged, not trained. Música sits at
zero — background consumption that costs nothing and pays nothing. A profile starts with an
empty stock, so the first leisure act runs a debt: spending is never blocked, the balance
simply goes negative until productivity covers it.

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
| POST | `/auth/register` | create a profile and sign in (`{username, password, email?}`) |
| POST | `/auth/login` | sign in (`{username, password}`) |
| POST | `/auth/logout` | revoke the current session |
| POST | `/auth/logout-all` | revoke every session of the profile, on every device |
| GET | `/auth/me` | the account behind the token (id, username, creation date), its session's start and expiry, and how many sessions are active |
| PATCH | `/auth/me` | set or clear the recovery e-mail (`{email, password}`; 403 if the password is wrong, 409 if the address is taken) |
| DELETE | `/auth/me` | delete the profile and all its data (`{password}`; 403 if wrong) |
| POST | `/auth/forgot` | mail a password-reset link (`{login}`, username or e-mail); same answer whether or not it exists; no token |
| POST | `/auth/reset` | set a new password from a link (`{token, password}`); ends every session; no token |
| GET | `/redefinir-senha` | public page to ask for a link and to set the new password from it; no token |
| GET | `/excluir-conta` | public page to delete an account without the app; no token |
| GET | `/user` | full state: marks, rank and level, resources, bonuses |
| GET | `/journey` | stage and time left until the next checkpoint |
| GET | `/actions` | the profile's actions, each with its six tiers, `log_only`, `path` (the primary chain to the attribute it is registered under, empty for a log action) and `leaves` (what it feeds, with weights); a patch adds its `attributes` with their link weight |
| POST | `/actions/{id}/act` | execute an action (`{option, note?}`; option is the tier, 0–5). The answer's `log_only` says whether `user_marks` moved |
| GET | `/actions/{id}/window` | marks already earned in the action's 6-hour window, and its tiers |
| GET | `/attributes` | every leaf with its rank and marks |
| GET | `/attributes/roots` | every root with its rank and marks |
| GET | `/attributes/recent` | the leaves that most recently gained marks, custom ones included (`?limit=10`) |
| GET | `/attributes/tree` | the whole graph; each child link says its `weight` and whether it is `primary`; a node can carry `patches` |
| GET | `/attribute-suggestions` | the names the interface offers when creating an attribute (ISCED-F fields, O*NET skills); static, no token |
| GET | `/user-attributes` | the user's own attributes as a tree, with rank, marks and the patches that train each, with their link weight |
| PATCH | `/user-attributes/{id}` | rename (`{name}`) or move with its marks (`{parent_id}`, `null` for a root) |
| POST | `/user-attributes` | create one (`{name, parent_id?}`), free — or a suggestion's whole chain (`{path: [...]}`), reusing each level the profile already has |
| POST | `/patches` | create a patch (`{base_action_id, name, attribute_ids, new_attributes}`), costs the base's price; an entry of `new_attributes` is a name, `{name, parent_id}` or `{path: [...]}`; on a log base the attributes are refused, since it trains none |
| PATCH | `/patches/{id}` | rename (`{name}`) or replace the attributes it trains (`{attribute_ids}`); kept links keep their weight |
| PUT | `/patches/{id}/attributes/{attribute_id}` | set a link's weight (`{weight}`, above 0 and at most 1) |
| DELETE | `/patches/{id}/attributes/{attribute_id}` | the attribute stops receiving the patch's marks |
| GET | `/shop/packages` | available actions grouped by theme |
| GET | `/shop/catalog` | the same, with each action's leaves and weights — none for a log action |
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
variable and the sidebar switches between `profile`, `home`, `agenda`, `journey`, `shop`,
`skills` and `me`. `profile` holds the journey (day, streak, stage), the technical details —
account, session, API — and the log out options. `me` is what the profile has earned: its
rank and marks, the leaves that gained marks most recently in two columns, the attributes
of one degree as flat rows, and the actions grouped by their attribute of one degree. A
single star button cycles each list by click: ★1, ★2, ★3 and ★p for the custom attributes;
★1, ★2 and ★p for the patches, by base; log actions have no attribute to group by and sit
in one of their own, *registro*. Clicking an attribute or an action — not a recent one —
opens it in `DetailModal.svelte` (see "Editing" above). The theme is dark and
monospaced.

The home screen is a grid of windows you can drag between slots and the bottom tray —
`actions`, `agenda`, `logs` and `projects`. The profile name lives in `localStorage` under
the key `evove_username`; without it the user picker takes over. Two stores (`logsVersion`,
`userVersion`) act as signals telling panels to refetch after an act.

## Android client

Capacitor 8 wraps the built `dist/` in a WebView. There is no second codebase: `npm run
apk` builds the web client, `cap sync` copies the bundle into
`android/app/src/main/assets/public`, and Gradle packages it. `apps/web/android/` is an
ordinary Gradle project, versioned — generated once by `cap add android` and edited by hand
since. The identifiers live in `capacitor.config.ts`: `com.evove.app`, app name *Evove*,
`webDir: dist`.

Three things the template does not get right for this app:

- **The API is not on the phone.** `VITE_API_BASE` is baked into the bundle at build time,
  and its default — `http://localhost:8000` — resolves to the phone itself. `.env.local`
  holds the public HTTPS address of the backend and stays out of git. For now that is a
  cloudflared quick tunnel (`cloudflared tunnel --url http://localhost:8000`), whose
  `*.trycloudflare.com` URL changes whenever the tunnel restarts — the APK has to be rebuilt
  when it does. Its replacement is the `tunnel` service in `docker-compose.yml`: a named
  Cloudflare tunnel serving `https://api.voide.shop`, opt-in through a Compose profile
  (`docker compose --profile tunnel up -d tunnel`) and fed its token by `tunnel.env`, which
  is not versioned. The tunnel's hostname is set in the Cloudflare dashboard and points at
  `http://backend:8000`, inside the Compose network.
- **HTTPS only.** Android blocks plain HTTP since API 28, and the bundle is served from
  `https://localhost` inside the WebView, so an http API would also be mixed content. The
  app allows neither: there is no cleartext exception and no `allowMixedContent`, and the
  API must answer over HTTPS in debug and release alike.
- **Black.** The web app is black on black (`src/app.css`), so the native shell matches:
  `styles.xml`, the launcher background and the WebView background. Otherwise every cold
  start flashes white before the first frame. `colors.xml` is ours too — the template
  references `@color/colorPrimary` without defining it anywhere, and without that file the
  build does not resolve.

The bottom nav pads itself by `env(safe-area-inset-bottom)` (`lib/NavBar.svelte`), which
Capacitor feeds from the real window insets: `index.html` declares `viewport-fit=cover`,
which is what makes WebView 140+ pass them through. Older WebViews report nothing to
`env()`; there Capacitor pads the native view instead, so the nav clears the gesture bar
either way.

The launcher icon is the first "e" of the wordmark in `apps/cli/assets/media/evovepng.png`,
white on black — the whole word is unreadable at 48dp. `scripts/android-icon.sh` cuts that
letter out and writes every density: the adaptive foreground, which stays inside the 66dp
safe zone the launcher mask leaves alone, plus square and round legacy icons for launchers
that predate adaptive icons. The adaptive background is `@color/ic_launcher_background`,
black, and the same letter serves as the `monochrome` layer for themed icons on Android 13+.

What sits behind the WebView while the bundle boots is the load screen of the visual
identity: "evove / by roko" in the bottom-right corner of black, from
`apps/cli/assets/media/evove-mobile-loadscreen.png`. `scripts/android-splash.sh` cuts that
block out and `drawable/launch_screen.xml` places it at the margins the original uses — as
a layer-list rather than the source image, so the bitmap draws at its own size and keeps its
proportions instead of being stretched to whatever screen it lands on. On API 31+ the system
splash comes first, the launcher icon on black, and hands off to it. Capacitor's own
`splash.png` in eleven orientations and densities is gone; nothing referenced it.

`npm run apk:release` produces a signed release APK. What signs it is described by
`android/keystore.properties`, which is not versioned: it names a keystore outside the
repository — `~/keystores/evove-release.jks` on this machine — and carries its passwords.
`app/build.gradle` tolerates its absence, so the project still configures and debug builds
still work on a machine that does not have it; only `assembleRelease` comes out unsigned.
**That pair is not reproducible.** Whoever holds it can publish updates of `com.evove.app`,
and losing it means the app can never be updated on the Play Store again — only
republished under another package name. Back it up off this machine.

## Terminal client

A single-key menu over the same database: `l` lists actions, `a` executes one — listing its
six tiers and the window, then asking which — `g` shows
today's logs, `s` shows status, `u` switches profile, `q` quits. The profile picker holds
up to four users and can create and delete them.

Patches show up in `l` under their base and can be executed with `a` by their nine-digit id
(spaces allowed). Creating patches and attributes is only in the web shop.

---

## Current state

Known rough edges, for whoever touches this next:

- **The root `.env` is stale.** It still describes Postgres (`POSTGRES_*` and a
  `DATABASE_URL` pointing at `postgresql://…`), while `docker-compose.yml` brings up MySQL
  and sets `DATABASE_URL` on both services itself. Its `JWT_SECRET` is stale too: sessions
  are opaque tokens in a table, not signed ones. Nothing on the current path reads that
  file. It is no longer versioned, but its old values remain in the git history, so none
  of them should be reused.
- **`npm run check` reports 3 type errors** under `apps/web/src/lib/` — `api.ts:421`
  (`ProjectItem` does not exist; the declared type is `Project`, and `/projects` returns
  `{items: [...]}` rather than an array), and `ProjectsPanel.svelte:16` and `:44` following
  from it. The app still runs — Vite does not type-check in `dev` — but `check` is red.
- **The APK's API address is frozen at build time.** `VITE_API_BASE` goes into the bundle,
  so a new network means a rebuild — and a release build, which cannot use cleartext, needs
  the API on HTTPS before it is good for anything.
- **Leftovers of xp.** The `xp`/`score` columns, `Action`'s score formula and the five
  "XP I–V" skills remain but pay nothing; the skills need a new effect.
- **A fourth, dead notion of attribute.** The per-user tables `attributes`,
  `attribute_actions` and `project_attributes` are still loaded and saved with every
  profile, and the legacy branch of agenda matching reads them, but nothing has filled them
  since `b7c1`. Attribute scoring is the graph. Removing them touches projects and the old
  agenda path.
- Three attributes are named "Mobilidade" (`mobilidade`, `c_mobilidade`, `t_mobilidade`).
  The keys differ, but in the unified tree they sit side by side.
- `storage.py` and `EVOVE_DATA_DIR` are leftovers from the JSON era. State lives in the
  database; the per-user directory is only used to locate legacy files.
- **The sensorial branch is thinly fed.** Leisure used to be most of what moved `visual`,
  `auditivo` and `recompensa`; now `visual` has one feeder (ESCREVER DESCRIÇÕES), `auditivo`
  one (PODCAST) and `recompensa` three (the AI-assisted dev actions). Since a parent is the
  mean of its children, `sensorial` caps `mente` at a fifth of its weight. The conceptual
  population is where those get feeders — nothing is broken, it is unbalanced.
- **"Naming and language" is a convention, not the code.** Keys and action names are still
  mixed Portuguese and English and there is no label layer; the i18n pass is separate.
- **A log action still records `type` and `diff`.** Both are dead for every action (see
  "Catalog balance"), and on a log action they are meaningless twice over.
- **The catalog's Portuguese is an adaptation.** Codes, hierarchy and English titles come
  from the sources; the labels are shortened and reworded to fit 64 characters and to read
  like something a person would name an attribute. `source_label` on every node is what
  makes that auditable. O*NET also renames its own sections — what older writing calls
  Basic and Cross-Functional Skills it now calls Essential and Transferable — so a refresh
  means re-reading the model, not diffing against memory.
