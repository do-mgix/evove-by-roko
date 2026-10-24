package com.evove.app.sound

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** 16-bit PCM WAV, the format SoundPool decodes fastest. */
object Wav {
    /** `mono` keeps the left channel alone: the music's loops, half the size. */
    fun write(file: File, sound: Synth.Stereo, rate: Int = Synth.RATE, mono: Boolean = false) {
        val frames = sound.frames
        val channels = if (mono) 1 else 2
        val data = frames * 2 * channels
        val b = ByteBuffer.allocate(44 + data).order(ByteOrder.LITTLE_ENDIAN)
        b.put("RIFF".toByteArray()).putInt(36 + data).put("WAVE".toByteArray())
        b.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(channels.toShort()).putInt(rate)
            .putInt(rate * 2 * channels).putShort((2 * channels).toShort()).putShort(16)
        b.put("data".toByteArray()).putInt(data)
        for (i in 0 until frames) {
            b.putShort((sound.left[i] * 32767).toInt().toShort())
            if (!mono) b.putShort((sound.right[i] * 32767).toInt().toShort())
        }
        file.writeBytes(b.array())
    }
}
