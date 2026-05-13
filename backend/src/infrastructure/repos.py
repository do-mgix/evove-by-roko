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
        "max_tokens": state.max_tokens if state else 50,
        "daily_refill": state.daily_refill if state else 20,
        "days_until_next_checkpoint": state.days_until_next_checkpoint if state else 20,
        "last_checkpoint_check": _date_iso(state.last_checkpoint_check) if state else None,
        "last_token_refill": _date_iso(state.last_token_refill) if state else None,
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
    state.max_tokens = int(md.get("max_tokens", 50) or 50)
    state.build_points = int(md.get("build_points", 0) or 0)
    state.skill_points = int(md.get("skill_points", 0) or 0)
    state.stage = int(md.get("stage", 1) or 1)
    state.mode = str(md.get("mode", "progressive") or "progressive")
    state.date = _parse_date(md.get("date")) or state.date
    state.days_until_next_checkpoint = int(md.get("days_until_next_checkpoint", 20) or 20)
    state.last_checkpoint_check = _parse_date(md.get("last_checkpoint_check"))
    state.last_token_refill = _parse_date(md.get("last_token_refill"))
    state.last_decay_check = _parse_date(md.get("last_decay_check"))
    state.daily_refill = int(md.get("daily_refill", 20) or 20)


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

def create_user(username: str, initial_user: dict, initial_sequences: dict | None = None) -> None:
    s = SessionLocal()
    try:
        if _get_user(s, username):
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="user already exists")
        u = orm.User(username=username, created_at=datetime.now())
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


# ---------- attribute tree ----------

_TREE_CACHE: dict | None = None


def load_attr_tree():
    """Load and cache the static tree (nodes/edges/contributions) from DB.

    Returns a domain.attributes.Tree instance.
    """
    global _TREE_CACHE
    if _TREE_CACHE is not None:
        return _TREE_CACHE

    from src.domain.attributes import Tree, NodeMeta, LeafMeta

    s = SessionLocal()
    try:
        node_rows = s.execute(select(orm.AttrNode)).scalars().all()
        edge_rows = s.execute(select(orm.AttrEdge)).scalars().all()

        nodes_by_key: dict[str, NodeMeta] = {}
        leaves_by_key: dict[str, LeafMeta] = {}
        leaves_by_id: dict[int, LeafMeta] = {}
        id_to_key: dict[int, str] = {}

        for n in node_rows:
            nodes_by_key[n.key] = NodeMeta(id=n.id, key=n.key, name=n.name, is_leaf=bool(n.is_leaf))
            id_to_key[n.id] = n.key
            if n.is_leaf:
                leaf = LeafMeta(
                    id=n.id, key=n.key, name=n.name,
                    half_life_hours=float(n.half_life_hours or 0),
                    floor=float(n.floor or 0),
                    threshold=float(n.threshold or 0),
                )
                leaves_by_key[n.key] = leaf
                leaves_by_id[n.id] = leaf

        children: dict[str, list[tuple[str, float]]] = {}
        child_ids: set[int] = set()
        for e in edge_rows:
            parent_key = id_to_key.get(e.parent_id)
            child_key = id_to_key.get(e.child_id)
            if parent_key is None or child_key is None:
                continue
            children.setdefault(parent_key, []).append((child_key, float(e.weight)))
            child_ids.add(e.child_id)

        roots = [n.key for n in node_rows if n.id not in child_ids]

        _TREE_CACHE = Tree(
            nodes_by_key=nodes_by_key,
            leaves_by_key=leaves_by_key,
            leaves_by_id=leaves_by_id,
            children=children,
            roots=roots,
        )
        return _TREE_CACHE
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


_TAGS_CACHE: list[dict] | None = None


def load_attr_tags() -> list[dict]:
    """Returns ordered list of tag definitions.

    Each entry: {key, name, category, display_order, sources: [(leaf_key, weight)]}.
    Order: Físico < Mental, then by display_order asc.
    """
    global _TAGS_CACHE
    if _TAGS_CACHE is not None:
        return _TAGS_CACHE

    s = SessionLocal()
    try:
        tag_rows = s.execute(select(orm.AttributeTag)).scalars().all()
        src_rows = s.execute(
            select(orm.AttributeTagSource, orm.AttrNode.key)
            .join(orm.AttrNode, orm.AttributeTagSource.leaf_id == orm.AttrNode.id)
        ).all()

        sources_by_tag: dict[int, list[tuple[str, float]]] = {}
        for src, leaf_key in src_rows:
            sources_by_tag.setdefault(src.tag_id, []).append((leaf_key, float(src.weight)))

        category_order = {"Físico": 0, "Mental": 1}
        tags = [
            {
                "key": t.key,
                "name": t.name,
                "category": t.category,
                "display_order": int(t.display_order),
                "sources": sources_by_tag.get(t.id, []),
            }
            for t in tag_rows
        ]
        tags.sort(key=lambda t: (category_order.get(t["category"], 99), t["display_order"]))
        _TAGS_CACHE = tags
        return _TAGS_CACHE
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
            }
        return out
    finally:
        s.close()


def upsert_user_leaf_score(username: str, leaf_id: int, score: float, last_updated_at: datetime) -> None:
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
            ))
        else:
            s.execute(
                update(orm.UserLeafScore)
                .where(
                    orm.UserLeafScore.user_id == u.id,
                    orm.UserLeafScore.leaf_id == int(leaf_id),
                )
                .values(score=float(score), last_updated_at=last_updated_at)
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

