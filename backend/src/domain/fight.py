"""The journey's fights: an autobattler in real time.

Two fighters face each other — the profile and another of the people trapped
in the journey (src.domain.dungeon) — and the fight plays itself, a tick
every tenth of a second:

- a fighter's attacks are its actions — two of them for the profile — each
  with its own cooldown, and they
  are paid out of its own bar: there is no mp, every attack takes a little of
  the hp it fights with. **Resistência** slows how fast the bar goes down that
  way, **defesa** cuts the damage taken, **absorção** raises what a heal gives;
- it carries one heal — the profile's best action of reward, the ones that
  spend tokens — used by itself when the bar drops under 60%;
- both sides play **truques** by themselves, a little after one is charged:
  the next is shown, and once charged the one on offer changes every few
  seconds, so the wait may bring a better one. Atordoar pauses the opponent's cooldowns,
  fúria moves one's own forward in time, baque stops everyone (and both sides
  then tend to strike together), rasteira sends one of the opponent's
  attacks back to the start of its cooldown, escudo takes most of the next
  blow and eco repeats the last attack, weaker, for free;
- each side may bring entities (src.domain.entities): one, or two in the
  journey's third act. An entity grows impatient as the fight drags on, and
  the longer it lasts the likelier it steps in with a blow of its own — its
  side's best attack times its força, neutral, no cooldown spent, enough to
  turn a fight. It also has a skill, on a short cooldown set by its
  agilidade, and an ability, on a longer one. Roko's, the decree, rewrites
  the profile's attacks as the best possible against this opponent, a rank
  above, and raises its stats. The opponent's entity has no name.

Everything is integer arithmetic over a xorshift32 generator, so a fight is
fully decided by its setup (and, for an older app, the ticks a trick was
played at by hand): the app runs it live (com.evove.app.fight.Fight, the same rules in Kotlin) and
the server replays it to decide what it pays. `tests` in the app check both
against the same cases.

Pure logic — no I/O.
"""
from __future__ import annotations


TICK_MS = 100
MAX_TICKS = 2400

TRICKS = ("atordoar", "furia", "baque", "rasteira", "escudo", "eco")
TRICK_CD = 120
TRICK_ROLL = 60
TRICK_PPM = 15_000

STUN_TICKS = 50
FURY_TICKS = 40
THUD_TICKS = 40
SHIELD_PCT = 60
ECHO_PCT = 60

HEAL_AT_PCT = 60
DEFENSE_CAP = 75

PATIENCE_BASE_PPM = 250
PATIENCE_GROWTH_PPM = 5
ABILITY_CD = 400
ABILITY_FIRST = 300

SKILLS = ("negar", "atacar", "potencia", "cura", "truques")
BOOST_TICKS = 100
STAND_TICKS = 160
HASTE_TICKS = 120
BLOCK_TICKS = 240
BURN_TICKS = 200
DECREE_TICKS = 120

# the kinds of event, in the order the checksum numbers them
EVENTS = ("attack", "heal", "trick", "skill", "ability", "interfere", "deny", "miss", "burn", "end")

MASK = 0xFFFFFFFF


def skill_cd(agilidade: int) -> int:
    return max(60, 240 - 16 * int(agilidade))


class Rng:
    """xorshift32: the same numbers in Python and in Kotlin."""

    def __init__(self, seed: int):
        self.x = (int(seed) & MASK) or 0x9E3779B9

    def next(self) -> int:
        x = self.x
        x ^= (x << 13) & MASK
        x ^= x >> 17
        x ^= (x << 5) & MASK
        self.x = x & MASK
        return self.x

    def below(self, n: int) -> int:
        return self.next() % n


class Side:
    def __init__(self, d: dict, tricks: bool):
        self.name = d["name"]
        self.hp = int(d["hp"])
        self.max_hp = int(d["max_hp"])
        self.resist = int(d["resist"])
        self.defense = int(d["defense"])
        self.absorb = int(d["absorb"])
        self.moves = [{"name": m["name"], "dmg": int(m["dmg"]), "decree": int(m.get("decree", m["dmg"])),
                       "cd": int(m["cd"]), "t": int(m["cd"]) // 2 + 3 * i} for i, m in enumerate(d["moves"])]
        h = d["heal"]
        self.heal = {"name": h["name"], "amount": int(h["amount"]), "cd": int(h["cd"]), "t": int(h["cd"]) // 2}
        self.entities = [{"id": e["id"], "name": e["name"], "forca": int(e["forca"]), "agilidade": int(e["agilidade"]),
                          "skill": e["skill"], "ability": e["ability"], "skill_t": skill_cd(e["agilidade"]),
                          "ability_t": ABILITY_FIRST, "patience": 0} for e in d.get("entities") or []]
        self.tricks = tricks
        self.charge = TRICK_CD // 2
        self.roll = 0
        self.cur = self.nxt = None
        self.stun = self.boost = self.stand = self.haste = self.block = self.burn = 0
        self.deny = self.doubt = self.shield = 0
        self.decree = 0
        self.last: int | None = None
        self.dealt = self.heals = self.used = self.interfered = 0

    def defense_now(self) -> int:
        return min(DEFENSE_CAP, self.defense + (15 if self.boost else 0) + (30 if self.stand else 0) + (10 if self.decree else 0))

    def resist_now(self) -> int:
        return self.resist + (20 if self.boost else 0) + (20 if self.decree else 0)

    def absorb_now(self) -> int:
        return self.absorb + (20 if self.decree else 0)

    def best(self) -> int:
        return max([m["decree"] if self.decree else m["dmg"] for m in self.moves] or [1])

    def view(self) -> dict:
        return {"hp": self.hp, "max_hp": self.max_hp, "moves": [m["t"] for m in self.moves], "heal": self.heal["t"],
                "charge": self.charge, "trick": self.cur, "next": self.nxt, "stun": self.stun}


class Fight:
    """A fight from its setup. `step(play)` runs one tick — `play` is whether
    the person played the trick on offer at its start — and returns whether
    the fight is over."""

    def __init__(self, setup: dict):
        self.rng = Rng(setup["seed"])
        self.max_ticks = int(setup.get("max_ticks", MAX_TICKS))
        self.sides = [Side(setup["you"], True), Side(setup["foe"], bool(setup["foe"].get("tricks", True)))]
        for s in self.sides:
            if s.tricks:
                s.cur, s.nxt = self._draw(), self._draw()
        self.tick = 0
        self.freeze = 0
        self.over = False
        self.won = False
        self.check = 0
        self.events: list[dict] = []

    # ------------------------------------------------------------ helpers

    def _draw(self) -> str:
        return TRICKS[self.rng.below(len(TRICKS))]

    def _event(self, kind: str, side: int, value: int, name: str = "") -> None:
        self.events.append({"t": self.tick, "k": kind, "s": side, "v": value, "n": name})
        self.check = (self.check * 31 + self.tick * 7 + EVENTS.index(kind) * 13 + side * 17 + value) & MASK

    def _hit(self, i: int, dmg: int, kind: str, name: str) -> None:
        """Damage that ignores every modifier: an entity's blow, a burn."""
        o = self.sides[1 - i]
        o.hp -= dmg
        self.sides[i].dealt += dmg
        self._event(kind, i, dmg, name)

    def _attack(self, i: int, m: int, pct: int = 100, free: bool = False) -> None:
        s, o = self.sides[i], self.sides[1 - i]
        move = s.moves[m]
        if not free:
            s.hp -= max(1, s.max_hp // (100 + s.resist_now()))
        s.last = m
        dmg = (move["decree"] if s.decree else move["dmg"]) * pct // 100
        if s.boost:
            dmg = dmg * 125 // 100
        if o.deny:
            o.deny -= 1
            self._event("deny", i, 0, move["name"])
            return
        if s.doubt:
            s.doubt -= 1
            if self.rng.below(2) == 0:
                self._event("miss", i, 0, move["name"])
                return
        dmg = dmg * (100 - o.defense_now()) // 100
        if o.shield:
            o.shield = 0
            dmg = dmg * (100 - SHIELD_PCT) // 100
        dmg = max(1, dmg)
        o.hp -= dmg
        s.dealt += dmg
        self._event("attack", i, dmg, move["name"])

    def _heal(self, i: int, amount: int, name: str) -> None:
        s = self.sides[i]
        got = max(0, min(s.max_hp - s.hp, amount * s.absorb_now() // 100))
        s.hp += got
        self._event("heal", i, got, name)

    def _trick(self, i: int, trick: str) -> None:
        s, o = self.sides[i], self.sides[1 - i]
        if trick == "atordoar":
            o.stun = max(o.stun, STUN_TICKS)
        elif trick == "furia":
            for m in s.moves:
                m["t"] = max(0, m["t"] - FURY_TICKS)
            s.heal["t"] = max(0, s.heal["t"] - FURY_TICKS)
        elif trick == "baque":
            self.freeze = max(self.freeze, THUD_TICKS)
        elif trick == "rasteira":
            if o.moves:
                k = min(range(len(o.moves)), key=lambda j: (o.moves[j]["t"], j))
                o.moves[k]["t"] = o.moves[k]["cd"]
        elif trick == "escudo":
            s.shield = 1
        elif trick == "eco":
            if s.last is not None:
                self._attack(i, s.last, ECHO_PCT, free=True)
        self._event("trick", i, TRICKS.index(trick), trick)

    def _play(self, i: int) -> None:
        s = self.sides[i]
        if not s.tricks or s.charge < TRICK_CD:
            return
        trick = s.cur
        s.used += 1
        s.cur, s.nxt = s.nxt, self._draw()
        s.charge = 0
        s.roll = 0
        self._trick(i, trick)

    def _skill(self, i: int, e: dict) -> None:
        s = self.sides[i]
        k = e["skill"]
        if k == "negar":
            s.deny += 1
        elif k == "atacar":
            self._hit(i, max(1, s.best() * e["forca"] // 20), "skill", e["name"])
            return
        elif k == "potencia":
            s.boost = BOOST_TICKS
        elif k == "cura":
            self._heal(i, s.max_hp * 12 // 100, e["name"])
            return
        elif k == "truques":
            self._trick(i, self._draw())
            self._trick(i, self._draw())
        self._event("skill", i, SKILLS.index(k), e["name"])

    def _ability(self, i: int, e: dict) -> None:
        s, o = self.sides[i], self.sides[1 - i]
        a = e["ability"]
        if a == "decreto":
            s.decree = DECREE_TICKS
        elif a == "pergunta":
            o.doubt = 3
        elif a == "ficar":
            s.stand = STAND_TICKS
        elif a == "pressa":
            s.haste = HASTE_TICKS
        elif a == "troca":
            o.block = BLOCK_TICKS
            self._heal(i, o.heal["amount"], e["name"])
        elif a == "amarra":
            for m in o.moves:
                m["t"] = m["cd"]
            o.stun = max(o.stun, 10)
        elif a == "chama":
            o.burn = BURN_TICKS
        else:
            # what the opponent's nameless entity does: one of three, by chance
            r = self.rng.below(3)
            if r == 0:
                o.stun = max(o.stun, 15)
            elif r == 1:
                s.deny += 1
            else:
                self._heal(i, s.max_hp * 8 // 100, e["name"])
        self._event("ability", i, 0, a)

    # ------------------------------------------------------------ the tick

    def step(self, play: bool = False) -> bool:
        if self.over:
            return True
        you, foe = self.sides
        if play:
            self._play(0)
        # the tricks play themselves, a little after they are charged: waiting
        # may bring a better one, and no one decides
        for i, s in enumerate(self.sides):
            if s.tricks and s.charge >= TRICK_CD and self.rng.below(1_000_000) < TRICK_PPM:
                self._play(i)
        if self.freeze:
            self.freeze -= 1
        else:
            for s in self.sides:
                if s.stun:
                    s.stun -= 1
                    continue
                step = 2 if s.haste else 1
                for m in s.moves:
                    m["t"] = max(0, m["t"] - step)
                s.heal["t"] = max(0, s.heal["t"] - step)
            for i, s in enumerate(self.sides):
                if s.stun:
                    continue
                for k, m in enumerate(s.moves):
                    if m["t"] == 0 and s.hp > max(1, s.max_hp // (100 + s.resist_now())):
                        self._attack(i, k)
                        m["t"] = m["cd"]
                if s.heal["t"] == 0 and not s.block and s.hp * 100 <= HEAL_AT_PCT * s.max_hp:
                    self._heal(i, s.heal["amount"], s.heal["name"])
                    s.heals += 1
                    s.heal["t"] = s.heal["cd"]
            for i, s in enumerate(self.sides):
                for e in s.entities:
                    e["skill_t"] -= 1
                    if e["skill_t"] <= 0:
                        self._skill(i, e)
                        e["skill_t"] = skill_cd(e["agilidade"])
                    e["ability_t"] -= 1
                    if e["ability_t"] <= 0:
                        self._ability(i, e)
                        e["ability_t"] = ABILITY_CD
            for i, s in enumerate(self.sides):
                for e in s.entities:
                    e["patience"] += 1
                    if self.rng.below(1_000_000) < PATIENCE_BASE_PPM + PATIENCE_GROWTH_PPM * e["patience"]:
                        self._hit(i, max(1, s.best() * e["forca"] // 10), "interfere", e["name"])
                        s.interfered += 1
                        e["patience"] //= 2
        for i, s in enumerate(self.sides):
            for b in ("boost", "stand", "haste", "block", "decree"):
                if getattr(s, b):
                    setattr(s, b, getattr(s, b) - 1)
            if s.burn:
                s.burn -= 1
                if s.burn % 20 == 0:
                    self._hit(1 - i, max(1, s.max_hp * 2 // 100), "burn", "chama")
            if s.tricks:
                if s.charge < TRICK_CD:
                    s.charge += 1
                else:
                    s.roll += 1
                    if s.roll >= TRICK_ROLL:
                        s.cur, s.nxt = s.nxt, self._draw()
                        s.roll = 0
        self.tick += 1
        if you.hp <= 0 or foe.hp <= 0:
            self.won = foe.hp <= 0 < you.hp
            self._end()
        elif self.tick >= self.max_ticks:
            self.won = you.hp * foe.max_hp > foe.hp * you.max_hp
            self._end()
        return self.over

    def _end(self) -> None:
        self.over = True
        self._event("end", 0 if self.won else 1, 0)

    def result(self) -> dict:
        you, foe = self.sides
        return {
            "won": self.won,
            "ticks": self.tick,
            "hp": [max(0, you.hp), max(0, foe.hp)],
            "dealt": [you.dealt, foe.dealt],
            "heals": [you.heals, foe.heals],
            "tricks": [you.used, foe.used],
            "interfered": [you.interfered, foe.interfered],
            "check": self.check,
        }


def replay(setup: dict, plays: list[int]) -> dict:
    """The fight `setup` describes with the person's tricks played at `plays`
    (ticks), to the end."""
    at = set(int(t) for t in plays or [])
    f = Fight(setup)
    while not f.step(f.tick in at):
        pass
    return f.result()
