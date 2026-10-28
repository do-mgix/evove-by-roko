"""The two currencies, and what moves them.

Tokens are scarce: an act releases 1 to 4 and a profile holds at most
BASE_MAX_TOKENS (skills raise it a little). They pay for what keeps the journey
going — the recoveries — and leisure actions spend them.

Their scale is the plain-text ledger's (~/journal/token-history) divided by
five: work, a project or a course +2, writing +2 to +3, cooking +3, a chore
+1; music or light reading 1, an episode 3, a film 2 to 4, a game 2 to 8.
Leisure prices its tiers (src.domain.marks.token_cost), so the longer evening
costs more, as the ledger charged it.

Points are abundant: gains run from 50 to 2000. They buy actions in the shop,
equipment for the journey and anything that is only for show. They are what the
database still calls `build_points`.

Pure constants; the modules that move a currency import them from here.
"""

BASE_MAX_TOKENS = 25

# what a profile starts with, to fill its first shop
INITIAL_POINTS = 5000

# paid by the journey for every day survived, at every point and checkpoint
POINTS_PER_DAY = 100

# a finished to-do: so much per action in it, within the bounds of any gain
TODO_POINTS_PER_ACTION = 100
MIN_GAIN = 50
MAX_GAIN = 2000


def todo_reward(actions: int) -> int:
    """Points for completing a to-do holding `actions` actions. Late or not, the
    same: the deadline only shows."""
    return max(MIN_GAIN, min(MAX_GAIN, TODO_POINTS_PER_ACTION * max(1, int(actions))))
