/** Dial keypad feedback: DTMF tone + haptic buzz.
 *
 * Ported from the phone-keypad UI this project used before the dashboard
 * (src/interfaces/web/templates/index.html, removed in 3eb603f). Same twelve
 * frequency pairs, same 0.8 pitch shift and the same feedback delay line —
 * that short echo is what makes it sound like the original.
 */

const FREQS: Record<string, [number, number]> = {
  "1": [697, 1209], "2": [697, 1336], "3": [697, 1477],
  "4": [770, 1209], "5": [770, 1336], "6": [770, 1477],
  "7": [852, 1209], "8": [852, 1336], "9": [852, 1477],
  "0": [941, 1336], "*": [941, 1209], "#": [941, 1477],
};

const PITCH = 0.8;

let ctx: AudioContext | null = null;
let muted = false;

/** Create or resume the context. Browsers only allow this from a user gesture,
 *  so call it from the click that opens the keypad. */
export function primeAudio(): void {
  try {
    if (!ctx) {
      const Ctor = window.AudioContext ?? (window as any).webkitAudioContext;
      if (!Ctor) return;
      ctx = new Ctor();
    }
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
  } catch {
    ctx = null;
  }
}

export function setMuted(value: boolean): void {
  muted = value;
}

export function playTone(digit: string, duration = 100): void {
  if (muted || !ctx || !FREQS[digit]) return;
  try {
    const [f1, f2] = FREQS[digit];
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();
    const delay = ctx.createDelay(1.0);
    const feedback = ctx.createGain();
    const wet = ctx.createGain();
    const dry = ctx.createGain();

    osc1.type = "sine";
    osc2.type = "sine";
    osc1.frequency.value = f1 * PITCH;
    osc2.frequency.value = f2 * PITCH;
    delay.delayTime.value = 0.12;
    feedback.gain.value = 0.35;
    wet.gain.value = 0.35;
    dry.gain.value = 0.8;

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(dry);
    gain.connect(delay);
    delay.connect(feedback);
    feedback.connect(delay);
    delay.connect(wet);
    dry.connect(ctx.destination);
    wet.connect(ctx.destination);

    const now = ctx.currentTime;
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.1, now + 0.01);
    gain.gain.linearRampToValueAtTime(0, now + duration / 1000);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + duration / 1000);
    osc2.stop(now + duration / 1000);
  } catch {
    /* audio is a nicety, never break the input over it */
  }
}

export function buzz(pattern: number | number[] = 10): void {
  try {
    navigator.vibrate?.(pattern as any);
  } catch {
    /* not supported on desktop */
  }
}

/** Tone + buzz for one key press. */
export function keyFeedback(digit: string): void {
  playTone(digit);
  buzz(10);
}
