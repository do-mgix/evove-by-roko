package com.evove.app.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.evove.app.R

// The dial interface's look, as apps/web/src/app.css and the pages' styles set
// it: black, neon outlines, two typefaces.

/** One rem of the web client inside the Android shell: 16px raised by 112.5%. */
val Number.rem: TextUnit get() = (toFloat() * 18f).sp

@OptIn(ExperimentalTextApi::class)
private fun variable(res: Int, weight: Int) =
    Font(res, FontWeight(weight), variationSettings = FontVariation.Settings(FontVariation.weight(weight)))

/** JetBrains Mono, for everything the dark screens say. */
val Mono = FontFamily(
    variable(R.font.jetbrains_mono, 400),
    variable(R.font.jetbrains_mono, 500),
    variable(R.font.jetbrains_mono, 600),
    variable(R.font.jetbrains_mono, 700),
)

/** Zalando Sans Expanded, for names and what entities say. */
val Display = FontFamily(
    variable(R.font.zalando_sans_expanded, 400),
    variable(R.font.zalando_sans_expanded, 500),
    variable(R.font.zalando_sans_expanded, 600),
    variable(R.font.zalando_sans_expanded, 700),
)

/** The web client's Arial, for the white pages. */
val Sans = FontFamily.SansSerif

fun hex(s: String): Color {
    val v = s.removePrefix("#")
    val n = v.toLong(16)
    return if (v.length == 8) Color(n.toInt()) else Color((0xFF000000 or n).toInt())
}

object Ink {
    val act = hex("#00f0ff")
    val attributes = hex("#00c8ff")
    val roko = hex("#3dfff0")
    val shop = hex("#7af9ff")
    val agenda = hex("#00a8e8")
    val build = hex("#00e0ff")
    val journey = hex("#00ffd0")
    val gold = hex("#ffd166")
    val late = hex("#ffb347")
    val danger = hex("#ff5c7a")
    val enemy = hex("#ff8fa3")
    val eve = hex("#ff9de2")
    val sandbox = hex("#7dff6b")
    val mute = hex("#5f7373")
}

/** The long pages' tones. They were white pages once — grey text and one teal
 *  accent on paper — and kept the names when they went dark like the rest. */
object Paper {
    val text = Color.White
    val soft = Color.White.copy(alpha = 0.78f)
    val muted = Color.White.copy(alpha = 0.52f)
    val line = Color.White.copy(alpha = 0.2f)
    val accent = hex("#00f0ff")
    val error = hex("#ff5c7a")
}

/** Upper case for everything but the Greek ranks: α stays α, where a plain
 *  upper case would turn it into Α, which reads as a Latin A. */
fun caps(s: String?): String = (s ?: "").replace(Regex("[^α-ω]+")) { it.value.uppercase() }

object Type {
    val big = TextStyle(fontFamily = Mono, fontSize = 1.5.rem, lineHeight = 1.15.em, color = Color.White)
    val small = TextStyle(fontFamily = Mono, fontSize = 0.85.rem, color = Color.White.copy(alpha = 0.7f))
    val label = TextStyle(fontFamily = Mono, fontSize = 0.68.rem, letterSpacing = 0.1.em)
    val row = TextStyle(fontFamily = Mono, fontSize = 0.8.rem, color = Color.White)
    val key = TextStyle(fontFamily = Mono, fontSize = 0.78.rem)
    val empty = TextStyle(fontFamily = Mono, fontSize = 0.8.rem, color = Color.White.copy(alpha = 0.5f))
}
