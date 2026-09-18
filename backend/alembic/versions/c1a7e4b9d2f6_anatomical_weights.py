"""anatomical weights from published muscle volumes

Revision ID: c1a7e4b9d2f6
Revises: b9f4c2e7a1d6
Create Date: 2026-09-17 18:00:00.000000

The weights inside the two limbs were round numbers, picked by hand. They are now
the fraction of the limb's muscle volume each group holds, which is what makes a
mark on a muscle worth what that muscle is worth.

Upper limb — Holzbaur, Murray, Gold & Delp 2007, "Upper limb muscle volumes in
adult subjects", J Biomech 40:742-749, Table 2 (10 subjects, 32 muscles, total
2554.0 cm3). Volume fractions of the whole upper limb: deltoid 15.2, triceps
14.5, anconeus 0.4, biceps 5.6, brachialis 5.7, brachioradialis 2.5, and the
18 forearm muscles 19.0 together. Grouped onto the four leaves the tree has:
triceps takes the elbow extensors (triceps + anconeus), biceps the elbow flexors
(biceps + brachialis), antebraco the brachioradialis and every forearm muscle,
deltoide the deltoid alone — the rotator cuff (16.7% across SUPRA, INFRA,
SUBSCAP, TMIN, TMAJ) is left out because the leaf is Deltoide, not Ombro.
Pectoralis and latissimus are in Holzbaur's total but live under `tronco` here,
so they leave the sum too. The four hold 62.9% of the limb; renormalised over
that: 0.2417, 0.2369, 0.1797, 0.3418.

Lower limb — Ward, Eng, Smallwood & Lieber 2009, "Are current measurements of
lower extremity muscle architecture accurate?", Clin Orthop Relat Res, Table 3
(21 cadaver limbs, 83 +/- 9 years, 9M:12F). Masses in grams: quadriceps
110.6+375.9+171.9+239.4 = 897.8, gluteals 547.2+273.5 = 820.7, hamstrings
113.4+59.8+99.7+134.3 = 407.2, triceps surae 113.5+62.2+275.8 = 451.5. Over
their 2577.2 g: 0.3484, 0.3184, 0.1580, 0.1752.

Handsfield et al. 2014 is the in vivo source and was the one first reached for,
but it publishes its fractions as Fig. 2A, a figure — the body of the paper
carries none of the numbers. It does compare itself to Ward and finds the
cadaver fractions consistent "with a few exceptions": gluteus medius, psoas and
vastus lateralis differ significantly, and two of those fall in the groups that
rise here. Ward is the best source available as text, and that is the caveat.

Rounded to two decimals, as the rest of the seed is. The raw fractions sum to
1.0000 but round to 1.01 in the lower limb, so panturrilha — the one that gains
most from rounding, 0.1752 — goes down to 0.17 instead of up.

Not touched, for want of a source: `tronco` (neither paper covers the abdominals
or the erectors; Holzbaur gives pectoralis 10.7% and latissimus 9.8% but those
are two of four leaves), and `musculatura` itself, where comparing Holzbaur's in
vivo total to Ward's cadaver total would not mean anything.

A reweight moves the parent, on purpose: `memb_sup` and `memb_inf` are worth
something different after this. No profile loses a mark — nothing is stored on
either node.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a7e4b9d2f6"
down_revision: Union[str, None] = "b9f4c2e7a1d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# parent -> {child: weight}, every child the parent has, so each row sums to 1
REWEIGHT = {
    "memb_sup": {"deltoide": 0.24, "triceps": 0.24, "biceps": 0.18, "antebraco": 0.34},
    "memb_inf": {"quadriceps": 0.35, "gluteo": 0.32, "panturrilha": 0.17, "posterior_coxa": 0.16},
}

BEFORE = {
    "memb_sup": {"deltoide": 0.25, "triceps": 0.3, "biceps": 0.3, "antebraco": 0.15},
    "memb_inf": {"quadriceps": 0.3, "gluteo": 0.25, "panturrilha": 0.2, "posterior_coxa": 0.25},
}


def _apply(weights: dict) -> None:
    conn = op.get_bind()
    ids = {k: i for i, k in conn.execute(sa.text("SELECT id, `key` FROM attr_nodes")).fetchall()}
    for parent, children in weights.items():
        total = sum(children.values())
        if abs(total - 1.0) > 1e-6:          # the migration writes SQL, so nothing else checks
            raise RuntimeError(f"{parent}: weights sum to {total}, not 1")
        for child, weight in children.items():
            conn.execute(sa.text("""UPDATE attr_edges SET weight = :w
                WHERE parent_id = :p AND child_id = :c"""),
                         {"w": float(weight), "p": ids[parent], "c": ids[child]})


def upgrade() -> None:
    _apply(REWEIGHT)


def downgrade() -> None:
    _apply(BEFORE)
