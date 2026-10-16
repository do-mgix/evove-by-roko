/** Generic icons, for buttons that are not one of the home's options: plain
 *  shapes, arrows and an ellipsis, drawn like the glyphs — round-capped strokes
 *  on a 24×24 grid, and dots. */

import type { Glyph } from "./homeLayout";

export type IconName =
  | "circle" | "square" | "triangle" | "diamond" | "plus" | "cross"
  | "right" | "left" | "up" | "down" | "dots" | "shuffle";

export const ICONS: Record<IconName, Glyph> = {
  circle: { d: "M5 12 A7 7 0 1 0 19 12 A7 7 0 1 0 5 12 Z", dots: [] },
  square: { d: "M6 6 H18 V18 H6 Z", dots: [] },
  triangle: { d: "M12 5 L19 18 H5 Z", dots: [] },
  diamond: { d: "M12 4 L20 12 L12 20 L4 12 Z", dots: [] },
  plus: { d: "M12 5 V19 M5 12 H19", dots: [] },
  cross: { d: "M6.5 6.5 L17.5 17.5 M17.5 6.5 L6.5 17.5", dots: [] },
  right: { d: "M5 12 H19 M13 6 L19 12 L13 18", dots: [] },
  left: { d: "M19 12 H5 M11 6 L5 12 L11 18", dots: [] },
  up: { d: "M12 19 V5 M6 11 L12 5 L18 11", dots: [] },
  down: { d: "M12 5 V19 M6 13 L12 19 L18 13", dots: [] },
  dots: { d: "", dots: [[6, 12], [12, 12], [18, 12]] },
  shuffle: { d: "M4 7 H8 L16 17 H20 M4 17 H8 L16 7 H20 M17.5 4.5 L20 7 L17.5 9.5 M17.5 14.5 L20 17 L17.5 19.5", dots: [] },
};

/** The icons a built button may wear, in the order a long press walks them. */
export const BUTTON_ICONS: IconName[] = [
  "circle", "square", "triangle", "diamond", "plus", "cross", "right", "left", "up", "down", "dots",
];
