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
 * They play on the media stream, as a game's do. They used to go out as
 * sonification, which Android routes to the system stream — the one a phone on
 * silent or vibrate mutes, and the one most phones keep low — so on most phones
 * they were never heard.
 *
 * As on the web, nothing plays until the first tap: a screen coming on at
 * launch stays silent until someone has touched the app. */
object Sfx {
    private var pool: SoundPool? = null
    private var vibrator: Vibrator? = null
    private val taps = IntArray(10)
    private val powerOns = IntArray(3)
    private val gainsTakes = IntArray(3)
    private var typeId = 0
    private var hitId = 0
    private var healId = 0
    private var entityId = 0
    private var boomId = 0
    private var primed = false
    var muted = false

    fun init(context: Context) {
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_GAME)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        val p = SoundPool.Builder().setMaxStreams(8).setAudioAttributes(attrs).build()
        val tapIds = intArrayOf(R.raw.tap_0, R.raw.tap_1, R.raw.tap_2, R.raw.tap_3, R.raw.tap_4,
            R.raw.tap_5, R.raw.tap_6, R.raw.tap_7, R.raw.tap_8, R.raw.tap_9)
        tapIds.forEachIndexed { i, id -> taps[i] = p.load(context, id, 1) }
        intArrayOf(R.raw.power_on_0, R.raw.power_on_1, R.raw.power_on_2).forEachIndexed { i, id -> powerOns[i] = p.load(context, id, 1) }
        intArrayOf(R.raw.gains_0, R.raw.gains_1, R.raw.gains_2).forEachIndexed { i, id -> gainsTakes[i] = p.load(context, id, 1) }
        typeId = p.load(context, R.raw.type, 1)
        hitId = p.load(context, R.raw.hit, 1)
        healId = p.load(context, R.raw.heal, 1)
        entityId = p.load(context, R.raw.entity, 1)
        boomId = p.load(context, R.raw.boom, 1)
        pool = p
        vibrator = if (Build.VERSION.SDK_INT >= 31) {
            (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
    }

    private fun play(id: Int, volume: Float) {
        if (muted || !primed || id == 0) return
        pool?.play(id, volume, volume, 1, 0, 1f)
    }

    /** Every button: light, with a buzz. `variant` (0–9) nudges the pitch. */
    fun tap(variant: Int = 0) {
        primed = true
        play(taps[Math.floorMod(variant, 10)], 0.55f)
        buzz(10)
    }

    /** An entity's letter typed out: one soft tone, always the same, no buzz. */
    fun type() = play(typeId, 0.22f)

    /** In a fight: a blow landing, a heal, an entity stepping in. */
    fun hit() = play(hitId, 0.6f)
    fun heal() = play(healId, 0.55f)
    fun entity() = play(entityId, 0.6f)

    /** An entity's blow: muffled, heavy. */
    fun boom() {
        play(boomId, 1f)
        buzz(60)
    }

    /** A screen of cells coming on. */
    fun powerOn() = play(powerOns.random(), 0.7f)

    /** What an act paid, arriving. */
    fun gains() {
        play(gainsTakes.random(), 1f)
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
