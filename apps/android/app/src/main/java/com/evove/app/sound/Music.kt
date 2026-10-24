package com.evove.app.sound

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import com.evove.app.R

/** The music: an ambience under the menus, and, in a fight, layers that all
 *  play together from its start — a ground always heard, and four
 *  instruments that come in one by one as the fight asks for them: the bass as
 *  it drags on, the arpeggio under fúria, the pad as the entities grow
 *  impatient, the lead when the hp runs low. Rendered by Synth, like every
 *  sound, and looped by MediaPlayer, on the media stream.
 *
 * Nothing plays before the first tap, nor while the app is away. */
object Music {
    private var context: Context? = null
    private var ambient: MediaPlayer? = null
    private val layers = linkedMapOf<String, MediaPlayer>()
    private var mode = "none"
    private var away = false

    private val LAYERS = mapOf("base" to R.raw.layer_base, "bass" to R.raw.layer_bass, "lead" to R.raw.layer_lead,
        "arp" to R.raw.layer_arp, "pad" to R.raw.layer_pad)

    fun init(c: Context) { context = c.applicationContext }

    private fun player(res: Int, volume: Float): MediaPlayer? {
        val c = context ?: return null
        return runCatching {
            MediaPlayer.create(c, res, AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_GAME)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build(), 0)?.apply {
                isLooping = true
                setVolume(volume, volume)
            }
        }.getOrNull()
    }

    /** The menus: the ambience, the fight's layers gone. */
    fun menus() {
        if (mode == "menus") return
        mode = "menus"
        stopLayers()
        apply()
    }

    /** A fight began: the layers from the top, the ambience silent. */
    fun battle() {
        mode = "battle"
        ambient?.pause()
        stopLayers()
        apply()
    }

    private fun apply() {
        if (away || !Sfx.primed || Sfx.muted) return
        when (mode) {
            "menus" -> {
                val a = ambient ?: player(R.raw.ambient, 0.22f).also { ambient = it }
                runCatching { if (a?.isPlaying == false) a.start() }
            }
            "battle" -> if (layers.isEmpty()) {
                for ((k, res) in LAYERS) player(res, if (k == "base") 0.5f else 0f)?.let { layers[k] = it }
                // started together, so they stay in time
                layers.values.forEach { runCatching { it.start() } }
            }
        }
    }

    /** What the fight asks for now, each instrument in or out. */
    fun mix(seconds: Float, lowHp: Boolean, fury: Boolean, impatience: Float) {
        if (mode != "battle") return
        if (layers.isEmpty()) apply()
        fun set(k: String, v: Float) = layers[k]?.let { runCatching { it.setVolume(v, v) } }
        set("bass", if (seconds > 45f) 0.45f else 0f)
        set("arp", if (fury) 0.35f else 0f)
        set("pad", if (impatience >= 0.02f) 0.3f else 0f)
        set("lead", if (lowHp) 0.4f else 0f)
    }

    private fun stopLayers() {
        layers.values.forEach { runCatching { it.stop(); it.release() } }
        layers.clear()
    }

    /** The app went away, or came back. */
    fun pause() {
        away = true
        ambient?.let { runCatching { if (it.isPlaying) it.pause() } }
        layers.values.forEach { runCatching { if (it.isPlaying) it.pause() } }
    }

    fun resume() {
        away = false
        if (mode == "battle" && layers.isNotEmpty()) layers.values.forEach { runCatching { it.start() } } else apply()
    }

    /** The first tap: what should have been playing starts. */
    fun primed() = apply()
}
