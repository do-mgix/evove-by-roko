/** Moving between buttons with the keyboard: the arrows, or h j k l. */

export type Direction = "left" | "down" | "up" | "right";

/** The direction a key moves in, if it moves. */
export function directionOf(key: string): Direction | null {
  switch (key) {
    case "ArrowLeft": case "h": return "left";
    case "ArrowDown": case "j": return "down";
    case "ArrowUp": case "k": return "up";
    case "ArrowRight": case "l": return "right";
    default: return null;
  }
}

/** What can be moved to: buttons, and the cells drawn as buttons. */
const SELECTOR = 'button:not(:disabled), [role="button"][tabindex="0"]';

const centre = (el: Element) => {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2, seen: r.width > 0 && r.height > 0 };
};

/** Moves the focus, within `root`, to the nearest button that way — nearest
 *  along the way, with a sidelong step counting double. With nothing focused
 *  yet, the first move lands on the button nearest the bottom-right corner,
 *  where the thumb is. */
export function moveFocus(root: Element, dir: Direction): void {
  const all = [...root.querySelectorAll<HTMLElement | SVGElement>(SELECTOR)].filter((el) => centre(el).seen);
  if (!all.length) return;
  const here = document.activeElement;
  if (!here || !all.includes(here as HTMLElement)) {
    const corner = all.reduce((best, el) => {
      const c = centre(el);
      const b = centre(best);
      return c.x + c.y > b.x + b.y ? el : best;
    });
    corner.focus();
    return;
  }
  const from = centre(here);
  let best: HTMLElement | SVGElement | null = null;
  let score = Infinity;
  for (const el of all) {
    if (el === here) continue;
    const c = centre(el);
    const dx = c.x - from.x;
    const dy = c.y - from.y;
    const along = dir === "left" ? -dx : dir === "right" ? dx : dir === "up" ? -dy : dy;
    const aside = dir === "left" || dir === "right" ? Math.abs(dy) : Math.abs(dx);
    if (along <= 1) continue;
    const s = along + 2 * aside;
    if (s < score) {
      score = s;
      best = el;
    }
  }
  best?.focus();
}
