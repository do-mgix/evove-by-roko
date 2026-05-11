"""One-shot importer: ~/.local/share/evove/<username>/{user,logs,agenda,sequences,projects}.json → MySQL.

Idempotent: each user is upserted by username. Re-running replaces all
state for that user (actions/attributes/logs/agenda/projects/skills) with
what's in the JSON files. Useful while we still have JSON as the
authoritative source.

Usage:
    DATABASE_URL=mysql+pymysql://... python backend/scripts/migrate_json_to_db.py
    # or with default URL:
    python backend/scripts/migrate_json_to_db.py
    # filter to specific users:
    python backend/scripts/migrate_json_to_db.py super tete
"""
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.infrastructure.db import SessionLocal  # noqa: E402
from src.infrastructure import orm  # noqa: E402


_LOG_TS_FMT = "%d %m %Y : %H:%M:%S"
_DATE_FMT = "%d %m %Y"
_DATE_ISO = "%Y-%m-%d"


def _parse_date(s):
    if not s:
        return None
    for fmt in (_DATE_ISO, _DATE_FMT):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s).strip(), _LOG_TS_FMT)
    except ValueError:
        return None


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ! failed to read {path}: {e}")
        return None


def _evove_root() -> Path:
    override = os.environ.get("EVOVE_DATA_DIR")
    return Path(override) if override else Path.home() / ".local/share/evove"


def _upsert_user(session, username: str) -> orm.User:
    user = session.query(orm.User).filter_by(username=username).one_or_none()
    if user is None:
        user = orm.User(username=username, created_at=datetime.now())
        session.add(user)
        session.flush()
    return user


def _import_user_state(session, user: orm.User, data: dict):
    metadata = data.get("metadata") or {}
    state = session.query(orm.UserState).filter_by(user_id=user.id).one_or_none()
    if state is None:
        state = orm.UserState(user_id=user.id)
        session.add(state)
    state.score = float(data.get("score", 0) or 0)
    state.energy = int(metadata.get("energy", 1000) or 1000)
    state.tokens = int(metadata.get("tokens", 50) or 0)
    state.max_tokens = int(metadata.get("max_tokens", 50) or 50)
    state.build_points = int(metadata.get("build_points", 0) or 0)
    state.skill_points = int(metadata.get("skill_points", 0) or 0)
    state.stage = int(metadata.get("stage", 1) or 1)
    state.mode = str(metadata.get("mode", "progressive") or "progressive")
    state.days_until_next_checkpoint = int(metadata.get("days_until_next_checkpoint", 20) or 20)
    state.last_checkpoint_check = _parse_date(metadata.get("last_checkpoint_check"))
    state.last_token_refill = _parse_date(metadata.get("last_token_refill"))
    state.daily_refill = int(metadata.get("daily_refill", 20) or 20)


def _import_tutorial(session, user: orm.User, data: dict):
    metadata = data.get("metadata") or {}
    tutorial = metadata.get("tutorial") or {}
    session.query(orm.UserTutorial).filter_by(user_id=user.id).delete()
    for key, val in tutorial.items():
        if not isinstance(val, dict):
            continue
        session.add(orm.UserTutorial(
            user_id=user.id,
            key=str(key)[:64],
            status=bool(val.get("status")),
            priority=int(val.get("priority", 0) or 0),
        ))


def _import_actions(session, user: orm.User, data: dict):
    actions = (data.get("actions") or {}) or {}
    session.query(orm.Action).filter_by(user_id=user.id).delete()
    for aid, a in actions.items():
        session.add(orm.Action(
            user_id=user.id,
            action_id=str(aid),
            name=str(a.get("name", "") or ""),
            type=int(a.get("type", 0) or 0),
            diff=int(a.get("diff", 0) or 0),
            value=float(a.get("value", 0) or 0),
            max_value=float(a.get("max_value", 0) or 0),
            score=float(a.get("score", 0) or 0),
            deleted=bool(a.get("deleted", False)),
            logic_type=a.get("logic_type") or None,
            sub_logic_type=a.get("sub_logic_type") or None,
            token_cost=int(a.get("token_cost", 0) or 0),
        ))


def _import_attributes(session, user: orm.User, data: dict):
    attrs = (data.get("attributes") or {}) or {}
    # delete first → cascade clears attribute_actions
    session.query(orm.Attribute).filter_by(user_id=user.id).delete()
    session.flush()
    for aid, a in attrs.items():
        attr = orm.Attribute(
            user_id=user.id,
            attr_id=str(aid),
            name=str(a.get("name", "") or ""),
            total_score=float(a.get("total_score", 0) or 0),
        )
        session.add(attr)
        session.flush()
        seen = set()
        for action_id in (a.get("related_actions") or []):
            sid = str(action_id)
            if sid in seen:
                continue
            seen.add(sid)
            session.add(orm.AttributeAction(attribute_pk=attr.id, action_id=sid))


def _import_skills(session, user: orm.User, data: dict):
    skills = data.get("skills") or []
    session.query(orm.AcquiredSkill).filter_by(user_id=user.id).delete()
    for sid in skills:
        session.add(orm.AcquiredSkill(user_id=user.id, skill_id=str(sid)))


def _import_logs(session, user: orm.User, logs_payload):
    logs = logs_payload or []
    session.query(orm.Log).filter_by(user_id=user.id).delete()
    for log in logs:
        ts = _parse_dt(log.get("timestamp")) or datetime.now()
        coord = log.get("coord") or [0, 0]
        try:
            day_num = int(coord[0]) if len(coord) > 0 else 0
            order = int(coord[1]) if len(coord) > 1 else 0
        except (TypeError, ValueError):
            day_num, order = 0, 0
        try:
            log_id = int(log.get("id", 0) or 0)
        except (TypeError, ValueError):
            log_id = 0
        session.add(orm.Log(
            user_id=user.id,
            log_id=log_id,
            timestamp=ts,
            content=str(log.get("content", "") or ""),
            status=str(log.get("status", "[CLOUD]") or "[CLOUD]")[:32],
            xp=int(log.get("xp", 0) or 0),
            day_num=day_num,
            order_in_day=order,
        ))


def _import_agenda(session, user: orm.User, agenda_payload):
    items = (agenda_payload or {}).get("items", []) if isinstance(agenda_payload, dict) else []
    session.query(orm.AgendaItem).filter_by(user_id=user.id).delete()
    for it in items:
        session.add(orm.AgendaItem(
            user_id=user.id,
            item_id=str(it.get("id", "") or ""),
            day=it.get("day"),
            date=_parse_date(it.get("date")),
            start_time=it.get("start"),
            end_time=it.get("end"),
            label=str(it.get("label", "") or ""),
            label_kind=str(it.get("label_kind", "text") or "text")[:16],
            label_id=it.get("label_id") or None,
        ))


def _import_sequences_state(session, user: orm.User, sequences_payload):
    payload = sequences_payload or {}
    state = session.query(orm.SequencesState).filter_by(user_id=user.id).one_or_none()
    if state is None:
        state = orm.SequencesState(user_id=user.id)
        session.add(state)
    state.first_activity_date = _parse_date(payload.get("first_activity_date"))
    state.last_active_date = _parse_date(payload.get("last_active_date"))
    state.consecutive_days = int(payload.get("consecutive_days", 0) or 0)


def _import_projects(session, user: orm.User, projects_payload):
    items = projects_payload or []
    if isinstance(items, dict):
        items = items.get("items") or []
    # Cascade clears project_actions / project_attributes
    session.query(orm.Project).filter_by(user_id=user.id).delete()
    session.flush()
    for p in items:
        proj = orm.Project(
            user_id=user.id,
            project_id=str(p.get("id", "") or ""),
            name=str(p.get("name", "") or ""),
            deadline=_parse_date(p.get("deadline")),
            active=bool(p.get("active", True)),
            created_at=_parse_dt(p.get("created_at")) or datetime.now(),
        )
        session.add(proj)
        session.flush()
        seen_a = set()
        for aid in (p.get("related_actions") or []):
            sid = str(aid)
            if sid in seen_a:
                continue
            seen_a.add(sid)
            session.add(orm.ProjectAction(project_pk=proj.id, action_id=sid))
        seen_at = set()
        for attr_id in (p.get("related_attributes") or []):
            sid = str(attr_id)
            if sid in seen_at:
                continue
            seen_at.add(sid)
            session.add(orm.ProjectAttribute(project_pk=proj.id, attr_id=sid))


def import_user(session, root: Path, username: str):
    udir = root / username
    user_data = _read_json(udir / "user.json")
    if not user_data:
        print(f"  skipping {username} (no user.json)")
        return
    user = _upsert_user(session, username)
    _import_user_state(session, user, user_data)
    _import_tutorial(session, user, user_data)
    _import_actions(session, user, user_data)
    _import_attributes(session, user, user_data)
    _import_skills(session, user, user_data)
    _import_logs(session, user, _read_json(udir / "logs.json") or [])
    _import_agenda(session, user, _read_json(udir / "agenda.json") or {})
    _import_sequences_state(session, user, _read_json(udir / "sequences.json") or {})
    _import_projects(session, user, _read_json(udir / "projects.json") or [])
    print(f"  imported {username}")


def main(filter_users: list[str] | None = None):
    root = _evove_root()
    if not root.exists():
        print(f"no data dir at {root}")
        return
    targets = []
    for entry in sorted(os.scandir(root), key=lambda e: e.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if filter_users and entry.name not in filter_users:
            continue
        if not (Path(entry.path) / "user.json").exists():
            continue
        targets.append(entry.name)
    if not targets:
        print("no users to import")
        return
    print(f"importing {len(targets)} user(s) from {root}")
    session = SessionLocal()
    try:
        for username in targets:
            import_user(session, root, username)
        session.commit()
        print("done")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main(sys.argv[1:] or None)
