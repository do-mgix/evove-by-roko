import os
import re
import sys
from datetime import datetime
from pathlib import Path

import roman
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

_BACKEND_DIR = Path(__file__).parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from src.domain.action import Action  # noqa: E402
from src.domain.act import apply_act, ActError  # noqa: E402
from src.domain.agenda import collect_labels, DAY_NAMES as _DOMAIN_DAY_NAMES  # noqa: E402
from src.domain.daily import apply_daily_tick  # noqa: E402
from src.domain.contributions import apply_action_contributions  # noqa: E402
from src.domain.attributes import apply_decay  # noqa: E402
from src.domain.skills import (  # noqa: E402
    aggregate_bonuses,
    acquire_skill as _acquire_skill,
    SkillError,
)
from src.infrastructure.static_data import (  # noqa: E402
    load_skill_tree,
    skill_nodes_by_id,
    load_packages,
    lookup_token_cost as _lookup_token_cost_static,
)
from src.infrastructure.storage import (  # noqa: E402
    get_evove_root_dir,
    get_user_data_dir,
)
from src.infrastructure import repos  # noqa: E402

_GREEK = ['α','β','γ','δ','ε','ζ','η','θ','ι','κ','λ','μ','ν','ξ','ο','π','ρ','σ','τ','υ','φ','χ','ψ','ω']
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


app = FastAPI(title="Roko API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")


def _root_dir() -> Path:
    override = os.environ.get("EVOVE_DATA_DIR")
    return Path(override) if override else Path(get_evove_root_dir())


def _resolve_username(x_evove_username: str | None) -> str:
    name = (x_evove_username or os.environ.get("EVOVE_USERNAME") or "default").strip()
    if not _USERNAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid username")
    return name


def _data_dir(username: str | None = None) -> Path:
    name = _resolve_username(username)
    override = os.environ.get("EVOVE_DATA_DIR")
    if override:
        path = Path(override) / name
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path(get_user_data_dir(name))


_INITIAL_BUILD_POINTS = 100


def _apply_initial_grants(data: dict) -> bool:
    """Grants one-time bonuses based on tutorial flags. Returns True if mutated."""
    metadata = data.setdefault("metadata", {})
    tutorial = metadata.setdefault("tutorial", {})
    flag = tutorial.get("received_start_build_points")
    if isinstance(flag, dict):
        already = bool(flag.get("status"))
    elif isinstance(flag, bool):
        already = flag
    else:
        return False
    if already:
        return False
    metadata["build_points"] = int(metadata.get("build_points", 0) or 0) + _INITIAL_BUILD_POINTS
    if isinstance(flag, dict):
        flag["status"] = True
        tutorial["received_start_build_points"] = flag
    else:
        tutorial["received_start_build_points"] = {"status": True, "priority": 12}
    return True


def _load_user(username: str) -> dict:
    data = repos.load_user_dict(username)
    if data is None:
        raise HTTPException(status_code=404, detail=f"user '{username}' not found")
    dirty = _apply_initial_grants(data)
    dirty = apply_daily_tick(data) or dirty
    if dirty:
        repos.save_user_dict(username, data)
    _apply_leaf_decay_if_due(username, data)
    return data


def _apply_leaf_decay_if_due(username: str, data: dict) -> None:
    """Once per day, decay every user leaf score with hour precision."""
    now = datetime.now()
    today_str = now.date().isoformat()
    metadata = data.setdefault("metadata", {})
    if metadata.get("last_decay_check") == today_str:
        return
    repos.apply_decay_to_all_leaves(username, now)
    metadata["last_decay_check"] = today_str
    repos.save_user_dict(username, data)


def _save_user(username: str, data: dict) -> None:
    repos.save_user_dict(username, data)


def _build_tiers():
    tiers = []
    cumulative_xp = 0
    global_level = 1
    total_ranks = len(_LETTERS)
    for rank_index, letter in enumerate(_LETTERS):
        levels_in_rank = max(1, total_ranks - rank_index)
        rank_symbol = _GREEK[rank_index % len(_GREEK)]
        for local_level in range(1, levels_in_rank + 1):
            xp_cost = max(1, int(round(200 * (1.06 ** (global_level - 1)) * (1.28 ** rank_index))))
            cumulative_xp += xp_cost
            tiers.append({
                "level": global_level,
                "rank_index": rank_index,
                "rank_letter": letter,
                "rank_symbol": rank_symbol,
                "local_level": local_level,
                "local_level_roman": roman.toRoman(local_level),
                "local_levels_total": levels_in_rank,
                "xp_cost": xp_cost,
                "threshold": cumulative_xp,
            })
            global_level += 1
    return tiers


def _progression_state(xp: int):
    tiers = _build_tiers()
    current = tiers[0]
    for tier in tiers:
        current = tier
        if xp < tier["threshold"]:
            break
    else:
        current = tiers[-1]
    next_xp = max(0, current["threshold"] - xp)
    if xp >= tiers[-1]["threshold"]:
        next_xp = 0
    return {
        "xp": xp,
        "level": current["level"],
        "rank_letter": current["rank_letter"],
        "rank_symbol": current["rank_symbol"],
        "local_level": current["local_level"],
        "local_level_roman": current["local_level_roman"],
        "local_levels_total": current["local_levels_total"],
        "next_xp": next_xp,
        "xp_cost": current["xp_cost"],
    }


def _load_sequences(username: str) -> dict:
    return repos.load_sequences(username)


def _save_sequences(username: str, data: dict):
    repos.save_sequences(username, data)


def _ensure_sequences(username: str, now: datetime | None = None) -> dict:
    """Initializes missing fields in sequences.json. Returns the data."""
    now = now or datetime.now()
    today = now.strftime("%d %m %Y")
    data = _load_sequences(username)
    changed = False
    if not data.get("first_activity_date"):
        data["first_activity_date"] = today
        changed = True
    if "consecutive_days" not in data:
        data["consecutive_days"] = 1
        changed = True
    if not data.get("last_active_date"):
        data["last_active_date"] = today
        changed = True
    data.setdefault("sequences", [])
    if changed:
        _save_sequences(username, data)
    return data


def _day_number(username: str):
    data = _ensure_sequences(username)
    first = data.get("first_activity_date")
    if not first:
        return 0
    try:
        first_dt = datetime.strptime(first, "%d %m %Y").date()
        return (datetime.now().date() - first_dt).days + 1
    except Exception:
        return 0


def _record_activity(username: str, now: datetime | None = None) -> int:
    """Updates consecutive_days based on last_active_date. Returns the new consecutive count."""
    now = now or datetime.now()
    today = now.date()
    data = _ensure_sequences(username, now=now)
    try:
        last = datetime.strptime(data.get("last_active_date", ""), "%d %m %Y").date()
    except Exception:
        last = today
    if today == last:
        return int(data.get("consecutive_days", 1) or 1)
    delta = (today - last).days
    if delta == 1:
        data["consecutive_days"] = int(data.get("consecutive_days", 0) or 0) + 1
    else:
        data["consecutive_days"] = 1
    data["last_active_date"] = now.strftime("%d %m %Y")
    _save_sequences(username, data)
    return int(data["consecutive_days"])


@app.get("/health")
def health():
    return {"status": "ok"}


def _checkpoint_interval_for_stage(stage: int) -> int:
    return 19 + max(1, int(stage or 1))


@app.get("/journey")
def journey(x_evove_username: str | None = Header(None)):
    from datetime import timedelta
    username = _resolve_username(x_evove_username)
    data = _load_user(username)
    metadata = data.get("metadata", {}) or {}
    stage = int(metadata.get("stage", 1) or 1)
    days_until = int(metadata.get("days_until_next_checkpoint", _checkpoint_interval_for_stage(stage)) or _checkpoint_interval_for_stage(stage))
    interval = _checkpoint_interval_for_stage(stage)

    # Checkpoint triggers at start of the day when days_until reaches 0.
    now = datetime.now()
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if days_until <= 0:
        next_at = now
    else:
        next_at = next_midnight + timedelta(days=max(0, days_until - 1))
    seconds_left = max(0, int((next_at - now).total_seconds()))
    hours_left = seconds_left // 3600
    minutes_left = (seconds_left % 3600) // 60

    return {
        "stage": stage,
        "days_until_next_checkpoint": days_until,
        "interval_for_current_stage": interval,
        "next_checkpoint_at": next_at.isoformat(),
        "seconds_left": seconds_left,
        "hours_left": hours_left,
        "minutes_left": minutes_left,
    }


@app.get("/users")
def list_users():
    root = _root_dir()
    return repos.list_usernames()


@app.post("/users")
def create_user(payload: dict):
    name = (payload or {}).get("name", "").strip()
    if not _USERNAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid username (a-z, 0-9, _ -, max 24)")
    if repos.user_exists(name):
        raise HTTPException(status_code=409, detail=f"user '{name}' already exists")
    today = datetime.now().strftime("%Y-%m-%d")
    initial = {
        "username": name,
        "score": 0,
        "value": 0,
        "attributes": {},
        "actions": {},
        "parameters": {},
        "statuses": {},
        "shop_items": {},
        "shop_action_links": {},
        "tags": {},
        "action_tags": {},
        "param_tags": {},
        "logic_types": {},
        "sublogic_types": {},
        "skills": [],
        "metadata": {
            "mode": "progressive",
            "username": name,
            "energy": 1000,
            "score": 0,
            "stage": 1,
            "skill_points": 0,
            "build_points": 0,
            "tutorial": {
                "received_start_build_points": {"status": False, "priority": 12},
            },
            "tokens": 50,
            "max_tokens": 50,
            "daily_refill": 20,
            "days_until_next_checkpoint": 20,
            "last_checkpoint_check": today,
            "last_token_refill": today,
        },
    }
    today_seq = datetime.now().strftime("%d %m %Y")
    initial_sequences = {
        "first_activity_date": today_seq,
        "last_active_date": today_seq,
        "consecutive_days": 1,
    }
    repos.create_user(name, initial, initial_sequences)
    return {"name": name}


@app.get("/user")
def user_state(x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    data = _load_user(username)
    metadata = data.get("metadata", {}) or {}
    xp = int(round(float(data.get("score", 0) or 0)))
    progression = _progression_state(xp)
    user_leaf_scores = repos.get_user_leaf_scores(username)
    active_attrs = [s for s in user_leaf_scores.values() if float(s.get("score", 0) or 0) > 0]
    bonuses = aggregate_bonuses(set(data.get("skills") or []), skill_nodes_by_id())
    base_max_tokens = int(metadata.get("max_tokens", 50) or 50)
    base_max_energy = 1000
    seq = _ensure_sequences(username)
    return {
        "username": metadata.get("username") or data.get("username"),
        "date": metadata.get("date"),
        "day": _day_number(username),
        "consecutive_days": int(seq.get("consecutive_days", 0) or 0),
        "xp": xp,
        "level": progression["level"],
        "rank_letter": progression["rank_letter"],
        "rank_symbol": progression["rank_symbol"],
        "local_level_roman": progression["local_level_roman"],
        "local_levels_total": progression["local_levels_total"],
        "next_xp": progression["next_xp"],
        "xp_cost": progression["xp_cost"],
        "stage": int(metadata.get("stage", 1) or 1),
        "energy": int(metadata.get("energy", 0) or 0),
        "max_energy": base_max_energy + bonuses["max_energy"],
        "skill_points": int(metadata.get("skill_points", 0) or 0),
        "build_points": int(metadata.get("build_points", 0) or 0),
        "tokens": int(metadata.get("tokens", 0) or 0),
        "max_tokens": base_max_tokens + bonuses["max_tokens"],
        "days_until_next_checkpoint": int(metadata.get("days_until_next_checkpoint", 0) or 0),
        "attributes_count": len(active_attrs),
        "bonuses": bonuses,
    }


_DAY_NAMES = ("SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM")


class Agenda:
    """Per-user agenda backed by the DB."""

    def __init__(self, username: str):
        self.username = username
        self.items: list[dict] = []
        self._load()

    def _load(self):
        self.items = repos.load_agenda_items(self.username)

    def _save(self):
        repos.save_agenda_items(self.username, self.items)

    def _next_id(self) -> str:
        max_n = 0
        for it in self.items:
            try:
                n = int(str(it.get("id", "")).removeprefix("ag_"))
                if n > max_n:
                    max_n = n
            except (TypeError, ValueError):
                continue
        return f"ag_{max_n + 1:04d}"

    def add(self, start: str, end: str | None, day: str, label: str, label_kind: str = "text", label_id: str | None = None, date: str | None = None) -> dict:
        if not date and day != "*" and day not in _DAY_NAMES:
            raise HTTPException(status_code=400, detail=f"invalid day '{day}'")
        if not label:
            raise HTTPException(status_code=400, detail="label is required")
        item = {
            "id": self._next_id(),
            "day": day if not date else None,
            "date": date,
            "start": start or None,
            "end": end or None,
            "label": label,
            "label_kind": label_kind or "text",
            "label_id": label_id,
        }
        self.items.append(item)
        self._save()
        return item

    def for_date(self, iso: str) -> list[dict]:
        return [it for it in self.items if it.get("date") == iso]

    def remove(self, item_id: str) -> bool:
        before = len(self.items)
        self.items = [it for it in self.items if it.get("id") != item_id]
        if len(self.items) == before:
            return False
        self._save()
        return True

    def update(self, item_id: str, payload: dict) -> dict:
        idx = next((i for i, it in enumerate(self.items) if it.get("id") == item_id), -1)
        if idx == -1:
            raise HTTPException(status_code=404, detail="item not found")
        item = dict(self.items[idx])
        for key in ("start", "end", "day", "label", "label_kind", "label_id"):
            if key in payload:
                item[key] = payload[key] or None if key in ("end", "label_id") else payload[key]
        self.items[idx] = item
        self._save()
        return item

    def for_day(self, day_name: str) -> list[dict]:
        return [it for it in self.items if it.get("day") == day_name or it.get("day") == "*"]


class Projects:
    """Per-user projects/goals backed by the DB."""

    def __init__(self, username: str):
        self.username = username
        self.items: list[dict] = []
        self._load()

    def _load(self):
        self.items = repos.load_projects(self.username)

    def _save(self):
        repos.save_projects(self.username, self.items)

    def _next_id(self) -> str:
        max_n = 0
        for it in self.items:
            try:
                n = int(str(it.get("id", "")).removeprefix("p_"))
                if n > max_n:
                    max_n = n
            except (TypeError, ValueError):
                continue
        return f"p_{max_n + 1:04d}"

    def add(self, name: str, deadline: str | None, related_actions: list[str], related_attributes: list[str], active: bool = True) -> dict:
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        item = {
            "id": self._next_id(),
            "name": name,
            "deadline": deadline or None,
            "active": bool(active),
            "related_actions": list(related_actions or []),
            "related_attributes": list(related_attributes or []),
            "created_at": datetime.now().isoformat(),
        }
        self.items.append(item)
        self._save()
        return item

    def update(self, item_id: str, payload: dict) -> dict:
        for it in self.items:
            if it.get("id") == item_id:
                if "name" in payload and str(payload["name"]).strip():
                    it["name"] = str(payload["name"]).strip()
                if "deadline" in payload:
                    it["deadline"] = (str(payload["deadline"]).strip() or None) if payload["deadline"] else None
                if "active" in payload:
                    it["active"] = bool(payload["active"])
                if "related_actions" in payload:
                    it["related_actions"] = list(payload["related_actions"] or [])
                if "related_attributes" in payload:
                    it["related_attributes"] = list(payload["related_attributes"] or [])
                self._save()
                return it
        raise HTTPException(status_code=404, detail="project not found")

    def remove(self, item_id: str) -> bool:
        before = len(self.items)
        self.items = [it for it in self.items if it.get("id") != item_id]
        if len(self.items) == before:
            return False
        self._save()
        return True


@app.get("/projects")
def projects_all(x_evove_username: str | None = Header(None)):
    return {"items": Projects(_resolve_username(x_evove_username)).items}


@app.post("/projects")
def projects_add(payload: dict, x_evove_username: str | None = Header(None)):
    pj = Projects(_resolve_username(x_evove_username))
    return pj.add(
        name=str(payload.get("name", "")).strip(),
        deadline=(str(payload.get("deadline")).strip() if payload.get("deadline") else None),
        related_actions=payload.get("related_actions") or [],
        related_attributes=payload.get("related_attributes") or [],
        active=bool(payload.get("active", True)),
    )


@app.patch("/projects/{item_id}")
def projects_update(item_id: str, payload: dict, x_evove_username: str | None = Header(None)):
    return Projects(_resolve_username(x_evove_username)).update(item_id, payload or {})


@app.delete("/projects/{item_id}")
def projects_remove(item_id: str, x_evove_username: str | None = Header(None)):
    ok = Projects(_resolve_username(x_evove_username)).remove(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@app.get("/agenda")
def agenda_all(x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    return {"items": Agenda(username).items}


@app.post("/agenda")
def agenda_add(payload: dict, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    ag = Agenda(username)
    item = ag.add(
        start=str(payload.get("start", "")).strip(),
        end=(str(payload.get("end")).strip() if payload.get("end") else None),
        day=str(payload.get("day", "*")).strip().upper(),
        label=str(payload.get("label", "")).strip(),
        label_kind=str(payload.get("label_kind", "text")).strip(),
        label_id=payload.get("label_id"),
        date=(str(payload.get("date")).strip() if payload.get("date") else None),
    )
    return item


@app.get("/calendar")
def calendar(year: int, month: int, x_evove_username: str | None = Header(None)):
    """Returns per-date stats for a given month: log counts and special events."""
    from datetime import date as _date, timedelta
    username = _resolve_username(x_evove_username)
    seq = _ensure_sequences(username)
    try:
        first_dt = datetime.strptime(seq.get("first_activity_date", ""), "%d %m %Y").date()
    except (ValueError, TypeError):
        first_dt = None

    # Load logs and group by attribution date (via coord)
    by_date: dict[str, int] = {}
    if first_dt:
        logs = repos.load_logs(username)
        for log in logs:
            status = str(log.get("status", "")).upper()
            if "DELETED" in status or "PROCESSED" in status:
                continue
            coord = log.get("coord")
            if not (isinstance(coord, list) and len(coord) >= 2):
                continue
            day_num = int(coord[0])
            d = first_dt + timedelta(days=day_num - 1)
            iso = d.isoformat()
            by_date[iso] = by_date.get(iso, 0) + 1

    # Load events (date-based agenda items) for the month
    ag = Agenda(username)
    events_by_date: dict[str, list[dict]] = {}
    prefix = f"{year:04d}-{month:02d}"
    for it in ag.items:
        d = it.get("date")
        if d and d.startswith(prefix):
            events_by_date.setdefault(d, []).append(it)

    # Build full month grid
    days: dict[str, dict] = {}
    if month == 12:
        next_first = _date(year + 1, 1, 1)
    else:
        next_first = _date(year, month + 1, 1)
    cur = _date(year, month, 1)
    while cur < next_first:
        iso = cur.isoformat()
        days[iso] = {
            "log_count": by_date.get(iso, 0),
            "events": events_by_date.get(iso, []),
        }
        cur += timedelta(days=1)

    return {"year": year, "month": month, "days": days}


@app.get("/logs/by-date")
def logs_by_date(date: str, x_evove_username: str | None = Header(None)):
    """Returns logs whose attribution date matches the given ISO date."""
    from datetime import datetime as _dt, timedelta
    username = _resolve_username(x_evove_username)
    try:
        target = _dt.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid date")
    seq = _ensure_sequences(username)
    try:
        first_dt = _dt.strptime(seq.get("first_activity_date", ""), "%d %m %Y").date()
    except (ValueError, TypeError):
        return {"date": date, "logs": []}
    target_day = (target - first_dt).days + 1
    logs = repos.load_logs(username)
    result = []
    for log in logs:
        status = str(log.get("status", "")).upper()
        if "DELETED" in status or "PROCESSED" in status:
            continue
        coord = log.get("coord") or []
        if not (isinstance(coord, list) and len(coord) >= 2 and int(coord[0]) == target_day):
            continue
        result.append({
            "id": log.get("id"),
            "timestamp": log.get("timestamp"),
            "content": log.get("content"),
            "xp": int(log.get("xp", 0) or 0),
            "order": int(coord[1]),
        })
    result.sort(key=lambda l: l.get("order", 0))
    return {"date": date, "day": target_day, "logs": result}


@app.patch("/agenda/{item_id}")
def agenda_update(item_id: str, payload: dict, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    return Agenda(username).update(item_id, payload or {})


@app.delete("/agenda/{item_id}")
def agenda_remove(item_id: str, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    ok = Agenda(username).remove(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True}
@app.get("/skills/tree")
def skills_tree(x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    data = _load_user(username)
    tree = load_skill_tree()
    acquired = set(data.get("skills") or [])
    return {
        "nodes": tree.get("nodes", []),
        "acquired": sorted(acquired),
        "skill_points": int((data.get("metadata") or {}).get("skill_points", 0) or 0),
        "bonuses": aggregate_bonuses(acquired, skill_nodes_by_id()),
    }


@app.post("/skills/{skill_id}/acquire")
def acquire_skill(skill_id: str, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    data = _load_user(username)
    try:
        result = _acquire_skill(data, skill_id, skill_nodes_by_id())
    except SkillError as e:
        msg = str(e)
        status = 404 if "not found" in msg else 409 if "already" in msg else 400
        raise HTTPException(status_code=status, detail=msg)
    _save_user(username, data)
    return result


@app.get("/shop/packages")
def shop_packages():
    return load_packages()


@app.get("/shop/catalog")
def shop_catalog():
    """Group action templates by their primary anatomical/neurological zone.

    For each action, find the leaf with highest contribution weight, then
    group by that leaf's parent node. Returns flat list of groups in tree order.
    """
    packages = load_packages()
    tree = repos.load_attr_tree()
    contributions = repos.load_all_contributions()

    leaf_to_parent: dict[str, str] = {}
    for parent_key, children in tree.children.items():
        for child_key, _w in children:
            if child_key in tree.leaves_by_key:
                leaf_to_parent[child_key] = parent_key

    grouped: dict[str, dict] = {}
    unmapped: list[dict] = []

    for pkg in packages:
        for action in pkg.get("actions", []) or []:
            name_upper = str(action.get("name", "")).upper()
            contribs = contributions.get(name_upper, [])
            entry = {
                "name": action.get("name"),
                "type": action.get("type"),
                "diff": action.get("diff"),
                "cost": action.get("cost"),
                "token_cost": int(action.get("token_cost", 0) or 0),
                "package_attribute": pkg.get("attribute"),
                "leaves": [
                    {
                        "key": leaf_key,
                        "name": tree.leaves_by_key[leaf_key].name,
                        "weight": w,
                    }
                    for leaf_key, w in contribs
                ],
            }
            if not contribs:
                unmapped.append(entry)
                continue
            primary_leaf = contribs[0][0]
            group_key = leaf_to_parent.get(primary_leaf)
            if not group_key:
                unmapped.append(entry)
                continue
            group_name = tree.nodes_by_key[group_key].name
            grouped.setdefault(group_key, {"key": group_key, "name": group_name, "actions": []})
            grouped[group_key]["actions"].append(entry)

    result = sorted(grouped.values(), key=lambda g: g["name"])
    if unmapped:
        result.append({"key": "_unmapped", "name": "Outros", "actions": unmapped})
    return result


@app.post("/shop/actions/buy")
def buy_action(payload: dict, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    data = _load_user(username)

    name = (payload or {}).get("name", "").strip().upper()
    attr_name = (payload or {}).get("attribute", "").strip()
    if not name or not attr_name:
        raise HTTPException(status_code=400, detail="missing name or attribute")

    pkg = next((p for p in load_packages() if p.get("attribute") == attr_name), None)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"package '{attr_name}' not found")
    template = next((a for a in pkg.get("actions", []) if str(a.get("name", "")).upper() == name), None)
    if not template:
        raise HTTPException(status_code=404, detail=f"action '{name}' not found in package")

    cost = int(template.get("cost", 0))
    metadata = data.setdefault("metadata", {})
    bp = int(metadata.get("build_points", 0) or 0)
    if bp < cost:
        raise HTTPException(status_code=400, detail=f"insufficient build points (have {bp}, need {cost})")

    actions = data.setdefault("actions", {})
    if any(str(a.get("name", "")).upper() == name and not a.get("deleted") for a in actions.values()):
        raise HTTPException(status_code=409, detail=f"action '{name}' already exists")

    existing_ids = [int(aid) for aid in actions.keys() if aid.isdigit()]
    next_id = (max(existing_ids) + 1) if existing_ids else 501
    new_id = str(next_id)
    actions[new_id] = {
        "id": new_id,
        "name": name,
        "type": int(template.get("type", 0)),
        "diff": int(template.get("diff", 0)),
        "value": 0,
        "max_value": 0,
        "score": 0,
        "deleted": False,
        "logic_type": None,
        "sub_logic_type": None,
        "token_cost": int(template.get("token_cost", 0) or 0),
    }

    # Attribute scoring is now driven by the action_contributions tree (DB-side),
    # not the legacy per-user attribute table. No attribute row created on buy.

    metadata["build_points"] = bp - cost

    _save_user(username, data)

    return {"id": new_id, "name": name, "build_points": metadata["build_points"]}


def _day_for(username: str, date_obj) -> int:
    return repos.day_for_user(username, date_obj)


@app.post("/logs/reorder")
def reorder_logs(payload: dict, x_evove_username: str | None = Header(None)):
    """Body: {day: int, ids: [int, ...]}. Sets coord[1] of each id to its new 1-based index within day."""
    username = _resolve_username(x_evove_username)
    day = int(payload.get("day", -1))
    ids = payload.get("ids") or []
    if day < 0 or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="invalid payload")
    logs = repos.load_logs(username)
    by_id = {int(l.get("id")): l for l in logs if l.get("id") is not None}
    for new_idx, lid in enumerate(ids, start=1):
        log = by_id.get(int(lid))
        if not log:
            continue
        coord = log.get("coord") or [day, 0]
        if int(coord[0]) != day:
            continue
        log["coord"] = [day, new_idx]
    repos.save_logs(username, logs)
    return {"ok": True, "count": len(ids)}


@app.delete("/logs/{log_id}")
def delete_log(log_id: int, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    removed = repos.delete_log(username, int(log_id))
    if removed is None:
        raise HTTPException(status_code=404, detail=f"log {log_id} not found")
    return {"ok": True, "id": int(log_id), "removed": removed}


@app.patch("/logs/{log_id}")
def update_log(log_id: int, payload: dict, x_evove_username: str | None = Header(None)):
    """Body: {note?: str, content?: str, day_delta?: int}."""
    username = _resolve_username(x_evove_username)

    if "day_delta" in payload and payload["day_delta"] is not None:
        delta = int(payload["day_delta"])
        updated = repos.shift_log_day(username, int(log_id), delta)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"log {log_id} not found or invalid day")
        return updated

    logs = repos.load_logs(username)
    log = next((l for l in logs if int(l.get("id", -1)) == int(log_id)), None)
    if not log:
        raise HTTPException(status_code=404, detail=f"log {log_id} not found")

    new_content = None
    if "content" in payload and payload["content"] is not None:
        new_content = str(payload["content"])
    elif "note" in payload:
        note = (payload.get("note") or "").strip()
        cur = str(log.get("content", ""))
        head = cur
        m = re.match(r"^(.+?)\s*:\s*(.+)$", cur)
        if m:
            head = m.group(1).strip()
        else:
            m2 = re.match(r"^(\d+)\s*[xX]\s*(.+)$", cur)
            if m2:
                head = m2.group(2).strip()
        new_content = f"{head} : {note}" if note else head

    if new_content is not None:
        updated = repos.update_log_content(username, int(log_id), new_content)
        return updated or log
    return log


@app.get("/logs")
def list_logs(offset: int = 0, x_evove_username: str | None = Header(None)):
    """offset: 0 = today, -1 = yesterday, +1 = tomorrow."""
    from datetime import timedelta
    username = _resolve_username(x_evove_username)
    target_date = (datetime.now() + timedelta(days=offset)).date()
    target_day = _day_for(username, target_date)
    logs = repos.load_logs(username)
    result = []
    for log in logs:
        status = str(log.get("status", "")).upper()
        if "DELETED" in status or "PROCESSED" in status:
            continue
        coord = log.get("coord") or []
        if not (isinstance(coord, list) and len(coord) >= 2 and int(coord[0]) == target_day):
            continue
        result.append({
            "id": log.get("id"),
            "timestamp": log.get("timestamp"),
            "content": log.get("content"),
            "xp": int(log.get("xp", 0) or 0),
            "order": int(coord[1]),
        })
    result.sort(key=lambda l: l.get("order", 0))
    return {"day": target_day, "offset": offset, "date": target_date.isoformat(), "logs": result}


@app.get("/agenda/today")
def agenda_today(x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    day_name = _DAY_NAMES[datetime.now().weekday()]
    items = Agenda(username).for_day(day_name)
    return {"day": day_name, "items": items}


@app.get("/attributes")
def list_attributes(x_evove_username: str | None = Header(None)):
    """Flat list of leaves with current (decay-applied) user scores."""
    username = _resolve_username(x_evove_username)
    _load_user(username)  # triggers daily decay if due
    tree = repos.load_attr_tree()
    user_scores = repos.get_user_leaf_scores(username)
    now = datetime.now()
    result = []
    for key, leaf in tree.leaves_by_key.items():
        ls = user_scores.get(key)
        if ls is None:
            score = leaf.floor
        else:
            score = apply_decay(ls["score"], ls["last_updated_at"], now,
                                leaf.half_life_hours, leaf.floor)
        result.append({
            "key": key,
            "name": leaf.name,
            "score": round(score, 2),
            "half_life_hours": leaf.half_life_hours,
            "floor": leaf.floor,
        })
    result.sort(key=lambda a: a["score"], reverse=True)
    return result


@app.get("/attributes/tree")
def attributes_tree(x_evove_username: str | None = Header(None)):
    """Hierarchical tree with computed (decay-applied) scores at every node."""
    from src.domain.attributes import compute_node_score

    username = _resolve_username(x_evove_username)
    _load_user(username)
    tree = repos.load_attr_tree()
    user_scores = repos.get_user_leaf_scores(username)
    now = datetime.now()

    leaf_scores: dict[str, float] = {}
    for key, leaf in tree.leaves_by_key.items():
        ls = user_scores.get(key)
        if ls is None:
            leaf_scores[key] = leaf.floor
        else:
            leaf_scores[key] = apply_decay(
                ls["score"], ls["last_updated_at"], now,
                leaf.half_life_hours, leaf.floor,
            )

    def render(key: str) -> dict:
        node = tree.nodes_by_key[key]
        score = compute_node_score(key, leaf_scores, tree)
        out: dict = {
            "key": key,
            "name": node.name,
            "is_leaf": node.is_leaf,
            "score": round(score, 2),
        }
        if node.is_leaf:
            leaf = tree.leaves_by_key[key]
            out["half_life_hours"] = leaf.half_life_hours
            out["floor"] = leaf.floor
        else:
            out["children"] = [
                {"weight": w, **render(ck)}
                for ck, w in tree.children.get(key, [])
            ]
        return out

    return {"roots": [render(r) for r in tree.roots]}


_LOG_ID_PREFIX = 73
_LOG_ID_WIDTH = 4


def _today_agenda_labels(username: str) -> set[str]:
    """Build the set of today's agenda labels (normalized) for this user."""
    now = datetime.now()
    day_name = _DAY_NAMES[now.weekday()]
    iso = now.strftime("%Y-%m-%d")
    return collect_labels(Agenda(username).items, day_name=day_name, iso_date=iso)


def _append_log(username: str, content: str, xp: int) -> dict | None:
    logs = repos.load_logs(username)
    today_day = _day_for(username, datetime.now().date())
    max_id = 0
    next_order = 0
    for log in logs:
        try:
            v = int(log.get("id", 0))
        except (TypeError, ValueError):
            v = 0
        if v > max_id:
            max_id = v
        coord = log.get("coord")
        if isinstance(coord, list) and len(coord) >= 2 and int(coord[0]) == today_day:
            try:
                if int(coord[1]) > next_order:
                    next_order = int(coord[1])
            except (TypeError, ValueError):
                pass
    next_id = max_id + 1 if max_id else int(f"{_LOG_ID_PREFIX}{1:0{_LOG_ID_WIDTH}d}")
    entry = {
        "id": next_id,
        "timestamp": datetime.now().strftime("%d %m %Y : %H:%M:%S"),
        "content": content,
        "status": "[CLOUD]",
        "xp": int(xp),
        "coord": [today_day, next_order + 1],
    }
    repos.append_log(username, entry)
    return entry


@app.post("/actions/{action_id}/act")
def act_on_action(action_id: str, payload: dict | None = None, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    data = _load_user(username)

    action = (data.get("actions") or {}).get(action_id)
    if not action or action.get("deleted"):
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")

    # Determine note input: explicit note, or numeric value, or default 1.
    manual_value: str | int = 1
    if payload:
        if "note" in payload and payload["note"] is not None:
            note_text = str(payload["note"]).strip()
            if note_text:
                manual_value = note_text
        elif "value" in payload and payload["value"] is not None:
            try:
                manual_value = int(payload["value"])
            except (TypeError, ValueError):
                manual_value = 1

    today_labels = _today_agenda_labels(username)
    try:
        outcome = apply_act(
            data,
            action_id,
            manual_value=manual_value,
            today_agenda_labels=today_labels,
            token_cost_lookup=_lookup_token_cost_static,
            skill_nodes_by_id=skill_nodes_by_id(),
        )
    except ActError as e:
        raise HTTPException(status_code=404, detail=str(e))

    _save_user(username, data)

    apply_action_contributions(username, action.get("name", ""), float(outcome.score_diff), datetime.now())

    _record_activity(username)
    log_entry = _append_log(username, outcome.log_content, int(round(outcome.score_diff)))

    return {
        "id": action_id,
        "name": action.get("name"),
        "value": action["value"],
        "score": action["score"],
        "score_diff": outcome.score_diff,
        "user_score": data["score"],
        "log": log_entry,
    }


@app.get("/actions")
def list_actions(x_evove_username: str | None = Header(None)):
    data = _load_user(_resolve_username(x_evove_username))
    actions = data.get("actions", {}) or {}
    result = []
    for action_id, action in actions.items():
        if action.get("deleted"):
            continue
        result.append({
            "id": action_id,
            "name": action.get("name"),
            "type": action.get("type"),
            "diff": action.get("diff"),
            "value": action.get("value"),
            "score": action.get("score"),
            "token_cost": int(action.get("token_cost") or 0),
        })
    result.sort(key=lambda a: (a.get("name") or "").upper())
    return result
