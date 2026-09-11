# Frozen seeds

`*.pre_engine.json` are the seed files exactly as they stood before the attribute
engine refactor (`d8e4b2c6f1a3`). Every migration older than that one reads these
copies, never `backend/data/`.

Those migrations used to re-read the live seed. That meant any later edit to it
changed what a fresh install built — which is how 17 conceptual leaves ended up with
a null `max_level`, and it would have broken fresh installs outright once the seed
changed shape. Freezing the inputs makes the history reproducible.

Do not edit these files. Change `backend/data/` and write a new migration instead.
