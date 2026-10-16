/** The home screen: the options that cover it, and what they look like.
 *
 * Coordinates are normalized to the screen (0–1 on both axes, portrait) and the
 * rectangles share their edges, so together they tile the area; Home.svelte
 * scales them to where it draws and pulls every edge in to open the gaps.
 *
 * Nothing is written on them: an option is known by its glyph — a sign from a
 * script that does not exist — and its color.
 *
 * `unlocked` is the hook for revealing the options little by little: a locked
 * option is not drawn. Everything is unlocked for now.
 */

export type HomeOptionId = "act" | "logs" | "shop" | "roko" | "attributes" | "journey";

export type Point = [number, number];
/** x0, y0, x1, y1 */
export type Rect = [number, number, number, number];
export type Corner = "tl" | "tr" | "br" | "bl";

export type HomeOption = {
  id: HomeOptionId;
  /** for screen readers only — nothing is written on the tile */
  label: string;
  /** its one color: outline and glyph */
  color: string;
  /** the DTMF key it sounds like when pressed, as on the dial */
  tone: string;
  /** its rectangle in the unit square, x0 y0 x1 y1 */
  rect: Rect;
  /** the corner cut off diagonally, if any */
  cut: Corner | null;
  unlocked: boolean;
};

// Agir stands tall on the right, under the thumb; the other five fill the left.
// Plain rectangles of different sizes, some with a corner cut off diagonally.
// All of them in jornada's neon cyan, each in a tone of its own.
export const HOME_OPTIONS: HomeOption[] = [
  { id: "act", label: "agir", color: "#00f0ff", tone: "1", unlocked: true,
    rect: [0.6, 0, 1, 1], cut: "tl" },
  { id: "attributes", label: "atributos", color: "#00c8ff", tone: "5", unlocked: true,
    rect: [0, 0, 0.27, 0.34], cut: null },
  { id: "roko", label: "roko", color: "#3dfff0", tone: "3", unlocked: true,
    rect: [0.27, 0, 0.6, 0.34], cut: "br" },
  { id: "shop", label: "shop", color: "#7af9ff", tone: "2", unlocked: true,
    rect: [0, 0.34, 0.34, 0.66], cut: "bl" },
  { id: "logs", label: "logs", color: "#00a8e8", tone: "4", unlocked: true,
    rect: [0.34, 0.34, 0.6, 0.66], cut: null },
  { id: "journey", label: "jornada", color: "#00ffd0", tone: "6", unlocked: true,
    rect: [0, 0.66, 0.6, 1], cut: "tr" },
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
export const SHRINK = 0.7;

/** A point of the unit square, placed in the bottom-right SHRINK × SHRINK of a
 *  w×h area. */
export function toCorner([x, y]: Point, w: number, h: number): Point {
  return [w * (1 - SHRINK) + x * w * SHRINK, h * (1 - SHRINK) + y * h * SHRINK];
}

/** A rectangle of the unit square, placed in the corner of a w×h area by
 *  toCorner and pulled in by `gap` pixels on every side, with one corner cut
 *  off diagonally by `cut` of its shorter side. Clockwise from the top left. */
export function cutRect([x0, y0, x1, y1]: Rect, w: number, h: number, gap: number, corner: Corner | null, cut = 0.3): Point[] {
  [x0, y0] = toCorner([x0, y0], w, h);
  [x1, y1] = toCorner([x1, y1], w, h);
  x0 += gap; y0 += gap; x1 -= gap; y1 -= gap;
  const c = corner ? Math.min(x1 - x0, y1 - y0) * cut : 0;
  return [
    ...(corner === "tl" ? [[x0, y0 + c], [x0 + c, y0]] : [[x0, y0]]),
    ...(corner === "tr" ? [[x1 - c, y0], [x1, y0 + c]] : [[x1, y0]]),
    ...(corner === "br" ? [[x1, y1 - c], [x1 - c, y1]] : [[x1, y1]]),
    ...(corner === "bl" ? [[x0 + c, y1], [x0, y1 - c]] : [[x0, y1]]),
  ] as Point[];
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

const CORNERS: Corner[] = ["tl", "tr", "br", "bl"];

/** A corner to cut off, or none — about half the time. */
export function pickCut(rand: () => number): Corner | null {
  const v = rand() + 0.5;
  return v < 0.5 ? null : CORNERS[Math.floor((v - 0.5) * 8) % 4];
}

/** An SVG path of a polygon, its corners left sharp. */
export function polyPath(points: Point[]): string {
  return "M" + points.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" L") + " Z";
}

/** The centre of a shape's bounding box: where its glyph or name sits, a cut
 *  corner not pulling it aside. */
export function centroid(points: Point[]): Point {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}
