"""Storage of media: the titles a profile tags its thoughts with.

Same manners as `agenda_repo`: every public function opens its own session,
commits and closes, and speaks in dicts. See src.domain.media for the rules.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from src.domain.media import (
    KINDS, PATCH_AFTER_DAYS, PATCH_BASE, MediaError, can_patch, check_kind, check_status, clean_title,
)
from src.infrastructure import orm
from src.infrastructure.db import SessionLocal
from src.infrastructure.repos import _get_user


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _user(s, username: str) -> orm.User:
    u = _get_user(s, username)
    if not u:
        raise MediaError(f"user '{username}' not found", 404)
    return u


def _get(s, user_id: int, media_id: int) -> orm.Media:
    m = s.execute(select(orm.Media).where(orm.Media.user_id == user_id, orm.Media.id == int(media_id))).scalar_one_or_none()
    if m is None:
        raise MediaError(f"title {media_id} not found", 404)
    return m


def tag(m: orm.Media | None) -> dict | None:
    """What a thought shows of its title."""
    if m is None:
        return None
    return {"id": m.id, "kind": m.kind, "title": m.title, "status": m.status}


def _uses(s, user_id: int) -> dict[int, dict]:
    """Per title: the thoughts tagged with it, on how many days, the last one."""
    rows = s.execute(
        select(orm.Thought.media_id, func.count(orm.Thought.id), func.count(func.distinct(orm.Thought.day)),
               func.max(orm.Thought.day))
        .where(orm.Thought.user_id == user_id, orm.Thought.media_id.is_not(None))
        .group_by(orm.Thought.media_id)
    ).all()
    return {mid: {"uses": int(n), "days": int(d), "last": last.isoformat() if last else None} for mid, n, d, last in rows}


def _dict(m: orm.Media, uses: dict | None) -> dict:
    u = uses or {"uses": 0, "days": 0, "last": None}
    return {
        **tag(m),
        "note": m.note,
        "created_at": m.created_at.isoformat(timespec="seconds"),
        "finished_at": m.finished_at.isoformat(timespec="seconds") if m.finished_at else None,
        "patch_action_id": m.patch_action_id,
        **u,
        "can_patch": can_patch(u["days"], m.patch_action_id),
    }


def list_media(username: str, kind: str | None = None) -> list[dict]:
    """The profile's titles, of one kind or all: the active first, then by the
    last day they were tagged, then by title."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        q = select(orm.Media).where(orm.Media.user_id == u.id)
        if kind:
            q = q.where(orm.Media.kind == check_kind(kind))
        rows = s.execute(q).scalars().all()
        uses = _uses(s, u.id)
        out = [_dict(m, uses.get(m.id)) for m in rows]
        out.sort(key=lambda d: (d["status"] != "ativo", -(int(d["last"].replace("-", "")) if d["last"] else 0),
                                d["title"].lower()))
        return out
    finally:
        s.close()


def get_media(username: str, media_id: int) -> dict:
    s = SessionLocal()
    try:
        u = _user(s, username)
        return _dict(_get(s, u.id, media_id), _uses(s, u.id).get(int(media_id)))
    finally:
        s.close()


def create_media(username: str, kind, title, status="ativo", note=None) -> dict:
    """A new title. One already there under the same kind and name (case and
    accents aside) is answered instead of a second one."""
    kind, title, status = check_kind(kind), clean_title(title), check_status(status)
    s = SessionLocal()
    try:
        u = _user(s, username)
        same = s.execute(select(orm.Media).where(orm.Media.user_id == u.id, orm.Media.kind == kind,
                                                 orm.Media.title == title)).scalar_one_or_none()
        if same is None:
            now = _now()
            same = orm.Media(user_id=u.id, kind=kind, title=title, status=status,
                             note=(str(note).strip()[:64] or None) if note else None, created_at=now,
                             finished_at=now if status == "finalizado" else None)
            s.add(same)
            s.commit()
        return _dict(same, _uses(s, u.id).get(same.id))
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def update_media(username: str, media_id: int, fields: dict) -> dict:
    """{title?, status?, note?}. Finishing a title dates it; leaving
    `finalizado` clears the date."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        m = _get(s, u.id, media_id)
        if "title" in fields:
            m.title = clean_title(fields["title"])
        if "status" in fields:
            status = check_status(fields["status"])
            if status == "finalizado" and m.status != "finalizado":
                m.finished_at = _now()
            elif status != "finalizado":
                m.finished_at = None
            m.status = status
        if "note" in fields:
            m.note = (str(fields["note"] or "").strip()[:64]) or None
        s.commit()
        return _dict(m, _uses(s, u.id).get(m.id))
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def delete_media(username: str, media_id: int) -> None:
    """The title goes; the thoughts tagged with it stay, untagged."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        m = _get(s, u.id, media_id)
        s.query(orm.Thought).filter(orm.Thought.user_id == u.id, orm.Thought.media_id == m.id) \
            .update({orm.Thought.media_id: None}, synchronize_session=False)
        s.delete(m)
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def owned(username: str, media_id: int) -> orm.Media:
    """The title, checked to be the profile's — for tagging a thought."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        m = _get(s, u.id, media_id)
        s.expunge(m)
        return m
    finally:
        s.close()


def by_ids(username: str, ids) -> dict[int, dict]:
    ids = {int(i) for i in ids if i is not None}
    if not ids:
        return {}
    s = SessionLocal()
    try:
        u = _user(s, username)
        rows = s.execute(select(orm.Media).where(orm.Media.user_id == u.id, orm.Media.id.in_(ids))).scalars().all()
        return {m.id: tag(m) for m in rows}
    finally:
        s.close()


def by_patch(username: str) -> dict[str, dict]:
    """The titles that became patches, by the patch's action id."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        rows = s.execute(select(orm.Media).where(orm.Media.user_id == u.id,
                                                 orm.Media.patch_action_id.is_not(None))).scalars().all()
        return {m.patch_action_id: tag(m) for m in rows}
    finally:
        s.close()


def base_for(username: str, media_id: int) -> tuple[orm.Media, str]:
    """The title and the id of the profile's action it would be a patch of.
    Refuses a title that is a patch already, has not come back often enough,
    or whose action the profile does not own."""
    s = SessionLocal()
    try:
        u = _user(s, username)
        m = _get(s, u.id, media_id)
        days = _uses(s, u.id).get(m.id, {}).get("days", 0)
        if m.patch_action_id:
            raise MediaError(f"'{m.title}' is a patch already", 409)
        if not can_patch(days, m.patch_action_id):
            raise MediaError(f"'{m.title}' was tagged on {days} days; a patch takes {PATCH_AFTER_DAYS}", 409)
        name = PATCH_BASE[m.kind]
        base = s.execute(select(orm.Action).where(orm.Action.user_id == u.id, orm.Action.name == name,
                                                  orm.Action.deleted.is_(False))).scalar_one_or_none()
        if base is None:
            raise MediaError(f"own {name} first: a {KINDS[m.kind][0]} becomes a patch of it", 409)
        s.expunge(m)
        return m, base.action_id
    finally:
        s.close()


def set_patch(username: str, media_id: int, patch_action_id: str) -> dict:
    s = SessionLocal()
    try:
        u = _user(s, username)
        m = _get(s, u.id, media_id)
        m.patch_action_id = patch_action_id
        if m.status in ("fila", "retirado"):
            m.status = "ativo"
        s.commit()
        return _dict(m, _uses(s, u.id).get(m.id))
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
