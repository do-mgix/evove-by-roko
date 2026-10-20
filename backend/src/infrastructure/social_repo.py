"""Storage of what a profile found and who it knows: shop discoveries, allies,
its nickname, and how often it acts on each action.

Same manners as `repos`: every public function opens its own session, commits
and closes, and speaks in dicts.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from src.infrastructure import orm
from src.infrastructure.db import SessionLocal
from src.infrastructure.repos import _get_user, new_nickname


class SocialError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _user(s, username: str) -> orm.User:
    u = _get_user(s, username)
    if not u:
        raise SocialError(f"user '{username}' not found", 404)
    return u


# ---------- discoveries ----------

def load_discoveries(username: str) -> dict[str, datetime]:
    """{ACTION_NAME: when it was discovered}."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        rows = s.execute(select(orm.UserDiscovery).where(orm.UserDiscovery.user_id == u.id)).scalars().all()
        return {r.action_name: r.discovered_at for r in rows}
    finally:
        s.close()


def add_discoveries(username: str, names: list[str]) -> None:
    s = SessionLocal()
    try:
        u = _user(s, username)
        have = set(s.execute(select(orm.UserDiscovery.action_name).where(orm.UserDiscovery.user_id == u.id)).scalars().all())
        now = datetime.now().replace(microsecond=0)
        for name in names:
            if name not in have:
                s.add(orm.UserDiscovery(user_id=u.id, action_name=name, discovered_at=now))
                have.add(name)
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- usage ----------

def act_counts(username: str, days: int | None = None) -> dict[str, dict]:
    """{action_id: {"acts", "last"}} from the marks window's events: how many
    times each action was acted on (in the last `days`, when given) and when
    last."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        q = select(orm.MarkEvent.action_id, func.count(), func.max(orm.MarkEvent.acted_at)).where(
            orm.MarkEvent.user_id == u.id)
        if days:
            q = q.where(orm.MarkEvent.acted_at >= datetime.now() - timedelta(days=days))
        rows = s.execute(q.group_by(orm.MarkEvent.action_id)).all()
        return {aid: {"acts": int(n), "last": last} for aid, n, last in rows}
    finally:
        s.close()


def count_logs(username: str) -> int:
    s = SessionLocal()
    try:
        u = _user(s, username)
        return s.execute(select(func.count()).select_from(orm.Log).where(orm.Log.user_id == u.id)).scalar_one()
    finally:
        s.close()


# ---------- nickname and allies ----------

def identity(username: str) -> dict:
    s = SessionLocal()
    try:
        u = _user(s, username)
        return {"id": u.id, "nickname": u.nickname, "passcode": u.passcode}
    finally:
        s.close()


def reroll_nickname(username: str) -> str:
    s = SessionLocal()
    try:
        u = _user(s, username)
        u.nickname = new_nickname(s)
        s.commit()
        return u.nickname
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _ally_view(s, a: orm.User) -> dict:
    state = s.get(orm.UserState, a.id)
    return {
        "nickname": a.nickname,
        "marks": int(state.marks) if state else 0,
        "stage": int(state.stage) if state else 1,
    }


def load_allies(username: str) -> list[dict]:
    """Allies by nickname — never by login — each with its marks and stage."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        ids = s.execute(select(orm.Ally.ally_id).where(orm.Ally.user_id == u.id).order_by(orm.Ally.created_at)).scalars().all()
        return [_ally_view(s, a) for a in (s.get(orm.User, i) for i in ids) if a]
    finally:
        s.close()


def add_ally(username: str, passcode: str) -> dict:
    """Both profiles become each other's allies."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        code = str(passcode or "").strip().upper()
        other = s.execute(select(orm.User).where(orm.User.passcode == code)).scalar_one_or_none() if code else None
        if not other:
            raise SocialError("no profile with that passcode", 404)
        if other.id == u.id:
            raise SocialError("that is your own passcode", 400)
        now = datetime.now().replace(microsecond=0)
        for a, b in ((u.id, other.id), (other.id, u.id)):
            if not s.get(orm.Ally, (a, b)):
                s.add(orm.Ally(user_id=a, ally_id=b, created_at=now))
        s.commit()
        return _ally_view(s, other)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def remove_ally(username: str, nickname: str) -> None:
    s = SessionLocal()
    try:
        u = _user(s, username)
        other = s.execute(select(orm.User).where(orm.User.nickname == str(nickname).upper())).scalar_one_or_none()
        if not other:
            raise SocialError("ally not found", 404)
        for a, b in ((u.id, other.id), (other.id, u.id)):
            row = s.get(orm.Ally, (a, b))
            if row:
                s.delete(row)
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
