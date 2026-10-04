/** The home screen: the options that cover it, and what they look like.
 *
 * Coordinates are normalized to the screen (0–1 on both axes, portrait) and the
 * shapes share their vertices, so together they tile the whole screen; Home.svelte
 * scales them to the area it draws in and insets every edge to open the gaps.
 *
 * Nothing is written on them: an option is known by its glyph — a sign from a
 * script that does not exist — and its color.
 *
 * `unlocked` is the hook for revealing the options little by little: a locked
 * option is not drawn. Everything is unlocked for now.
 */

export type HomeOptionId = "act" | "logs" | "shop" | "roko" | "attributes" | "journey";

export type Point = [number, number];

export type HomeOption = {
  id: HomeOptionId;
  /** for screen readers only — nothing is written on the tile */
  label: string;
  /** its one color: outline and glyph */
  color: string;
  /** the DTMF key it sounds like when pressed, as on the dial */
  tone: string;
  polygon: Point[];
  unlocked: boolean;
};

// Agir stands tall on the right, under the thumb; the other five fill the left.
// Colors in the order of discovery: agir, shop, roko, logs, atributos, jornada.
export const HOME_OPTIONS: HomeOption[] = [
  { id: "act", label: "agir", color: "#ffd23f", tone: "1", unlocked: true,
    polygon: [[0.62, 0], [1, 0], [1, 1], [0.56, 1]] },
  { id: "attributes", label: "atributos", color: "#9b6bff", tone: "5", unlocked: true,
    polygon: [[0, 0], [0.34, 0], [0.3, 0.36], [0, 0.32]] },
  { id: "roko", label: "roko", color: "#ff9a3c", tone: "3", unlocked: true,
    polygon: [[0.34, 0], [0.62, 0], [0.6, 0.34], [0.3, 0.36]] },
  { id: "shop", label: "shop", color: "#ff6fb5", tone: "2", unlocked: true,
    polygon: [[0, 0.32], [0.3, 0.36], [0.26, 0.662], [0, 0.68]] },
  { id: "logs", label: "logs", color: "#4d8dff", tone: "4", unlocked: true,
    polygon: [[0.3, 0.36], [0.6, 0.34], [0.5816, 0.64], [0.26, 0.662]] },
  { id: "journey", label: "jornada", color: "#2fe0e6", tone: "6", unlocked: true,
    polygon: [[0, 0.68], [0.5816, 0.64], [0.56, 1], [0, 1]] },
];

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

/** Moves every edge of a convex polygon `d` inwards; vertices are where the moved
 *  edges meet. Works in screen pixels, so every gap is the same width. */
export function inset(points: Point[], d: number): Point[] {
  const n = points.length;
  // orientation, so "inwards" is the same side for every edge
  let area = 0;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % n];
    area += x1 * y2 - x2 * y1;
  }
  const sign = area > 0 ? 1 : -1;
  const lines = points.map((p, i) => {
    const q = points[(i + 1) % n];
    const dx = q[0] - p[0];
    const dy = q[1] - p[1];
    const len = Math.hypot(dx, dy) || 1;
    // left normal for a counter-clockwise polygon
    const nx = (-dy / len) * sign;
    const ny = (dx / len) * sign;
    return { p: [p[0] + nx * d, p[1] + ny * d] as Point, dir: [dx, dy] as Point };
  });
  return lines.map((a, i) => {
    const b = lines[(i + n - 1) % n];
    const cross = b.dir[0] * a.dir[1] - b.dir[1] * a.dir[0];
    if (Math.abs(cross) < 1e-9) return a.p;
    const t = ((a.p[0] - b.p[0]) * a.dir[1] - (a.p[1] - b.p[1]) * a.dir[0]) / cross;
    return [b.p[0] + b.dir[0] * t, b.p[1] + b.dir[1] * t] as Point;
  });
}


/** The option the interface suggests next, whose outline is lit. A placeholder
 *  for the model that will learn to predict what the user does: for now, acting. */
export function suggestedOption(): HomeOptionId | null {
  return "act";
}

/** A grid of `cols` × `rows` quadrilaterals tiling the unit square, its inner
 *  vertices nudged by up to `jitter` so no two pages look alike. Neighbours share
 *  their vertices, so the cells still tile; `seed` makes a page look the same
 *  every time it comes back. */
export function jitteredGrid(cols: number, rows: number, seed: number, jitter = 0.28): Point[][] {
  // a small deterministic generator: the same seed, the same page
  let state = (seed * 2654435761) >>> 0 || 1;
  const rand = () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return ((state >>> 0) % 10000) / 10000 - 0.5;
  };
  const v: Point[][] = [];
  for (let r = 0; r <= rows; r++) {
    v.push([]);
    for (let c = 0; c <= cols; c++) {
      // edges stay on the border; inner vertices move by a share of a cell
      const dx = c > 0 && c < cols ? (rand() * jitter) / cols : 0;
      const dy = r > 0 && r < rows ? (rand() * jitter) / rows : 0;
      v[r].push([c / cols + dx, r / rows + dy]);
    }
  }
  const cells: Point[][] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      cells.push([v[r][c], v[r][c + 1], v[r + 1][c + 1], v[r + 1][c]]);
    }
  }
  return cells;
}

export function centroid(points: Point[]): Point {
  const n = points.length;
  return [
    points.reduce((s, p) => s + p[0], 0) / n,
    points.reduce((s, p) => s + p[1], 0) / n,
  ];
}
