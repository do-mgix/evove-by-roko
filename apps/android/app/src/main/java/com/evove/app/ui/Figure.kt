package com.evove.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.sp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

// What an attribute is, drawn: the body as a sign's figure with the part it
// trains lit, a close on an arm, a leg or the torso for the muscles; the
// brain from the side with its region lit for the anatomy of the mind; and,
// for what the mind does that has no place — focus, language, writing,
// programming — a web of its parts, each as far out as its rank.

/** How an attribute is drawn, and what in it is lit. */
data class FigureKind(val view: String, val part: String)

private val ARM = setOf("biceps", "triceps", "antebraco", "deltoide")
private val LEG = setOf("quadriceps", "posterior_coxa", "panturrilha", "gluteo")
private val TORSO = setOf("peitoral", "core", "dorsal", "lombar")
private val BRAIN = setOf("mente", "cerebelo", "coordenacao", "equilibrio", "limbico", "amigdala", "hipocampo", "recompensa",
    "linguagem", "broca", "wernicke", "pre_frontal", "executiva", "foco", "sensorial", "auditivo", "somatossensorial", "visual")

/** What `chain` — the attribute's keys from its root down to it — is drawn as. */
fun figureOf(chain: List<String>): FigureKind {
    val key = chain.lastOrNull() ?: ""
    return when {
        key in ARM -> FigureKind("arm", key)
        key in LEG -> FigureKind("leg", key)
        key in TORSO -> FigureKind("torso", key)
        key == "memb_sup" -> FigureKind("body", "arms")
        key == "memb_inf" -> FigureKind("body", "legs")
        key == "tronco" -> FigureKind("body", "torso")
        key in setOf("cardiovascular", "aerobico", "anaerobico", "c_cardio", "t_resistencia", "t_saude") -> FigureKind("body", "heart")
        key in setOf("mobilidade", "estabilidade", "flexibilidade", "c_mobilidade", "t_mobilidade") -> FigureKind("body", "joints")
        key in BRAIN || chain.firstOrNull() == "mente" -> FigureKind("brain", key)
        chain.firstOrNull() in setOf("corpo", "fisico", "c_treino") -> FigureKind("body", "all")
        else -> FigureKind("web", key)
    }
}

/** The figure of an attribute. `web` holds, for the web, its parts and how
 *  far each reached (0 to 1). */
@Composable
fun AttributeFigure(kind: FigureKind, ink: Color, modifier: Modifier, web: List<Pair<String, Float>> = emptyList()) {
    val measurer = rememberTextMeasurer()
    Canvas(modifier) {
        when (kind.view) {
            "arm" -> arm(kind.part, ink)
            "leg" -> leg(kind.part, ink)
            "torso" -> torso(kind.part, ink)
            "brain" -> brain(kind.part, ink)
            "body" -> body(kind.part, ink)
            else -> {
                val stroke = 1.5f * density
                val c = Offset(size.width / 2, size.height / 2)
                val r = min(size.width, size.height) * 0.36f
                val n = maxOf(3, web.size)
                fun at(i: Int, k: Float) = Offset(c.x + r * k * sin(2 * PI * i / n).toFloat(), c.y - r * k * cos(2 * PI * i / n).toFloat())
                for (ring in 1..4) {
                    val p = Path().apply { for (i in 0 until n) at(i, ring / 4f).let { if (i == 0) moveTo(it.x, it.y) else lineTo(it.x, it.y) }; close() }
                    drawPath(p, ink.copy(alpha = 0.18f), style = Stroke(stroke))
                }
                for (i in 0 until n) drawLine(ink.copy(alpha = 0.18f), c, at(i, 1f), stroke)
                val vals = (0 until n).map { web.getOrNull(it)?.second ?: 0f }
                val p = Path().apply { for (i in 0 until n) at(i, 0.08f + 0.92f * vals[i].coerceIn(0f, 1f)).let { if (i == 0) moveTo(it.x, it.y) else lineTo(it.x, it.y) }; close() }
                drawPath(p, ink.copy(alpha = 0.3f))
                drawPath(p, ink, style = Stroke(stroke * 1.4f))
                for (i in 0 until n) {
                    val name = web.getOrNull(i)?.first ?: continue
                    val t = measurer.measure(caps(name.take(12)), TextStyle(fontFamily = Mono, fontSize = 9.sp, color = Color.White.copy(alpha = 0.75f)))
                    val q = at(i, 1.18f)
                    drawText(t, topLeft = Offset(q.x - t.size.width / 2, q.y - t.size.height / 2))
                }
            }
        }
    }
}

private fun DrawScope.part(lit: Boolean, ink: Color, draw: (Color, Stroke?) -> Unit) {
    if (lit) draw(ink.copy(alpha = 0.55f), null)
    draw(ink.copy(alpha = if (lit) 1f else 0.4f), Stroke(1.6f * density))
}

private fun DrawScope.capsule(c: Color, s: Stroke?, x: Float, y: Float, w: Float, h: Float) {
    if (s == null) drawRoundRect(c, Offset(x, y), Size(w, h), CornerRadius(min(w, h) / 2))
    else drawRoundRect(c, Offset(x, y), Size(w, h), CornerRadius(min(w, h) / 2), style = s)
}

private fun DrawScope.oval(c: Color, s: Stroke?, x: Float, y: Float, w: Float, h: Float) {
    if (s == null) drawOval(c, Offset(x, y), Size(w, h)) else drawOval(c, Offset(x, y), Size(w, h), style = s)
}

/** The sign's figure: head, torso, arms and legs, the trained part lit. */
private fun DrawScope.body(lit: String, ink: Color) {
    val u = min(size.width / 6f, size.height / 10f)
    val cx = size.width / 2
    val top = (size.height - u * 10f) / 2
    part(lit == "all", ink) { c, s -> if (s == null) drawCircle(c, u * 0.75f, Offset(cx, top + u * 0.8f)) else drawCircle(c, u * 0.75f, Offset(cx, top + u * 0.8f), style = s) }
    part(lit == "all" || lit == "torso" || lit == "heart", ink) { c, s -> capsule(c, s, cx - u * 1.1f, top + u * 1.8f, u * 2.2f, u * 3.6f) }
    for (side in listOf(-1, 1)) {
        part(lit == "all" || lit == "arms", ink) { c, s -> capsule(c, s, cx + side * u * 1.35f - u * 0.35f, top + u * 1.9f, u * 0.7f, u * 3.3f) }
        part(lit == "all" || lit == "legs", ink) { c, s -> capsule(c, s, cx + side * u * 0.55f - u * 0.42f, top + u * 5.6f, u * 0.84f, u * 4.2f) }
    }
    if (lit == "heart") {
        val h = Offset(cx - u * 0.35f, top + u * 2.9f)
        val p = Path().apply {
            moveTo(h.x, h.y + u * 0.45f)
            cubicTo(h.x - u * 0.7f, h.y - u * 0.1f, h.x - u * 0.2f, h.y - u * 0.6f, h.x, h.y - u * 0.15f)
            cubicTo(h.x + u * 0.2f, h.y - u * 0.6f, h.x + u * 0.7f, h.y - u * 0.1f, h.x, h.y + u * 0.45f)
        }
        drawPath(p, Ink.danger)
    }
    if (lit == "joints") {
        for (j in listOf(Offset(cx - u * 1.35f, top + u * 2.1f), Offset(cx + u * 1.35f, top + u * 2.1f), Offset(cx - u * 1.35f, top + u * 3.6f),
                Offset(cx + u * 1.35f, top + u * 3.6f), Offset(cx - u * 0.55f, top + u * 5.8f), Offset(cx + u * 0.55f, top + u * 5.8f),
                Offset(cx - u * 0.55f, top + u * 7.7f), Offset(cx + u * 0.55f, top + u * 7.7f))) {
            drawCircle(ink, u * 0.22f, j)
        }
    }
}

/** A close on an arm: shoulder, upper arm, forearm, hand, the muscle lit. */
private fun DrawScope.arm(lit: String, ink: Color) {
    val u = min(size.width / 6f, size.height / 8f)
    val x0 = size.width / 2 - u * 1.6f
    val y0 = (size.height - u * 8f) / 2
    // the upper arm hangs down; the forearm rises forward from the elbow
    part(false, ink) { c, s -> capsule(c, s, x0, y0 + u * 0.8f, u * 1.5f, u * 4f) }
    part(lit == "deltoide", ink) { c, s -> oval(c, s, x0 - u * 0.25f, y0, u * 2f, u * 1.7f) }
    part(lit == "biceps", ink) { c, s -> oval(c, s, x0 + u * 0.75f, y0 + u * 1.6f, u * 0.95f, u * 2.4f) }
    part(lit == "triceps", ink) { c, s -> oval(c, s, x0 - u * 0.2f, y0 + u * 1.5f, u * 0.95f, u * 2.6f) }
    val elbow = Offset(x0 + u * 0.75f, y0 + u * 4.6f)
    rotate(-55f, elbow) {
        part(lit == "antebraco", ink) { c, s -> capsule(c, s, elbow.x - u * 0.6f, elbow.y - u * 0.4f, u * 1.2f, u * 3.8f) }
        part(false, ink) { c, s -> oval(c, s, elbow.x - u * 0.55f, elbow.y + u * 3.3f, u * 1.1f, u * 1.2f) }
    }
}

/** A close on a leg: hip, thigh, knee, calf and foot, the muscle lit. */
private fun DrawScope.leg(lit: String, ink: Color) {
    val u = min(size.width / 6f, size.height / 10f)
    val x0 = size.width / 2 - u * 0.9f
    val y0 = (size.height - u * 10f) / 2
    part(lit == "gluteo", ink) { c, s -> oval(c, s, x0 - u * 0.6f, y0, u * 2.6f, u * 1.8f) }
    part(false, ink) { c, s -> capsule(c, s, x0, y0 + u * 1.1f, u * 1.8f, u * 4.2f) }
    part(lit == "quadriceps", ink) { c, s -> oval(c, s, x0 + u * 0.85f, y0 + u * 1.6f, u * 0.95f, u * 3.2f) }
    part(lit == "posterior_coxa", ink) { c, s -> oval(c, s, x0 - u * 0.05f, y0 + u * 1.7f, u * 0.95f, u * 3.1f) }
    part(false, ink) { c, s -> capsule(c, s, x0 + u * 0.2f, y0 + u * 5.4f, u * 1.4f, u * 3.8f) }
    part(lit == "panturrilha", ink) { c, s -> oval(c, s, x0 + u * 0.05f, y0 + u * 5.8f, u * 1.05f, u * 2.2f) }
    part(false, ink) { c, s -> capsule(c, s, x0 + u * 0.2f, y0 + u * 9.1f, u * 2.4f, u * 0.8f) }
}

/** A close on the torso: the chest, the abdomen, the back's wings and its
 *  lower band, the muscle lit. */
private fun DrawScope.torso(lit: String, ink: Color) {
    val u = min(size.width / 7f, size.height / 8f)
    val cx = size.width / 2
    val y0 = (size.height - u * 8f) / 2
    part(lit == "dorsal", ink) { c, s ->
        for (side in listOf(-1, 1)) {
            val p = Path().apply {
                moveTo(cx + side * u * 2.4f, y0 + u * 1.2f); lineTo(cx + side * u * 3.3f, y0 + u * 1.6f)
                lineTo(cx + side * u * 2.3f, y0 + u * 5.2f); lineTo(cx + side * u * 2.0f, y0 + u * 3f); close()
            }
            if (s == null) drawPath(p, c) else drawPath(p, c, style = s)
        }
    }
    part(false, ink) { c, s -> capsule(c, s, cx - u * 2.3f, y0 + u * 0.6f, u * 4.6f, u * 7f) }
    part(lit == "peitoral", ink) { c, s -> for (side in listOf(-1, 1)) oval(c, s, cx + (if (side < 0) -u * 2f else u * 0.1f), y0 + u * 1.2f, u * 1.9f, u * 1.5f) }
    part(lit == "core", ink) { c, s ->
        for (r in 0 until 3) for (side in listOf(-1, 1)) {
            val x = cx + (if (side < 0) -u * 1.0f else u * 0.1f)
            val y = y0 + u * 3.0f + r * u * 0.95f
            if (s == null) drawRoundRect(c, Offset(x, y), Size(u * 0.9f, u * 0.8f), CornerRadius(u * 0.2f))
            else drawRoundRect(c, Offset(x, y), Size(u * 0.9f, u * 0.8f), CornerRadius(u * 0.2f), style = s)
        }
    }
    part(lit == "lombar", ink) { c, s ->
        if (s == null) drawRect(c, Offset(cx - u * 2.2f, y0 + u * 6.0f), Size(u * 4.4f, u * 1.0f))
        else drawRect(c, Offset(cx - u * 2.2f, y0 + u * 6.0f), Size(u * 4.4f, u * 1.0f), style = Stroke(s.width, pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 4f))))
    }
}

/** The brain from the side, facing left: the cortex, the cerebellum below at
 *  the back, the stem, and the region lit. */
private fun DrawScope.brain(lit: String, ink: Color) {
    val w = min(size.width, size.height * 1.3f) * 0.86f
    val h = w * 0.66f
    val x0 = (size.width - w) / 2
    val y0 = (size.height - h) / 2
    val stroke = Stroke(1.6f * density)
    // the cortex
    drawOval(ink.copy(alpha = 0.08f), Offset(x0, y0), Size(w, h * 0.8f))
    drawOval(ink.copy(alpha = 0.5f), Offset(x0, y0), Size(w, h * 0.8f), style = stroke)
    // a few folds
    for (k in 1..3) {
        val p = Path().apply {
            moveTo(x0 + w * (0.2f + 0.2f * k), y0 + h * 0.08f)
            quadraticBezierTo(x0 + w * (0.15f + 0.2f * k), y0 + h * 0.35f, x0 + w * (0.25f + 0.2f * k), y0 + h * 0.55f)
        }
        drawPath(p, ink.copy(alpha = 0.3f), style = stroke)
    }
    val cerebellum = lit in setOf("cerebelo", "coordenacao", "equilibrio")
    part(cerebellum, ink) { c, s -> oval(c, s, x0 + w * 0.62f, y0 + h * 0.6f, w * 0.3f, h * 0.3f) }
    part(false, ink) { c, s -> capsule(c, s, x0 + w * 0.52f, y0 + h * 0.62f, w * 0.09f, h * 0.38f) }
    val (rx, ry, rw, rh) = when (lit) {
        "pre_frontal", "executiva", "foco" -> listOf(0.03f, 0.1f, 0.3f, 0.5f)
        "broca" -> listOf(0.16f, 0.42f, 0.14f, 0.14f)
        "wernicke" -> listOf(0.55f, 0.4f, 0.14f, 0.14f)
        "auditivo", "linguagem" -> listOf(0.3f, 0.45f, 0.32f, 0.2f)
        "visual" -> listOf(0.78f, 0.15f, 0.2f, 0.4f)
        "somatossensorial", "sensorial" -> listOf(0.45f, 0.02f, 0.12f, 0.45f)
        "limbico", "amigdala", "hipocampo", "recompensa" -> listOf(0.38f, 0.3f, 0.22f, 0.18f)
        else -> listOf(0f, 0f, 0f, 0f)
    }
    if (rw > 0f) {
        val deep = lit in setOf("limbico", "amigdala", "hipocampo", "recompensa")
        drawOval(ink.copy(alpha = 0.55f), Offset(x0 + w * rx, y0 + h * ry), Size(w * rw, h * rh))
        drawOval(ink, Offset(x0 + w * rx, y0 + h * ry), Size(w * rw, h * rh),
            style = if (deep) Stroke(1.6f * density, pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 4f))) else stroke)
    }
}
