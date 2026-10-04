/** The interface's one sound: a scatter of low, bell-like glints — a deep
 *  shimmer, one or two of them — over a soft impact, in a room with a moderate
 *  echo.
 *
 * Synthesized with Web Audio — no files to ship. Three strengths of the same
 * sound: a light `tap` for every button, `powerOn` when a screen of cells comes
 * on, and the full `gains` when an act pays out. The context is the dial's
 * (src/lib/dtmf.ts), so nothing plays until a tap has primed it.
 */
import { audioContext, buzz } from "./dtmf";

type Strength = {
  /** loudness of the dry sound */
  gain: number;
  /** how much of it reaches the room */
  wet: number;
  /** seconds of the impact's fall */
  thump: number;
  /** how many glints, and over how many seconds they scatter */
  glints: number;
  spread: number;
};

const TAP: Strength = { gain: 0.35, wet: 0.2, thump: 0.18, glints: 1, spread: 0 };
const POWER_ON: Strength = { gain: 0.4, wet: 0.3, thump: 0.3, glints: 2, spread: 0.12 };
const GAINS: Strength = { gain: 0.45, wet: 0.4, thump: 0.45, glints: 2, spread: 0.18 };

// The room: a stereo impulse response of decaying noise, built once — two
// seconds, enough for the glints to ring a little without trailing on.
let hall: ConvolverNode | null = null;
let hallOf: AudioContext | null = null;

function space(ctx: AudioContext): ConvolverNode {
  if (hall && hallOf === ctx) return hall;
  const seconds = 2;
  const length = Math.floor(ctx.sampleRate * seconds);
  const ir = ctx.createBuffer(2, length, ctx.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const data = ir.getChannelData(ch);
    for (let i = 0; i < length; i++) {
      // a few early reflections, then a long, slightly uneven tail
      const t = i / length;
      const early = i < ctx.sampleRate * 0.08 && i % 997 < 40 ? 0.6 : 0;
      data[i] = ((Math.random() * 2 - 1) + early) * Math.pow(1 - t, 3.5);
    }
  }
  hall = ctx.createConvolver();
  hall.buffer = ir;
  hallOf = ctx;
  return hall;
}

let noiseBuffer: AudioBuffer | null = null;
function noise(ctx: AudioContext): AudioBuffer {
  if (noiseBuffer && noiseBuffer.sampleRate === ctx.sampleRate) return noiseBuffer;
  noiseBuffer = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
  const d = noiseBuffer.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return noiseBuffer;
}

/** `pitch` shifts the whole sound (1 = as designed), so options can differ. */
function play(s: Strength, pitch = 1): void {
  const ctx = audioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const out = ctx.createGain();
    out.gain.value = s.gain;
    const wet = ctx.createGain();
    wet.gain.value = s.wet;
    out.connect(ctx.destination);
    out.connect(wet);
    wet.connect(space(ctx));
    space(ctx).connect(ctx.destination);

    // The impact, underneath and quiet: a deep tone falling to the floor, with a
    // dull burst on top. A triangle rather than a sine: a phone's speaker barely
    // moves below 150 Hz, and the triangle's overtones let the ear hear it.
    const body = ctx.createOscillator();
    const bodyGain = ctx.createGain();
    body.type = "triangle";
    body.frequency.setValueAtTime(95 * pitch, now);
    body.frequency.exponentialRampToValueAtTime(30 * pitch, now + s.thump);
    bodyGain.gain.setValueAtTime(0.0001, now);
    bodyGain.gain.exponentialRampToValueAtTime(0.35, now + 0.006);
    bodyGain.gain.exponentialRampToValueAtTime(0.001, now + s.thump);
    body.connect(bodyGain).connect(out);
    body.start(now);
    body.stop(now + s.thump + 0.02);

    // a second, lower sine an octave down gives it weight
    const sub = ctx.createOscillator();
    const subGain = ctx.createGain();
    sub.type = "sine";
    sub.frequency.setValueAtTime(48 * pitch, now);
    sub.frequency.exponentialRampToValueAtTime(24 * pitch, now + s.thump);
    subGain.gain.setValueAtTime(0.0001, now);
    subGain.gain.exponentialRampToValueAtTime(0.2, now + 0.01);
    subGain.gain.exponentialRampToValueAtTime(0.001, now + s.thump * 1.2);
    sub.connect(subGain).connect(out);
    sub.start(now);
    sub.stop(now + s.thump * 1.2 + 0.02);

    const burst = ctx.createBufferSource();
    burst.buffer = noise(ctx);
    const low = ctx.createBiquadFilter();
    low.type = "lowpass";
    low.frequency.value = 380 * pitch;
    const burstGain = ctx.createGain();
    burstGain.gain.setValueAtTime(0.15, now);
    burstGain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);
    burst.connect(low).connect(burstGain).connect(out);
    burst.start(now);
    burst.stop(now + 0.08);

    // The shimmer, in front: one or two low glints, the second a moment after
    // the first. Each is a pair of sines a hair apart, whose beating makes it
    // twinkle; low notes ring longer, so they decay slower than a high sparkle
    // would. Part of them goes on into the room.
    const shimmer = ctx.createGain();
    shimmer.gain.value = 0.3;
    shimmer.connect(out);
    const glow = ctx.createGain();
    glow.gain.value = 0.4;
    shimmer.connect(glow);
    glow.connect(space(ctx));
    for (let i = 0; i < s.glints; i++) {
      // the first right away, the second (if any) at the end of the window
      const t0 = now + 0.01 + (i === 0 ? 0 : s.spread);
      const f = (220 + Math.random() * 230) * pitch;
      const decay = 0.12 + Math.random() * 0.13;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(0.4, t0 + 0.008);
      g.gain.exponentialRampToValueAtTime(0.001, t0 + decay);
      g.connect(shimmer);
      for (const detune of [1, 1.005 + Math.random() * 0.005]) {
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = f * detune;
        osc.connect(g);
        osc.start(t0);
        osc.stop(t0 + decay + 0.02);
      }
    }
  } catch {
    /* sound is a nicety, never break the interface over it */
  }
}

/** Every button: light, with a buzz. `variant` (0–9) nudges the pitch. */
export function tap(variant = 0): void {
  play(TAP, 0.9 + (variant % 10) * 0.03);
  buzz(10);
}

/** A screen of cells coming on. */
export function powerOn(): void {
  play(POWER_ON, 0.9);
}

/** What an act paid, arriving. */
export function gains(): void {
  play(GAINS, 0.75);
  buzz([20, 40, 20]);
}
