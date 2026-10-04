/** The home screen: the options that cover it, as quadrilaterals.
 *
 * Coordinates are normalized to the screen (0–1 on both axes, portrait) and the
 * shapes share their vertices, so together they tile the whole screen; Home.svelte
 * scales them to the measured size and insets every edge to open the gaps.
 *
 * `unlocked` is the hook for revealing the options little by little: a locked
 * option is not drawn. Everything is unlocked for now.
 */

export type HomeOptionId = "act" | "logs" | "shop" | "roko" | "attributes" | "journey";

export type Point = [number, number];

export type HomeOption = {
  id: HomeOptionId;
  label: string;
  icon: IconName;
  /** the DTMF key it sounds like when pressed, as on the dial */
  tone: string;
  polygon: Point[];
  unlocked: boolean;
};

export type IconName = "exclamation" | "square" | "bag" | "eye" | "bars" | "hourglass";

export const HOME_OPTIONS: HomeOption[] = [
  {
    id: "attributes", label: "atributos", icon: "bars", tone: "5", unlocked: true,
    polygon: [[0, 0], [0.58, 0], [0.52, 0.29], [0, 0.25]],
  },
  {
    id: "roko", label: "roko", icon: "eye", tone: "3", unlocked: true,
    polygon: [[0.58, 0], [1, 0], [1, 0.33], [0.52, 0.29]],
  },
  {
    id: "shop", label: "shop", icon: "bag", tone: "2", unlocked: true,
    polygon: [[0, 0.25], [0.52, 0.29], [0.42, 0.55], [0, 0.586]],
  },
  {
    id: "logs", label: "logs", icon: "square", tone: "4", unlocked: true,
    polygon: [[0.52, 0.29], [0.8, 0.313], [0.77, 0.52], [0.42, 0.55]],
  },
  {
    id: "journey", label: "jornada", icon: "hourglass", tone: "6", unlocked: true,
    polygon: [[0.8, 0.313], [1, 0.33], [1, 1], [0.7, 1]],
  },
  {
    id: "act", label: "agir", icon: "exclamation", tone: "1", unlocked: true,
    polygon: [[0, 0.586], [0.77, 0.52], [0.7, 1], [0, 1]],
  },
];

/** Icons on a 24×24 grid, stroked in the tile's color. */
export const ICONS: Record<IconName, string> = {
  exclamation: "M12 3 L12 15 M12 19.5 L12 21",
  square: "M5 5 H19 V19 H5 Z",
  bag: "M4 8 H20 L18.5 21 H5.5 Z M8.5 8 V6.5 A3.5 3.5 0 0 1 15.5 6.5 V8",
  eye: "M2 12 C6 5 18 5 22 12 C18 19 6 19 2 12 Z M12 9 A3 3 0 1 0 12 15 A3 3 0 1 0 12 9 Z",
  bars: "M5 20 V14 M12 20 V9 M19 20 V4",
  hourglass: "M6 3 H18 M6 21 H18 M7 3 C7 9 17 9 17 12 C17 15 7 15 7 21 M17 3 C17 9 7 9 7 12 C7 15 17 15 17 21",
};

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

export function centroid(points: Point[]): Point {
  const n = points.length;
  return [
    points.reduce((s, p) => s + p[0], 0) / n,
    points.reduce((s, p) => s + p[1], 0) / n,
  ];
}
