"""Storage of a profile's evove (src.domain.engine): one JSON state and a
passcode per profile. Same manners as `repos`."""
from __future__ import annotations

import json
import random
from datetime import datetime

from sqlalchemy import select

from src.domain import engine
from src.infrastructure import orm
from src.infrastructure.db import SessionLocal
from src.infrastructure.repos import _get_user


def _new_code(s) -> str:
    rng = random.SystemRandom()
    taken = set(s.execute(select(orm.UserEngine.passcode)).scalars().all())
    while True:
        code = engine.evove_code(rng)
        if code not in taken:
            return code


def load(username: str) -> tuple[dict, str]:
    """The profile's state and passcode. A profile without one starts from the
    beginning — it was created after the engine, or its row was reset."""
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            raise KeyError(username)
        row = s.get(orm.UserEngine, u.id)
        if row is None:
            state = engine.fresh(random.Random())
            row = orm.UserEngine(user_id=u.id, passcode=_new_code(s), state=json.dumps(state), updated_at=datetime.now())
            s.add(row)
            s.commit()
            return state, row.passcode
        return engine.normalized(json.loads(row.state), random.Random()), row.passcode
    finally:
        s.close()


def save(username: str, state: dict) -> None:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        row = s.get(orm.UserEngine, u.id)
        if row is None:
            row = orm.UserEngine(user_id=u.id, passcode=_new_code(s), state="{}", updated_at=datetime.now())
            s.add(row)
        row.state = json.dumps(state, ensure_ascii=False)
        row.updated_at = datetime.now()
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def by_passcode(code: str) -> dict | None:
    """The state of the evove a passcode names, or None."""
    s = SessionLocal()
    try:
        row = s.execute(select(orm.UserEngine).where(orm.UserEngine.passcode == code)).scalar_one_or_none()
        return json.loads(row.state) if row else None
    finally:
        s.close()
