/** How the interface is used, counted on the device, for the small algorithms
 *  that make it more practical the more it is used.
 *
 *  For now: which option of the home is opened, in which part of the day. The
 *  home lights the one most opened at this hour — the guess of what comes next.
 */

import { currentPeriod, type Period } from "./api";
import type { HomeOptionId } from "./homeLayout";

const KEY = "evove_usage";

type Counts = Partial<Record<Period, Partial<Record<HomeOptionId, number>>>>;

function read(): Counts {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") ?? {};
  } catch {
    return {};
  }
}

/** One more opening of `id`, in the part of the day the clock is in. */
export function recordOpen(id: HomeOptionId): void {
  const counts = read();
  const period = currentPeriod();
  const here = (counts[period] ??= {});
  here[id] = (here[id] ?? 0) + 1;
  try {
    localStorage.setItem(KEY, JSON.stringify(counts));
  } catch {
    // nowhere to keep it: the guess stays acting
  }
}

/** The option most opened in this part of the day, among `among`; acting when
 *  nothing was counted yet. */
export function suggestedOption(among: Set<HomeOptionId>): HomeOptionId | null {
  const here = read()[currentPeriod()] ?? {};
  let best: HomeOptionId | null = null;
  let most = 0;
  for (const [id, n] of Object.entries(here) as [HomeOptionId, number][]) {
    if (among.has(id) && n > most) {
      best = id;
      most = n;
    }
  }
  return best ?? (among.has("act") ? "act" : null);
}
