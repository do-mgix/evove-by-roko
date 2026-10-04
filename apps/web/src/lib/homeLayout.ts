/** The home screen: the options that cover it, and what they look like.
 *
 * Coordinates are normalized to the screen (0–1 on both axes, portrait) and the
 * shapes share their vertices, so together they tile the whole screen; Home.svelte
 * scales them to the measured size, insets every edge to open the gaps and lets the
 * outlines drift through a slow displacement field, so the tiles read as cells
 * rather than buttons.
 *
 * Nothing is written on them and nothing is colored: an option is known by its
 * glyph alone, a sign from a script that does not exist.
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
  /** the DTMF key it sounds like when pressed, as on the dial */
  tone: string;
  polygon: Point[];
  unlocked: boolean;
};

export const HOME_OPTIONS: HomeOption[] = [
  { id: "attributes", label: "atributos", tone: "5", unlocked: true,
    polygon: [[0, 0], [0.58, 0], [0.52, 0.29], [0, 0.25]] },
  { id: "roko", label: "roko", tone: "3", unlocked: true,
    polygon: [[0.58, 0], [1, 0], [1, 0.33], [0.52, 0.29]] },
  { id: "shop", label: "shop", tone: "2", unlocked: true,
    polygon: [[0, 0.25], [0.52, 0.29], [0.42, 0.55], [0, 0.586]] },
  { id: "logs", label: "logs", tone: "4", unlocked: true,
    polygon: [[0.52, 0.29], [0.8, 0.313], [0.77, 0.52], [0.42, 0.55]] },
  { id: "journey", label: "jornada", tone: "6", unlocked: true,
    polygon: [[0.8, 0.313], [1, 0.33], [1, 1], [0.7, 1]] },
  { id: "act", label: "agir", tone: "1", unlocked: true,
    polygon: [[0, 0.586], [0.77, 0.52], [0.7, 1], [0, 1]] },
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


/** The outline of a convex polygon with rounded corners, as a dense list of
 *  points — dense enough to bend smoothly once displaced. */
export function outline(points: Point[], r: number, step = 10): Point[] {
  const n = points.length;
  const cut = (from: Point, to: Point): Point => {
    const dx = to[0] - from[0];
    const dy = to[1] - from[1];
    const d = Math.hypot(dx, dy) || 1;
    const k = Math.min(r, d / 2) / d;
    return [from[0] + dx * k, from[1] + dy * k];
  };
  const out: Point[] = [];
  for (let i = 0; i < n; i++) {
    const p = points[i];
    const a = cut(p, points[(i + n - 1) % n]);
    const b = cut(p, points[(i + 1) % n]);
    // the corner: a quadratic curve through the vertex
    for (let s = 0; s < 6; s++) {
      const t = s / 6;
      const u = 1 - t;
      out.push([u * u * a[0] + 2 * u * t * p[0] + t * t * b[0], u * u * a[1] + 2 * u * t * p[1] + t * t * b[1]]);
    }
    // the edge to the next corner, sampled every `step` pixels
    const next = points[(i + 1) % n];
    const c = cut(next, p);
    const len = Math.hypot(c[0] - b[0], c[1] - b[1]);
    const k = Math.max(1, Math.round(len / step));
    for (let s = 0; s < k; s++) {
      const t = s / k;
      out.push([b[0] + (c[0] - b[0]) * t, b[1] + (c[1] - b[1]) * t]);
    }
  }
  return out;
}

/** A slow, smooth displacement field. Neighbours sample it at nearly the same
 *  places, so their walls bend together and the gap between them holds. */
export function displace(points: Point[], amp: number, t: number): Point[] {
  return points.map(([x, y]) => [
    x + amp * Math.sin(x / 83 + y / 131 + t),
    y + amp * Math.cos(x / 109 - y / 97 + t * 1.3),
  ]);
}

/** A closed, smooth path through `points` (Catmull-Rom as cubic Béziers). */
export function smoothPath(points: Point[]): string {
  const n = points.length;
  const f = (v: number) => v.toFixed(1);
  let d = `M${f(points[0][0])} ${f(points[0][1])}`;
  for (let i = 0; i < n; i++) {
    const p0 = points[(i + n - 1) % n];
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += `C${f(c1x)} ${f(c1y)} ${f(c2x)} ${f(c2y)} ${f(p2[0])} ${f(p2[1])}`;
  }
  return d + "Z";
}

/** The option the interface suggests next, which glows a little. A placeholder
 *  for the model that will learn to predict what the user does: for now, acting. */
export function suggestedOption(): HomeOptionId | null {
  return "act";
}

export function centroid(points: Point[]): Point {
  const n = points.length;
  return [
    points.reduce((s, p) => s + p[0], 0) / n,
    points.reduce((s, p) => s + p[1], 0) / n,
  ];
}
