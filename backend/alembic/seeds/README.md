# Frozen seeds

Inputs to the migrations, frozen at the revision that reads them. No migration
reads `backend/data/attributes_tree.json` any more.

- `*.pre_engine.json` — the seed exactly as it stood before the attribute engine
  refactor (`d8e4b2c6f1a3`). Every migration older than that one reads these.
- `attributes_tree.engine.json` — the seed as it stood after the engine refactor
  and before the population (`b9f4c2e7a1d6`). `d8e4` and `f3b8` read this one.

They all used to re-read the live seed. That meant any later edit to it changed what
a fresh install built — which is how 17 conceptual leaves ended up with a null
`max_level`. `d8e4` was the worse case: it validates every action code against its
parent's chain, so the first action added to the live seed would have broken fresh
installs outright. Freezing the inputs makes the history reproducible, and leaves the
live seed free to be what a fresh install should *end* at.

Do not edit these files. Change `backend/data/` and write a new migration instead.
