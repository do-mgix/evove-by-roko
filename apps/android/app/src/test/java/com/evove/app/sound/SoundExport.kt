package com.evove.app.sound

import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.util.Random

/** Renders the interface's sounds into res/raw, where Sfx plays them from.
 *
 *     ./gradlew :app:testDebugUnitTest --tests '*SoundExport*' -PexportSounds
 *
 * Without -PexportSounds it does nothing, so the sounds stay as exported. Each
 * sound is rendered from a fixed seed, so exporting twice gives the same files;
 * the glints are random in the synthesis, so there are a few takes of the
 * sounds that repeat most, and Sfx picks one each time.
 */
class SoundExport {
    @Test
    fun export() {
        val dir = System.getProperty("evove.sounds")
        assumeTrue("pass -PexportSounds to export", dir != null)
        val raw = File(dir!!).apply { mkdirs() }
        for (v in 0..9) Wav.write(File(raw, "tap_$v.wav"), Synth.tap(v, Random(100L + v)))
        for (k in 0..2) Wav.write(File(raw, "power_on_$k.wav"), Synth.powerOn(Random(200L + k)))
        for (k in 0..2) Wav.write(File(raw, "gains_$k.wav"), Synth.gains(Random(300L + k)))
        Wav.write(File(raw, "type.wav"), Synth.type())
        Wav.write(File(raw, "hit.wav"), Synth.hit())
        Wav.write(File(raw, "heal.wav"), Synth.heal())
        Wav.write(File(raw, "entity.wav"), Synth.entity())
        Wav.write(File(raw, "boom.wav"), Synth.boom())
    }
}
