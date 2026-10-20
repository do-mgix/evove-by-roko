"""Storage of the agenda: to-dos, projects and thoughts.

Same manners as `repos`: every public function opens its own session, commits
and closes, and speaks in dicts. A to-do is known by its row id; a project keeps
the logical `p_0001` id it always had.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select

from src.infrastructure import orm
from src.infrastructure.db import SessionLocal
from src.infrastructure.repos import _get_user


class AgendaError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    # whole seconds: MySQL rounds the fraction away, sometimes up
    return datetime.now().replace(microsecond=0)


def _iso(d) -> str | None:
    if d is None:
        return None
    return d.isoformat(timespec="seconds") if isinstance(d, datetime) else d.isoformat()


def _user(s, username: str) -> orm.User:
    u = _get_user(s, username)
    if not u:
        raise AgendaError(f"user '{username}' not found", 404)
    return u


def _action_names(s, user_id: int) -> dict[str, str]:
    rows = s.execute(select(orm.Action.action_id, orm.Action.name).where(
        orm.Action.user_id == user_id, orm.Action.deleted.is_(False),
    )).all()
    return {aid: name for aid, name in rows}


def _acted_since(s, user_id: int, action_ids: list[str], since: datetime) -> set[str]:
    """Which of `action_ids` were acted on at or after `since`."""
    if not action_ids:
        return set()
    rows = s.execute(select(orm.MarkEvent.action_id).where(
        orm.MarkEvent.user_id == user_id,
        orm.MarkEvent.action_id.in_(action_ids),
        orm.MarkEvent.acted_at >= since,
    ).distinct()).scalars().all()
    return set(rows)


# ---------- to-dos ----------

def _todo_dict(s, t: orm.Todo, names: dict[str, str], projects: dict[int, str]) -> dict:
    ids = sorted(s.execute(select(orm.TodoAction.action_id).where(orm.TodoAction.todo_id == t.id)).scalars().all())
    acted = _acted_since(s, t.user_id, ids, t.created_at)
    done_day = t.done_at.date() if t.done_at else None
    return {
        "id": t.id,
        "title": t.title,
        "project_id": projects.get(t.project_pk) if t.project_pk else None,
        "deadline": _iso(t.deadline),
        "created_at": _iso(t.created_at),
        "done_at": _iso(t.done_at),
        "done": t.done_at is not None,
        "reward": t.reward,
        # past the deadline: done after it, or still open after it
        "late": bool(t.deadline and (done_day or date.today()) > t.deadline),
        "actions": [{"id": i, "name": names.get(i, i), "acted": i in acted} for i in ids],
    }


def _project_ids(s, user_id: int) -> dict[int, str]:
    rows = s.execute(select(orm.Project.id, orm.Project.project_id).where(orm.Project.user_id == user_id)).all()
    return {pk: pid for pk, pid in rows}


def _project_pk(s, user_id: int, project_id) -> int | None:
    if not project_id:
        return None
    pk = s.execute(select(orm.Project.id).where(
        orm.Project.user_id == user_id, orm.Project.project_id == str(project_id),
    )).scalar_one_or_none()
    if pk is None:
        raise AgendaError(f"project '{project_id}' not found", 404)
    return pk


def _owned_action_ids(s, user_id: int, raw: list) -> list[str]:
    names = _action_names(s, user_id)
    ids = []
    for a in raw or []:
        a = str(a)
        if a not in names:
            raise AgendaError(f"action '{a}' not found", 404)
        if a not in ids:
            ids.append(a)
    return ids


def _clean_title(raw) -> str:
    title = " ".join(str(raw or "").split())
    if not title:
        raise AgendaError("title is required")
    return title[:128]


def _clean_date(raw) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        raise AgendaError("deadline must be YYYY-MM-DD")


def list_todos(username: str) -> list[dict]:
    """Open to-dos first, by deadline then age; then the done ones, newest first."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        names = _action_names(s, u.id)
        projects = _project_ids(s, u.id)
        rows = s.execute(select(orm.Todo).where(orm.Todo.user_id == u.id)).scalars().all()
        out = [_todo_dict(s, t, names, projects) for t in rows]
        open_ = sorted((t for t in out if not t["done"]), key=lambda t: (t["deadline"] or "9999", t["created_at"]))
        done = sorted((t for t in out if t["done"]), key=lambda t: t["done_at"], reverse=True)
        return open_ + done
    finally:
        s.close()


def _get_todo(s, user_id: int, todo_id: int) -> orm.Todo:
    t = s.get(orm.Todo, int(todo_id))
    if not t or t.user_id != user_id:
        raise AgendaError(f"to-do {todo_id} not found", 404)
    return t


def create_todo(username: str, title, action_ids: list, deadline=None, project_id=None) -> dict:
    s = SessionLocal()
    try:
        u = _user(s, username)
        t = orm.Todo(
            user_id=u.id,
            title=_clean_title(title),
            project_pk=_project_pk(s, u.id, project_id),
            deadline=_clean_date(deadline),
            created_at=_now(),
        )
        s.add(t)
        s.flush()
        for a in _owned_action_ids(s, u.id, action_ids):
            s.add(orm.TodoAction(todo_id=t.id, action_id=a))
        s.commit()
        return _todo_dict(s, t, _action_names(s, u.id), _project_ids(s, u.id))
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def update_todo(username: str, todo_id: int, change: dict) -> dict:
    """{title?, deadline?, project_id?, action_ids?}. A done to-do keeps its
    actions: what it paid was counted on them."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        t = _get_todo(s, u.id, todo_id)
        if "title" in change:
            t.title = _clean_title(change["title"])
        if "deadline" in change:
            t.deadline = _clean_date(change["deadline"])
        if "project_id" in change:
            t.project_pk = _project_pk(s, u.id, change["project_id"])
        if "action_ids" in change:
            if t.done_at:
                raise AgendaError("a done to-do keeps its actions", 409)
            ids = _owned_action_ids(s, u.id, change["action_ids"])
            s.query(orm.TodoAction).filter_by(todo_id=t.id).delete()
            for a in ids:
                s.add(orm.TodoAction(todo_id=t.id, action_id=a))
        s.commit()
        return _todo_dict(s, t, _action_names(s, u.id), _project_ids(s, u.id))
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def complete_todo(username: str, todo_id: int, reward_for) -> dict:
    """Marks it done now and records the points `reward_for(actions)` pays.
    The caller credits them. Done is done: completing twice is refused."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        t = _get_todo(s, u.id, todo_id)
        if t.done_at:
            raise AgendaError("already done", 409)
        count = s.execute(select(func.count()).select_from(orm.TodoAction).where(orm.TodoAction.todo_id == t.id)).scalar_one()
        t.done_at = _now()
        t.reward = int(reward_for(count))
        s.commit()
        return _todo_dict(s, t, _action_names(s, u.id), _project_ids(s, u.id))
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def delete_todo(username: str, todo_id: int) -> None:
    s = SessionLocal()
    try:
        u = _user(s, username)
        s.delete(_get_todo(s, u.id, todo_id))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def todos_done_on(username: str, day: date) -> int:
    s = SessionLocal()
    try:
        u = _user(s, username)
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())
        return s.execute(select(func.count()).select_from(orm.Todo).where(
            orm.Todo.user_id == u.id, orm.Todo.done_at >= start, orm.Todo.done_at <= end,
        )).scalar_one()
    finally:
        s.close()


# ---------- projects ----------

def _project_dict(s, p: orm.Project, now: datetime) -> dict:
    todos = s.execute(select(orm.Todo).where(orm.Todo.project_pk == p.id)).scalars().all()
    action_ids = sorted(set(s.execute(
        select(orm.TodoAction.action_id).where(orm.TodoAction.todo_id.in_([t.id for t in todos]))
    ).scalars().all())) if todos else []
    marks = 0
    if action_ids:
        q = select(func.coalesce(func.sum(orm.MarkEvent.marks), 0)).where(
            orm.MarkEvent.user_id == p.user_id,
            orm.MarkEvent.action_id.in_(action_ids),
            orm.MarkEvent.acted_at >= p.created_at,
        )
        if p.ended_at:
            q = q.where(orm.MarkEvent.acted_at <= p.ended_at)
        marks = int(s.execute(q).scalar_one())
    active_seconds = p.active_seconds + (int((now - p.active_since).total_seconds()) if p.active and p.active_since else 0)
    end = p.ended_at or now
    return {
        "id": p.project_id,
        "name": p.name,
        "deadline": _iso(p.deadline),
        "active": bool(p.active),
        "created_at": _iso(p.created_at),
        "ended_at": _iso(p.ended_at),
        "outcome": p.outcome,
        "emblem": p.outcome is not None,
        "stats": {
            "active_seconds": max(0, active_seconds),
            "inactive_seconds": max(0, int((end - p.created_at).total_seconds()) - active_seconds),
            "actions": len(action_ids),
            "marks": marks,
            "todos": len(todos),
            "todos_done": sum(1 for t in todos if t.done_at),
        },
    }


def _next_project_id(s, user_id: int) -> str:
    best = 0
    for pid in s.execute(select(orm.Project.project_id).where(orm.Project.user_id == user_id)).scalars().all():
        try:
            best = max(best, int(str(pid).removeprefix("p_")))
        except ValueError:
            continue
    return f"p_{best + 1:04d}"


def _get_project(s, user_id: int, project_id: str) -> orm.Project:
    p = s.execute(select(orm.Project).where(
        orm.Project.user_id == user_id, orm.Project.project_id == str(project_id),
    )).scalar_one_or_none()
    if not p:
        raise AgendaError(f"project '{project_id}' not found", 404)
    return p


def list_projects(username: str) -> list[dict]:
    """Running projects first, oldest first; then the emblems, newest first."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        now = _now()
        rows = s.execute(select(orm.Project).where(orm.Project.user_id == u.id).order_by(orm.Project.id)).scalars().all()
        running = [_project_dict(s, p, now) for p in rows if not p.outcome]
        ended = [_project_dict(s, p, now) for p in rows if p.outcome]
        ended.sort(key=lambda p: p["ended_at"] or "", reverse=True)
        return running + ended
    finally:
        s.close()


def create_project(username: str, name, deadline=None) -> dict:
    s = SessionLocal()
    try:
        u = _user(s, username)
        now = _now()
        p = orm.Project(
            user_id=u.id,
            project_id=_next_project_id(s, u.id),
            name=_clean_title(name)[:255],
            deadline=_clean_date(deadline),
            active=True,
            created_at=now,
            active_seconds=0,
            active_since=now,
        )
        s.add(p)
        s.commit()
        return _project_dict(s, p, now)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def update_project(username: str, project_id: str, change: dict) -> dict:
    """{name?, deadline?, active?}. Turning it off banks the time it was on."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        p = _get_project(s, u.id, project_id)
        now = _now()
        if "name" in change:
            p.name = _clean_title(change["name"])[:255]
        if "deadline" in change:
            p.deadline = _clean_date(change["deadline"])
        if "active" in change and bool(change["active"]) != bool(p.active):
            if p.outcome:
                raise AgendaError("an emblem is no longer running", 409)
            if p.active and p.active_since:
                p.active_seconds += int((now - p.active_since).total_seconds())
            p.active = bool(change["active"])
            p.active_since = now if p.active else None
        s.commit()
        return _project_dict(s, p, now)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def end_project(username: str, project_id: str) -> dict:
    """Closes it for good and turns it into an emblem: completed when every one
    of its to-dos is done, finished otherwise."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        p = _get_project(s, u.id, project_id)
        if p.outcome:
            raise AgendaError("already ended", 409)
        now = _now()
        todos = s.execute(select(orm.Todo).where(orm.Todo.project_pk == p.id)).scalars().all()
        if p.active and p.active_since:
            p.active_seconds += int((now - p.active_since).total_seconds())
        p.active = False
        p.active_since = None
        p.ended_at = now
        p.outcome = "completed" if todos and all(t.done_at for t in todos) else "finished"
        s.commit()
        return _project_dict(s, p, now)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def delete_project(username: str, project_id: str) -> None:
    """Its to-dos stay, loose."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        s.delete(_get_project(s, u.id, project_id))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- thoughts ----------

def _thought_dict(t: orm.Thought) -> dict:
    return {"id": t.id, "day": _iso(t.day), "log_id": t.log_id, "content": t.content, "updated_at": _iso(t.updated_at)}


def thoughts_on(username: str, day: date) -> list[dict]:
    s = SessionLocal()
    try:
        u = _user(s, username)
        rows = s.execute(select(orm.Thought).where(orm.Thought.user_id == u.id, orm.Thought.day == day)
                         .order_by(orm.Thought.id)).scalars().all()
        return [_thought_dict(t) for t in rows]
    finally:
        s.close()


def set_thought(username: str, day: date, log_id: int | None, content: str) -> dict | None:
    """The one thought of a log, or of the day when `log_id` is None, written or
    replaced. Empty content takes it away and returns None."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        q = select(orm.Thought).where(orm.Thought.user_id == u.id, orm.Thought.day == day)
        q = q.where(orm.Thought.log_id.is_(None)) if log_id is None else q.where(orm.Thought.log_id == int(log_id))
        t = s.execute(q).scalars().first()
        text = str(content or "").strip()
        now = _now()
        if not text:
            if t:
                s.delete(t)
                s.commit()
            return None
        if t:
            t.content = text
            t.updated_at = now
        else:
            t = orm.Thought(user_id=u.id, day=day, log_id=log_id, content=text, created_at=now, updated_at=now)
            s.add(t)
        s.commit()
        return _thought_dict(t)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
