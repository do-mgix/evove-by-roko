"""Write the fights the app's tests replay, with what the server decides.

The journey's fights run twice: live in the app (Kotlin) and replayed on the
server (src.domain.fight) to decide what they pay. Both must agree to the
tick. This writes a set of fights — every skill, ability and trick, both
sides with entities, tricks played at odd moments — and their results to the
app's test resources, where FightParityTest checks the Kotlin rules against
them. Run it again whenever src.domain.fight changes:

    python backend/scripts/fight_cases.py
"""
import json
import random
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from src.domain import fight  # noqa: E402

OUT = BACKEND.parent / "apps" / "android" / "app" / "src" / "test" / "resources" / "fight_cases.json"

ABILITIES = ("decreto", "pergunta", "ficar", "pressa", "troca", "amarra", "chama", "interferencia")


def side(rng: random.Random, name: str, ents: int, tricks: bool) -> dict:
    hp = rng.randint(150, 900)
    moves = []
    for i in range(rng.randint(1, 4)):
        dmg = rng.randint(5, 120)
        moves.append({"name": f"{name}{i}", "dmg": dmg, "decree": dmg * rng.randint(2, 5), "cd": rng.randint(20, 70),
                      "crit": rng.choice((0, 0, 10, 20, 30))})
    return {
        "name": name, "hp": hp - rng.randint(0, hp // 3), "max_hp": hp,
        "resist": rng.randint(0, 60), "defense": rng.randint(0, 60), "absorb": rng.randint(80, 200),
        "moves": moves, "heal": {"name": name + "H", "amount": rng.randint(10, hp // 4), "cd": rng.randint(50, 120)},
        "entities": [{"id": f"e{k}", "name": f"E{k}", "forca": rng.randint(40, 70), "agilidade": rng.randint(1, 10),
                      "skill": rng.choice(fight.SKILLS), "ability": rng.choice(ABILITIES), "level": rng.randint(1, 4)} for k in range(ents)],
        "tricks": tricks,
        "level": rng.randint(1, 9), "xp": rng.randint(0, 5), "xp_need": rng.choice((0, 6, 10)), "bonus": rng.randint(0, 30),
        "per_level": {"hp": rng.randint(0, 8), "resist": 5, "defense": 1, "bonus": 4},
    }


def main() -> None:
    rng = random.Random(20261023)
    cases = []
    for n in range(60):
        setup = {
            "seed": rng.randrange(1, 1 << 32),
            "max_ticks": rng.choice((fight.MAX_TICKS, 300, 600)),
            "you": side(rng, "Y", rng.randint(0, 2), True),
            "foe": side(rng, "F", rng.randint(0, 1), rng.random() < 0.8),
        }
        plays = sorted(rng.sample(range(0, 600), rng.randint(0, 40)))
        cases.append({"setup": setup, "plays": plays, "result": fight.replay(setup, plays)})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cases, ensure_ascii=False, separators=(",", ":")))
    won = sum(c["result"]["won"] for c in cases)
    print(f"{len(cases)} fights, {won} won, written to {OUT}")


if __name__ == "__main__":
    main()
