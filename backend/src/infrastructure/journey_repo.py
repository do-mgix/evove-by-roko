"""Storage of the journey's battles and equipment.

Same manners as `repos`: every public function opens its own session, commits
and closes, and speaks in dicts.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from src.infrastructure import orm
from src.infrastructure.db import SessionLocal
from src.infrastructure.repos import _get_user


def user_id(username: str) -> int | None:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        return u.id if u else None
    finally:
        s.close()


# ---------- battles ----------

def _battle_dict(b: orm.Battle) -> dict:
    return {
        "run": b.run, "stage": b.stage, "slot": b.slot, "boss_name": b.boss_name,
        "won": b.won, "dealt": b.dealt, "taken": b.taken, "best_hit": b.best_hit,
        "points": b.points, "fought_at": b.fought_at.isoformat(timespec="seconds"),
    }


def load_battles(username: str) -> list[dict]:
    """Every fight, oldest first."""
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return []
        rows = s.execute(select(orm.Battle).where(orm.Battle.user_id == u.id).order_by(orm.Battle.id)).scalars().all()
        return [_battle_dict(b) for b in rows]
    finally:
        s.close()


def record_battle(username: str, battle: dict) -> None:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return
        s.add(orm.Battle(
            user_id=u.id,
            run=int(battle["run"]),
            stage=int(battle["stage"]),
            slot=int(battle["slot"]),
            boss_name=str(battle["boss_name"])[:32],
            won=bool(battle["won"]),
            dealt=int(battle.get("dealt", 0)),
            taken=int(battle.get("taken", 0)),
            best_hit=int(battle.get("best_hit", 0)),
            points=int(battle.get("points", 0)),
            fought_at=battle.get("fought_at") or datetime.now(),
        ))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------- equipment ----------

def load_equipment(username: str) -> dict[str, bool]:
    """{item_id: worn} for every item the profile owns."""
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return {}
        rows = s.execute(select(orm.UserEquipment).where(orm.UserEquipment.user_id == u.id)).scalars().all()
        return {r.item_id: bool(r.equipped) for r in rows}
    finally:
        s.close()


def add_equipment(username: str, item_id: str) -> None:
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return
        s.add(orm.UserEquipment(user_id=u.id, item_id=item_id, equipped=False, bought_at=datetime.now()))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def wear(username: str, item_id: str, same_slot: list[str], on: bool) -> None:
    """Puts `item_id` on, taking off the others of its slot, or takes it off."""
    s = SessionLocal()
    try:
        u = _get_user(s, username)
        if not u:
            return
        rows = s.execute(select(orm.UserEquipment).where(
            orm.UserEquipment.user_id == u.id, orm.UserEquipment.item_id.in_(same_slot),
        )).scalars().all()
        for r in rows:
            r.equipped = on and r.item_id == item_id
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
