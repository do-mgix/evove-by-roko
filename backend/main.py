import json
import os
import re
from datetime import datetime
from pathlib import Path

import roman
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

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
    return Path(os.environ.get("EVOVE_DATA_DIR", Path.home() / ".local" / "share" / "evove"))


def _resolve_username(x_evove_username: str | None) -> str:
    name = (x_evove_username or os.environ.get("EVOVE_USERNAME") or "default").strip()
    if not _USERNAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid username")
    return name


def _data_dir(username: str | None = None) -> Path:
    return _root_dir() / _resolve_username(username)


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


def _load_user_json(username: str) -> dict:
    path = _data_dir(username) / "user.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"user.json not found at {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if _apply_initial_grants(data):
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return data


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
    path = _data_dir(username) / "sequences.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_sequences(username: str, data: dict):
    path = _data_dir(username) / "sequences.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


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
    data = _load_user_json(username)
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
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir() and (p / "user.json").exists()])


@app.post("/users")
def create_user(payload: dict):
    name = (payload or {}).get("name", "").strip()
    if not _USERNAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid username (a-z, 0-9, _ -, max 24)")
    user_dir = _root_dir() / name
    user_file = user_dir / "user.json"
    if user_file.exists():
        raise HTTPException(status_code=409, detail=f"user '{name}' already exists")
    user_dir.mkdir(parents=True, exist_ok=True)
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
    with user_file.open("w", encoding="utf-8") as f:
        json.dump(initial, f, indent=2)

    # Initialize sequences: first activity date = today, consecutive days = 1
    seq_path = user_dir / "sequences.json"
    today_seq = datetime.now().strftime("%d %m %Y")
    seq_data = {
        "first_activity_date": today_seq,
        "last_active_date": today_seq,
        "consecutive_days": 1,
        "sequences": [],
    }
    with seq_path.open("w", encoding="utf-8") as f:
        json.dump(seq_data, f, indent=2)
    return {"name": name}


@app.get("/user")
def user_state(x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    data = _load_user_json(username)
    metadata = data.get("metadata", {}) or {}
    xp = int(round(float(data.get("score", 0) or 0)))
    progression = _progression_state(xp)
    attributes = data.get("attributes", {}) or {}
    active_attrs = [a for a in attributes.values() if not a.get("deleted")]
    bonuses = _skill_bonuses(data)
    base_max_tokens = int(metadata.get("max_tokens", 50) or 50)
    base_max_energy = 1000
    seq = _ensure_sequences(username)
    return {
        "username": metadata.get("username") or data.get("username"),
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
_LEGACY_AGENDA_FILE = Path(os.environ.get("EVOVE_AGENDA_FILE", Path.home() / "journal" / "evove-agenda"))


class Agenda:
    """Per-user agenda persisted at <data_dir>/agenda.json."""

    def __init__(self, username: str):
        self.username = username
        self.path = _data_dir(username) / "agenda.json"
        self.items: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    self.items = (json.load(f) or {}).get("items", [])
                return
            except Exception:
                self.items = []
        self.items = []
        self._save()

    def _migrate_legacy(self):
        if not _LEGACY_AGENDA_FILE.exists():
            return
        items: list[dict] = []
        next_id = 1
        current_day = None
        try:
            with _LEGACY_AGENDA_FILE.open("r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        continue
                    upper = line.upper()
                    if upper in _DAY_NAMES:
                        current_day = upper
                        continue
                    if current_day is None or "-" not in line:
                        continue
                    colon = line.find(":", line.index("-"))
                    if colon == -1:
                        continue
                    time_part = line[:colon].strip()
                    label = line[colon + 1:].strip()
                    if "-" not in time_part:
                        continue
                    start, end = (s.strip() for s in time_part.split("-", 1))
                    items.append({
                        "id": f"ag_{next_id:04d}",
                        "day": current_day,
                        "start": start,
                        "end": end,
                        "label": label,
                        "label_kind": "text",
                        "label_id": None,
                    })
                    next_id += 1
        except OSError:
            return
        self.items = items

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump({"items": self.items}, f, indent=2)

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

    def for_day(self, day_name: str) -> list[dict]:
        return [it for it in self.items if it.get("day") == day_name or it.get("day") == "*"]


class Projects:
    """Per-user projects/goals at <data_dir>/projects.json."""

    def __init__(self, username: str):
        self.username = username
        self.path = _data_dir(username) / "projects.json"
        self.items: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    self.items = (json.load(f) or {}).get("items", [])
                return
            except Exception:
                self.items = []
        self.items = []
        self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump({"items": self.items}, f, indent=2)

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
    logs_path = _data_dir(username) / "logs.json"
    by_date: dict[str, int] = {}
    if logs_path.exists() and first_dt:
        try:
            with logs_path.open("r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
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
    logs_path = _data_dir(username) / "logs.json"
    if not logs_path.exists():
        return {"date": date, "day": target_day, "logs": []}
    with logs_path.open("r", encoding="utf-8") as f:
        logs = json.load(f)
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


@app.delete("/agenda/{item_id}")
def agenda_remove(item_id: str, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    ok = Agenda(username).remove(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True}
_PACKAGES_DIR = Path(__file__).parent / "data" / "packages"
_SKILLS_FILE = Path(__file__).parent / "data" / "skills.json"


def _load_skill_tree():
    if not _SKILLS_FILE.exists():
        return {"nodes": []}
    try:
        with _SKILLS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"nodes": []}


def _skill_bonuses(data: dict) -> dict:
    """Aggregates skill effects from data['skills'] (list of acquired ids)."""
    bonuses = {"max_energy": 0, "max_tokens": 0, "xp_multiplier": 1.0, "points_multiplier": 1.0}
    acquired = set(data.get("skills") or [])
    if not acquired:
        return bonuses
    by_id = {n["id"]: n for n in _load_skill_tree().get("nodes", [])}
    for sid in acquired:
        node = by_id.get(sid)
        if not node or not node.get("effect"):
            continue
        eff = node["effect"]
        t = eff.get("type")
        v = eff.get("value", 0)
        if t == "max_energy":
            bonuses["max_energy"] += v
        elif t == "max_tokens":
            bonuses["max_tokens"] += v
        elif t == "xp_multiplier":
            bonuses["xp_multiplier"] *= v
        elif t == "points_multiplier":
            bonuses["points_multiplier"] *= v
    return bonuses


@app.get("/skills/tree")
def skills_tree(x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    data = _load_user_json(username)
    tree = _load_skill_tree()
    acquired = set(data.get("skills") or [])
    return {
        "nodes": tree.get("nodes", []),
        "acquired": sorted(acquired),
        "skill_points": int((data.get("metadata") or {}).get("skill_points", 0) or 0),
        "bonuses": _skill_bonuses(data),
    }


@app.post("/skills/{skill_id}/acquire")
def acquire_skill(skill_id: str, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    user_path = _data_dir(username) / "user.json"
    if not user_path.exists():
        raise HTTPException(status_code=404, detail="user.json not found")
    with user_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    tree = _load_skill_tree()
    by_id = {n["id"]: n for n in tree.get("nodes", [])}
    node = by_id.get(skill_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"skill '{skill_id}' not found")
    acquired = set(data.get("skills") or [])
    if skill_id in acquired:
        raise HTTPException(status_code=409, detail="already acquired")
    parent = node.get("parent")
    if parent and parent not in acquired and parent != "root":
        raise HTTPException(status_code=400, detail=f"requires parent '{parent}'")
    metadata = data.setdefault("metadata", {})
    sp = int(metadata.get("skill_points", 0) or 0)
    cost = int(node.get("cost", 0))
    if sp < cost:
        raise HTTPException(status_code=400, detail=f"need {cost} sp (have {sp})")
    acquired.add(skill_id)
    data["skills"] = sorted(acquired)
    metadata["skill_points"] = sp - cost
    with user_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return {"acquired": data["skills"], "skill_points": metadata["skill_points"], "bonuses": _skill_bonuses(data)}


def _load_packages():
    if not _PACKAGES_DIR.is_dir():
        return []
    result = []
    for path in sorted(_PACKAGES_DIR.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                result.append(json.load(f))
        except Exception:
            continue
    return result


def _lookup_token_cost(action_name: str) -> int:
    if not action_name:
        return 0
    target = action_name.strip().upper()
    for pkg in _load_packages():
        for a in pkg.get("actions", []) or []:
            if str(a.get("name", "")).strip().upper() == target:
                return int(a.get("token_cost", 0) or 0)
    return 0


@app.get("/shop/packages")
def shop_packages():
    return _load_packages()


@app.post("/shop/actions/buy")
def buy_action(payload: dict, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    user_path = _data_dir(username) / "user.json"
    if not user_path.exists():
        raise HTTPException(status_code=404, detail="user.json not found")
    with user_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    name = (payload or {}).get("name", "").strip().upper()
    attr_name = (payload or {}).get("attribute", "").strip()
    if not name or not attr_name:
        raise HTTPException(status_code=400, detail="missing name or attribute")

    pkg = next((p for p in _load_packages() if p.get("attribute") == attr_name), None)
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

    # Ensure attribute exists; link the new action to it
    attributes = data.setdefault("attributes", {})
    target_attr = next(
        (a for a in attributes.values() if str(a.get("name", "")).strip().lower() == attr_name.lower()),
        None,
    )
    if target_attr is None:
        attr_ids = [int(aid) for aid in attributes.keys() if aid.isdigit()]
        new_attr_id = str((max(attr_ids) + 1) if attr_ids else 801)
        target_attr = {
            "id": new_attr_id,
            "name": attr_name,
            "related_actions": [],
            "children": [],
            "parent": [],
            "total_score": 0,
        }
        attributes[new_attr_id] = target_attr
    related = target_attr.setdefault("related_actions", [])
    if new_id not in related:
        related.append(new_id)

    metadata["build_points"] = bp - cost

    with user_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return {"id": new_id, "name": name, "build_points": metadata["build_points"]}


def _day_for(username: str, date_obj):
    data = _ensure_sequences(username)
    first = data.get("first_activity_date")
    if not first:
        return 0
    try:
        first_dt = datetime.strptime(first, "%d %m %Y").date()
        return (date_obj - first_dt).days + 1
    except Exception:
        return 0


@app.post("/logs/reorder")
def reorder_logs(payload: dict, x_evove_username: str | None = Header(None)):
    """Body: {day: int, ids: [int, ...]}. Sets coord[1] of each id to its new 1-based index within day."""
    username = _resolve_username(x_evove_username)
    day = int(payload.get("day", -1))
    ids = payload.get("ids") or []
    if day < 0 or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="invalid payload")
    path = _data_dir(username) / "logs.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="logs.json not found")
    with path.open("r", encoding="utf-8") as f:
        logs = json.load(f)
    by_id = {int(l.get("id")): l for l in logs if l.get("id") is not None}
    for new_idx, lid in enumerate(ids, start=1):
        log = by_id.get(int(lid))
        if not log:
            continue
        coord = log.get("coord") or [day, 0]
        if int(coord[0]) != day:
            continue
        log["coord"] = [day, new_idx]
    with path.open("w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4)
    return {"ok": True, "count": len(ids)}


@app.get("/logs")
def list_logs(offset: int = 0, x_evove_username: str | None = Header(None)):
    """offset: 0 = today, -1 = yesterday, +1 = tomorrow."""
    from datetime import timedelta
    username = _resolve_username(x_evove_username)
    path = _data_dir(username) / "logs.json"
    target_date = (datetime.now() + timedelta(days=offset)).date()
    target_day = _day_for(username, target_date)
    if not path.exists():
        return {"day": target_day, "offset": offset, "date": target_date.isoformat(), "logs": []}
    with path.open("r", encoding="utf-8") as f:
        logs = json.load(f)
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
    data = _load_user_json(_resolve_username(x_evove_username))
    attributes = data.get("attributes", {}) or {}
    result = []
    for attr_id, attr in attributes.items():
        if attr.get("deleted"):
            continue
        result.append({
            "id": attr_id,
            "name": attr.get("name"),
            "total_score": int(round(float(attr.get("total_score", 0) or 0))),
            "related_actions_count": len(attr.get("related_actions") or []),
        })
    result.sort(key=lambda a: a.get("total_score", 0), reverse=True)
    return result


_DIFF_MULTIPLIER = {0: 1, 1: 30, 2: 120, 3: 400, 4: 1000, 5: 2500}
_TYPE_FACTOR = {0: 3, 1: 1, 2: 1, 3: 2, 4: 3, 5: 0.1, 6: 0.5, 7: 0.3, 8: 0}
_LOG_ID_PREFIX = 73
_LOG_ID_WIDTH = 4


def _is_action_in_today_agenda(username: str, action_name: str, user_data: dict) -> bool:
    """True if action name matches any of today's agenda labels, OR if any agenda label matches an attribute that contains this action."""
    if not action_name:
        return False
    name_norm = " ".join(str(action_name).strip().upper().split())
    if not name_norm:
        return False
    day_name = _DAY_NAMES[datetime.now().weekday()]
    items = Agenda(username).for_day(day_name)
    labels = {" ".join(str(it.get("label", "")).strip().upper().split()) for it in items}
    labels.discard("")
    if name_norm in labels:
        return True
    # Match via attribute name → related_actions
    attributes = (user_data.get("attributes") or {})
    # Find action_id of given name
    action_id = None
    for aid, a in (user_data.get("actions") or {}).items():
        if str(a.get("name", "")).strip().upper() == name_norm:
            action_id = str(aid)
            break
    if not action_id:
        return False
    for attr in attributes.values():
        attr_label = " ".join(str(attr.get("name", "")).strip().upper().split())
        if attr_label in labels and action_id in (attr.get("related_actions") or []):
            return True
    return False


def _action_score(action: dict) -> float:
    return float(action.get("value", 0) or 0) * _TYPE_FACTOR.get(int(action.get("type", 0)), 0) * _DIFF_MULTIPLIER.get(int(action.get("diff", 0)), 0)


def _append_log(username: str, content: str, xp: int) -> dict | None:
    path = _data_dir(username) / "logs.json"
    logs = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
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
    logs.append(entry)
    with path.open("w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4)
    return entry


@app.post("/actions/{action_id}/act")
def act_on_action(action_id: str, payload: dict | None = None, x_evove_username: str | None = Header(None)):
    username = _resolve_username(x_evove_username)
    user_path = _data_dir(username) / "user.json"
    if not user_path.exists():
        raise HTTPException(status_code=404, detail="user.json not found")
    with user_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    action = (data.get("actions") or {}).get(action_id)
    if not action or action.get("deleted"):
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")

    delta = 1
    note = None
    if payload:
        if "value" in payload and payload["value"] is not None:
            try:
                delta = int(payload["value"])
            except (TypeError, ValueError):
                delta = 1
        if "note" in payload and payload["note"]:
            note_text = str(payload["note"]).strip()
            if note_text:
                # Numeric notes act as the delta value
                try:
                    delta = int(note_text)
                except ValueError:
                    note = note_text

    metadata = data.setdefault("metadata", {})

    # Token cost: actions of leisure-style cost tokens. Allows negative balance.
    per_unit_cost = action.get("token_cost")
    if per_unit_cost is None:
        per_unit_cost = _lookup_token_cost(action.get("name", ""))
        if per_unit_cost > 0:
            action["token_cost"] = per_unit_cost
    per_unit_cost = int(per_unit_cost or 0)
    token_cost = per_unit_cost * max(1, abs(delta))
    if token_cost > 0:
        cur_tokens = int(metadata.get("tokens", 0) or 0)
        metadata["tokens"] = cur_tokens - token_cost

    old_score = _action_score(action)
    action["value"] = float(action.get("value", 0) or 0) + delta
    if action["value"] > float(action.get("max_value", 0) or 0):
        action["max_value"] = action["value"]
    new_score = _action_score(action)
    action["score"] = new_score

    raw_diff = new_score - old_score
    bonuses = _skill_bonuses(data)
    score_diff = raw_diff * bonuses["xp_multiplier"]
    data["score"] = float(data.get("score", 0) or 0) + score_diff
    metadata["score"] = data["score"]

    # Energy penalty when acting outside today's agenda.
    in_agenda = _is_action_in_today_agenda(username, action.get("name", ""), data)
    if not in_agenda:
        cur_energy = int(metadata.get("energy", 0) or 0)
        metadata["energy"] = max(0, cur_energy - 10)

    # Update related attribute total_score
    for attr in (data.get("attributes") or {}).values():
        if action_id in (attr.get("related_actions") or []):
            attr["total_score"] = float(attr.get("total_score", 0) or 0) + score_diff

    with user_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    _record_activity(username)
    if note:
        log_content = f"{action.get('name', '')} : {note}".strip()
    else:
        log_content = f"{int(delta)} X {action.get('name', '')}".strip()
    log_entry = _append_log(username, log_content, int(round(score_diff)))

    return {
        "id": action_id,
        "name": action.get("name"),
        "value": action["value"],
        "score": new_score,
        "score_diff": score_diff,
        "user_score": data["score"],
        "log": log_entry,
    }


@app.get("/actions")
def list_actions(x_evove_username: str | None = Header(None)):
    data = _load_user_json(_resolve_username(x_evove_username))
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
        })
    result.sort(key=lambda a: (a.get("name") or "").upper())
    return result
