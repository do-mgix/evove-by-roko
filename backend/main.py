import math
import os
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import roman
from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

_BACKEND_DIR = Path(__file__).parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from src.domain.action import Action  # noqa: E402
from src.domain.act import ENERGY_PENALTY_OUT_OF_AGENDA, ActError  # noqa: E402
from src.domain.acting import perform_act, tiers_for, window_state  # noqa: E402
from src.domain.marks import DEFAULT_TIERS, MARKS_PER_WINDOW, MarkError, options as tier_options  # noqa: E402
from src.domain.agenda import collect_labels, DAY_NAMES as _DOMAIN_DAY_NAMES  # noqa: E402
from src.domain.daily import PERIODS, apply_daily_tick, period_of  # noqa: E402
from src.domain import journey as journey_mode  # noqa: E402
from src.domain import battle, discovery, engine, entities, equipment, recover as recovery, sandbox, save, dungeon, fight  # noqa: E402
from src.domain.economy import BASE_MAX_TOKENS, INITIAL_POINTS, todo_reward  # noqa: E402
from src.domain.user_attributes import PATCH_SEPARATOR, PatchError, engine_name  # noqa: E402
from src.domain.attributes import (  # noqa: E402
    CLAIM_POINTS_PER_RANK, CLAIM_SKILL_POINTS_PER_RANK, CLAIM_TOKENS_PER_RANK, RANK_LETTERS, RANK_NAMES,
    claimable_ranks, node_total, rank_view, total_marks,
)
from src.domain.skills import (  # noqa: E402
    aggregate_bonuses,
    acquire_skill as _acquire_skill,
    SkillError,
)
from src.infrastructure.static_data import (  # noqa: E402
    load_attribute_suggestions,
    load_skill_tree,
    skill_nodes_by_id,
)
from src.infrastructure import repos  # noqa: E402
from src.infrastructure import agenda_repo, engine_repo, journey_repo, social_repo  # noqa: E402
from src.infrastructure import auth  # noqa: E402
from src.infrastructure import mailer  # noqa: E402

_LETTERS = RANK_LETTERS


LOG_GROUP = "_log"          # the shop section log actions fall in; not an attribute


def _theme_for(contribs, tree) -> str | None:
    """Shop group for an action: the primary parent of its heaviest leaf that
    lives under a `shop_group` root.

    The shop groups by practice (Treino, Programação…) while the engine has no
    notion of kinds, so the practice roots carry a display mark and this is the
    only reader of it. Marked leaves are preferred explicitly rather than by
    weight: ESPORTE feeds aerobico and c_esportes both at 1.0, and a tie would
    otherwise be settled by row order. Falls back to the heaviest leaf of any
    root, so an action outside every practice still lands somewhere.
    """
    if not contribs:
        return None
    for leaf_key, _w in contribs:          # arrives sorted by descending weight
        if leaf_key in tree.nodes_by_key and tree.nodes_by_key[tree.root_of(leaf_key)].shop_group:
            return tree.primary_parent.get(leaf_key)
    return tree.primary_parent.get(contribs[0][0])


def load_packages() -> list[dict]:
    """The catalog grouped by practice.

    Assembled from `action_templates`: the catalog is the set of templates, since
    a log action has no contributions at all and grouping by them would drop it.
    A template is also what makes an action buyable — it carries the code the id
    comes from — so nothing listed here is unbuyable.
    """
    tree = repos.load_attr_tree()
    contributions = repos.load_all_contributions()

    packages: dict[str, dict] = {}
    logged = {"attribute": LOG_GROUP, "name": "Registro", "actions": []}
    unmapped = {"attribute": "_unmapped", "name": "Outros", "actions": []}
    for action_name, meta in sorted(repos.load_action_templates().items()):
        action = {
            "name": action_name,
            "code": meta["code"],
            "type": meta["type"],
            "diff": meta["diff"],
            "cost": meta["cost"],
            "token_cost": meta["token_cost"],
            "token_gain": meta["token_gain"],
            "log_only": meta["log_only"],
            "author": meta.get("author") or "roko",
        }
        if meta["log_only"]:
            logged["actions"].append(action)
            continue
        group_key = _theme_for(contributions.get(action_name, []), tree)
        group_name = tree.nodes_by_key[group_key].name if group_key and group_key in tree.nodes_by_key else None
        if group_key and group_name:
            pkg = packages.setdefault(group_key, {"attribute": group_key, "name": group_name, "actions": []})
            pkg["actions"].append(action)
        else:
            unmapped["actions"].append(action)

    out = sorted(packages.values(), key=lambda p: p["name"])
    for extra in (logged, unmapped):
        if extra["actions"]:
            out.append(extra)
    return out


app = FastAPI(title="Roko API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(raw) -> str | None:
    """Lower-cased address, None when blank; 400 when it is not one."""
    email = str(raw or "").strip().lower()
    if not email:
        return None
    if len(email) > 254 or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="invalid e-mail")
    return email


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def current_username(authorization: str | None = Header(None)) -> str:
    """FastAPI dependency: the profile behind the request's session token.

    Every user route depends on this, so an endpoint cannot accidentally be
    left open — without a valid session there is no username to act as.
    """
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="missing session token")
    username = repos.username_for_session(auth.token_digest(token))
    if not username:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return username


_INITIAL_BUILD_POINTS = INITIAL_POINTS


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


def _worn(username: str) -> dict:
    """What the equipment the profile wears adds up to (src.domain.equipment)."""
    return equipment.bonuses([i for i, on in journey_repo.load_equipment(username).items() if on])


def _max_energy(data: dict, username: str | None = None) -> int:
    """The profile's max hp: the base, its skills and, given `username`, the
    pulso it wears."""
    bonuses = aggregate_bonuses(set(data.get("skills") or []), skill_nodes_by_id())
    worn = int(_worn(username)["hp"]) if username else 0
    return journey_mode.BASE_MAX_ENERGY + int(bonuses.get("max_energy", 0) or 0) + worn


def _load_user(username: str) -> dict:
    data = repos.load_user_dict(username)
    if data is None:
        raise HTTPException(status_code=404, detail=f"user '{username}' not found")
    dirty = _apply_initial_grants(data)
    dirty = apply_daily_tick(data, max_energy=_max_energy(data, username)) or dirty
    if dirty:
        repos.save_user_dict(username, data)
    return data


def _save_user(username: str, data: dict) -> None:
    repos.save_user_dict(username, data)


def _build_tiers():
    """The user's progression: the Greek ranks with roman levels inside each. A
    level costs marks — the old xp curve divided by 70, which makes α·I cost 3."""
    tiers = []
    cumulative = 0
    global_level = 1
    total_ranks = len(_LETTERS)
    for rank_index, letter in enumerate(_LETTERS):
        levels_in_rank = max(1, total_ranks - rank_index)
        rank_symbol = letter
        for local_level in range(1, levels_in_rank + 1):
            cost = max(1, int(round(200 * (1.06 ** (global_level - 1)) * (1.28 ** rank_index) / 70)))
            cumulative += cost
            tiers.append({
                "level": global_level,
                "rank_index": rank_index,
                "rank_letter": letter,
                "rank_name": RANK_NAMES[rank_index],
                "rank_symbol": rank_symbol,
                "local_level": local_level,
                "local_level_roman": roman.toRoman(local_level),
                "local_levels_total": levels_in_rank,
                "cost": cost,
                "threshold": cumulative,
            })
            global_level += 1
    return tiers


def _progression_state(marks: int):
    tiers = _build_tiers()
    current = tiers[-1]
    for tier in tiers:
        if marks < tier["threshold"]:
            current = tier
            break
    next_marks = max(0, current["threshold"] - marks)
    return {
        "marks": marks,
        "level": current["level"],
        "rank_letter": current["rank_letter"],
        "rank_name": current["rank_name"],
        "rank_symbol": current["rank_symbol"],
        "local_level": current["local_level"],
        "local_level_roman": current["local_level_roman"],
        "local_levels_total": current["local_levels_total"],
        "next_marks": next_marks,
        "level_cost": current["cost"],
        "level_marks": current["cost"] - next_marks,
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


@app.get("/journey")
def journey(username: str = Depends(current_username)):
    """The current stage: its countdown, its smaller points, the hp left and the
    two recoveries. See src.domain.journey and src.domain.recover."""
    data = _load_user(username)
    metadata = data.get("metadata", {}) or {}
    now = datetime.now()
    max_energy = _max_energy(data, username)
    view = journey_mode.view(metadata, now, max_energy)
    return {
        **view,
        "energy_penalty": ENERGY_PENALTY_OUT_OF_AGENDA,
        "tokens": int(metadata.get("tokens", 0) or 0),
        "balance": int(metadata.get("build_points", 0) or 0),
        "recover": recovery.view(metadata, now, max_energy),
    }


@app.post("/journey/recover")
def journey_recover(payload: dict, username: str = Depends(current_username)):
    """Body: {kind: "small" | "large"}. Tokens bought back into hp."""
    data = _load_user(username)
    metadata = data.setdefault("metadata", {})
    now = datetime.now()
    max_energy = _max_energy(data, username)
    try:
        healed = recovery.recover(metadata, str((payload or {}).get("kind", "")), now, max_energy)
    except recovery.RecoverError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _save_user(username, data)
    return {
        "healed": healed,
        "energy": metadata["energy"],
        "max_energy": max_energy,
        "tokens": metadata["tokens"],
        "recover": recovery.view(metadata, now, max_energy),
    }


def _current_boss(username: str, data: dict):
    """The boss of the stretch the journey is in, the stretch's coordinates and
    whether this run already beat it."""
    metadata = data.get("metadata", {}) or {}
    run = int(metadata.get("journey_resets", 0) or 0)
    stage = int(metadata.get("stage", 1) or 1)
    slot = int(metadata.get("journey_points", 0) or 0)
    tree = repos.load_attr_tree()
    templates = repos.load_action_templates()
    seed = battle.boss_seed(journey_repo.user_id(username) or 0, run, stage, slot)
    boss = battle.make_boss(tree, templates, seed, stage, slot)
    beaten = any(b["won"] and (b["run"], b["stage"], b["slot"]) == (run, stage, slot)
                 for b in journey_repo.load_battles(username))
    return boss, (run, stage, slot), beaten, tree, templates


def _lineup(username: str, data: dict, boss, tree, templates, worn: dict) -> list[dict]:
    totals = _user_leaf_totals(username, tree)
    memo: dict[str, float] = {}
    moves = battle.moves_for(
        tree, templates, data.get("actions") or {},
        lambda key: rank_view(node_total(key, totals, tree, memo))["rank_index"],
    )
    return battle.lineup(tree, moves, boss, worn["damage"])


@app.get("/journey/boss")
def journey_boss(username: str = Depends(current_username)):
    """The boss of the current stretch, and the lineup the autobattler would take
    against it. See src.domain.battle."""
    data = _load_user(username)
    boss, (run, stage, slot), beaten, tree, templates = _current_boss(username, data)
    worn = _worn(username)
    return {
        "boss": boss.view(),
        "beaten": beaten,
        "lineup": _lineup(username, data, boss, tree, templates, worn),
        "hp": int((data.get("metadata") or {}).get("energy", 0) or 0),
        "max_hp": _max_energy(data, username),
        "armor": worn["armor"],
        "reward": battle.win_points(stage, slot, worn["points"]),
        "kinship": battle.KINSHIP,
    }


@app.post("/journey/boss/fight")
def journey_fight(username: str = Depends(current_username)):
    """Fights the current boss with the autobattler's lineup. A victory pays
    points; a defeat costs the hp the boss took, and at 0 the journey restarts."""
    data = _load_user(username)
    metadata = data.setdefault("metadata", {})
    boss, (run, stage, slot), beaten, tree, templates = _current_boss(username, data)
    if beaten:
        raise HTTPException(status_code=409, detail="boss already beaten")
    hp = int(metadata.get("energy", 0) or 0)
    if hp <= 0:
        raise HTTPException(status_code=409, detail="no hp left")
    worn = _worn(username)
    chosen = _lineup(username, data, boss, tree, templates, worn)
    if not chosen:
        raise HTTPException(status_code=409, detail="no action to fight with")
    result = battle.fight(boss, chosen, hp, worn["armor"])
    now = datetime.now()
    points = battle.win_points(stage, slot, worn["points"]) if result["won"] else 0
    reset = False
    if result["won"]:
        metadata["build_points"] = int(metadata.get("build_points", 0) or 0) + points
    else:
        metadata["energy"] = max(0, hp - result["taken"])
        if metadata["energy"] <= 0:
            journey_mode.fail(metadata, now, _max_energy(data, username))
            reset = True
    _save_user(username, data)
    journey_repo.record_battle(username, {
        "run": run, "stage": stage, "slot": slot, "boss_name": boss.name, "won": result["won"],
        "dealt": result["dealt"], "taken": result["taken"],
        "best_hit": max((m["damage"] for m in chosen), default=0), "points": points, "fought_at": now,
    })
    return {
        **result,
        "boss": boss.view(),
        "lineup": chosen,
        "points": points,
        "energy": int(metadata.get("energy", 0) or 0),
        "journey_reset": reset,
    }


@app.get("/journey/stats")
def journey_stats(username: str = Depends(current_username)):
    """Everything the journey has seen: fights, bosses, damage, restarts."""
    data = _load_user(username)
    metadata = data.get("metadata", {}) or {}
    fights = journey_repo.load_battles(username)
    wins = [b for b in fights if b["won"]]
    stage = int(metadata.get("stage", 1) or 1)
    return {
        "fights": len(fights),
        "wins": len(wins),
        "losses": len(fights) - len(wins),
        "bosses": len({(b["run"], b["stage"], b["slot"]) for b in wins}),
        "dealt": sum(b["dealt"] for b in fights),
        "taken": sum(b["taken"] for b in fights),
        "best_hit": max((b["best_hit"] for b in fights), default=0),
        "points_won": sum(b["points"] for b in wins),
        "stage": stage,
        "highest_stage": max([stage] + [b["stage"] for b in fights]),
        "resets": int(metadata.get("journey_resets", 0) or 0),
        "recover_uses": int(metadata.get("recover_uses", 0) or 0),
        "energy": int(metadata.get("energy", 0) or 0),
        "max_energy": _max_energy(data, username),
    }


@app.get("/journey/equipment")
def journey_equipment(username: str = Depends(current_username)):
    """The catalog of equipment, each item with whether it is owned and worn."""
    data = _load_user(username)
    owned = journey_repo.load_equipment(username)
    return {
        "points": int((data.get("metadata") or {}).get("build_points", 0) or 0),
        "slots": list(equipment.SLOTS),
        "items": [{**i, "owned": i["id"] in owned, "worn": bool(owned.get(i["id"]))} for i in equipment.ITEMS],
        "bonuses": _worn(username),
    }


@app.post("/journey/equipment/{item_id}/buy")
def buy_equipment(item_id: str, username: str = Depends(current_username)):
    item = equipment.ITEMS_BY_ID.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"item '{item_id}' not found")
    if item_id in journey_repo.load_equipment(username):
        raise HTTPException(status_code=409, detail="already owned")
    data = _load_user(username)
    metadata = data.setdefault("metadata", {})
    points = int(metadata.get("build_points", 0) or 0)
    if points < item["price"]:
        raise HTTPException(status_code=400, detail=f"insufficient points (have {points}, need {item['price']})")
    metadata["build_points"] = points - item["price"]
    _save_user(username, data)
    journey_repo.add_equipment(username, item_id)
    return journey_equipment(username)


@app.post("/journey/equipment/{item_id}/wear")
def wear_equipment(item_id: str, payload: dict | None = None, username: str = Depends(current_username)):
    """Body: {on: bool}, true by default. One item per slot: wearing one takes
    the other off."""
    item = equipment.ITEMS_BY_ID.get(item_id)
    if not item or item_id not in journey_repo.load_equipment(username):
        raise HTTPException(status_code=404, detail=f"item '{item_id}' not owned")
    same_slot = [i["id"] for i in equipment.ITEMS if i["slot"] == item["slot"]]
    journey_repo.wear(username, item_id, same_slot, bool((payload or {}).get("on", True)))
    return journey_equipment(username)


def _initial_profile(name: str) -> tuple[dict, dict]:
    """The blank slate a freshly registered profile starts from."""
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
            "energy": journey_mode.BASE_MAX_ENERGY,
            "score": 0,
            "stage": 1,
            "skill_points": 0,
            "build_points": 0,
            "tutorial": {
                "received_start_build_points": {"status": False, "priority": 12},
            },
            "tokens": 0,
            "max_tokens": BASE_MAX_TOKENS,
            "journey_started_at": datetime.now().isoformat(timespec="seconds"),
        },
    }
    today_seq = datetime.now().strftime("%d %m %Y")
    initial_sequences = {
        "first_activity_date": today_seq,
        "last_active_date": today_seq,
        "consecutive_days": 1,
    }
    return initial, initial_sequences


def _issue_session(username: str) -> dict:
    token = auth.new_session_token()
    expires_at = auth.session_expiry()
    if not repos.create_session(username, auth.token_digest(token), expires_at):
        raise HTTPException(status_code=404, detail=f"user '{username}' not found")
    return {"token": token, "username": username, "expires_at": expires_at.isoformat()}


@app.post("/auth/register")
def register(payload: dict):
    """Create a profile and sign it in. Body: {username, password, email?}."""
    name = str((payload or {}).get("username", "")).strip()
    password = str((payload or {}).get("password", ""))
    if not _USERNAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid username (a-z, 0-9, _ -, max 24)")
    try:
        password_hash = auth.hash_password(password)
    except auth.PasswordError as e:
        raise HTTPException(status_code=400, detail=str(e))
    email = _clean_email((payload or {}).get("email"))
    if repos.user_exists(name):
        raise HTTPException(status_code=409, detail=f"user '{name}' already exists")

    initial, initial_sequences = _initial_profile(name)
    repos.create_user(name, initial, initial_sequences, password_hash=password_hash)
    if email:
        try:
            repos.set_email(name, email)
        except repos.EmailTaken:
            # the profile stands; the address can be set later from the profile
            pass
    return _issue_session(name)


@app.post("/auth/login")
def login(payload: dict):
    """Body: {username, password}. Same error either way, so the response does
    not tell an attacker which usernames exist."""
    name = str((payload or {}).get("username", "")).strip()
    password = str((payload or {}).get("password", ""))
    stored = repos.get_password_hash(name) if _USERNAME_RE.match(name) else None
    if not stored or not auth.verify_password(password, stored):
        raise HTTPException(status_code=401, detail="invalid username or password")
    repos.purge_expired_sessions()
    return _issue_session(name)


@app.post("/auth/logout")
def logout(authorization: str | None = Header(None)):
    token = _bearer_token(authorization)
    if token:
        repos.delete_session(auth.token_digest(token))
    return {"ok": True}


@app.post("/auth/logout-all")
def logout_all(username: str = Depends(current_username)):
    """Revoke every session of the profile, on every device, this one included."""
    return {"ok": True, "revoked": repos.delete_user_sessions(username)}


@app.get("/auth/me")
def auth_me(authorization: str | None = Header(None), username: str = Depends(current_username)):
    """The account and the session behind the token."""
    info = repos.session_info(auth.token_digest(_bearer_token(authorization)))
    if not info:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return info


@app.delete("/auth/me")
def delete_account(payload: dict | None = Body(None), username: str = Depends(current_username)):
    """Delete the profile and everything it owns, sessions included. Body:
    {password}, checked again so a session left open on another device is not
    enough to erase the account. A wrong password is 403, not 401: the session
    itself is still valid, and the client drops to login on any 401."""
    password = str((payload or {}).get("password", ""))
    stored = repos.get_password_hash(username)
    if not stored or not auth.verify_password(password, stored):
        raise HTTPException(status_code=403, detail="wrong password")
    repos.delete_user(username)
    return {"ok": True}


@app.post("/auth/me/reset")
def reset_account(payload: dict | None = Body(None), username: str = Depends(current_username)):
    """Start the profile over: every piece of its data — actions, logs,
    attributes, points, discoveries, agenda, journey, allies, its evove — is
    erased and it begins again from the first step, under the same name,
    password and e-mail. Every session ends with it; the answer is a new one
    for this device. Body: {password}, as for deleting the account."""
    password = str((payload or {}).get("password", ""))
    stored = repos.get_password_hash(username)
    if not stored or not auth.verify_password(password, stored):
        raise HTTPException(status_code=403, detail="wrong password")
    email = repos.get_email(username)
    repos.delete_user(username)
    initial, initial_sequences = _initial_profile(username)
    repos.create_user(username, initial, initial_sequences, password_hash=stored)
    if email:
        repos.set_email(username, email)
    return _issue_session(username)


@app.patch("/auth/me")
def update_account(payload: dict, username: str = Depends(current_username)):
    """Set or clear the recovery e-mail. Body: {email, password}; the password
    is asked again because whoever controls the address can reset it."""
    password = str((payload or {}).get("password", ""))
    stored = repos.get_password_hash(username)
    if not stored or not auth.verify_password(password, stored):
        raise HTTPException(status_code=403, detail="wrong password")
    email = _clean_email((payload or {}).get("email"))
    try:
        repos.set_email(username, email)
    except repos.EmailTaken:
        raise HTTPException(status_code=409, detail="e-mail already in use")
    return {"ok": True, "email": email}


_RESET_TTL_MINUTES = 60
_RESET_COOLDOWN_SECONDS = 60
_PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://api.voide.shop").rstrip("/")


def _send_reset(username: str, email: str, token: str) -> None:
    # The token rides in the fragment, which browsers never send to a server,
    # so it stays out of access logs and the tunnel.
    link = f"{_PUBLIC_BASE_URL}/redefinir-senha#token={token}"
    mailer.send(
        email,
        "evove · redefinir senha",
        f"Olá, {username}.\n\n"
        f"Para criar uma senha nova no evove, abra o link abaixo. Ele vale por "
        f"{_RESET_TTL_MINUTES} minutos e só pode ser usado uma vez.\n\n{link}\n\n"
        "Se não foi você que pediu, ignore este e-mail: a senha atual continua valendo.\n",
    )


@app.post("/auth/forgot")
def forgot_password(payload: dict, background: BackgroundTasks):
    """Body: {login}, a username or an e-mail address. Always answers the same,
    and sends after answering, so neither the body nor the timing tells whether
    the profile exists or has an address."""
    login = str((payload or {}).get("login", "")).strip()
    target = repos.recovery_target(login) if login else None
    if target:
        name, email = target
        token = auth.new_session_token()
        expires = datetime.now() + timedelta(minutes=_RESET_TTL_MINUTES)
        if repos.create_password_reset(name, auth.token_digest(token), expires, _RESET_COOLDOWN_SECONDS):
            background.add_task(_send_reset, name, email, token)
    return {"ok": True}


@app.post("/auth/reset")
def reset_password(payload: dict):
    """Body: {token, password}. Sets the password, spends every open link of
    the profile and ends all its sessions; the new password is what logs in."""
    token = str((payload or {}).get("token", "")).strip()
    try:
        password_hash = auth.hash_password(str((payload or {}).get("password", "")))
    except auth.PasswordError as e:
        raise HTTPException(status_code=400, detail=str(e))
    username = repos.use_password_reset(auth.token_digest(token), password_hash) if token else None
    if not username:
        raise HTTPException(status_code=400, detail="invalid or expired link")
    return {"ok": True, "username": username}


_RESET_PAGE = _BACKEND_DIR / "pages" / "redefinir-senha.html"


@app.get("/redefinir-senha", response_class=HTMLResponse, include_in_schema=False)
def reset_password_page():
    return HTMLResponse(_RESET_PAGE.read_text(encoding="utf-8"))


_PRIVACY_PAGE = _BACKEND_DIR / "pages" / "privacidade.html"


@app.get("/privacidade", response_class=HTMLResponse, include_in_schema=False)
def privacy_page():
    """The privacy policy, at the public URL the Play Store listing points to."""
    return HTMLResponse(_PRIVACY_PAGE.read_text(encoding="utf-8"))


# Public page for deleting an account without the app, which the Play Store
# requires to exist at a URL of its own.
_DELETE_ACCOUNT_PAGE = _BACKEND_DIR / "pages" / "excluir-conta.html"


@app.get("/excluir-conta", response_class=HTMLResponse, include_in_schema=False)
def delete_account_page():
    return HTMLResponse(_DELETE_ACCOUNT_PAGE.read_text(encoding="utf-8"))


@app.get("/user")
def user_state(username: str = Depends(current_username)):
    data = _load_user(username)
    metadata = data.get("metadata", {}) or {}
    marks = int(data.get("marks", 0) or 0)
    progression = _progression_state(marks)
    user_leaf_scores = repos.get_user_leaf_scores(username)
    active_attrs = [s for s in user_leaf_scores.values() if s["marks"] > 0 or s["rank_index"] > 0]
    bonuses = aggregate_bonuses(set(data.get("skills") or []), skill_nodes_by_id())
    base_max_tokens = int(metadata.get("max_tokens", BASE_MAX_TOKENS) or BASE_MAX_TOKENS)
    base_max_energy = journey_mode.BASE_MAX_ENERGY
    seq = _ensure_sequences(username)
    ident = social_repo.identity(username)
    return {
        "username": metadata.get("username") or data.get("username"),
        "date": metadata.get("date"),
        "day": _day_number(username),
        "consecutive_days": int(seq.get("consecutive_days", 0) or 0),
        "marks": marks,
        "level": progression["level"],
        "rank_letter": progression["rank_letter"],
        "rank_name": progression["rank_name"],
        "rank_symbol": progression["rank_symbol"],
        "local_level_roman": progression["local_level_roman"],
        "local_levels_total": progression["local_levels_total"],
        "next_marks": progression["next_marks"],
        "level_cost": progression["level_cost"],
        "level_marks": progression["level_marks"],
        "stage": int(metadata.get("stage", 1) or 1),
        "energy": int(metadata.get("energy", 0) or 0),
        "max_energy": _max_energy(data, username),
        "skill_points": int(metadata.get("skill_points", 0) or 0),
        "build_points": int(metadata.get("build_points", 0) or 0),
        "points": int(metadata.get("build_points", 0) or 0),
        "tokens": int(metadata.get("tokens", 0) or 0),
        "max_tokens": base_max_tokens + bonuses["max_tokens"],
        "checkpoint_seconds_left": journey_mode.view(metadata, datetime.now(), base_max_energy)["seconds_left"],
        "attributes_count": len(active_attrs),
        "bonuses": bonuses,
        "nickname": ident["nickname"],
        "passcode": ident["passcode"],
        # every act ever logged: the interface reveals itself as this grows
        "acts": social_repo.count_logs(username),
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


def _agenda_call(fn, *args):
    """Runs an agenda_repo call, its refusals turned into HTTP errors."""
    try:
        return fn(*args)
    except agenda_repo.AgendaError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@app.get("/projects")
def projects_all(username: str = Depends(current_username)):
    """Running projects with their stats, then the emblems."""
    return {"items": _agenda_call(agenda_repo.list_projects, username)}


@app.post("/projects")
def projects_add(payload: dict, username: str = Depends(current_username)):
    """Body: {name, deadline?}. A project starts active."""
    p = payload or {}
    project = _agenda_call(agenda_repo.create_project, username, p.get("name"), p.get("deadline"))
    return {**project, "lines": _engine_event(username, {"kind": "plan"})}


@app.patch("/projects/{item_id}")
def projects_update(item_id: str, payload: dict, username: str = Depends(current_username)):
    """Body: {name?, deadline?, active?}."""
    return _agenda_call(agenda_repo.update_project, username, item_id, payload or {})


@app.post("/projects/{item_id}/end")
def projects_end(item_id: str, username: str = Depends(current_username)):
    """Ends it as an emblem: completed when all its to-dos are done, finished
    otherwise."""
    return _agenda_call(agenda_repo.end_project, username, item_id)


@app.delete("/projects/{item_id}")
def projects_remove(item_id: str, username: str = Depends(current_username)):
    _agenda_call(agenda_repo.delete_project, username, item_id)
    return {"ok": True}


@app.get("/emblems")
def emblems(username: str = Depends(current_username)):
    """The projects that ended, each an emblem with the stats it ended on."""
    return [p for p in _agenda_call(agenda_repo.list_projects, username) if p["emblem"]]


@app.get("/todos")
def todos_all(username: str = Depends(current_username)):
    """Open to-dos by deadline, then the done ones. Each action says whether it
    was acted on since the to-do was made."""
    return {"items": _agenda_call(agenda_repo.list_todos, username)}


@app.post("/todos")
def todos_add(payload: dict, username: str = Depends(current_username)):
    """Body: {title, action_ids, deadline?, project_id?}."""
    p = payload or {}
    todo = _agenda_call(agenda_repo.create_todo, username, p.get("title"), p.get("action_ids") or [],
                        p.get("deadline"), p.get("project_id"))
    return {**todo, "lines": _engine_event(username, {"kind": "plan"})}


@app.patch("/todos/{todo_id}")
def todos_update(todo_id: int, payload: dict, username: str = Depends(current_username)):
    """Body: {title?, deadline?, project_id?, action_ids?}."""
    return _agenda_call(agenda_repo.update_todo, username, todo_id, payload or {})


@app.post("/todos/{todo_id}/done")
def todos_done(todo_id: int, username: str = Depends(current_username)):
    """Closes it by hand and pays points for the actions it holds. Done late
    shows as late and pays the same."""
    data = _load_user(username)
    todo = _agenda_call(agenda_repo.complete_todo, username, todo_id, todo_reward)
    metadata = data.setdefault("metadata", {})
    metadata["build_points"] = int(metadata.get("build_points", 0) or 0) + todo["reward"]
    _save_user(username, data)
    return {**todo, "points": metadata["build_points"]}


@app.delete("/todos/{todo_id}")
def todos_remove(todo_id: int, username: str = Depends(current_username)):
    _agenda_call(agenda_repo.delete_todo, username, todo_id)
    return {"ok": True}


def _logs_on(username: str, target_date) -> tuple[int, list[dict]]:
    """The day number of `target_date` and its logs, in their order."""
    target_day = _day_for(username, target_date)
    result = []
    for log in repos.load_logs(username):
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
            "marks": int(log.get("marks", 0) or 0),
            "tokens": int(log.get("tokens", 0) or 0),
            "order": int(coord[1]),
            "period": log.get("period"),
        })
    result.sort(key=lambda l: l.get("order", 0))
    return target_day, result


def _iso_day(raw) -> "datetime.date":
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")


@app.get("/agenda/day")
def agenda_day(offset: int = 0, username: str = Depends(current_username)):
    """A day's records: its logs, each with its thought, the thought of the day,
    and how far the day's cycle went — act, to-do, a thought on every act, the
    thought of the day. The to-do is the one step the cycle can skip."""
    _load_user(username)
    target = (datetime.now() + timedelta(days=offset)).date()
    day, logs = _logs_on(username, target)
    thoughts = _agenda_call(agenda_repo.thoughts_on, username, target)
    by_log = {t["log_id"]: t for t in thoughts if t["log_id"] is not None}
    day_thought = next((t for t in thoughts if t["log_id"] is None), None)
    for log in logs:
        log["thought"] = by_log.get(log["id"])
    thought_count = sum(1 for log in logs if log["thought"])
    todos = _agenda_call(agenda_repo.todos_done_on, username, target)
    return {
        "date": target.isoformat(),
        "offset": offset,
        "day": day,
        "logs": logs,
        "day_thought": day_thought,
        "cycle": {
            "acted": bool(logs),
            "todo": todos > 0,
            "todos_done": todos,
            "thoughts": thought_count,
            "logs": len(logs),
            "day_thought": day_thought is not None,
            "complete": bool(logs) and thought_count == len(logs) and day_thought is not None,
        },
    }


@app.put("/thoughts")
def put_thought(payload: dict, username: str = Depends(current_username)):
    """Body: {date, log_id?, content}. The thought of a log, or of the day
    without `log_id`; empty content takes it away."""
    p = payload or {}
    day = _iso_day(p.get("date"))
    log_id = p.get("log_id")
    if log_id is not None:
        day_num, logs = _logs_on(username, day)
        if not any(int(l["id"]) == int(log_id) for l in logs):
            raise HTTPException(status_code=404, detail=f"log {log_id} not on {day.isoformat()}")
    thought = _agenda_call(agenda_repo.set_thought, username, day, int(log_id) if log_id is not None else None,
                           str(p.get("content") or ""))
    lines = _engine_event(username, {"kind": "plan"}) if str(p.get("content") or "").strip() else []
    return {"thought": thought, "lines": lines}


_WEEKDAYS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")
_MONTHS = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
           "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")


@app.get("/journal")
def journal(date: str, username: str = Depends(current_username)):
    """A day as the plain-text journal writes it: the summary (`ddmm` and the
    first and last log times, then one line per log under its period, its
    thought after a dash) and the dated entry with the thought of the day."""
    target = _iso_day(date)
    _day, logs = _logs_on(username, target)
    thoughts = _agenda_call(agenda_repo.thoughts_on, username, target)
    by_log = {t["log_id"]: t["content"] for t in thoughts if t["log_id"] is not None}
    day_thought = next((t["content"] for t in thoughts if t["log_id"] is None), "")

    def clock(log) -> str:
        try:
            return datetime.strptime(log["timestamp"], "%d %m %Y : %H:%M:%S").strftime("%H%M")
        except (TypeError, ValueError):
            return "0000"

    lines = []
    if logs:
        lines.append(f"{target.strftime('%d%m')} {clock(logs[0])} {clock(logs[-1])}")
        for log in logs:
            text = str(log["content"] or "").lower()
            if log["id"] in by_log:
                text += f" - {by_log[log['id']]}"
            lines.append(f" {log.get('period') or 'mo'} {text}")
    summary = "\n".join(lines)
    heading = f"{_WEEKDAYS[target.weekday()]}, {target.day} de {_MONTHS[target.month - 1]}"
    entry = f"{heading}\n{day_thought}" if day_thought else ""
    return {"date": target.isoformat(), "summary": summary, "entry": entry,
            "text": "\n\n".join(x for x in (summary, entry) if x)}


@app.get("/agenda")
def agenda_all(username: str = Depends(current_username)):
    return {"items": Agenda(username).items}


@app.post("/agenda")
def agenda_add(payload: dict, username: str = Depends(current_username)):
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
def calendar(year: int, month: int, username: str = Depends(current_username)):
    """Returns per-date stats for a given month: log counts and special events."""
    from datetime import date as _date, timedelta
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
def logs_by_date(date: str, username: str = Depends(current_username)):
    """Returns logs whose attribution date matches the given ISO date."""
    from datetime import datetime as _dt, timedelta
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
            "marks": int(log.get("marks", 0) or 0),
            "tokens": int(log.get("tokens", 0) or 0),
            "order": int(coord[1]),
            "period": log.get("period"),
        })
    result.sort(key=lambda l: l.get("order", 0))
    return {"date": date, "day": target_day, "logs": result}


@app.patch("/agenda/{item_id}")
def agenda_update(item_id: str, payload: dict, username: str = Depends(current_username)):
    return Agenda(username).update(item_id, payload or {})


@app.delete("/agenda/{item_id}")
def agenda_remove(item_id: str, username: str = Depends(current_username)):
    ok = Agenda(username).remove(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True}
@app.get("/skills/tree")
def skills_tree(username: str = Depends(current_username)):
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
def acquire_skill(skill_id: str, username: str = Depends(current_username)):
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
    """The same groups as `/shop/packages`, each action with the leaves it feeds.

    A log action lists none: it is logged, not trained.
    """
    tree = repos.load_attr_tree()
    contributions = repos.load_all_contributions()

    result = []
    for pkg in load_packages():
        actions = [
            {**action, "package_attribute": pkg.get("attribute"), "leaves": _leaves_of(action, tree, contributions)}
            for action in pkg.get("actions", []) or []
        ]
        result.append({"key": pkg.get("attribute"), "name": pkg.get("name"), "actions": actions})
    return result


def _leaves_of(action: dict, tree, contributions: dict) -> list[dict]:
    """The leaves a catalog action feeds, with their weights."""
    contribs = contributions.get(str(action.get("name", "")).upper(), [])
    return [
        {"key": leaf_key, "name": tree.nodes_by_key[leaf_key].name, "weight": w}
        for leaf_key, w in contribs if leaf_key in tree.nodes_by_key
    ]


def _discovery_state(username: str, data: dict, now: datetime) -> dict:
    """Where the profile stands in discovering the catalog today."""
    metadata = data.get("metadata", {}) or {}
    found = social_repo.load_discoveries(username)
    today = now.date().isoformat()
    used = int(metadata.get("discover_used", 0) or 0) if metadata.get("discover_date") == today else 0
    before = max(0, len(found) - used)
    return {
        "found": found,
        "used": used,
        "phase": discovery.phase(before),
        "rate": discovery.rate(before),
        # nothing found before today: the first day, which opens a few more
        "left": discovery.left_today(before, used, all(at.date() == now.date() for at in found.values())),
    }


def _affinity(username: str, templates: dict) -> dict[str, float]:
    """How much the profile uses what each catalog action trains: the marks of
    the root it falls under, against the profile's best root."""
    tree = repos.load_attr_tree()
    totals = _user_leaf_totals(username, tree)
    memo: dict[str, float] = {}
    roots = {r: node_total(r, totals, tree, memo) for r in tree.roots}
    best = max(roots.values(), default=0) or 0
    if best <= 0:
        return {}
    out = {}
    for name, meta in templates.items():
        parent = meta.get("parent")
        if parent and parent in tree.nodes_by_key:
            out[name] = roots.get(tree.root_of(parent), 0) / best
    return out


def _discover(username: str, data: dict, now: datetime, count: int) -> list[str]:
    """Opens up to `count` of today's discoveries. Returns the names found."""
    state = _discovery_state(username, data, now)
    count = min(count, state["left"])
    if count <= 0:
        return []
    templates = repos.load_action_templates()
    hidden = [n for n in templates if n not in state["found"]]
    names = discovery.draw(random.Random(), hidden, _affinity(username, templates), count)
    if names:
        social_repo.add_discoveries(username, names)
        metadata = data.setdefault("metadata", {})
        metadata["discover_date"] = now.date().isoformat()
        metadata["discover_used"] = state["used"] + len(names)
        _save_user(username, data)
    return names


def _shop_view(username: str, data: dict, now: datetime, new: list[str]) -> dict:
    state = _discovery_state(username, data, now)
    owned = {str(a.get("name", "")).upper() for a in (data.get("actions") or {}).values() if not a.get("deleted")}
    tree = repos.load_attr_tree()
    contributions = repos.load_all_contributions()
    groups = []
    for pkg in load_packages():
        actions = [
            {**a, "package_attribute": pkg["attribute"], "owned": a["name"] in owned, "new": a["name"] in new,
             "leaves": _leaves_of(a, tree, contributions)}
            for a in pkg.get("actions", []) if a["name"] in state["found"]
        ]
        if actions:
            groups.append({"key": pkg["attribute"], "name": pkg["name"], "actions": actions})
    return {
        "phase": state["phase"],
        "rate": state["rate"],
        "left": state["left"],
        "found": len(state["found"]),
        "catalog": len(repos.load_action_templates()),
        "points": int((data.get("metadata") or {}).get("build_points", 0) or 0),
        "new": new,
        "groups": groups,
    }


_STORY_OFFER = 3


def _story_shop(username: str, data: dict) -> bool:
    """While the story asks for a purchase — or for an act on one, and the
    profile owns nothing it chose — the shop must hold something it can buy,
    whatever the day's discoveries and the points left say: when nothing found
    is unowned, a few cheap actions are found for it, and when the cheapest of
    them costs more than it has, the points are made up to it. Returns whether
    the profile changed."""
    state, _code = engine_repo.load(username)
    step = state.get("story")
    if step not in ("buy", "prove"):
        return False
    templates = repos.load_action_templates()
    owned = {str(a.get("name", "")).upper() for a in (data.get("actions") or {}).values() if not a.get("deleted")}
    if step == "prove" and owned - set(state.get("given") or {}):
        return False
    found = social_repo.load_discoveries(username)
    buyable = [n for n in found if n in templates and n not in owned and not templates[n]["log_only"]]
    if not buyable:
        pool = sorted((n for n, m in templates.items()
                       if n not in owned and n not in found and not m["log_only"] and m["code"]),
                      key=lambda n: templates[n]["cost"])
        if not pool:
            return False
        cheap = [n for n in pool if templates[n]["cost"] <= max(500, templates[pool[0]]["cost"])]
        buyable = random.Random().sample(cheap, min(_STORY_OFFER, len(cheap)))
        social_repo.add_discoveries(username, buyable)
    metadata = data.setdefault("metadata", {})
    cheapest = min(templates[n]["cost"] for n in buyable)
    if int(metadata.get("build_points", 0) or 0) < cheapest:
        metadata["build_points"] = cheapest
        _save_user(username, data)
    return True


@app.get("/shop")
def shop(username: str = Depends(current_username)):
    """The profile's shop: only what it discovered, grouped by practice, each
    action with its author and whether it is owned. In the `auto` phase the
    day's discoveries open on their own here. While the story asks for a
    purchase there is always one within reach (`_story_shop`). See
    src.domain.discovery."""
    data = _load_user(username)
    if _story_shop(username, data):
        data = _load_user(username)
    now = datetime.now()
    new = _discover(username, data, now, discovery.MAX_RATE * 2) if _discovery_state(username, data, now)["phase"] == "auto" else []
    return _shop_view(username, data, now, new)


@app.post("/shop/discover")
def shop_discover(username: str = Depends(current_username)):
    """Opens discoveries: one frame of static in the `frames` phase, all of
    today's at once after it."""
    data = _load_user(username)
    now = datetime.now()
    state = _discovery_state(username, data, now)
    if state["left"] <= 0:
        raise HTTPException(status_code=409, detail="no discoveries left today")
    new = _discover(username, data, now, 1 if state["phase"] == "frames" else state["left"])
    return _shop_view(username, data, now, new)


def _owned_action(action_id: str, name: str, template: dict) -> dict:
    """An action of the catalog as a profile holds it, never acted on."""
    return {
        "id": action_id,
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
        "token_gain": int(template.get("token_gain", 0) or 0),
    }


@app.post("/shop/actions/buy")
def buy_action(payload: dict, username: str = Depends(current_username)):
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
    if name not in social_repo.load_discoveries(username):
        raise HTTPException(status_code=403, detail=f"action '{name}' not discovered yet")

    cost = int(template.get("cost", 0))
    metadata = data.setdefault("metadata", {})
    bp = int(metadata.get("build_points", 0) or 0)
    if bp < cost:
        raise HTTPException(status_code=400, detail=f"insufficient points (have {bp}, need {cost})")

    actions = data.setdefault("actions", {})
    if any(str(a.get("name", "")).upper() == name and not a.get("deleted") for a in actions.values()):
        raise HTTPException(status_code=409, detail=f"action '{name}' already exists")

    # The id is the catalog code, the same for every profile. It is never
    # generated here, so it cannot drift from what the shop shows.
    new_id = template.get("code")
    if not new_id:
        raise HTTPException(status_code=500, detail=f"action '{name}' has no catalog code")
    if new_id in actions:
        raise HTTPException(status_code=409, detail=f"action '{name}' already exists")
    actions[new_id] = _owned_action(new_id, name, template)

    # Attribute scoring is now driven by the action_contributions tree (DB-side),
    # not the legacy per-user attribute table. No attribute row created on buy.

    metadata["build_points"] = bp - cost

    _save_user(username, data)

    return {"id": new_id, "name": name, "build_points": metadata["build_points"], "points": metadata["build_points"],
            "lines": _engine_event(username, {"kind": "buy", "name": name})}


def _day_for(username: str, date_obj) -> int:
    return repos.day_for_user(username, date_obj)


@app.post("/logs/reorder")
def reorder_logs(payload: dict, username: str = Depends(current_username)):
    """Body: {day: int, ids: [int, ...]}. Sets coord[1] of each id to its new 1-based index within day."""
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


def _legacy_undo(username: str, data: dict, log: dict) -> dict | None:
    """What an act changed, rebuilt for a log written before `logs.undo`: the
    action from the log's name, its mark event from the time and the marks, the
    leaves from the action's contributions. None when the action is gone."""
    from src.domain.user_attributes import children_of, reached_leaves

    head = str(log.get("content") or "").split(" : ")[0]
    name = re.sub(r"\s*\[[^\]]*\]\s*$", "", head).strip().upper()
    actions = data.get("actions") or {}
    action_id = next((i for i, a in actions.items()
                      if str(a.get("name", "")).upper() == name and not a.get("deleted")), None)
    if not action_id:
        return None
    action = actions[action_id]
    marks = int(log.get("marks", 0) or 0)
    at = repos._parse_log_dt(log.get("timestamp")) or datetime.now()
    templates = repos.load_action_templates()
    engine = engine_name(actions, action)
    log_only = bool((templates.get(engine) or {}).get("log_only"))
    leaves, custom = {}, {}
    if not log_only and marks > 0:
        leaves = {str(lid): marks * float(w) for lid, _k, w in repos.load_action_contributions(engine)}
        links = repos.load_patch_links(username).get(action_id) or {}
        if links:
            attrs = repos.load_user_attributes(username)
            by_id = {a["id"] for a in attrs}
            reached = reached_leaves({a: w for a, w in links.items() if a in by_id}, children_of(attrs))
            custom = {str(i): marks * w for i, w in reached.items()}
    return {
        "action_id": action_id,
        "mark_event_id": repos.find_mark_event(username, action_id, at, marks),
        "marks": marks,
        "log_only": log_only,
        "tokens": int(log.get("tokens", 0) or 0),
        "energy": ENERGY_PENALTY_OUT_OF_AGENDA,
        "leaves": leaves,
        "custom": custom,
    }


@app.delete("/logs/{log_id}")
def delete_log(log_id: int, username: str = Depends(current_username)):
    """Deletes a log and takes back what its act gave: the marks on the action,
    on the profile and on every attribute (ranks included), the mark event that
    filled the 6-hour window, the tokens it moved and the hp it cost. The answer's
    `reverted` says what was taken back; it is null for a log no act wrote."""
    log = next((l for l in repos.load_logs(username) if int(l.get("id", -1)) == int(log_id)), None)
    if log is None:
        raise HTTPException(status_code=404, detail=f"log {log_id} not found")
    data = _load_user(username)
    undo = log.get("undo") or _legacy_undo(username, data, log)
    reverted = None
    if undo:
        metadata = data.setdefault("metadata", {})
        marks = int(undo.get("marks", 0) or 0)
        action = (data.get("actions") or {}).get(undo.get("action_id"))
        if action:
            action["value"] = max(0.0, float(action.get("value", 0) or 0) - 1)
            action["score"] = max(0.0, float(action.get("score", 0) or 0) - marks)
        if not undo.get("log_only"):
            data["marks"] = max(0, int(data.get("marks", 0) or 0) - marks)
        tokens = int(undo.get("tokens", 0) or 0)
        if tokens:
            metadata["tokens"] = int(metadata.get("tokens", 0) or 0) - tokens
        energy = int(undo.get("energy", 0) or 0)
        if energy:
            metadata["energy"] = min(_max_energy(data, username), int(metadata.get("energy", 0) or 0) + energy)
        _save_user(username, data)
        touched = repos.take_back_marks(
            username, undo.get("mark_event_id"),
            {int(k): float(v) for k, v in (undo.get("leaves") or {}).items()},
            {int(k): float(v) for k, v in (undo.get("custom") or {}).items()},
        )
        reverted = {
            "marks": marks,
            "tokens": -tokens,
            "energy": energy,
            "user_marks": int(data.get("marks", 0) or 0),
            "balance": int(metadata.get("tokens", 0) or 0),
            "leaves": sorted(touched["leaves"], key=lambda l: -l["marks"]),
            "custom": sorted(touched["custom"], key=lambda l: -l["marks"]),
        }
    removed = repos.delete_log(username, int(log_id))
    if removed is not None:
        removed.pop("undo", None)
    return {"ok": True, "id": int(log_id), "removed": removed, "reverted": reverted}


@app.patch("/logs/{log_id}")
def update_log(log_id: int, payload: dict, username: str = Depends(current_username)):
    """Body: {note?: str, content?: str, day_delta?: int, period?: str}."""

    if "period" in payload:
        period = _period(payload.get("period"))
        if period is None:
            raise HTTPException(status_code=400, detail="period required")
        updated = repos.set_log_period(username, int(log_id), period)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"log {log_id} not found")
        return updated

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
def list_logs(offset: int = 0, username: str = Depends(current_username)):
    """offset: 0 = today, -1 = yesterday, +1 = tomorrow."""
    target_date = (datetime.now() + timedelta(days=offset)).date()
    target_day, result = _logs_on(username, target_date)
    return {"day": target_day, "offset": offset, "date": target_date.isoformat(), "logs": result}


@app.get("/agenda/today")
def agenda_today(username: str = Depends(current_username)):
    day_name = _DAY_NAMES[datetime.now().weekday()]
    items = Agenda(username).for_day(day_name)
    return {"day": day_name, "items": items}


def _user_leaf_totals(username: str, tree) -> dict[str, float]:
    """Every leaf's total marks: what its rank took plus the marks above it."""
    return _user_leaf_totals_from(repos.get_user_leaf_scores(username), tree)


def _node_view(tree, key: str, totals: dict[str, float], memo: dict,
               claims: dict[str, int] | None = None) -> dict:
    """What every attribute endpoint says about one node, leaf or not. With
    `claims`, also how many of its ranks wait to be claimed and what they pay."""
    node = tree.nodes_by_key[key]
    out = {
        "key": key,
        "name": node.name,
        "degree": tree.degree(key),
        "star": tree.star(key),
        "is_leaf": tree.is_leaf(key),
        **rank_view(node_total(key, totals, tree, memo)),
    }
    if claims is not None:
        n = claimable_ranks(out["rank_index"], claims.get(key, 0), out["degree"])
        if n:
            out["claim"] = {
                "ranks": n,
                "tokens": n * CLAIM_TOKENS_PER_RANK,
                "points": n * CLAIM_POINTS_PER_RANK,
                "skill_points": n * CLAIM_SKILL_POINTS_PER_RANK,
            }
    return out


@app.post("/attributes/{key}/claim")
def claim_rank(key: str, username: str = Depends(current_username)):
    """Take the reward of every rank `key` reached and was not claimed yet:
    tokens, capped like an act's, points and skill points."""
    data = _load_user(username)
    tree = repos.load_attr_tree()
    if key not in tree.nodes_by_key:
        raise HTTPException(status_code=404, detail=f"attribute '{key}' not found")
    claims = repos.load_rank_claims(username)
    view = _node_view(tree, key, _user_leaf_totals(username, tree), {}, claims)
    claim = view.get("claim")
    if not claim:
        raise HTTPException(status_code=409, detail="nothing to claim")

    metadata = data.setdefault("metadata", {})
    bonuses = aggregate_bonuses(set(data.get("skills") or []), skill_nodes_by_id())
    cap = int(metadata.get("max_tokens", BASE_MAX_TOKENS) or BASE_MAX_TOKENS) + int(bonuses.get("max_tokens", 0) or 0)
    tokens = int(metadata.get("tokens", 0) or 0)
    gained = max(0, min(claim["tokens"], cap - tokens))
    metadata["tokens"] = tokens + gained
    metadata["skill_points"] = int(metadata.get("skill_points", 0) or 0) + claim["skill_points"]
    metadata["build_points"] = int(metadata.get("build_points", 0) or 0) + claim["points"]
    _save_user(username, data)
    repos.set_rank_claim(username, key, view["rank_index"])
    return {
        "key": key,
        "ranks": claim["ranks"],
        "tokens_gained": gained,
        "tokens_wasted": claim["tokens"] - gained,
        "skill_points_gained": claim["skill_points"],
        "points_gained": claim["points"],
        "points": metadata["build_points"],
        "tokens": metadata["tokens"],
        "skill_points": metadata["skill_points"],
    }


def _recent_attributes(tree, leaf_scores: dict, user_attrs: list[dict], limit: int, now: datetime) -> list[dict]:
    """Leaves holding marks, newest update first: the graph's and the user's own
    (`custom`). Only leaves store marks, so only a leaf has an update time."""
    from src.domain.user_attributes import children_of

    totals = _user_leaf_totals_from(leaf_scores, tree)
    memo: dict[str, float] = {}
    rows: list[tuple[datetime, dict]] = []
    for key, total in totals.items():
        if total <= 0:
            continue
        parent = tree.primary_parent.get(key)
        item = _node_view(tree, key, totals, memo)
        item["parent"] = tree.nodes_by_key[parent].name if parent else None
        rows.append((leaf_scores[key]["last_updated_at"], item))

    by_id = {a["id"]: a for a in user_attrs}
    kids = children_of(user_attrs)
    for a in user_attrs:
        total = total_marks(a["marks"], a["rank_index"])
        if kids.get(a["id"]) or total <= 0:
            continue
        parent = by_id.get(a["parent_id"])
        rows.append((a["last_updated_at"], {
            "key": f"user:{a['id']}",
            "name": a["name"],
            "degree": 0,
            "is_leaf": True,
            **rank_view(total),
            "custom": True,
            "parent": parent["name"] if parent else None,
        }))

    rows.sort(key=lambda r: r[0], reverse=True)
    # measured here, so the browser's clock and zone never enter it
    return [{**item, "seconds_ago": max(0, int((now - at).total_seconds()))} for at, item in rows[:limit]]


def _user_leaf_totals_from(leaf_scores: dict, tree) -> dict[str, float]:
    return {
        key: total_marks(row["marks"], row["rank_index"])
        for key, row in leaf_scores.items()
        if key in tree.leaves_by_key
    }


def _action_path(tree, templates: dict, actions: dict, action: dict) -> list[dict]:
    """Root first, the primary chain down to the attribute an action is registered
    under — a patch's is its base's. Empty for an action without a template."""
    parent = (templates.get(engine_name(actions, action)) or {}).get("parent")
    if not parent or parent not in tree.nodes_by_key:
        return []
    return [{"key": k, "name": tree.nodes_by_key[k].name} for k in tree.primary_chain(parent)]


@app.get("/attributes")
def list_attributes(username: str = Depends(current_username)):
    """Every leaf — the attributes that hold marks — with its rank."""
    _load_user(username)
    tree = repos.load_attr_tree()
    totals = _user_leaf_totals(username, tree)
    memo: dict[str, float] = {}
    out = [_node_view(tree, k, totals, memo) for k in tree.leaves_by_key]
    out.sort(key=lambda a: a["total_marks"], reverse=True)
    return out


@app.get("/attributes/roots")
def attribute_roots(username: str = Depends(current_username)):
    """Every root with its power and aggregated level. Replaces the separate
    tag and conceptual-root views: those are ordinary attributes now."""
    _load_user(username)
    tree = repos.load_attr_tree()
    totals = _user_leaf_totals(username, tree)
    memo: dict[str, float] = {}
    return [_node_view(tree, r, totals, memo) for r in tree.roots]


@app.get("/attributes/recent")
def recent_attributes(limit: int = 10, username: str = Depends(current_username)):
    """The leaves that most recently gained marks, the user's own included, newest
    first, each with `parent` and `seconds_ago`."""
    _load_user(username)
    return _recent_attributes(
        repos.load_attr_tree(),
        repos.get_user_leaf_scores(username),
        repos.load_user_attributes(username),
        max(1, min(limit, 50)),
        datetime.now(),
    )


@app.get("/attributes/tree")
def attributes_tree(username: str = Depends(current_username)):
    """The whole graph from its roots. Each child carries the link `weight` and
    whether it is the node's `primary` parent — a node with several parents shows
    up under each of them. A node that is the registered parent of a base action
    with patches lists them in `patches`, with their own attributes; they are
    display only and never enter the node's marks."""
    data = _load_user(username)
    tree = repos.load_attr_tree()
    totals = _user_leaf_totals(username, tree)
    memo: dict[str, float] = {}
    attachments = _patch_attachments(username, data)
    claims = repos.load_rank_claims(username)

    def render(key: str, path: frozenset) -> dict:
        out = _node_view(tree, key, totals, memo, claims)
        if key in attachments:
            out["patches"] = attachments[key]
        if key in path:            # registration refuses cycles; never recurse forever
            return out
        kids = []
        for child, weight in tree.children.get(key, []):
            view = render(child, path | {key})
            view["weight"] = weight
            view["primary"] = tree.primary_parent.get(child) == key
            kids.append(view)
        if kids:
            out["children"] = kids
        return out

    return {"roots": [render(r, frozenset()) for r in tree.roots]}


def _patch_attachments(username: str, data: dict) -> dict[str, list[dict]]:
    """{node_key: [patch, ...]} — each patch sits where its base action would, under
    the base's registered parent."""
    from src.domain.user_attributes import children_of, view

    links = repos.load_patch_links(username)
    if not links:
        return {}
    actions = data.get("actions") or {}
    templates = repos.load_action_templates()
    attrs = repos.load_user_attributes(username)
    by_id = {a["id"]: a for a in attrs}
    kids = children_of(attrs)
    memo: dict = {}
    out: dict[str, list[dict]] = {}
    for patch_id in sorted(links):
        patch = actions.get(patch_id)
        if not patch or patch.get("deleted") or not patch.get("base_action_id"):
            continue
        base = actions.get(patch["base_action_id"]) or {}
        parent = (templates.get(base.get("name", "")) or {}).get("parent")
        if not parent:
            continue
        out.setdefault(parent, []).append({
            "id": patch_id,
            "name": patch.get("name"),
            "attributes": [view(i, by_id, kids, memo) for i in links[patch_id] if i in by_id],
        })
    return out


@app.get("/user-attributes")
def list_user_attributes(username: str = Depends(current_username)):
    """The user's own attributes as a tree, each with rank, marks and the patches
    that train it, at the weight of their link."""
    from src.domain.user_attributes import children_of, view

    data = _load_user(username)
    actions = data.get("actions") or {}
    attrs = repos.load_user_attributes(username)
    trained_by: dict[int, list[dict]] = {}
    for patch_id, weights in repos.load_patch_links(username).items():
        patch = actions.get(patch_id)
        if not patch or patch.get("deleted"):
            continue
        for i, weight in weights.items():
            trained_by.setdefault(i, []).append({"id": patch_id, "name": patch.get("name"), "weight": weight})

    by_id = {a["id"]: a for a in attrs}
    kids = children_of(attrs)
    memo: dict = {}

    def with_patches(v: dict) -> dict:
        v["patches"] = trained_by.get(v["id"], [])
        for c in v["children"]:
            with_patches(c)
        return v

    return [with_patches(view(r["id"], by_id, kids, memo)) for r in kids.get(None, [])]


@app.get("/attribute-suggestions")
def attribute_suggestions():
    """Names the interface can offer when the user creates an attribute: the ISCED-F
    fields of education and the O*NET skills, adapted to Portuguese.

    This is not the attribute graph and never becomes it — nothing user-created can
    feed `attr_nodes`. Picking one creates an ordinary user attribute with that text.
    Static and the same for everyone, so no token, like `/shop/packages`.
    """
    return load_attribute_suggestions()


@app.post("/user-attributes")
def post_user_attribute(payload: dict, username: str = Depends(current_username)):
    """Body: {name, parent_id?} or {path: [...]}. Free. Under a parent, the new
    attribute starts so that the parent keeps its value.

    `path` is a suggestion's whole chain — ["Ciências naturais", "Física"]: each
    level the user already has by that name is reused where it is, the rest is
    created, and the answer's `chain` says which was which."""
    p = payload or {}
    try:
        if p.get("path") is not None:
            return repos.create_user_attribute_path(username, p["path"])
        return repos.create_user_attribute(username, p.get("name", ""), _attribute_id(p.get("parent_id")))
    except PatchError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


def _attribute_id(raw) -> int | None:
    """A user attribute id from a request body; None for none."""
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail=f"attribute {raw!r} not found")


@app.patch("/user-attributes/{attr_id}")
def patch_user_attribute(attr_id: int, payload: dict, username: str = Depends(current_username)):
    """Body: {name?, parent_id?}. Renames it, or moves it with its marks under
    another attribute — null for a root. A leaf holding marks takes no children,
    and a parent left without children keeps its total."""
    p = payload or {}
    if "name" not in p and "parent_id" not in p:
        raise HTTPException(status_code=400, detail="give name or parent_id")
    try:
        out: dict = {}
        if "name" in p:
            out = repos.rename_user_attribute(username, attr_id, p["name"])
        if "parent_id" in p:
            out = repos.move_user_attribute(username, attr_id, _attribute_id(p["parent_id"]))
        return out
    except PatchError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@app.post("/patches")
def post_patch(payload: dict, username: str = Depends(current_username)):
    """Body: {base_action_id, name, attribute_ids, new_attributes}. Costs the base's
    price in points; the id is the base's id plus the lowest free two digits.

    An entry of `new_attributes` is a name, `{name, parent_id}`, or `{path: [...]}`
    for a suggestion's whole chain — all created in the same transaction as the
    patch, so a payment that fails leaves no attribute behind."""
    p = payload or {}
    _load_user(username)  # run any due daily tick before the patch is written
    try:
        return repos.create_patch(
            username,
            str(p.get("base_action_id", "")).strip(),
            p.get("name", ""),
            p.get("attribute_ids") or [],
            p.get("new_attributes") or [],
        )
    except PatchError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@app.patch("/patches/{patch_id}")
def patch_patch(patch_id: str, payload: dict, username: str = Depends(current_username)):
    """Body: {name?, attribute_ids?}. Renames it, or replaces the attributes it
    trains: a kept link keeps its weight, a new one starts at 1, and a dropped
    attribute stops receiving its marks."""
    p = payload or {}
    if "name" not in p and "attribute_ids" not in p:
        raise HTTPException(status_code=400, detail="give name or attribute_ids")
    if "attribute_ids" in p and not isinstance(p["attribute_ids"], list):
        raise HTTPException(status_code=400, detail="attribute_ids must be a list")
    try:
        out: dict = {}
        if "name" in p:
            out = repos.rename_patch(username, patch_id, p["name"])
        if "attribute_ids" in p:
            out = {**out, **repos.set_patch_attributes(username, patch_id, p["attribute_ids"])}
        return out
    except PatchError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@app.put("/patches/{patch_id}/attributes/{attr_id}")
def put_patch_link(patch_id: str, attr_id: int, payload: dict, username: str = Depends(current_username)):
    """Body: {weight}. The share of the patch's marks this attribute receives, above
    0 and at most 1."""
    try:
        return repos.set_patch_link_weight(username, patch_id, attr_id, (payload or {}).get("weight"))
    except PatchError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@app.delete("/patches/{patch_id}/attributes/{attr_id}")
def delete_patch_link(patch_id: str, attr_id: int, username: str = Depends(current_username)):
    """The attribute stops receiving the patch's marks."""
    try:
        return repos.unlink_patch_attribute(username, patch_id, attr_id)
    except PatchError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


_LOG_ID_PREFIX = 73
_LOG_ID_WIDTH = 4


def _today_agenda_labels(username: str) -> set[str]:
    """Build the set of today's agenda labels (normalized) for this user."""
    now = datetime.now()
    day_name = _DAY_NAMES[now.weekday()]
    iso = now.strftime("%Y-%m-%d")
    return collect_labels(Agenda(username).items, day_name=day_name, iso_date=iso)


def _period(raw) -> str | None:
    """A period from a request body; None when absent, 400 when not one."""
    if raw is None or raw == "":
        return None
    if raw not in PERIODS:
        raise HTTPException(status_code=400, detail=f"period must be one of {', '.join(PERIODS)}")
    return raw


def _append_log(username: str, content: str, marks: int, tokens: int = 0,
                period: str | None = None, undo: dict | None = None) -> dict | None:
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
        "marks": int(marks),
        "tokens": int(tokens),
        "coord": [today_day, next_order + 1],
        "period": period or period_of(datetime.now()),
        "undo": undo,
    }
    repos.append_log(username, entry)
    return {k: v for k, v in entry.items() if k != "undo"}


@app.post("/actions/{action_id}/act")
def act_on_action(action_id: str, payload: dict | None = None, username: str = Depends(current_username)):
    """Body: {option, note?, period?}. `option` is the tier, 0-5; how many marks
    it yields depends on what the action already earned in its 6-hour window.
    `period` (mo, ev, ni) files the log under that part of the day; it defaults
    to the one the clock is in."""
    data = _load_user(username)

    action = (data.get("actions") or {}).get(action_id)
    if not action or action.get("deleted"):
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")
    p = payload or {}
    if p.get("option") is None:
        raise HTTPException(status_code=400, detail="choose a tier: option 0-5")
    note = str(p.get("note") or "").strip()
    period = _period(p.get("period"))

    today_labels = _today_agenda_labels(username)

    # Attribute agenda match: if one of today's labels names an attribute, the
    # action counts as "in agenda" when it feeds a leaf under it.
    from src.domain.agenda import leaves_for_labels, normalize as _norm
    _tree = repos.load_attr_tree()
    by_name: dict[str, list[str]] = {}
    for n in _tree.nodes_by_key.values():
        by_name.setdefault(_norm(n.name), []).append(n.key)
    concept_leaves_today = leaves_for_labels(today_labels, by_name, _tree.children)
    # A patch runs on its base: the base's contributions decide the agenda match,
    # and a label naming one of its own attributes counts too.
    engine = engine_name(data.get("actions") or {}, action)
    action_leaf_keys = {lk for _id, lk, _w in repos.load_action_contributions(engine)}
    in_agenda_extra = bool(action_leaf_keys & concept_leaves_today)
    if action.get("base_action_id") and not in_agenda_extra:
        own = set(repos.load_patch_links(username).get(action_id, []))
        names = {_norm(a["name"]) for a in repos.load_user_attributes(username) if a["id"] in own}
        in_agenda_extra = bool(names & today_labels)

    try:
        outcome = perform_act(
            username, data, action_id, p["option"], note,
            today_labels=today_labels,
            in_agenda_extra=in_agenda_extra,
            save=lambda d: _save_user(username, d),
        )
    except MarkError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ActError as e:
        raise HTTPException(status_code=404, detail=str(e))

    _record_activity(username)
    lines = _engine_event(username, {"kind": "act", "action": action_id, "name": str(action.get("name") or "").upper()})
    # what is said on the screen that follows: the story's line when the act
    # moved it, one of the entity carried otherwise — or the system's, mute
    said = lines[-1] if lines else entities.say(
        engine_repo.load(username)[0].get("entity"), "after_act", random.Random(),
        {"nickname": social_repo.identity(username)["nickname"]})
    token_delta = (outcome.token_gain - outcome.tokens_wasted) - outcome.token_cost
    log_entry = _append_log(username, outcome.log_content, outcome.marks, token_delta, period, outcome.undo)

    return {
        "id": action_id,
        "name": action.get("name"),
        "value": action["value"],
        "score": action["score"],
        "marks": outcome.marks,
        "nominal": int(p["option"]),
        "window_marks": outcome.window_marks,
        "window_limit": MARKS_PER_WINDOW,
        "user_marks": int(data.get("marks", 0) or 0),
        # a log action's marks stayed on the action: `user_marks` did not move
        "log_only": outcome.log_only,
        "token_gain": outcome.token_gain,
        "token_cost": outcome.token_cost,
        "tokens_wasted": outcome.tokens_wasted,
        "tokens": int(data.get("metadata", {}).get("tokens", 0) or 0),
        "in_agenda": outcome.in_agenda,
        "energy_penalty": outcome.energy_penalty,
        "energy": int(data.get("metadata", {}).get("energy", 0) or 0),
        # the energy ran out on this act: the journey is back at stage 1
        "journey_reset": outcome.journey_reset,
        "log": log_entry,
        "roko": said["text"],
        "speaker": said["entity"],
        "lines": lines,
    }


@app.get("/actions/{action_id}/window")
def action_window(action_id: str, username: str = Depends(current_username)):
    """Marks this action — its base, for a patch — already earned in the current
    window, the limit, and its tiers."""
    data = _load_user(username)
    try:
        return window_state(username, data, action_id)
    except ActError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/actions")
def list_actions(username: str = Depends(current_username)):
    data = _load_user(username)
    actions = data.get("actions", {}) or {}
    links = repos.load_patch_links(username)
    attr_names = {a["id"]: a["name"] for a in repos.load_user_attributes(username)} if links else {}
    templates = repos.load_action_templates()
    tree = repos.load_attr_tree()
    contributions = repos.load_all_contributions()
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
            "token_gain": int(action.get("token_gain") or 0),
            "log_only": bool((templates.get(engine_name(actions, action)) or {}).get("log_only")),
            "tiers": tier_options(tiers_for(data, action, templates)),
            "path": _action_path(tree, templates, actions, action),
            "leaves": [
                {"key": key, "name": tree.nodes_by_key[key].name, "weight": weight}
                for key, weight in contributions.get(engine_name(actions, action).upper(), [])
                if key in tree.nodes_by_key
            ],
        })
        if action.get("base_action_id"):
            result[-1]["base_action_id"] = action["base_action_id"]
            result[-1]["attributes"] = [
                {"id": i, "name": attr_names[i], "weight": weight}
                for i, weight in links.get(action_id, {}).items() if i in attr_names
            ]
    # a patch right under its base: group by the base's name, base first
    result.sort(key=lambda a: (
        (a.get("name") or "").split(PATCH_SEPARATOR)[0].upper(),
        1 if a.get("base_action_id") else 0,
        (a.get("name") or "").upper(),
    ))
    return result


def _social_call(fn, *args):
    try:
        return fn(*args)
    except social_repo.SocialError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@app.post("/me/nickname")
def reroll_nickname(username: str = Depends(current_username)):
    """Draws a new random nickname."""
    return {"nickname": _social_call(social_repo.reroll_nickname, username)}


@app.get("/allies")
def allies(username: str = Depends(current_username)):
    return {"passcode": social_repo.identity(username)["passcode"], "items": _social_call(social_repo.load_allies, username)}


@app.post("/allies")
def add_ally(payload: dict, username: str = Depends(current_username)):
    """Body: {passcode}. The two profiles become allies, each seeing the other
    by nickname."""
    return _social_call(social_repo.add_ally, username, (payload or {}).get("passcode"))


@app.delete("/allies/{nickname}")
def remove_ally(nickname: str, username: str = Depends(current_username)):
    _social_call(social_repo.remove_ally, username, nickname)
    return {"ok": True}


def _entity_state(username: str, data: dict) -> dict:
    """What an entity reads before it speaks (src.domain.entities)."""
    metadata = data.get("metadata", {}) or {}
    today = datetime.now().date()
    _day, logs = _logs_on(username, today)
    thoughts = agenda_repo.thoughts_on(username, today)
    with_thought = {t["log_id"] for t in thoughts if t["log_id"] is not None}
    state = {
        "nickname": social_repo.identity(username)["nickname"],
        "hp": int(metadata.get("energy", 0) or 0),
        "max_hp": _max_energy(data, username),
        "tokens": int(metadata.get("tokens", 0) or 0),
        "max_tokens": int(metadata.get("max_tokens", BASE_MAX_TOKENS) or BASE_MAX_TOKENS),
        "acts_today": len(logs),
        "cycle_complete": bool(logs) and all(l["id"] in with_thought for l in logs)
                          and any(t["log_id"] is None for t in thoughts),
        "streak": int(_ensure_sequences(username).get("consecutive_days", 0) or 0),
    }
    boss, _coords, beaten, _tree, _templates = _current_boss(username, data)
    if not beaten:
        state["boss"] = boss.name
        state["boss_type"] = boss.view()["type"]
    return state


@app.get("/entities")
def list_entities(username: str = Depends(current_username)):
    """The entities the profile has met, with their stats, in the order it met
    them."""
    state, _code = engine_repo.load(username)
    return [entities.public(entities.ENTITIES[e]) for e in state["entities"] if e in entities.ENTITIES]


@app.get("/entity")
def carried_entity(username: str = Depends(current_username)):
    """The one entity the profile carries, with its stats and its affinity —
    or `none`, when it carries none and the system answers alone."""
    state, _code = engine_repo.load(username)
    e = entities.entity(state.get("entity") or "")
    affinity = {k: round(float(v), 2) for k, v in (state.get("affinity") or {}).items()}
    if not e:
        return {"none": True, "affinity": affinity}
    return {**entities.public(e), "none": False, "affinity": affinity}


@app.get("/entity/talk")
def carried_talk(username: str = Depends(current_username)):
    """A tap on the entity's screen: the entity carried answers, as
    `/entities/{id}/talk`; with none, the system does, mute."""
    state, _code = engine_repo.load(username)
    if not state.get("entity"):
        return {"entity": None, **entities.mute(random.Random()), "lines": []}
    return entity_talk(state["entity"], username)


@app.get("/entities/{entity_id}/talk")
def entity_talk(entity_id: str, username: str = Depends(current_username)):
    """A tap on an entity's screen: whether it is there, whether it wants to
    answer, and what it says, picked from the profile's state. Only the
    entity carried talks here; the others met, in the sandbox."""
    e = entities.entity(entity_id)
    if not e:
        raise HTTPException(status_code=404, detail=f"entity '{entity_id}' not found")
    data = _load_user(username)
    now = datetime.now()
    minute = int(now.timestamp() // 60)
    state, _code = engine_repo.load(username)
    if entity_id != state.get("entity"):
        raise HTTPException(status_code=404, detail=f"entity '{entity_id}' is not the one carried")
    rng = random.Random()
    st = _entity_state(username, data)
    if engine.entity_presence(state):
        said = {"present": True, "answered": True, "line": entities.line(e, st, rng)}
    else:
        said = entities.talk(e, st, username, minute, rng)
    lines = _engine_event(username, {"kind": "talk", "entity": entity_id}) if said["answered"] else []
    own = [l["text"] for l in lines if l["entity"] == entity_id]
    if own:
        said["line"] = " ".join(own)
    return {"entity": entity_id, **said, "lines": [l for l in lines if l["entity"] != entity_id]}


@app.get("/attributes/usage")
def attribute_usage(days: int = 30, limit: int = 12, username: str = Depends(current_username)):
    """The attributes used most in the last `days`: every act counts for the
    attribute its action is registered under and every one above it."""
    data = _load_user(username)
    tree = repos.load_attr_tree()
    templates = repos.load_action_templates()
    actions = data.get("actions") or {}
    uses: dict[str, int] = {}
    last: dict[str, datetime] = {}
    for action_id, c in social_repo.act_counts(username, max(1, days)).items():
        action = actions.get(action_id)
        parent = (templates.get(engine_name(actions, action).upper()) or {}).get("parent") if action else None
        if not parent or parent not in tree.nodes_by_key:
            continue
        for key in tree.primary_chain(parent):
            uses[key] = uses.get(key, 0) + c["acts"]
            last[key] = max(last.get(key, c["last"]), c["last"])
    totals = _user_leaf_totals(username, tree)
    memo: dict[str, float] = {}
    now = datetime.now()
    out = []
    for key in sorted(uses, key=lambda k: (-uses[k], tree.degree(k), k))[:max(1, min(limit, 50))]:
        out.append({**_node_view(tree, key, totals, memo), "uses": uses[key],
                    "seconds_ago": max(0, int((now - last[key]).total_seconds()))})
    return out


# ---------------------------------------------------------------- the engine

def _engine_event(username: str, ev: dict) -> list[dict]:
    """Runs one event through the profile's evove and saves it; returns what
    the entities say about it (src.domain.engine)."""
    state, _code = engine_repo.load(username)
    lines = engine.event(state, ev, random.Random(), datetime.now())
    engine_repo.save(username, state)
    return lines


_GIVEN = 3


def _give_first(username: str, data: dict, state: dict) -> bool:
    """The story starts with agir and a few actions handed out, not chosen:
    drawn once among the cheap trained ones of the catalog and added to the
    profile, where they are acted on like any other. Roko doubts them until
    they come back on other days. Returns whether anything was given."""
    drawn = state.pop("ghosts", None)  # drawn by the first engine, never owned
    if state.get("story") != "start" or state.get("given"):
        return drawn is not None
    templates = repos.load_action_templates()
    actions = data.setdefault("actions", {})
    owned = {str(a.get("name", "")).upper() for a in actions.values() if not a.get("deleted")}
    pool = sorted(n for n, m in templates.items()
                  if not m["log_only"] and m["cost"] <= 500 and m["code"] and n not in owned)
    names = [n for n in (drawn or []) if n in pool][:_GIVEN]
    names += random.Random().sample([n for n in pool if n not in names], max(0, min(_GIVEN, len(pool)) - len(names)))
    for n in names:
        code = templates[n]["code"]
        if code not in actions:
            actions[code] = _owned_action(code, n, templates[n])
    _save_user(username, data)
    social_repo.add_discoveries(username, names)
    state["given"] = {n: [] for n in names}
    return True


def _engine_view(username: str, state: dict, code: str) -> dict:
    now = datetime.now()
    view = engine.view(state, code, period_of(now))
    d = state.get("dungeon")
    alert = dungeon.alert(d, now, bool(state["flags"].get("fast")))
    view["modes"]["journey_alert"] = alert
    view["modes"]["journey_ending"] = d.get("ending") if isinstance(d, dict) else None
    for t in view["tiles"]:
        t["alert"] = t["kind"] == "journey" and alert
    return view


@app.get("/engine")
def engine_state(username: str = Depends(current_username)):
    """The profile's evove: the home's tiles for this session, the modules and
    their passcodes, the entities met, the story, the selector, the counters."""
    data = _load_user(username)
    state, code = engine_repo.load(username)
    if _give_first(username, data, state):
        engine_repo.save(username, state)
    return _engine_view(username, state, code)


@app.post("/engine/visit")
def engine_visit(payload: dict | None = None, username: str = Depends(current_username)):
    """Body: {cold?: bool, turns?: int}. The app came on: after a pause, or cold,
    that is a new session — a new layout, a visit counted, the rules that wait
    for one run. `turns` carries what a device counted before the engine."""
    p = payload or {}
    data = _load_user(username)
    state, code = engine_repo.load(username)
    lines = engine.event(state, {"kind": "visit", "cold": bool(p.get("cold")), "turns": int(p.get("turns") or 0)},
                         random.Random(), datetime.now())
    _give_first(username, data, state)
    engine_repo.save(username, state)
    return {**_engine_view(username, state, code), "lines": lines}


@app.post("/engine/events")
def engine_events(payload: dict, username: str = Depends(current_username)):
    """Body: {events: [{kind: open|turn|dismiss, module?, n?}]}. What happened on
    the device since the last call, counted in order."""
    state, code = engine_repo.load(username)
    period = period_of(datetime.now())
    lines: list[dict] = []
    for ev in ((payload or {}).get("events") or [])[:200]:
        kind = str((ev or {}).get("kind") or "")
        if kind not in ("open", "turn", "dismiss"):
            continue
        lines += engine.event(state, {**ev, "kind": kind, "period": period}, random.Random(), datetime.now())
    engine_repo.save(username, state)
    return {**_engine_view(username, state, code), "lines": lines}


@app.post("/engine/passcode")
def engine_passcode(payload: dict, username: str = Depends(current_username)):
    """Body: {code}. A module's passcode unlocks it, an upgrade's applies it,
    another evove's loads its build, a save code mounts the save. 404 for a
    code that names nothing."""
    raw = (payload or {}).get("code")
    if save.is_save(raw):
        return save_mount({"code": raw}, username)
    state, code = engine_repo.load(username)
    module = engine.module_for_code(raw)
    upgrade = engine.upgrade_for_code(raw) if not module else None
    if module:
        kind, lines = "module", engine.take_module(state, module)
    elif upgrade:
        kind, lines = "upgrade", engine.take_upgrade(state, upgrade)
    else:
        typed = engine.clean_code(raw)
        if typed == code:
            raise HTTPException(status_code=409, detail="this is your own evove")
        other = engine_repo.by_passcode(typed) if len(typed) == engine.EVOVE_CODE_LENGTH else None
        if other is None:
            raise HTTPException(status_code=404, detail="no evove or module with this code")
        kind, lines = "evove", engine.take_build(state, other)
    if lines:
        state["line"] = {**lines[-1], "at": datetime.now().isoformat(timespec="seconds")}
    engine_repo.save(username, state)
    return {**_engine_view(username, state, code), "kind": kind, "lines": lines}


# ---------------------------------------------------------------- the sandbox

def _sandbox(username: str) -> tuple[dict, dict]:
    """The profile's evove and the sandbox inside it; 403 before the story is
    told (src.domain.sandbox)."""
    state, _code = engine_repo.load(username)
    if not engine.modes(state)["sandbox"]:
        raise HTTPException(status_code=403, detail="the sandbox opens when the story is told")
    return state, sandbox.state_of(state)


@app.get("/sandbox")
def sandbox_home(username: str = Depends(current_username)):
    """The sandbox's home: its tiles, what was done in it, the entities met."""
    state, sb = _sandbox(username)
    engine_repo.save(username, state)
    return sandbox.view(state, sb)


@app.post("/sandbox/visit")
def sandbox_visit(username: str = Depends(current_username)):
    """The sandbox was entered: a new layout for its home."""
    state, sb = _sandbox(username)
    sandbox.renew(sb, random.Random())
    engine_repo.save(username, state)
    return sandbox.view(state, sb)


@app.post("/sandbox/open")
def sandbox_open(payload: dict, username: str = Depends(current_username)):
    """Body: {module}. A module of the sandbox opened, for its layout."""
    state, sb = _sandbox(username)
    sandbox.open_module(sb, str((payload or {}).get("module") or ""))
    engine_repo.save(username, state)
    return {"ok": True}


def _sandbox_actions(sb: dict) -> list[dict]:
    templates = repos.load_action_templates()
    tree = repos.load_attr_tree()
    contributions = repos.load_all_contributions()
    out = []
    for name, meta in templates.items():
        if not meta["code"]:
            continue
        done = sb["actions"].get(name) or {}
        parent = meta.get("parent")
        out.append({
            "id": meta["code"],
            "name": name,
            "type": meta["type"],
            "diff": meta["diff"],
            "value": done.get("value", 0),
            "score": done.get("score", 0),
            "token_cost": 0,
            "token_gain": 0,
            "log_only": meta["log_only"],
            "tiers": tier_options(meta.get("tiers") or DEFAULT_TIERS),
            "path": [{"key": k, "name": tree.nodes_by_key[k].name} for k in tree.primary_chain(parent)]
                    if parent and parent in tree.nodes_by_key else [],
            "leaves": [{"key": k, "name": tree.nodes_by_key[k].name, "weight": w}
                       for k, w in contributions.get(name, []) if k in tree.nodes_by_key],
        })
    out.sort(key=lambda a: a["name"])
    return out


@app.get("/sandbox/actions")
def sandbox_actions(username: str = Depends(current_username)):
    """Every action of the catalog, owned or not, as `/actions` lists them, with
    what was done with each in the sandbox."""
    _state, sb = _sandbox(username)
    return _sandbox_actions(sb)


@app.post("/sandbox/actions/{code}/act")
def sandbox_act(code: str, payload: dict | None = None, username: str = Depends(current_username)):
    """Body: {option}. An act in the sandbox: free, unlimited, the tier's marks
    whole, into the sandbox's own attributes. Nothing real changes."""
    state, sb = _sandbox(username)
    templates = repos.load_action_templates()
    name = next((n for n, m in templates.items() if m["code"] == code), None)
    if not name:
        raise HTTPException(status_code=404, detail=f"action {code} not found")
    tree = repos.load_attr_tree()
    contributions = repos.load_all_contributions().get(name, [])
    option = (payload or {}).get("option")
    try:
        done = sandbox.act(sb, name, option, contributions, set(tree.leaves_by_key))
    except MarkError as e:
        raise HTTPException(status_code=400, detail=str(e))
    engine_repo.save(username, state)
    gains = []
    for key, (before, after) in done["gains"].items():
        b, a = rank_view(before), rank_view(after)
        gains.append({"key": key, "name": tree.nodes_by_key[key].name, "before": b, "after": a})
    said = entities.say("coleto", "after_act", random.Random())
    labels = tier_options(templates[name].get("tiers") or DEFAULT_TIERS)
    return {
        "id": code,
        "name": name,
        "option": labels[int(option)]["label"],
        "marks": done["marks"],
        "acts": sb["acts"],
        "gains": gains,
        "roko": said["text"],
        "speaker": said["entity"],
    }


@app.get("/sandbox/attributes")
def sandbox_attributes(username: str = Depends(current_username)):
    """Every leaf with marks in the sandbox, with its rank there, the most
    marked first — as `/attributes`."""
    _state, sb = _sandbox(username)
    tree = repos.load_attr_tree()
    totals = sandbox.totals(sb)
    memo: dict[str, float] = {}
    out = [_node_view(tree, k, totals, memo) for k in tree.leaves_by_key]
    out.sort(key=lambda a: a["total_marks"], reverse=True)
    return out


@app.get("/sandbox/entities")
def sandbox_entities(username: str = Depends(current_username)):
    """Coleto, and every entity the profile has met, to be talked to at will."""
    state, _sb = _sandbox(username)
    ids = ["coleto"] + [e for e in state["entities"] if e in entities.ENTITIES and e != "coleto"]
    return [entities.public(entities.ENTITIES[e]) for e in ids]


@app.get("/sandbox/entities/{entity_id}/talk")
def sandbox_talk(entity_id: str, username: str = Depends(current_username)):
    """In the sandbox every entity met is there, and always answers."""
    state, sb = _sandbox(username)
    e = entities.entity(entity_id)
    if not e or (entity_id != "coleto" and entity_id not in state["entities"]):
        raise HTTPException(status_code=404, detail=f"entity '{entity_id}' not met")
    sb["talks"] += 1
    engine_repo.save(username, state)
    data = _load_user(username)
    return {"entity": entity_id, "present": True, "answered": True,
            "line": entities.line(e, _entity_state(username, data), random.Random()), "lines": []}


# ---------------------------------------------------------------- saves

_SAVE_SECRET_FILE = _BACKEND_DIR / ".save_secret"


def _save_secret() -> bytes:
    """What signs the save codes: EVOVE_SAVE_SECRET, or a key made once and
    kept beside the backend (not versioned)."""
    env = os.environ.get("EVOVE_SAVE_SECRET")
    if env:
        return env.encode()
    if not _SAVE_SECRET_FILE.exists():
        import secrets
        _SAVE_SECRET_FILE.write_text(secrets.token_hex(32))
    return _SAVE_SECRET_FILE.read_text().strip().encode()


_SAVED_METADATA = ("build_points", "tokens", "max_tokens", "skill_points", "energy", "stage", "journey_resets")


def _snapshot(username: str) -> dict:
    """Everything of the profile a save carries (src.domain.save)."""
    data = _load_user(username)
    codes = {m["code"] for m in repos.load_action_templates().values() if m["code"]}
    metadata = data.get("metadata") or {}
    state, _code = engine_repo.load(username)
    state = engine.copy_state(state)
    state.pop("session", None)
    if isinstance(state.get("dungeon"), dict):
        state["dungeon"].pop("battle", None)
    return {
        "a": [[aid, a.get("value", 0), a.get("score", 0)] for aid, a in sorted((data.get("actions") or {}).items())
              if aid in codes and not a.get("deleted") and not a.get("base_action_id")],
        "l": [[k, round(float(r["marks"]), 4), int(r["rank_index"])] for k, r in sorted(repos.get_user_leaf_scores(username).items())],
        "c": repos.load_rank_claims(username),
        "m": {"marks": int(data.get("marks", 0) or 0), **{k: metadata.get(k) for k in _SAVED_METADATA}},
        "s": list(data.get("skills") or []),
        "d": sorted(social_repo.load_discoveries(username)),
        "q": journey_repo.load_equipment(username),
        "e": state,
    }


def _mount(username: str, snap: dict) -> list[dict]:
    """Puts a save in place of what the profile had of the same kind. The
    patches stay, and so does every action one of them is built on; the logs,
    thoughts and agenda are not touched. Returns what is said about it."""
    now = datetime.now()
    data = _load_user(username)
    templates = repos.load_action_templates()
    by_code = {m["code"]: (n, m) for n, m in templates.items() if m["code"]}
    actions = data.setdefault("actions", {})
    bases = {a.get("base_action_id") for a in actions.values() if a.get("base_action_id") and not a.get("deleted")}
    saved = {str(c): (v, sc) for c, v, sc in snap.get("a") or [] if str(c) in by_code}
    for aid, a in actions.items():
        if a.get("base_action_id") or aid not in by_code:
            continue
        if aid in saved:
            a["value"], a["score"] = saved[aid]
            a["deleted"] = False
        elif aid not in bases:
            a["deleted"] = True
    for code, (v, sc) in saved.items():
        if code not in actions:
            name, meta = by_code[code]
            actions[code] = {**_owned_action(code, name, meta), "value": v, "score": sc}
    m = snap.get("m") or {}
    data["marks"] = int(m.get("marks", 0) or 0)
    metadata = data.setdefault("metadata", {})
    for k in _SAVED_METADATA:
        if m.get(k) is not None:
            metadata[k] = m[k]
    # the journey's clock starts again from the stage it had
    metadata["journey_started_at"] = now.isoformat(timespec="seconds")
    metadata["journey_points"] = 0
    data["skills"] = list(snap.get("s") or [])
    _save_user(username, data)
    repos.replace_leaf_scores(username, [(k, mk, r) for k, mk, r in snap.get("l") or []], now)
    repos.replace_rank_claims(username, {str(k): int(v) for k, v in (snap.get("c") or {}).items()})
    social_repo.add_discoveries(username, [n for n in snap.get("d") or [] if n in templates])
    journey_repo.replace_equipment(username, {k: bool(v) for k, v in (snap.get("q") or {}).items()
                                              if k in equipment.ITEMS_BY_ID})
    state, _code = engine_repo.load(username)
    mounted = engine.normalized(snap.get("e") or {}, random.Random())
    mounted["session"] = state["session"]
    dungeon = mounted.get("dungeon")
    if isinstance(dungeon, dict) and dungeon.get("ending") in ("left", "entity"):
        # left behind: whoever mounts it walks the journey again
        mounted["dungeon"] = None
    line = {"entity": "system", "text": "SAVE MONTADO."}
    mounted["line"] = {**line, "at": now.isoformat(timespec="seconds")}
    engine_repo.save(username, mounted)
    return [line]


@app.get("/save")
def save_code(username: str = Depends(current_username)):
    """The profile's save code: its evove, ranks, attributes and actions of the
    system in one signed code, `grouped` in fours for the eye."""
    snap = _snapshot(username)
    code = save.pack(snap, _save_secret())
    return {
        "code": code,
        "grouped": save.group(code),
        "length": len(code),
        "actions": len(snap["a"]),
        "attributes": len(snap["l"]),
    }


@app.post("/save/mount")
def save_mount(payload: dict, username: str = Depends(current_username)):
    """Body: {code}. Mounts a save code on this profile (see `_mount`); 400 for
    a code that is not one, or was changed."""
    try:
        snap = save.unpack((payload or {}).get("code"), _save_secret())
    except save.SaveError as e:
        raise HTTPException(status_code=400, detail=str(e))
    lines = _mount(username, snap)
    state, code = engine_repo.load(username)
    return {**_engine_view(username, state, code), "kind": "save", "lines": lines}


# ---------------------------------------------------------------- the journey's mode

_FIGHT_CAP = 50_000_000
# a fight started and never ended is played out after this long
_STALE_FIGHT_SECONDS = 600


def _cap(n: float) -> int:
    return max(1, min(_FIGHT_CAP, int(round(n))))


def _entity_battle(entity_id: str) -> dict:
    b = (entities.entity(entity_id) or {}).get("battle") or {}
    return {k: b[k] for k in ("forca", "agilidade", "skill", "ability")} if b else \
        {"forca": 10, "agilidade": 3, "skill": "atacar", "ability": "interferencia"}


def _fight_setup(username: str, data: dict, state: dict, d: dict) -> dict:
    """Both sides of the floor's fight (src.domain.fight): the profile's best
    attacks against this opponent, its heal, stats and entities; the opponent
    mirrored on its rank (src.domain.dungeon.foe_setup)."""
    from src.domain.attributes import MAX_RANK
    tree = repos.load_attr_tree()
    templates = repos.load_action_templates()
    boss = battle.make_boss(tree, templates, f"dungeon:{d['seed']}:{d['floor']}", max(1, dungeon.floor_in_act(d)), 0)
    worn = _worn(username)
    totals = _user_leaf_totals(username, tree)
    memo: dict[str, float] = {}
    actions = data.get("actions") or {}
    moves = battle.moves_for(tree, templates, actions, lambda key: rank_view(node_total(key, totals, tree, memo))["rank_index"])
    scored = sorted((battle.score_move(tree, m, boss, worn["damage"]) for m in moves), key=lambda m: (-m["damage"], m["name"]))
    lineup = scored[:battle.LINEUP_SIZE]
    rank = sum(m["rank_index"] for m in lineup) // len(lineup) if lineup else 0
    best_mult = max((m["multiplier"] for m in lineup), default=1.0)
    out_moves = []
    for m in lineup:
        out_moves.append({
            "name": m["name"], "attribute": m["attribute_name"], "multiplier": m["multiplier"],
            "dmg": _cap(m["base_damage"] * m["multiplier"] * (1 + worn["damage"])),
            "decree": _cap(battle.rank_damage(min(MAX_RANK, m["rank_index"] + 1)) * best_mult * (1 + worn["damage"])),
        })
    if not out_moves:
        out_moves = [{"name": "EMPURRÃO (α)", "attribute": "", "multiplier": 1.0, "dmg": 15, "decree": 41}]
    order = sorted(range(len(out_moves)), key=lambda i: (out_moves[i]["dmg"], i))
    for k, i in enumerate(order):
        out_moves[i]["cd"] = 30 + 10 * k
    metadata = data.get("metadata") or {}
    max_energy = _max_energy(data, username)
    per = 10 * battle.rank_damage(rank) / battle.RANK_DAMAGE_BASE
    max_hp = _cap(max_energy * per)
    # the heal: the best of the actions of reward owned, the ones that spend tokens
    heals = []
    for a in actions.values():
        meta = templates.get(str(a.get("name", "")).upper()) or {}
        cost = int(a.get("token_cost") or meta.get("token_cost") or 0)
        if a.get("deleted") or not meta.get("log_only") or cost <= 0:
            continue
        heals.append({"name": str(a.get("name", "")).upper(), "amount": _cap(max_hp * min(35, 10 + 3 * cost) / 100),
                      "cd": 60 + 15 * cost})
    heal = max(heals, key=lambda h: (h["amount"] * 1000 // h["cd"], h["amount"]), default=None) or \
        {"name": "RESPIRO", "amount": _cap(max_hp * 8 / 100), "cd": 100}
    roots_marked = sum(1 for r in tree.roots if node_total(r, totals, tree, memo) > 0)
    companions = dungeon.companions(d, state.get("entity"))
    you = {
        "name": social_repo.identity(username)["nickname"],
        "hp": _cap(int(metadata.get("energy", 0) or 0) * per), "max_hp": max_hp, "per_energy": per,
        "resist": 10 * rank + 2 * int(worn["hp"]),
        "defense": min(60, 4 * int(worn["armor"]) + 3 * rank),
        "absorb": min(200, 100 + 5 * roots_marked),
        "moves": out_moves, "heal": heal,
        "entities": [{"id": e, "name": entities.name_of(e), **_entity_battle(e)} for e in companions],
    }
    foe = dungeon.foe_setup(d, rank, battle.rank_damage, [{**a, "star": t["star"]} for a, t in zip(boss.abilities, boss.types)],
                            boss.defense, _entity_battle)
    for m in foe["moves"]:
        m["dmg"] = _cap(m["dmg"])
    foe["hp"] = foe["max_hp"] = _cap(foe["max_hp"])
    foe["heal"]["amount"] = _cap(foe["heal"]["amount"])
    seed = random.SystemRandom().randrange(1, 1 << 32)
    return {"seed": seed, "max_ticks": fight.MAX_TICKS, "tick_ms": fight.TICK_MS, "you": you, "foe": foe,
            "opponent": dungeon.opponent(d), "tricks": list(fight.TRICKS)}


def _dungeon(username: str):
    state, code = engine_repo.load(username)
    if not engine.modes(state)["journey"]:
        raise HTTPException(status_code=403, detail="the journey opens in the evove's story")
    now = datetime.now()
    created = not isinstance(state.get("dungeon"), dict)
    d = dungeon.state_of(state, now)
    if created:
        engine_repo.save(username, state)
    return state, d, now, bool(state["flags"].get("fast"))


def _dungeon_view(username: str, state: dict, d: dict, now: datetime, fast: bool) -> dict:
    data = _load_user(username)
    metadata = data.get("metadata") or {}
    max_energy = _max_energy(data, username)
    view = dungeon.view(d, now, fast)
    view["companions"] = [
        {"id": e, "name": entities.name_of(e), "color": entities.ENTITIES[e]["color"], "glyph": entities.ENTITIES[e]["glyph"],
         "ability": (entities.ENTITIES[e].get("battle") or {}).get("ability_name")}
        for e in dungeon.companions(d, state.get("entity")) if e in entities.ENTITIES]
    view["energy"] = int(metadata.get("energy", 0) or 0)
    view["max_energy"] = max_energy
    view["tokens"] = int(metadata.get("tokens", 0) or 0)
    view["recover"] = recovery.view(metadata, now, max_energy)
    view["checkpoint"] = journey_mode.view(metadata, now, max_energy)
    view["fighting"] = bool(d.get("battle"))
    if d.get("ending") in ("left", "entity"):
        view["code"] = save.group(save.pack(_snapshot(username), _save_secret()))
    return view


@app.get("/dungeon")
def dungeon_home(username: str = Depends(current_username)):
    """The journey as a mode: the floor and its map, how far the figure walked,
    who waits at its end, the choice waiting, the ending — with its code — and
    the hp, tokens and recoveries. See src.domain.dungeon."""
    state, d, now, fast = _dungeon(username)
    b = d.get("battle")
    if b and (now - datetime.fromisoformat(b["at"])).total_seconds() > _STALE_FIGHT_SECONDS:
        # a fight the app never came back to: it played itself, no tricks
        _resolve_fight(username, state, d, now, [])
    return _dungeon_view(username, state, d, now, fast)


@app.post("/dungeon/fight")
def dungeon_fight(username: str = Depends(current_username)):
    """Starts the fight with whoever waits: answers its setup, which the app
    plays live (src.domain.fight) and sends back with the ticks of its tricks."""
    state, d, now, fast = _dungeon(username)
    if not dungeon.waiting(d, now, fast):
        raise HTTPException(status_code=409, detail="no one is waiting")
    data = _load_user(username)
    if int((data.get("metadata") or {}).get("energy", 0) or 0) <= 0:
        raise HTTPException(status_code=409, detail="no hp left")
    setup = _fight_setup(username, data, state, d)
    d["battle"] = {"setup": setup, "at": now.isoformat(timespec="seconds")}
    engine_repo.save(username, state)
    return setup


def _resolve_fight(username: str, state: dict, d: dict, now: datetime, plays: list[int]) -> dict:
    """The fight replayed on the server with the tricks played at `plays`:
    what it decides is what counts. A win pays points and moves the story; the
    bar's end is the hp left, and an empty one restarts the checkpoints
    (src.domain.journey.fail)."""
    setup = d["battle"]["setup"]
    result = fight.replay(setup, plays)
    result["max_hp"] = setup["you"]["max_hp"]
    data = _load_user(username)
    metadata = data.setdefault("metadata", {})
    max_energy = _max_energy(data, username)
    hp = result["hp"][0]
    metadata["energy"] = min(max_energy, int(math.ceil(hp / max(1e-9, float(setup["you"]["per_energy"]))))) if hp > 0 else 0
    reset = False
    points = 0
    if result["won"]:
        points = battle.win_points(int(d["floor"]), 0, _worn(username)["points"])
        metadata["build_points"] = int(metadata.get("build_points", 0) or 0) + points
        lines = dungeon.won(d, result, random.Random(), now)
    else:
        dungeon.lost(d)
        lines = ["O SINAL CAIU."]
    if metadata["energy"] <= 0:
        journey_mode.fail(metadata, now, max_energy)
        reset = True
        lines.append("SUA BARRA ACABOU. OS CHECKPOINTS VOLTARAM AO ESTÁGIO 1.")
    d["battle"] = None
    _save_user(username, data)
    engine_repo.save(username, state)
    return {"result": result, "won": result["won"], "points": points, "journey_reset": reset, "lines": lines,
            "close": d.get("ending") == "free"}


@app.post("/dungeon/fight/end")
def dungeon_fight_end(payload: dict | None = None, username: str = Depends(current_username)):
    """Body: {plays: [tick, …]}. The fight's end, as `_resolve_fight` decides
    it. A fight left halfway — the app closed — is sent with the tricks played
    so far: the rest plays itself, as an autobattler does."""
    state, d, now, fast = _dungeon(username)
    if not d.get("battle"):
        raise HTTPException(status_code=409, detail="no fight going on")
    plays = [int(t) for t in ((payload or {}).get("plays") or [])[:600] if 0 <= int(t) <= fight.MAX_TICKS]
    out = _resolve_fight(username, state, d, now, plays)
    return {**out, "view": _dungeon_view(username, state, d, now, fast)}


@app.post("/dungeon/choose")
def dungeon_choose(payload: dict, username: str = Depends(current_username)):
    """Body: {option}. The answer to the choice waiting — leave or stay, become
    an entity or let it escape."""
    state, d, now, fast = _dungeon(username)
    try:
        lines = dungeon.choose(d, str((payload or {}).get("option") or ""), state.get("entity"), now)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    engine_repo.save(username, state)
    return {"lines": lines, "view": _dungeon_view(username, state, d, now, fast)}


@app.post("/dungeon/pair")
def dungeon_pair(payload: dict, username: str = Depends(current_username)):
    """Body: {entities: [a, b]}. In the third act, the two entities carried."""
    state, d, now, fast = _dungeon(username)
    try:
        dungeon.set_pair(d, list((payload or {}).get("entities") or []))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    engine_repo.save(username, state)
    return _dungeon_view(username, state, d, now, fast)
