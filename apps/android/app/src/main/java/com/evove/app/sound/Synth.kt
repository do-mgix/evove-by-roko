package com.evove.app.sound

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt
import java.util.Random

/** The interface's sounds, synthesized: the same graphs the web client built
 *  with Web Audio (apps/web/src/lib/sfx.ts and dtmf.ts), rendered offline into
 *  samples instead of played live.
 *
 * The app does not call this while it runs. SoundExport (in the unit tests)
 * renders every sound once into res/raw, and Sfx plays those files, which costs
 * the phone nothing at tap time. Change a sound here, export again, and the
 * next build carries it.
 */
object Synth {
    /** The sounds' content stays under a few kHz (low glints, a lowpassed
     *  thump, a triangle's falling overtones), so a low rate loses nothing. */
    const val RATE = 22050

    /** Two channels of samples. */
    class Stereo(val left: FloatArray, val right: FloatArray) {
        val frames get() = left.size
    }

    /** Three strengths of the same sound, as in sfx.ts. */
    data class Strength(val gain: Double, val wet: Double, val thump: Double, val glints: Int, val spread: Double)

    val TAP = Strength(gain = 0.35, wet = 0.2, thump = 0.18, glints = 1, spread = 0.0)
    val POWER_ON = Strength(gain = 0.4, wet = 0.3, thump = 0.3, glints = 2, spread = 0.12)
    val GAINS = Strength(gain = 0.45, wet = 0.4, thump = 0.45, glints = 2, spread = 0.18)

    /** A light `tap` for every button; `variant` (0–9) nudges the pitch. */
    fun tap(variant: Int, random: Random = Random()) = play(TAP, 0.9 + (variant % 10) * 0.03, random)

    /** A screen of cells coming on. */
    fun powerOn(random: Random = Random()) = play(POWER_ON, 0.9, random)

    /** What an act paid, arriving. */
    fun gains(random: Random = Random()) = play(GAINS, 0.75, random)

    // ---------------------------------------------------------------- the sound

    /** A scatter of low, bell-like glints over a soft impact, in a room with a
     *  moderate echo. `pitch` shifts the whole sound (1 = as designed). */
    fun play(s: Strength, pitch: Double, random: Random): Stereo {
        val hall = hall(random)
        val length = seconds(maxOf(s.thump * 1.2 + 0.02, 0.08, 0.01 + s.spread + 0.27))
        // what goes through the gain of the dry sound, and the glints alone
        val bus = DoubleArray(length)
        val glints = DoubleArray(length)

        // The impact, underneath and quiet: a deep triangle falling to the floor.
        // A phone's speaker barely moves below 150 Hz; the triangle's overtones
        // let the ear hear it.
        val bodyFreq = Param(95 * pitch).set(95 * pitch, 0.0).exp(30 * pitch, s.thump)
        val bodyGain = Param(0.0).set(0.0001, 0.0).exp(0.35, 0.006).exp(0.001, s.thump)
        oscillator(bus, Wave.TRIANGLE, bodyFreq, bodyGain, 0.0, s.thump + 0.02)

        // a second, lower sine an octave down gives it weight
        val subFreq = Param(48 * pitch).set(48 * pitch, 0.0).exp(24 * pitch, s.thump)
        val subGain = Param(0.0).set(0.0001, 0.0).exp(0.2, 0.01).exp(0.001, s.thump * 1.2)
        oscillator(bus, Wave.SINE, subFreq, subGain, 0.0, s.thump * 1.2 + 0.02)

        // a dull burst on top: noise, lowpassed
        val burst = DoubleArray(seconds(0.08)) { random.nextDouble() * 2 - 1 }
        lowpass(burst, 380 * pitch)
        val burstGain = Param(0.15).set(0.15, 0.0).exp(0.001, 0.06)
        for (i in burst.indices) bus[i] += burst[i] * burstGain.at(i.toDouble() / RATE)

        // The shimmer, in front: one or two low glints, the second a moment
        // after the first. Each is a pair of sines a hair apart, whose beating
        // makes it twinkle.
        for (n in 0 until s.glints) {
            val t0 = 0.01 + if (n == 0) 0.0 else s.spread
            val f = (220 + random.nextDouble() * 230) * pitch
            val decay = 0.12 + random.nextDouble() * 0.13
            val g = Param(0.0).set(0.0001, t0).exp(0.4, t0 + 0.008).exp(0.001, t0 + decay)
            for (detune in doubleArrayOf(1.0, 1.005 + random.nextDouble() * 0.005)) {
                oscillator(glints, Wave.SINE, Param(f * detune), g, t0, t0 + decay + 0.02)
            }
        }

        // the mix: the shimmer joins the bus; the dry sound reaches the room
        // through `wet`, and part of the shimmer goes on into it by itself
        val dry = DoubleArray(length)
        val room = DoubleArray(length)
        for (i in 0 until length) {
            val shimmer = 0.3 * glints[i]
            dry[i] = s.gain * (bus[i] + shimmer)
            room[i] = s.wet * dry[i] + 0.4 * shimmer
        }
        val left = convolve(room, hall.left)
        val right = convolve(room, hall.right)
        return finish(Stereo(
            FloatArray(left.size) { (left[it] + dry.getOrElse(it) { 0.0 }).toFloat() },
            FloatArray(right.size) { (right[it] + dry.getOrElse(it) { 0.0 }).toFloat() },
        ))
    }

    /** The room: a stereo impulse response of decaying noise — two seconds,
     *  enough for the glints to ring a little without trailing on — scaled as a
     *  Web Audio convolver normalizes its buffer. */
    private fun hall(random: Random): Stereo {
        val length = seconds(2.0)
        val ch = Array(2) {
            FloatArray(length) { i ->
                // a few early reflections, then a long, slightly uneven tail
                val t = i.toDouble() / length
                val early = if (i < RATE * 0.08 && i % 997 < 40) 0.6 else 0.0
                (((random.nextDouble() * 2 - 1) + early) * (1 - t).pow(3.5)).toFloat()
            }
        }
        var power = 0.0
        for (c in ch) for (v in c) power += v.toDouble() * v
        power = sqrt(power / (2.0 * length))
        val scale = (1 / power.coerceAtLeast(0.000125)) * 0.00125 * 44100.0 / RATE
        for (c in ch) for (i in c.indices) c[i] = (c[i] * scale).toFloat()
        return Stereo(ch[0], ch[1])
    }

    // ---------------------------------------------------------------- the dial

    private val DTMF = mapOf(
        '1' to (697 to 1209), '2' to (697 to 1336), '3' to (697 to 1477),
        '4' to (770 to 1209), '5' to (770 to 1336), '6' to (770 to 1477),
        '7' to (852 to 1209), '8' to (852 to 1336), '9' to (852 to 1477),
        '0' to (941 to 1336), '*' to (941 to 1209), '#' to (941 to 1477),
    )

    /** A key of the old dial: its DTMF pair shifted down by 0.8, with the short
     *  feedback echo that made it sound like the original keypad. */
    fun dtmf(digit: Char, durationMs: Int = 100): Stereo {
        val (f1, f2) = DTMF[digit] ?: return Stereo(FloatArray(0), FloatArray(0))
        val d = durationMs / 1000.0
        val tone = DoubleArray(seconds(d))
        val gain = Param(0.0).set(0.0, 0.0).lin(0.1, 0.01).lin(0.0, d)
        oscillator(tone, Wave.SINE, Param(f1 * 0.8), gain, 0.0, d)
        oscillator(tone, Wave.SINE, Param(f2 * 0.8), gain, 0.0, d)
        val delay = seconds(0.12)
        val out = DoubleArray(tone.size + delay * 12)
        val line = DoubleArray(out.size)  // what enters the delay
        for (i in out.indices) {
            val x = tone.getOrElse(i) { 0.0 }
            val echoed = if (i >= delay) line[i - delay] else 0.0
            line[i] = x + 0.35 * echoed
            out[i] = 0.8 * x + 0.35 * echoed
        }
        val mono = FloatArray(out.size) { out[it].toFloat() }
        return finish(Stereo(mono, mono.copyOf()))
    }

    // ---------------------------------------------------------------- the parts

    private fun seconds(s: Double) = (s * RATE).toInt() + 1

    private enum class Wave { SINE, TRIANGLE }

    /** An AudioParam's automation: values set at times, and ramps to them. */
    private class Param(private val initial: Double) {
        private class Event(val time: Double, val value: Double, val ramp: Char)
        private val events = mutableListOf<Event>()
        fun set(v: Double, t: Double) = apply { events += Event(t, v, 's') }
        fun lin(v: Double, t: Double) = apply { events += Event(t, v, 'l') }
        fun exp(v: Double, t: Double) = apply { events += Event(t, v, 'e') }

        fun at(t: Double): Double {
            var before: Event? = null
            for (e in events) {
                if (e.time <= t) { before = e; continue }
                // the next event: a ramp toward it runs from the one before
                if (e.ramp == 's') break
                val t1 = before?.time ?: 0.0
                val v1 = before?.value ?: initial
                val k = ((t - t1) / (e.time - t1)).coerceIn(0.0, 1.0)
                return if (e.ramp == 'l') v1 + (e.value - v1) * k else v1 * (e.value / v1).pow(k)
            }
            return before?.value ?: initial
        }
    }

    private fun oscillator(into: DoubleArray, wave: Wave, freq: Param, gain: Param, start: Double, stop: Double) {
        var phase = 0.0
        val from = (start * RATE).toInt()
        val to = minOf(into.size, (stop * RATE).toInt())
        for (i in from until to) {
            val t = i.toDouble() / RATE
            val v = when (wave) {
                Wave.SINE -> sin(2 * PI * phase)
                Wave.TRIANGLE -> 1 - 4 * abs(((phase + 0.25) % 1.0) - 0.5)
            }
            into[i] += v * gain.at(t)
            phase = (phase + freq.at(t) / RATE) % 1.0
        }
    }

    /** Web Audio's lowpass biquad, at its default Q of 1 dB. */
    private fun lowpass(x: DoubleArray, freq: Double) {
        val w0 = 2 * PI * freq / RATE
        val alpha = sin(w0) / (2 * 10.0.pow(1.0 / 20))
        val c = cos(w0)
        val a0 = 1 + alpha
        val b0 = (1 - c) / 2 / a0
        val b1 = (1 - c) / a0
        val b2 = b0
        val a1 = -2 * c / a0
        val a2 = (1 - alpha) / a0
        var x1 = 0.0; var x2 = 0.0; var y1 = 0.0; var y2 = 0.0
        for (i in x.indices) {
            val y = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2 = x1; x1 = x[i]; y2 = y1; y1 = y
            x[i] = y
        }
    }

    /** Linear convolution, through the FFT: the room is two seconds long. */
    private fun convolve(signal: DoubleArray, ir: FloatArray): DoubleArray {
        val n = signal.size + ir.size - 1
        var size = 1
        while (size < n) size = size shl 1
        val ar = DoubleArray(size).also { signal.copyInto(it) }
        val ai = DoubleArray(size)
        val br = DoubleArray(size).also { for (i in ir.indices) it[i] = ir[i].toDouble() }
        val bi = DoubleArray(size)
        fft(ar, ai, false)
        fft(br, bi, false)
        for (i in 0 until size) {
            val r = ar[i] * br[i] - ai[i] * bi[i]
            val im = ar[i] * bi[i] + ai[i] * br[i]
            ar[i] = r; ai[i] = im
        }
        fft(ar, ai, true)
        return DoubleArray(n) { ar[it] / size }
    }

    private fun fft(re: DoubleArray, im: DoubleArray, inverse: Boolean) {
        val n = re.size
        var j = 0
        for (i in 1 until n) {
            var bit = n shr 1
            while (j and bit != 0) { j = j xor bit; bit = bit shr 1 }
            j = j xor bit
            if (i < j) {
                re[i] = re[j].also { re[j] = re[i] }
                im[i] = im[j].also { im[j] = im[i] }
            }
        }
        var len = 2
        while (len <= n) {
            val ang = 2 * PI / len * if (inverse) 1 else -1
            val wr = cos(ang); val wi = sin(ang)
            var i = 0
            while (i < n) {
                var cr = 1.0; var ci = 0.0
                for (k in 0 until len / 2) {
                    val ur = re[i + k]; val ui = im[i + k]
                    val vr = re[i + k + len / 2] * cr - im[i + k + len / 2] * ci
                    val vi = re[i + k + len / 2] * ci + im[i + k + len / 2] * cr
                    re[i + k] = ur + vr; im[i + k] = ui + vi
                    re[i + k + len / 2] = ur - vr; im[i + k + len / 2] = ui - vi
                    val nr = cr * wr - ci * wi
                    ci = cr * wi + ci * wr; cr = nr
                }
                i += len
            }
            len = len shl 1
        }
    }

    /** Clipped as the speaker's output would clip it, and cut where it falls
     *  under −60 dB, with a short fade so the cut does not click. */
    private fun finish(s: Stereo): Stereo {
        var end = s.frames
        while (end > 0 && abs(s.left[end - 1]) < 0.001f && abs(s.right[end - 1]) < 0.001f) end--
        val fade = minOf(end, RATE / 50)
        val l = FloatArray(end) { s.left[it].coerceIn(-1f, 1f) }
        val r = FloatArray(end) { s.right[it].coerceIn(-1f, 1f) }
        for (k in 0 until fade) {
            val g = k.toFloat() / fade
            l[end - 1 - k] *= g
            r[end - 1 - k] *= g
        }
        return Stereo(l, r)
    }
}
