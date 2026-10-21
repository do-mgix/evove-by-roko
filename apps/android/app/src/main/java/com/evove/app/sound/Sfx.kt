package com.evove.app.sound

import android.content.Context
import android.media.AudioAttributes
import android.media.SoundPool
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import com.evove.app.R

/** The interface's one sound, in three strengths, and the buzz under the
 *  thumb. The sounds are files rendered by Synth (see SoundExport), loaded into
 *  a SoundPool once: a tap only starts a stream that is already decoded.
 *
 * As on the web, nothing plays until the first tap: a screen coming on at
 * launch stays silent until someone has touched the app. */
object Sfx {
    private var pool: SoundPool? = null
    private var vibrator: Vibrator? = null
    private val taps = IntArray(10)
    private val powerOns = IntArray(3)
    private val gainsTakes = IntArray(3)
    private var primed = false
    var muted = false

    fun init(context: Context) {
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        val p = SoundPool.Builder().setMaxStreams(8).setAudioAttributes(attrs).build()
        val tapIds = intArrayOf(R.raw.tap_0, R.raw.tap_1, R.raw.tap_2, R.raw.tap_3, R.raw.tap_4,
            R.raw.tap_5, R.raw.tap_6, R.raw.tap_7, R.raw.tap_8, R.raw.tap_9)
        tapIds.forEachIndexed { i, id -> taps[i] = p.load(context, id, 1) }
        intArrayOf(R.raw.power_on_0, R.raw.power_on_1, R.raw.power_on_2).forEachIndexed { i, id -> powerOns[i] = p.load(context, id, 1) }
        intArrayOf(R.raw.gains_0, R.raw.gains_1, R.raw.gains_2).forEachIndexed { i, id -> gainsTakes[i] = p.load(context, id, 1) }
        pool = p
        vibrator = if (Build.VERSION.SDK_INT >= 31) {
            (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
    }

    private fun play(id: Int) {
        if (muted || !primed || id == 0) return
        pool?.play(id, 1f, 1f, 1, 0, 1f)
    }

    /** Every button: light, with a buzz. `variant` (0–9) nudges the pitch. */
    fun tap(variant: Int = 0) {
        primed = true
        play(taps[Math.floorMod(variant, 10)])
        buzz(10)
    }

    /** A screen of cells coming on. */
    fun powerOn() = play(powerOns.random())

    /** What an act paid, arriving. */
    fun gains() {
        play(gainsTakes.random())
        buzz(20, 40, 20)
    }

    /** A vibration: one length, or on, off, on… in milliseconds. */
    fun buzz(vararg pattern: Long) {
        val v = vibrator ?: return
        try {
            if (pattern.size == 1) v.vibrate(VibrationEffect.createOneShot(pattern[0], VibrationEffect.DEFAULT_AMPLITUDE))
            else v.vibrate(VibrationEffect.createWaveform(longArrayOf(0, *pattern), -1))
        } catch (_: Exception) {
            // a buzz is a nicety
        }
    }
}
