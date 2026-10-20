/** Upper case for everything but the Greek ranks: α stays α, where the CSS
 *  upper case would turn it into Α, which reads as a Latin A. */
export function caps(s: string | null | undefined): string {
  return String(s ?? "").replace(/[^α-ω]+/g, (m) => m.toUpperCase());
}
