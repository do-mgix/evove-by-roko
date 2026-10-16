/** The home screen: the options that cover it, and what they look like.
 *
 * The options sit on an imaginary grid four columns across and four rows down,
 * of narrow upright rectangles, filling the lower part of the screen. Agir is a
 * round button sitting where three cells meet; the cells around it are cut to
 * fit it, with the same gap as between any two.
 *
 * Nothing is written on them: an option is known by its glyph — a sign from a
 * script that does not exist — and its color.
 *
 * `unlocked` is the hook for revealing the options little by little: a locked
 * option is not drawn. Everything is unlocked for now.
 */

export type HomeOptionId = "act" | "logs" | "shop" | "roko" | "attributes" | "journey";

export type Point = [number, number];
/** A place on a grid of squares: x, y, width and height, in squares. */
export type Box = [number, number, number, number];

export type HomeOption = {
  id: HomeOptionId;
  /** for screen readers only — nothing is written on the tile */
  label: string;
  /** its one color: outline and glyph */
  color: string;
  /** the DTMF key it sounds like when pressed, as on the dial */
  tone: string;
  /** its place on the grid, in units: a rectangle… */
  box?: Box;
  /** …or a round button: its centre, a point of the grid, and its radius in
   *  unit widths */
  circle?: [number, number, number];
  unlocked: boolean;
};

// Roko narrow and atributos wide on top, logs and shop side by side under them,
// jornada wide across the bottom, and agir round where those three meet.
// All of them in jornada's neon cyan, each in a tone of its own.
export const HOME_OPTIONS: HomeOption[] = [
  { id: "act", label: "agir", color: "#00f0ff", tone: "1", unlocked: true,
    circle: [2, 2, 0.9] },
  { id: "attributes", label: "atributos", color: "#00c8ff", tone: "5", unlocked: true,
    box: [1, 0, 3, 1] },
  { id: "roko", label: "roko", color: "#3dfff0", tone: "3", unlocked: true,
    box: [0, 0, 1, 1] },
  { id: "shop", label: "shop", color: "#7af9ff", tone: "2", unlocked: true,
    box: [2, 1, 2, 1] },
  { id: "logs", label: "logs", color: "#00a8e8", tone: "4", unlocked: true,
    box: [0, 1, 2, 1] },
  { id: "journey", label: "jornada", color: "#00ffd0", tone: "6", unlocked: true,
    box: [0, 2, 4, 2] },
];

/** The home's grid: four units across, four down, each unit half again as tall
 *  as it is wide. */
export const HOME_COLS = 4;
export const HOME_ROWS = 4;
export const HOME_ASPECT = 1.5;

export type Glyph = {
  /** round-capped strokes on a 24×24 grid */
  d: string;
  /** dots, drawn as small filled discs */
  dots: Point[];
};

/** The glyphs. Each is a mutation of what the option used to show — the
 *  exclamation grew a hook and a crossbar, the bag became a vessel, the eye lost
 *  its lids — far enough to need learning, close enough to be learned. */
export const GLYPHS: Record<HomeOptionId, Glyph> = {
  act: { d: "M12 3.5 C12.8 7 11 9.5 12 14 M8.8 8.2 L15.2 6.6", dots: [[12, 19]] },
  shop: { d: "M5.5 9.5 C6.5 18.5 17.5 18.5 18.5 9.5 M8.5 9.5 C8.5 4.5 15.5 4.5 15.5 9.5", dots: [[12, 13.5]] },
  roko: { d: "M3.5 12 C7.5 6.5 16.5 6.5 20.5 12 M7 15.5 C10 18 14 18 17 15.5", dots: [[12, 11.5], [4, 17.5]] },
  logs: { d: "M6.5 4.5 C5.8 9 7.2 15 6.5 19.5 M6.5 7.5 H16 M6.5 12 C9 11.4 11 12.6 13 12 M6.5 16.5 H18.5", dots: [[18.5, 7.5]] },
  attributes: { d: "M12 21 V12 M12 15 C9 13 7 11 7 5 M12 12 C14 10 17 8 19 4", dots: [[7, 18.5]] },
  journey: { d: "M7 4.5 C11 4.5 14 6 17 4.5 L7 19.5 C10 18 14 20.5 17 19.5", dots: [[12, 12], [19.5, 7.5]] },
};

/** Dot radius on the 24×24 grid. */
export const DOT_R = 1.5;

/** The option the interface suggests next, whose outline is lit. A placeholder
 *  for the model that will learn to predict what the user does: for now, acting. */
export function suggestedOption(): HomeOptionId | null {
  return "act";
}

/** A color moved toward white (t > 0) or black (t < 0), by |t| of the way. */
export function shade(hex: string, t: number): string {
  const n = parseInt(hex.slice(1), 16);
  const to = t > 0 ? 255 : 0;
  const k = Math.abs(t);
  const c = [n >> 16, (n >> 8) & 255, n & 255].map((v) => Math.round(v + (to - v) * k));
  return "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
}

/** How much of each side of the screen the interface takes, shrunk into its
 *  bottom-right corner. */
export const SHRINK = 0.9;

/** The imaginary grid: three squares across. */
export const GRID_COLS = 3;

/** A cell's size on the grid: two squares side by side, one square, or a
 *  quarter of one — four quarters share a square. */
export type Size = "rect" | "square" | "quarter";

/** Lays cells of the given sizes on the grid in order, rows of GRID_COLS
 *  squares filled left to right; a row that is not full keeps to the right, as
 *  everything floats to the bottom-right corner. The boxes, and how many rows. */
export function pack(sizes: Size[]): { boxes: Box[]; rows: number } {
  // squares first: a rectangle is one two wide, quarters are grouped by four
  const units: { w: number; items: number[] }[] = [];
  sizes.forEach((size, i) => {
    const last = units[units.length - 1];
    if (size === "quarter" && last?.w === -1 && last.items.length < 4) last.items.push(i);
    else units.push({ w: size === "rect" ? 2 : size === "square" ? 1 : -1, items: [i] });
  });
  const rows: (typeof units)[] = [[]];
  let used = 0;
  for (const u of units) {
    const w = Math.abs(u.w);
    if (used + w > GRID_COLS) {
      rows.push([]);
      used = 0;
    }
    rows[rows.length - 1].push(u);
    used += w;
  }
  const boxes: Box[] = [];
  rows.forEach((row, y) => {
    let x = GRID_COLS - row.reduce((s, u) => s + Math.abs(u.w), 0);
    for (const u of row) {
      if (u.w === -1) {
        u.items.forEach((i, k) => (boxes[i] = [x + (k % 2) / 2, y + Math.floor(k / 2) / 2, 0.5, 0.5]));
        x += 1;
      } else {
        boxes[u.items[0]] = [x, y, u.w, 1];
        x += u.w;
      }
    }
  });
  return { boxes, rows: rows.length };
}

/** Draws boxes of a grid `rows` tall with units `side` pixels wide and `aspect`
 *  times as tall, gathered in the bottom-right corner of a w×h area, each pulled
 *  in by `gap` pixels on every side: plain, level rectangles. The polygon, its
 *  centre, width and height. */
export function drawBoxes(boxes: Box[], rows: number, w: number, h: number, side: number, gap: number, aspect = 1) {
  const tall = side * aspect;
  const left = w - GRID_COLS * side;
  const top = h - rows * tall;
  return boxes.map(([bx, by, bw, bh]) => {
    // quarters sit closer together, or they would be all gap
    const g = bw < 1 ? gap / 2 : gap;
    const x0 = left + bx * side + g;
    const y0 = top + by * tall + g;
    const x1 = left + (bx + bw) * side - g;
    const y1 = top + (by + bh) * tall - g;
    const shape: Point[] = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
    return { shape, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: x1 - x0, h: y1 - y0 };
  });
}

/** A small deterministic generator, in −0.5…0.5: the same seed, the same page. */
export function seeded(seed: number): () => number {
  let state = ((seed + 7) * 2654435761) >>> 0 || 1;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return ((state >>> 0) % 10000) / 10000 - 0.5;
  };
}

/** A rectangle with whatever part of it lies inside a circle taken out — the
 *  bite a round button takes from the cells around it. Walks the corners from
 *  one outside the circle; where an edge enters the circle the outline follows
 *  the circle, the short way, to where an edge leaves it. */
export function rectMinusCircle(x0: number, y0: number, x1: number, y1: number, cx: number, cy: number, r: number): Point[] {
  const inside = (p: Point) => Math.hypot(p[0] - cx, p[1] - cy) < r;
  let corners: Point[] = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  const start = corners.findIndex((p) => !inside(p));
  if (start < 0) return corners;
  corners = [...corners.slice(start), ...corners.slice(0, start)];
  const out: Point[] = [];
  let entry: Point | null = null;
  corners.forEach((p, i) => {
    const q = corners[(i + 1) % 4];
    if (!inside(p)) out.push(p);
    // where the edge p→q crosses the circle
    const dx = q[0] - p[0];
    const dy = q[1] - p[1];
    const fx = p[0] - cx;
    const fy = p[1] - cy;
    const a = dx * dx + dy * dy;
    const b = 2 * (fx * dx + fy * dy);
    const disc = b * b - 4 * a * (fx * fx + fy * fy - r * r);
    if (disc <= 0) return;
    const s = Math.sqrt(disc);
    for (const t of [(-b - s) / (2 * a), (-b + s) / (2 * a)]) {
      if (t <= 0 || t >= 1) continue;
      const x: Point = [p[0] + dx * t, p[1] + dy * t];
      if (!entry) entry = x;
      else {
        const a1 = Math.atan2(entry[1] - cy, entry[0] - cx);
        let turn = Math.atan2(x[1] - cy, x[0] - cx) - a1;
        if (turn > Math.PI) turn -= 2 * Math.PI;
        if (turn < -Math.PI) turn += 2 * Math.PI;
        const n = Math.max(2, Math.ceil(Math.abs(turn) / 0.06));
        for (let k = 0; k < n; k++) {
          const an = a1 + (turn * k) / n;
          out.push([cx + r * Math.cos(an), cy + r * Math.sin(an)]);
        }
        entry = null;
      }
      out.push(x);
    }
  });
  return out;
}

/** The centre of a polygon's area: where a glyph sits clear of a bite. */
export function areaCentre(points: Point[]): Point {
  let a = 0;
  let x = 0;
  let y = 0;
  points.forEach((p, i) => {
    const q = points[(i + 1) % points.length];
    const c = p[0] * q[1] - q[0] * p[1];
    a += c;
    x += (p[0] + q[0]) * c;
    y += (p[1] + q[1]) * c;
  });
  return a ? [x / (3 * a), y / (3 * a)] : points[0];
}

/** An SVG path of a circle. */
export function circlePath(cx: number, cy: number, r: number): string {
  const f = (v: number) => v.toFixed(1);
  return `M${f(cx - r)},${f(cy)} A${f(r)},${f(r)} 0 1 0 ${f(cx + r)},${f(cy)} A${f(r)},${f(r)} 0 1 0 ${f(cx - r)},${f(cy)} Z`;
}

/** An SVG path of a polygon, its corners left sharp. */
export function polyPath(points: Point[]): string {
  return "M" + points.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" L") + " Z";
}
