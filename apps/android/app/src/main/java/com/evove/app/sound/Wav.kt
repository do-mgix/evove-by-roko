package com.evove.app.sound

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** 16-bit PCM WAV, the format SoundPool decodes fastest. */
object Wav {
    fun write(file: File, sound: Synth.Stereo, rate: Int = Synth.RATE) {
        val frames = sound.frames
        val data = frames * 2 * 2
        val b = ByteBuffer.allocate(44 + data).order(ByteOrder.LITTLE_ENDIAN)
        b.put("RIFF".toByteArray()).putInt(36 + data).put("WAVE".toByteArray())
        b.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(2).putInt(rate)
            .putInt(rate * 4).putShort(4).putShort(16)
        b.put("data".toByteArray()).putInt(data)
        for (i in 0 until frames) {
            b.putShort((sound.left[i] * 32767).toInt().toShort())
            b.putShort((sound.right[i] * 32767).toInt().toShort())
        }
        file.writeBytes(b.array())
    }
}
