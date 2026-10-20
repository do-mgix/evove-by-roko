/** Generic icons, for buttons that are not one of the home's options: plain
 *  shapes, arrows and an ellipsis, drawn like the glyphs — round-capped strokes
 *  on a 24×24 grid, and dots. */

import type { Glyph } from "./homeLayout";

export type IconName =
  | "circle" | "square" | "triangle" | "diamond" | "plus" | "cross"
  | "right" | "left" | "up" | "down" | "dots" | "shuffle"
  | "check" | "calendar" | "book" | "pencil" | "trash" | "clock" | "pause" | "play"
  | "flag" | "star" | "heart" | "sword" | "shield" | "bars" | "user" | "list" | "tree"
  | "eye" | "coin" | "chat" | "link" | "dice" | "bolt" | "scan" | "amulet";

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
  check: { d: "M5 12.5 L10 17.5 L19 7", dots: [] },
  calendar: { d: "M5 7 H19 V19 H5 Z M5 10.5 H19 M9 4.5 V8 M15 4.5 V8", dots: [] },
  book: { d: "M12 6.5 C10.5 5 7.5 5 5 5.5 V18 C7.5 17.5 10.5 17.5 12 19 C13.5 17.5 16.5 17.5 19 18 V5.5 C16.5 5 13.5 5 12 6.5 Z M12 6.5 V19", dots: [] },
  pencil: { d: "M5 19 L6 15 L15.5 5.5 L18.5 8.5 L9 18 Z M13.5 7.5 L16.5 10.5", dots: [] },
  trash: { d: "M6 7 H18 M9.5 7 V5 H14.5 V7 M7.5 7 L8.5 19 H15.5 L16.5 7", dots: [] },
  clock: { d: "M5 12 A7 7 0 1 0 19 12 A7 7 0 1 0 5 12 Z M12 8 V12 L15 14", dots: [] },
  pause: { d: "M9 6 V18 M15 6 V18", dots: [] },
  play: { d: "M8 5.5 L18 12 L8 18.5 Z", dots: [] },
  flag: { d: "M6 20 V4.5 M6 5 H17 L14.5 8.5 L17 12 H6", dots: [] },
  star: { d: "M12 4 L14.3 9 L19.6 9.5 L15.5 13 L16.8 18.3 L12 15.5 L7.2 18.3 L8.5 13 L4.4 9.5 L9.7 9 Z", dots: [] },
  heart: { d: "M12 19 C5 14 4 10.5 5.5 8 C7 5.6 10.5 5.8 12 8.5 C13.5 5.8 17 5.6 18.5 8 C20 10.5 19 14 12 19 Z", dots: [] },
  sword: { d: "M14.5 4.5 H19.5 V9.5 L10 19 H7.5 L5 16.5 V14 Z M6.5 12.5 L11.5 17.5 M4.5 19.5 L7 17", dots: [] },
  shield: { d: "M12 4 L19 6.5 V11.5 C19 15.5 16 18.5 12 20 C8 18.5 5 15.5 5 11.5 V6.5 Z", dots: [] },
  bars: { d: "M6 19 V12 M12 19 V6 M18 19 V9", dots: [] },
  user: { d: "M12 4.5 A3.5 3.5 0 1 0 12 11.5 A3.5 3.5 0 1 0 12 4.5 Z M5.5 19.5 C6.5 15.5 9 14 12 14 C15 14 17.5 15.5 18.5 19.5", dots: [] },
  list: { d: "M9 7 H19 M9 12 H19 M9 17 H19", dots: [[5, 7], [5, 12], [5, 17]] },
  tree: { d: "M12 6.5 V10 M12 10 H6.5 V14.5 M12 10 H17.5 V14.5 M12 10 V14.5", dots: [[12, 4.5], [6.5, 17], [12, 17], [17.5, 17]] },
  eye: { d: "M3.5 12 C7 6.5 17 6.5 20.5 12 C17 17.5 7 17.5 3.5 12 Z", dots: [[12, 12]] },
  coin: { d: "M5 12 A7 7 0 1 0 19 12 A7 7 0 1 0 5 12 Z M12 8.5 V15.5", dots: [] },
  chat: { d: "M5 6 H19 V15 H11 L7 18.5 V15 H5 Z", dots: [] },
  link: { d: "M10 14 L14 10 M8.5 11.5 L6.5 13.5 A3 3 0 0 0 10.5 17.5 L12.5 15.5 M15.5 12.5 L17.5 10.5 A3 3 0 0 0 13.5 6.5 L11.5 8.5", dots: [] },
  dice: { d: "M5.5 5.5 H18.5 V18.5 H5.5 Z", dots: [[9, 9], [15, 15], [12, 12]] },
  bolt: { d: "M13 3.5 L6.5 13 H11.5 L10.5 20.5 L17.5 10.5 H12.5 Z", dots: [] },
  scan: { d: "M4 8 V4 H8 M16 4 H20 V8 M20 16 V20 H16 M8 20 H4 V16", dots: [[12, 12]] },
  amulet: { d: "M7 4.5 L12 11 L17 4.5 M12 13 L15.5 16.5 L12 20 L8.5 16.5 Z", dots: [] },
};

/** The icons a built button may wear, in the order a long press walks them. */
export const BUTTON_ICONS: IconName[] = [
  "circle", "square", "triangle", "diamond", "plus", "cross", "right", "left", "up", "down", "dots",
];
