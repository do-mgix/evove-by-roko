"""DB repositories. Public functions accept/return dicts/lists in the same
shape the JSON files used so handlers don't need to change their internals.

Each public function manages its own session and commits/closes. For now
that is fine — endpoints touch one user-aggregate at a time.
"""
from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from src.infrastructure.db import SessionLocal
from src.infrastructure import orm

_LOG_TS_FMT = "%d %m %Y : %H:%M:%S"


# ---------- helpers ----------

def _get_user(session: Session, username: str) -> orm.User | None:
    return session.execute(select(orm.User).where(orm.User.username == username)).scalar_one_or_none()


def _ensure_user(session: Session, username: str) -> orm.User:
    user = _get_user(session, username)
    if user is None:
        user = orm.User(username=username, created_at=datetime.now())
        session.add(user)
        session.flush()
    return user


def _parse_date(s):
    if not s:
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    for fmt in ("%Y-%m-%d", "%d %m %Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_log_dt(s):
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return datetime.strptime(str(s).strip(), _LOG_TS_FMT)
    except ValueError:
        return None


def _fmt_log_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime(_LOG_TS_FMT)


def _date_iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


# ---------- helpers (shared with CLI) ----------

def day_for_user(username: str, date_obj) -> int:
    """Return the day number for this user given a date (1-indexed from first_activity_date)."""
    data = load_sequences(username)
    first = data.get("first_activity_date")
    if not first:
        return 0
    try:
        if hasattr(date_obj, "date"):
            date_obj = date_obj.date()
        first_dt = datetime.strptime(str(first), "%d %m %Y").date()
        return (date_obj - first_dt).days + 1
    except Exception:
        return 0


# ---------- users ----------

def list_usernames() -> list[str]:
    s = SessionLocal()
    try:
        return [u for (u,) in s.execute(select(orm.User.username).order_by(orm.User.username)).all()]
    finally:
        s.close()


def user_exists(username: str) -> bool:
    s = SessionLocal()
    try:
        return _get_user(s, username) is not None
    finally:
        s.close()


def delete_user(username: str) -> bool:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return False
        s.delete(u)
        s.commit()
        return True
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- user.json shape ----------

def load_user_dict(username: str) -> dict | None:
    """Return user.json-shaped dict, or None if user not in DB."""
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return None
        return _user_to_dict(s, u)
    finally:
        s.close()


def _user_to_dict(s: Session, u: orm.User) -> dict:
    state = s.execute(select(orm.UserState).where(orm.UserState.user_id == u.id)).scalar_one_or_none()
    tutorial_rows = s.execute(select(orm.UserTutorial).where(orm.UserTutorial.user_id == u.id)).scalars().all()
    actions_rows = s.execute(select(orm.Action).where(orm.Action.user_id == u.id)).scalars().all()
    attrs_rows = s.execute(select(orm.Attribute).where(orm.Attribute.user_id == u.id)).scalars().all()
    skills_rows = s.execute(select(orm.AcquiredSkill).where(orm.AcquiredSkill.user_id == u.id)).scalars().all()

    actions: dict = {}
    for a in actions_rows:
        actions[a.action_id] = {
            "id": a.action_id,
            "name": a.name,
            "type": a.type,
            "diff": a.diff,
            "value": a.value,
            "max_value": a.max_value,
            "score": a.score,
            "deleted": a.deleted,
            "logic_type": a.logic_type,
            "sub_logic_type": a.sub_logic_type,
            "token_cost": a.token_cost,
            "token_gain": a.token_gain,
        }

    attributes: dict = {}
    for at in attrs_rows:
        related = [r.action_id for r in s.execute(
            select(orm.AttributeAction).where(orm.AttributeAction.attribute_pk == at.id)
        ).scalars().all()]
        attributes[at.attr_id] = {
            "id": at.attr_id,
            "name": at.name,
            "related_actions": related,
            "children": [],
            "parent": [],
            "total_score": at.total_score,
        }

    metadata: dict = {
        "username": u.username,
        "mode": state.mode if state else "progressive",
        "energy": state.energy if state else 1000,
        "score": state.score if state else 0.0,
        "stage": state.stage if state else 1,
        "skill_points": state.skill_points if state else 0,
        "build_points": state.build_points if state else 0,
        "tokens": state.tokens if state else 0,
        "max_tokens": state.max_tokens if state else 100,
        "days_until_next_checkpoint": state.days_until_next_checkpoint if state else 20,
        "last_checkpoint_check": _date_iso(state.last_checkpoint_check) if state else None,
        "last_decay_check": _date_iso(state.last_decay_check) if state else None,
        "date": _date_iso(state.date) if state else None,
        "tutorial": {
            t.key: {"status": t.status, "priority": t.priority} for t in tutorial_rows
        },
    }

    return {
        "username": u.username,
        "score": state.score if state else 0.0,
        "value": 0,
        "attributes": attributes,
        "actions": actions,
        "parameters": {},
        "statuses": {},
        "shop_items": {},
        "shop_action_links": {},
        "tags": {},
        "action_tags": {},
        "param_tags": {},
        "logic_types": {},
        "sublogic_types": {},
        "skills": [s_.skill_id for s_ in skills_rows],
        "metadata": metadata,
    }


def save_user_dict(username: str, data: dict) -> None:
    """Replace all user-aggregate state with `data` (user.json-shaped)."""
    s = SessionLocal()
    try:
        u = _ensure_user(s, username)
        _write_state(s, u, data)
        _write_tutorial(s, u, data)
        _write_actions(s, u, data)
        _write_attributes(s, u, data)
        _write_skills(s, u, data)
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _write_state(s: Session, u: orm.User, data: dict):
    md = data.get("metadata") or {}
    state = s.execute(select(orm.UserState).where(orm.UserState.user_id == u.id)).scalar_one_or_none()
    if state is None:
        state = orm.UserState(user_id=u.id)
        s.add(state)
    state.score = float(data.get("score", 0) or 0)
    state.energy = int(md.get("energy", 1000) or 0)
    state.tokens = int(md.get("tokens", 50) or 0)
    state.max_tokens = int(md.get("max_tokens", 100) or 100)
    state.build_points = int(md.get("build_points", 0) or 0)
    state.skill_points = int(md.get("skill_points", 0) or 0)
    state.stage = int(md.get("stage", 1) or 1)
    state.mode = str(md.get("mode", "progressive") or "progressive")
    state.date = _parse_date(md.get("date")) or state.date
    state.days_until_next_checkpoint = int(md.get("days_until_next_checkpoint", 20) or 20)
    state.last_checkpoint_check = _parse_date(md.get("last_checkpoint_check"))
    state.last_decay_check = _parse_date(md.get("last_decay_check"))


def _write_tutorial(s: Session, u: orm.User, data: dict):
    md = data.get("metadata") or {}
    tutorial = md.get("tutorial") or {}
    s.query(orm.UserTutorial).filter_by(user_id=u.id).delete()
    s.flush()
    for key, val in tutorial.items():
        if not isinstance(val, dict):
            continue
        s.add(orm.UserTutorial(
            user_id=u.id,
            key=str(key)[:64],
            status=bool(val.get("status")),
            priority=int(val.get("priority", 0) or 0),
        ))


def _write_actions(s: Session, u: orm.User, data: dict):
    actions = (data.get("actions") or {}) or {}
    s.query(orm.Action).filter_by(user_id=u.id).delete()
    s.flush()
    for aid, a in actions.items():
        s.add(orm.Action(
            user_id=u.id,
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
            token_gain=int(a.get("token_gain", 0) or 0),
        ))


def _write_attributes(s: Session, u: orm.User, data: dict):
    attrs = (data.get("attributes") or {}) or {}
    s.query(orm.Attribute).filter_by(user_id=u.id).delete()
    s.flush()
    for aid, a in attrs.items():
        attr = orm.Attribute(
            user_id=u.id,
            attr_id=str(aid),
            name=str(a.get("name", "") or ""),
            total_score=float(a.get("total_score", 0) or 0),
        )
        s.add(attr)
        s.flush()
        seen = set()
        for action_id in (a.get("related_actions") or []):
            sid = str(action_id)
            if sid in seen:
                continue
            seen.add(sid)
            s.add(orm.AttributeAction(attribute_pk=attr.id, action_id=sid))


def _write_skills(s: Session, u: orm.User, data: dict):
    skills = data.get("skills") or []
    s.query(orm.AcquiredSkill).filter_by(user_id=u.id).delete()
    s.flush()
    for sid in skills:
        s.add(orm.AcquiredSkill(user_id=u.id, skill_id=str(sid)))


# ---------- logs ----------

def load_logs(username: str) -> list[dict]:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return []
        rows = s.execute(
            select(orm.Log).where(orm.Log.user_id == u.id).order_by(orm.Log.timestamp.asc(), orm.Log.id.asc())
        ).scalars().all()
        return [_log_to_dict(r) for r in rows]
    finally:
        s.close()


def _log_to_dict(r: orm.Log) -> dict:
    return {
        "id": r.log_id,
        "timestamp": _fmt_log_dt(r.timestamp),
        "content": r.content,
        "status": r.status,
        "xp": r.xp,
        "tokens": r.tokens,
        "coord": [r.day_num, r.order_in_day],
    }


def save_logs(username: str, logs: list[dict]) -> None:
    """Replace all logs for the user."""
    s = SessionLocal()
    try:
        u = _ensure_user(s, username)
        s.query(orm.Log).filter_by(user_id=u.id).delete()
        s.flush()
        for log in logs:
            ts = _parse_log_dt(log.get("timestamp")) or datetime.now()
            coord = log.get("coord") or [0, 0]
            try:
                day = int(coord[0]) if len(coord) > 0 else 0
                order = int(coord[1]) if len(coord) > 1 else 0
            except (TypeError, ValueError):
                day, order = 0, 0
            try:
                lid = int(log.get("id", 0) or 0)
            except (TypeError, ValueError):
                lid = 0
            s.add(orm.Log(
                user_id=u.id,
                log_id=lid,
                timestamp=ts,
                content=str(log.get("content", "") or ""),
                status=str(log.get("status", "[CLOUD]") or "[CLOUD]")[:32],
                xp=int(log.get("xp", 0) or 0),
                tokens=int(log.get("tokens", 0) or 0),
                day_num=day,
                order_in_day=order,
            ))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def append_log(username: str, log: dict) -> None:
    """Insert a single log row. Caller already populated id/coord."""
    s = SessionLocal()
    try:
        u = _ensure_user(s, username)
        ts = _parse_log_dt(log.get("timestamp")) or datetime.now()
        coord = log.get("coord") or [0, 0]
        try:
            day = int(coord[0]) if len(coord) > 0 else 0
            order = int(coord[1]) if len(coord) > 1 else 0
        except (TypeError, ValueError):
            day, order = 0, 0
        try:
            lid = int(log.get("id", 0) or 0)
        except (TypeError, ValueError):
            lid = 0
        s.add(orm.Log(
            user_id=u.id,
            log_id=lid,
            timestamp=ts,
            content=str(log.get("content", "") or ""),
            status=str(log.get("status", "[CLOUD]") or "[CLOUD]")[:32],
            xp=int(log.get("xp", 0) or 0),
            tokens=int(log.get("tokens", 0) or 0),
            day_num=day,
            order_in_day=order,
        ))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def delete_log(username: str, log_id: int) -> dict | None:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return None
        row = s.execute(
            select(orm.Log).where(orm.Log.user_id == u.id, orm.Log.log_id == int(log_id))
        ).scalar_one_or_none()
        if not row:
            return None
        snap = _log_to_dict(row)
        s.delete(row)
        s.commit()
        return snap
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def update_log_content(username: str, log_id: int, content: str) -> dict | None:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return None
        row = s.execute(
            select(orm.Log).where(orm.Log.user_id == u.id, orm.Log.log_id == int(log_id))
        ).scalar_one_or_none()
        if not row:
            return None
        row.content = str(content)
        s.commit()
        return _log_to_dict(row)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def shift_log_day(username: str, log_id: int, delta: int) -> dict | None:
    """Move a log's day_num by `delta` days and append it to the target day's order."""
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return None
        row = s.execute(
            select(orm.Log).where(orm.Log.user_id == u.id, orm.Log.log_id == int(log_id))
        ).scalar_one_or_none()
        if not row:
            return None
        new_day = row.day_num + int(delta)
        if new_day < 0:
            return None
        max_order = s.execute(
            select(func.max(orm.Log.order_in_day))
            .where(orm.Log.user_id == u.id, orm.Log.day_num == new_day)
        ).scalar() or 0
        new_order = max_order + 1
        # Use a direct UPDATE to avoid identity-map stale-read with expire_on_commit=False.
        s.execute(
            update(orm.Log)
            .where(orm.Log.user_id == u.id, orm.Log.log_id == int(log_id))
            .values(day_num=new_day, order_in_day=new_order)
            .execution_options(synchronize_session=False)
        )
        s.commit()
        # Build the result from already-known values; no re-read needed.
        return {
            "id": row.log_id,
            "timestamp": _fmt_log_dt(row.timestamp),
            "content": row.content,
            "status": row.status,
            "xp": row.xp,
            "coord": [new_day, new_order],
        }
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- agenda ----------

def load_agenda_items(username: str) -> list[dict]:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return []
        rows = s.execute(
            select(orm.AgendaItem).where(orm.AgendaItem.user_id == u.id).order_by(orm.AgendaItem.id.asc())
        ).scalars().all()
        return [_agenda_to_dict(r) for r in rows]
    finally:
        s.close()


def _agenda_to_dict(r: orm.AgendaItem) -> dict:
    return {
        "id": r.item_id,
        "day": r.day,
        "date": _date_iso(r.date),
        "start": r.start_time,
        "end": r.end_time,
        "label": r.label,
        "label_kind": r.label_kind,
        "label_id": r.label_id,
    }


def save_agenda_items(username: str, items: list[dict]) -> None:
    s = SessionLocal()
    try:
        u = _ensure_user(s, username)
        s.query(orm.AgendaItem).filter_by(user_id=u.id).delete()
        s.flush()
        for it in items:
            s.add(orm.AgendaItem(
                user_id=u.id,
                item_id=str(it.get("id", "") or ""),
                day=it.get("day"),
                date=_parse_date(it.get("date")),
                start_time=it.get("start"),
                end_time=it.get("end"),
                label=str(it.get("label", "") or ""),
                label_kind=str(it.get("label_kind", "text") or "text")[:16],
                label_id=it.get("label_id") or None,
            ))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- projects ----------

def load_projects(username: str) -> list[dict]:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return []
        rows = s.execute(
            select(orm.Project).where(orm.Project.user_id == u.id).order_by(orm.Project.id.asc())
        ).scalars().all()
        out = []
        for p in rows:
            actions = [r.action_id for r in s.execute(
                select(orm.ProjectAction).where(orm.ProjectAction.project_pk == p.id)
            ).scalars().all()]
            attrs = [r.attr_id for r in s.execute(
                select(orm.ProjectAttribute).where(orm.ProjectAttribute.project_pk == p.id)
            ).scalars().all()]
            out.append({
                "id": p.project_id,
                "name": p.name,
                "deadline": _date_iso(p.deadline),
                "active": p.active,
                "related_actions": actions,
                "related_attributes": attrs,
                "created_at": _fmt_log_dt(p.created_at),
            })
        return out
    finally:
        s.close()


def save_projects(username: str, items: list[dict]) -> None:
    s = SessionLocal()
    try:
        u = _ensure_user(s, username)
        s.query(orm.Project).filter_by(user_id=u.id).delete()
        s.flush()
        for p in items:
            proj = orm.Project(
                user_id=u.id,
                project_id=str(p.get("id", "") or ""),
                name=str(p.get("name", "") or ""),
                deadline=_parse_date(p.get("deadline")),
                active=bool(p.get("active", True)),
                created_at=_parse_log_dt(p.get("created_at")) or datetime.now(),
            )
            s.add(proj)
            s.flush()
            seen_a = set()
            for aid in (p.get("related_actions") or []):
                sid = str(aid)
                if sid in seen_a:
                    continue
                seen_a.add(sid)
                s.add(orm.ProjectAction(project_pk=proj.id, action_id=sid))
            seen_at = set()
            for attr_id in (p.get("related_attributes") or []):
                sid = str(attr_id)
                if sid in seen_at:
                    continue
                seen_at.add(sid)
                s.add(orm.ProjectAttribute(project_pk=proj.id, attr_id=sid))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- sequences state ----------

def load_sequences(username: str) -> dict:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return {}
        st = s.execute(
            select(orm.SequencesState).where(orm.SequencesState.user_id == u.id)
        ).scalar_one_or_none()
        if not st:
            return {}
        return {
            "first_activity_date": st.first_activity_date.strftime("%d %m %Y") if st.first_activity_date else None,
            "last_active_date": st.last_active_date.strftime("%d %m %Y") if st.last_active_date else None,
            "consecutive_days": st.consecutive_days,
            "sequences": [],
        }
    finally:
        s.close()


def save_sequences(username: str, data: dict) -> None:
    s = SessionLocal()
    try:
        u = _ensure_user(s, username)
        st = s.execute(
            select(orm.SequencesState).where(orm.SequencesState.user_id == u.id)
        ).scalar_one_or_none()
        if st is None:
            st = orm.SequencesState(user_id=u.id)
            s.add(st)
        st.first_activity_date = _parse_date(data.get("first_activity_date"))
        st.last_active_date = _parse_date(data.get("last_active_date"))
        st.consecutive_days = int(data.get("consecutive_days", 0) or 0)
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- create user ----------

def create_user(username: str, initial_user: dict, initial_sequences: dict | None = None,
                password_hash: str = "") -> None:
    s = SessionLocal()
    try:
        if _get_user(s, username):
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="user already exists")
        u = orm.User(username=username, password_hash=password_hash, created_at=datetime.now())
        s.add(u)
        s.flush()
        _write_state(s, u, initial_user)
        _write_tutorial(s, u, initial_user)
        _write_actions(s, u, initial_user)
        _write_attributes(s, u, initial_user)
        _write_skills(s, u, initial_user)
        if initial_sequences:
            st = orm.SequencesState(user_id=u.id)
            s.add(st)
            st.first_activity_date = _parse_date(initial_sequences.get("first_activity_date"))
            st.last_active_date = _parse_date(initial_sequences.get("last_active_date"))
            st.consecutive_days = int(initial_sequences.get("consecutive_days", 0) or 0)
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- auth ----------

def get_password_hash(username: str) -> str | None:
    """Stored hash for a username, or None when there is no such user."""
    s = SessionLocal()
    try:
        return s.execute(
            select(orm.User.password_hash).where(orm.User.username == username)
        ).scalar_one_or_none()
    finally:
        s.close()


def set_password_hash(username: str, password_hash: str) -> bool:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return False
        u.password_hash = password_hash
        s.commit()
        return True
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def create_session(username: str, token_hash: str, expires_at: datetime) -> bool:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return False
        now = datetime.now()
        s.add(orm.Session(
            token_hash=token_hash, user_id=u.id,
            created_at=now, expires_at=expires_at, last_seen_at=now,
        ))
        s.commit()
        return True
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def username_for_session(token_hash: str) -> str | None:
    """Resolve a session to its username, refusing expired ones.

    Touches `last_seen_at` so open sessions can be told apart later.
    """
    s = SessionLocal()
    try:
        row = s.execute(
            select(orm.Session, orm.User.username)
            .join(orm.User, orm.Session.user_id == orm.User.id)
            .where(orm.Session.token_hash == token_hash)
        ).first()
        if row is None:
            return None
        session, username = row
        now = datetime.now()
        if session.expires_at <= now:
            s.delete(session)
            s.commit()
            return None
        session.last_seen_at = now
        s.commit()
        return username
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def delete_session(token_hash: str) -> bool:
    s = SessionLocal()
    try:
        n = s.query(orm.Session).filter_by(token_hash=token_hash).delete()
        s.commit()
        return bool(n)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def purge_expired_sessions() -> int:
    s = SessionLocal()
    try:
        n = s.query(orm.Session).filter(orm.Session.expires_at <= datetime.now()).delete()
        s.commit()
        return int(n)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- attribute tree ----------

_TREE_CACHE = None


def invalidate_attr_tree() -> None:
    """Forget the cached graph. Call after any change to nodes or links."""
    global _TREE_CACHE
    _TREE_CACHE = None


def load_attr_tree():
    """Load and cache the attribute graph. Returns a domain.attributes.Tree."""
    global _TREE_CACHE
    if _TREE_CACHE is not None:
        return _TREE_CACHE

    from src.domain.attributes import Tree, Node

    s = SessionLocal()
    try:
        node_rows = s.execute(select(orm.AttrNode).order_by(orm.AttrNode.id)).scalars().all()
        edge_rows = s.execute(select(orm.AttrEdge).order_by(orm.AttrEdge.id)).scalars().all()

        nodes_by_key: dict = {}
        id_to_key: dict[int, str] = {}
        for n in node_rows:
            nodes_by_key[n.key] = Node(
                id=n.id, key=n.key, name=n.name,
                half_life_hours=float(n.half_life_hours or 0),
                floor=float(n.floor or 0),
                threshold=float(n.threshold or 0),
                max_level=(int(n.max_level) if n.max_level is not None else None),
                shop_group=bool(n.shop_group),
            )
            id_to_key[n.id] = n.key

        children: dict[str, list[tuple[str, float]]] = {}
        parents: dict[str, list[tuple[str, float, bool]]] = {}
        primary_parent: dict[str, str] = {}
        for e in edge_rows:
            pk, ck = id_to_key.get(e.parent_id), id_to_key.get(e.child_id)
            if pk is None or ck is None:
                continue
            children.setdefault(pk, []).append((ck, float(e.weight)))
            parents.setdefault(ck, []).append((pk, float(e.weight), bool(e.is_primary)))
            if e.is_primary:
                primary_parent[ck] = pk

        _TREE_CACHE = Tree(nodes_by_key=nodes_by_key, children=children,
                           primary_parent=primary_parent, parents=parents)
        return _TREE_CACHE
    finally:
        s.close()


# ---------- registering attributes ----------
#
# Every write here keeps the promise the engine makes: registering children never
# changes what a parent is worth at that moment. Each function validates through
# src.domain.attributes, writes in one transaction, then drops the cached graph.

def _node_row(s: Session, key: str) -> orm.AttrNode:
    n = s.execute(select(orm.AttrNode).where(orm.AttrNode.key == key)).scalar_one_or_none()
    if n is None:
        from src.domain.attributes import RegistrationError
        raise RegistrationError(f"unknown attribute '{key}'")
    return n


def _holds_data(s: Session, node_id: int) -> bool:
    for model in (orm.UserLeafScore, orm.ActionContribution):
        if s.execute(select(func.count()).select_from(model).where(model.leaf_id == node_id)).scalar():
            return True
    return False


def _settings_from(n: orm.AttrNode) -> dict:
    return {"half_life_hours": n.half_life_hours, "floor": n.floor,
            "threshold": n.threshold, "max_level": n.max_level}


def subdivide_attribute(parent_key: str, children: list[tuple[str, str, float]]) -> dict:
    """A leaf becomes a parent. Each child inherits the leaf whole: every user's
    score and permanent level, and every action contribution at the same weight.
    Since the parent is the weighted mean of identical children, its value — and
    how much each act moves it — is exactly what it was."""
    from src.domain.attributes import check_subdivide
    check_subdivide(load_attr_tree(), parent_key, children)
    s = SessionLocal()
    try:
        parent = _node_row(s, parent_key)
        new_ids = []
        for key, name, weight in children:
            n = orm.AttrNode(key=key, name=name, shop_group=False, **_settings_from(parent))
            s.add(n)
            s.flush()
            s.add(orm.AttrEdge(parent_id=parent.id, child_id=n.id, weight=weight, is_primary=True))
            new_ids.append(n.id)
        scores = s.execute(select(orm.UserLeafScore).where(orm.UserLeafScore.leaf_id == parent.id)).scalars().all()
        for row in scores:
            for cid in new_ids:
                s.add(orm.UserLeafScore(user_id=row.user_id, leaf_id=cid, score=row.score,
                                        last_updated_at=row.last_updated_at, permanent_level=row.permanent_level))
            s.delete(row)
        contribs = s.execute(select(orm.ActionContribution).where(orm.ActionContribution.leaf_id == parent.id)).scalars().all()
        for c in contribs:
            for cid in new_ids:
                s.add(orm.ActionContribution(action_name=c.action_name, leaf_id=cid, weight=c.weight))
            s.delete(c)
        s.commit()
        return {"children": len(new_ids), "scores": len(scores), "contributions": len(contribs)}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
        invalidate_attr_tree()


def add_attribute_children(parent_key: str, children: list[tuple[str, str, float]]) -> dict:
    """More children for a node that already has some. Existing links are scaled
    by what the new weights leave, and each new child starts at the parent's
    current value for every user — so the parent does not move."""
    from src.domain.attributes import apply_decay, check_add, compute_node_score
    tree = load_attr_tree()
    room = check_add(tree, parent_key, children)
    now = datetime.now()
    s = SessionLocal()
    try:
        parent = _node_row(s, parent_key)
        sibling = _node_row(s, tree.children[parent_key][0][0])
        under = {tree.nodes_by_key[k].id: k for k in tree.leaves_by_key
                 if k in tree.descendants(parent_key)}
        by_user: dict[int, dict[str, float]] = {}
        for row in s.execute(select(orm.UserLeafScore).where(orm.UserLeafScore.leaf_id.in_(list(under)))).scalars():
            leaf = tree.leaves_by_id[row.leaf_id]
            by_user.setdefault(row.user_id, {})[leaf.key] = apply_decay(
                row.score, row.last_updated_at, now, leaf.half_life_hours, leaf.floor)
        s.execute(update(orm.AttrEdge).where(orm.AttrEdge.parent_id == parent.id)
                  .values(weight=orm.AttrEdge.weight * room).execution_options(synchronize_session=False))
        for key, name, weight in children:
            n = orm.AttrNode(key=key, name=name, shop_group=False, **_settings_from(sibling))
            s.add(n)
            s.flush()
            s.add(orm.AttrEdge(parent_id=parent.id, child_id=n.id, weight=weight, is_primary=True))
            for uid, scores in by_user.items():
                s.add(orm.UserLeafScore(user_id=uid, leaf_id=n.id, score=compute_node_score(parent_key, scores, tree),
                                        last_updated_at=now, permanent_level=0))
        s.commit()
        return {"children": len(children), "scaled_by": round(room, 6), "users": len(by_user)}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
        invalidate_attr_tree()


def link_attribute(parent_key: str, child_key: str, weight: float) -> dict:
    """A non-primary link, the way Força draws on peitoral. Nothing is rescaled:
    this is how an aggregate is assembled, and its weights reach 1 once every
    link is in. Returns the parent's weight total so far."""
    from src.domain.attributes import RegistrationError, check_link
    tree = load_attr_tree()
    check_link(tree, parent_key, child_key, weight)
    s = SessionLocal()
    try:
        parent, child = _node_row(s, parent_key), _node_row(s, child_key)
        if tree.is_leaf(parent_key) and _holds_data(s, parent.id):
            raise RegistrationError(f"'{parent_key}' holds scores or contributions; subdivide it instead")
        s.add(orm.AttrEdge(parent_id=parent.id, child_id=child.id, weight=weight, is_primary=False))
        s.commit()
        total = sum(w for _, w in tree.children.get(parent_key, [])) + weight
        return {"weight_total": round(total, 6)}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
        invalidate_attr_tree()


def reweight_attribute(parent_key: str, weights: dict[str, float]) -> None:
    """Set every child's weight. Unlike the other operations this does move the
    parent: that is its purpose."""
    from src.domain.attributes import check_reweight
    tree = load_attr_tree()
    check_reweight(tree, parent_key, weights)
    s = SessionLocal()
    try:
        pid = tree.nodes_by_key[parent_key].id
        for child, w in weights.items():
            s.execute(update(orm.AttrEdge)
                      .where(orm.AttrEdge.parent_id == pid, orm.AttrEdge.child_id == tree.nodes_by_key[child].id)
                      .values(weight=w))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
        invalidate_attr_tree()


def create_root(key: str, name: str) -> None:
    """A parentless attribute, to hang an aggregate on."""
    from src.domain.attributes import RegistrationError
    s = SessionLocal()
    try:
        if s.execute(select(orm.AttrNode.id).where(orm.AttrNode.key == key)).first():
            raise RegistrationError(f"'{key}' already exists")
        s.add(orm.AttrNode(key=key, name=name, shop_group=False))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
        invalidate_attr_tree()


def code_for_parent(parent_key: str) -> dict:
    """The code a new action registered under `parent_key` would get.

    Read-only: reuses a class number when one is registered and otherwise names
    the next free one, but writes nothing — the migration that adds the action
    records them.
    """
    from src.domain.attributes import id_classes
    tree = load_attr_tree()
    c1_key, c2_key = id_classes(tree, parent_key)
    s = SessionLocal()
    try:
        c1_id = tree.nodes_by_key[c1_key].id
        c1 = s.execute(select(orm.IdClass1.code).where(orm.IdClass1.node_id == c1_id)).scalar_one_or_none()
        new_c1 = c1 is None
        if new_c1:
            used = {int(x) for x in s.execute(select(orm.IdClass1.code)).scalars()}
            c1 = f"{min(set(range(1, 100)) - used):02d}"
        if c2_key is None:
            c2, new_c2 = "00", False
        else:
            c2 = None if new_c1 else s.execute(
                select(orm.IdClass2.code).where(orm.IdClass2.class1_node_id == c1_id,
                                                orm.IdClass2.node_id == tree.nodes_by_key[c2_key].id)
            ).scalar_one_or_none()
            new_c2 = c2 is None
            if new_c2:
                used = {int(x) for x in s.execute(
                    select(orm.IdClass2.code).where(orm.IdClass2.class1_node_id == c1_id)).scalars()}
                c2 = f"{min(set(range(1, 100)) - used):02d}"
        prefix = f"5{c1}{c2}"
        taken = {int(x[5:]) for x in s.execute(
            select(orm.ActionTemplate.code).where(orm.ActionTemplate.code.like(prefix + "%"))).scalars()}
        position = min(set(range(1, 100)) - taken)
        return {"code": f"{prefix}{position:02d}", "class1": c1_key, "class2": c2_key,
                "new_class1": new_c1, "new_class2": new_c2}
    finally:
        s.close()


def load_action_contributions(action_name: str) -> list[tuple[int, str, float]]:
    """Return [(leaf_id, leaf_key, weight)] for the given action name (case-insensitive)."""
    if not action_name:
        return []
    s = SessionLocal()
    try:
        rows = s.execute(
            select(orm.ActionContribution, orm.AttrNode.key)
            .join(orm.AttrNode, orm.ActionContribution.leaf_id == orm.AttrNode.id)
            .where(orm.ActionContribution.action_name == action_name.strip().upper())
        ).all()
        return [(r[0].leaf_id, r[1], float(r[0].weight)) for r in rows]
    finally:
        s.close()


def load_all_contributions() -> dict[str, list[tuple[str, float]]]:
    """Return {action_name_upper: [(leaf_key, weight)]} for the entire catalog."""
    s = SessionLocal()
    try:
        rows = s.execute(
            select(orm.ActionContribution, orm.AttrNode.key)
            .join(orm.AttrNode, orm.ActionContribution.leaf_id == orm.AttrNode.id)
        ).all()
        out: dict[str, list[tuple[str, float]]] = {}
        for ac, leaf_key in rows:
            out.setdefault(ac.action_name, []).append((leaf_key, float(ac.weight)))
        for k in out:
            out[k].sort(key=lambda x: -x[1])
        return out
    finally:
        s.close()


TEMPLATE_FALLBACK = {"code": None, "parent": None, "type": 0, "diff": 1, "cost": 0, "token_cost": 0, "token_gain": 0}


def load_action_templates() -> dict[str, dict]:
    """Return {action_name_upper: {code, parent, type, diff, cost, token_cost, token_gain}}."""
    s = SessionLocal()
    try:
        rows = s.execute(
            select(orm.ActionTemplate, orm.AttrNode.key)
            .join(orm.AttrNode, orm.ActionTemplate.parent_node_id == orm.AttrNode.id)
        ).all()
        return {
            t.action_name: {
                "code": t.code,
                "parent": parent_key,
                "type": int(t.type),
                "diff": int(t.diff),
                "cost": int(t.cost),
                "token_cost": int(t.token_cost),
                "token_gain": int(t.token_gain),
            }
            for t, parent_key in rows
        }
    finally:
        s.close()


def _lookup_template_field(column, action_name: str) -> int:
    name = str(action_name or "").upper()
    if not name:
        return 0
    s = SessionLocal()
    try:
        row = s.execute(
            select(column).where(orm.ActionTemplate.action_name == name)
        ).scalar_one_or_none()
        return int(row or 0)
    finally:
        s.close()


def lookup_token_cost(action_name: str) -> int:
    """Tokens an execution of this action spends, or 0 without a template."""
    return _lookup_template_field(orm.ActionTemplate.token_cost, action_name)


def lookup_token_gain(action_name: str) -> int:
    """Tokens an execution of this action releases, or 0 without a template."""
    return _lookup_template_field(orm.ActionTemplate.token_gain, action_name)


def get_user_leaf_scores(username: str) -> dict[str, dict]:
    """Returns {leaf_key: {'score': float, 'last_updated_at': datetime, 'leaf_id': int}}."""
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return {}
        rows = s.execute(
            select(orm.UserLeafScore, orm.AttrNode.key)
            .join(orm.AttrNode, orm.UserLeafScore.leaf_id == orm.AttrNode.id)
            .where(orm.UserLeafScore.user_id == u.id)
        ).all()
        out: dict[str, dict] = {}
        for ls, key in rows:
            out[key] = {
                "score": float(ls.score),
                "last_updated_at": ls.last_updated_at,
                "leaf_id": ls.leaf_id,
                "permanent_level": int(ls.permanent_level or 0),
            }
        return out
    finally:
        s.close()


def upsert_user_leaf_score(username: str, leaf_id: int, score: float, last_updated_at: datetime, permanent_level: int = 0) -> None:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return
        existing = s.execute(
            select(orm.UserLeafScore).where(
                orm.UserLeafScore.user_id == u.id,
                orm.UserLeafScore.leaf_id == int(leaf_id),
            )
        ).scalar_one_or_none()
        if existing is None:
            s.add(orm.UserLeafScore(
                user_id=u.id, leaf_id=int(leaf_id),
                score=float(score), last_updated_at=last_updated_at,
                permanent_level=int(permanent_level),
            ))
        else:
            s.execute(
                update(orm.UserLeafScore)
                .where(
                    orm.UserLeafScore.user_id == u.id,
                    orm.UserLeafScore.leaf_id == int(leaf_id),
                )
                .values(score=float(score), last_updated_at=last_updated_at, permanent_level=int(permanent_level))
                .execution_options(synchronize_session=False)
            )
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def apply_decay_to_all_leaves(username: str, now: datetime) -> int:
    """Apply decay to every user leaf score and stamp last_updated_at = now.

    Called by daily tick. Returns count of leaves touched.
    """
    from src.domain.attributes import apply_decay

    tree = load_attr_tree()
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return 0
        rows = s.execute(
            select(orm.UserLeafScore).where(orm.UserLeafScore.user_id == u.id)
        ).scalars().all()
        touched = 0
        for ls in rows:
            leaf = tree.leaves_by_id.get(ls.leaf_id)
            if leaf is None:
                continue
            new_score = apply_decay(
                float(ls.score), ls.last_updated_at, now,
                leaf.half_life_hours, leaf.floor,
            )
            s.execute(
                update(orm.UserLeafScore)
                .where(orm.UserLeafScore.id == ls.id)
                .values(score=new_score, last_updated_at=now)
                .execution_options(synchronize_session=False)
            )
            touched += 1
        s.commit()
        return touched
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

