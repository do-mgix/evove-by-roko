package com.evove.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.PathOperation
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.sp
import kotlin.math.PI
import kotlin.math.acos
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.min
import kotlin.math.sin

// What an attribute is, drawn: the body as a sign's figure with the part it
// trains lit, a close on an arm, a leg or the torso for the muscles; the
// brain from the side with its region lit for the anatomy of the mind; and,
// for what the mind does that has no place — focus, language, writing,
// programming — a web of its parts, each as far out as its rank.
//
// Everything of the body is made as a sign's figures are: straight parts
// closed by half circles. A limb is a stadium — a rectangle with a half
// circle at each end; a muscle is a taper — two circles of different sizes
// and the straight lines touching both — or two tapers sharing their big
// circle, a belly between two tendons.

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

// ---------------------------------------------------------------- the shapes

/** Two circles — at `a` of radius `ra`, at `b` of radius `rb` — and the two
 *  straight lines touching both: a stadium when the radii are equal, a taper
 *  when not. */
fun taper(a: Offset, ra: Float, b: Offset, rb: Float): Path {
    val d = maxOf(0.001f, hypot(b.x - a.x, b.y - a.y))
    val theta = atan2(b.y - a.y, b.x - a.x)
    val phi = acos(((ra - rb) / d).coerceIn(-1f, 1f))
    fun deg(r: Float) = (r * 180.0 / PI).toFloat()
    return Path().apply {
        moveTo(a.x + ra * cos(theta + phi), a.y + ra * sin(theta + phi))
        lineTo(b.x + rb * cos(theta + phi), b.y + rb * sin(theta + phi))
        // around b on its far side, then back along the other line and around a
        arcTo(Rect(b, rb), deg(theta + phi), -deg(2 * phi), false)
        lineTo(a.x + ra * cos(theta - phi), a.y + ra * sin(theta - phi))
        arcTo(Rect(a, ra), deg(theta - phi), -deg(2 * PI.toFloat() - 2 * phi), false)
        close()
    }
}

/** A rectangle with a half circle at each end, `w` wide, from `a` to `b`. */
fun stadium(a: Offset, b: Offset, w: Float): Path = taper(a, w / 2, b, w / 2)

/** A muscle's belly: thin at `a`, as wide as `r` at `m`, thin again at `b`. */
fun belly(a: Offset, ra: Float, m: Offset, r: Float, b: Offset, rb: Float): Path = union(taper(a, ra, m, r), taper(m, r, b, rb))

/** Shapes as one, overlaps filled once. */
fun union(vararg ps: Path): Path = ps.reduce { a, b -> Path().apply { op(a, b, PathOperation.Union) } }

private fun box(a: Offset, b: Offset) = Path().apply { addRect(Rect(a, b)) }

/** A shape of the figure: filled solid when lit, as a sign's are; faint
 *  otherwise. */
private fun DrawScope.solid(p: Path, lit: Boolean, ink: Color, faint: Float = 0.26f) {
    drawPath(p, ink.copy(alpha = if (lit) 1f else faint))
}

/** A muscle inside a limb: its outline always, filled when lit. */
private fun DrawScope.muscle(p: Path, lit: Boolean, ink: Color) {
    if (lit) drawPath(p, ink)
    drawPath(p, if (lit) Color.Black.copy(alpha = 0.55f) else ink.copy(alpha = 0.55f), style = Stroke(1.4f * density))
}

private fun circle(c: Offset, r: Float) = Path().apply { addOval(Rect(c, r)) }

// ---------------------------------------------------------------- the figures

/** The sign's figure from the front: a head; the torso, its shoulders closed
 *  by half circles; arms and legs as stadiums, apart from the torso by a gap,
 *  the trained part lit. */
private fun DrawScope.body(lit: String, ink: Color) {
    val u = min(size.width / 6f, size.height / 10.4f)
    val cx = size.width / 2
    val top = (size.height - u * 10.4f) / 2
    fun p(x: Float, y: Float) = Offset(cx + x * u, top + y * u)
    val all = lit == "all"
    solid(circle(p(0f, 0.85f), 0.8f * u), all, ink)
    // the torso: shoulders round as the arms' tops, a straight waist
    val torso = union(stadium(p(-0.55f, 2.55f), p(0.55f, 2.55f), 1.5f * u), box(p(-1.3f, 2.55f), p(1.3f, 5.7f)))
    solid(torso, all || lit == "torso" || lit == "heart", ink, if (lit == "heart") 0.4f else 0.26f)
    for (side in listOf(-1f, 1f)) {
        solid(stadium(p(side * 1.78f, 2.3f), p(side * 1.98f, 5.5f), 0.66f * u), all || lit == "arms", ink)
        solid(stadium(p(side * 0.66f, 6.3f), p(side * 0.72f, 9.95f), 1.0f * u), all || lit == "legs", ink)
    }
    if (lit == "heart") {
        // a heart as a sign makes it: two circles over a square turned on its corner
        val h = p(-0.4f, 3.5f)
        val r = 0.36f * u
        val point = Path().apply {
            moveTo(h.x - r * 1.62f, h.y); lineTo(h.x, h.y + r * 1.75f); lineTo(h.x + r * 1.62f, h.y); lineTo(h.x, h.y - r * 0.5f); close()
        }
        val heart = union(circle(Offset(h.x - r * 0.72f, h.y - r * 0.3f), r), circle(Offset(h.x + r * 0.72f, h.y - r * 0.3f), r), point)
        drawPath(heart, Ink.danger)
    }
    if (lit == "joints") {
        for (j in listOf(p(-1.8f, 2.4f), p(1.8f, 2.4f), p(-1.9f, 3.95f), p(1.9f, 3.95f), p(-0.66f, 6.4f), p(0.66f, 6.4f),
                p(-0.7f, 8.1f), p(0.7f, 8.1f))) {
            drawCircle(Color.Black, u * 0.3f, j)
            drawCircle(ink, u * 0.2f, j)
        }
    }
}

/** A close on an arm from the side, facing left: the upper arm hanging, the
 *  forearm rising forward from the elbow, the hand; inside, the deltoid
 *  capping the shoulder, the biceps in front, the triceps behind and the
 *  forearm's muscle, the one trained lit. */
private fun DrawScope.arm(lit: String, ink: Color) {
    val u = min(size.width / 5.4f, size.height / 6.4f)
    val ox = size.width / 2 + u * 1.45f
    val oy = (size.height - u * 5.6f) / 2
    fun p(x: Float, y: Float) = Offset(ox + x * u, oy + y * u)
    val shoulder = p(0f, 1.0f)
    val elbow = p(0f, 4.6f)
    val wrist = p(-2.6f, 2.6f)
    solid(union(stadium(shoulder, elbow, 1.9f * u), stadium(elbow, wrist, 1.5f * u), circle(p(-3.05f, 2.15f), 0.72f * u)), false, ink, 0.16f)
    muscle(belly(p(-0.35f, 1.9f), 0.18f * u, p(-0.42f, 3.0f), 0.5f * u, p(-0.2f, 4.35f), 0.14f * u), lit == "biceps", ink)
    muscle(belly(p(0.4f, 1.7f), 0.18f * u, p(0.42f, 2.9f), 0.5f * u, p(0.25f, 4.4f), 0.16f * u), lit == "triceps", ink)
    muscle(taper(p(0f, 0.95f), 1.02f * u, p(0f, 2.55f), 0.2f * u), lit == "deltoide", ink)
    muscle(taper(p(-0.55f, 4.25f), 0.58f * u, p(-2.3f, 2.85f), 0.22f * u), lit == "antebraco", ink)
}

/** A close on a leg from the side, facing left: the thigh, the shin and the
 *  foot; inside, the glute behind the hip, the quadriceps in front of the
 *  thigh, the hamstrings behind it and the calf, the one trained lit. */
private fun DrawScope.leg(lit: String, ink: Color) {
    val u = min(size.width / 6f, size.height / 10.4f)
    val ox = size.width / 2
    val oy = (size.height - u * 10.4f) / 2
    fun p(x: Float, y: Float) = Offset(ox + x * u, oy + y * u)
    val hip = p(0f, 1.2f)
    val knee = p(-0.15f, 5.4f)
    val ankle = p(0.1f, 9.2f)
    solid(union(stadium(hip, knee, 2.1f * u), stadium(knee, ankle, 1.45f * u), stadium(p(-1.4f, 9.75f), p(0.3f, 9.75f), 0.8f * u)), false, ink, 0.16f)
    muscle(taper(p(0.55f, 1.15f), 1.05f * u, p(0.5f, 2.6f), 0.3f * u), lit == "gluteo", ink)
    muscle(belly(p(-0.5f, 1.9f), 0.22f * u, p(-0.62f, 3.6f), 0.6f * u, p(-0.42f, 5.1f), 0.2f * u), lit == "quadriceps", ink)
    muscle(belly(p(0.45f, 2.6f), 0.2f * u, p(0.5f, 3.9f), 0.5f * u, p(0.25f, 5.2f), 0.16f * u), lit == "posterior_coxa", ink)
    muscle(taper(p(0.2f, 6.5f), 0.55f * u, p(0.1f, 8.6f), 0.16f * u), lit == "panturrilha", ink)
}

/** A close on the torso from the front: the shoulders round, the waist
 *  straight; inside, the chest's two plates, the abdomen's six, the back's
 *  wings showing at the sides and its lower band, the one trained lit. */
private fun DrawScope.torso(lit: String, ink: Color) {
    val u = min(size.width / 8f, size.height / 8.4f)
    val cx = size.width / 2
    val oy = (size.height - u * 8.4f) / 2
    fun p(x: Float, y: Float) = Offset(cx + x * u, oy + y * u)
    // the back's wings, behind: wide at the armpit, thin at the waist
    for (side in listOf(-1f, 1f)) muscle(taper(p(side * 2.75f, 2.1f), 0.75f * u, p(side * 1.7f, 6.0f), 0.2f * u), lit == "dorsal", ink)
    val trunk = union(stadium(p(-1.6f, 1.6f), p(1.6f, 1.6f), 2.2f * u), box(p(-2.25f, 1.6f), p(2.25f, 7.9f)))
    drawPath(trunk, Color.Black)
    solid(trunk, false, ink, 0.16f)
    for (side in listOf(-1f, 1f)) {
        // a plate of the chest: square at the sternum, round at the shoulder
        val plate = union(stadium(p(side * 0.65f, 2.3f), p(side * 1.55f, 2.3f), 1.3f * u),
            box(p(if (side < 0) -0.85f else 0.15f, 1.65f), p(if (side < 0) -0.15f else 0.85f, 2.95f)))
        muscle(plate, lit == "peitoral", ink)
        for (r in 0 until 3) {
            val y = 3.75f + r * 0.95f
            muscle(stadium(p(side * 0.42f, y), p(side * 0.62f, y), 0.75f * u), lit == "core", ink)
        }
    }
    val low = stadium(p(-1.55f, 7.2f), p(1.55f, 7.2f), 0.8f * u)
    if (lit == "lombar") drawPath(low, ink)
    drawPath(low, ink.copy(alpha = 0.55f), style = Stroke(1.4f * density, pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 4f))))
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
    val cb = Rect(Offset(x0 + w * 0.62f, y0 + h * 0.6f), Size(w * 0.3f, h * 0.3f))
    if (cerebellum) drawOval(ink.copy(alpha = 0.55f), cb.topLeft, cb.size)
    drawOval(ink.copy(alpha = if (cerebellum) 1f else 0.4f), cb.topLeft, cb.size, style = stroke)
    drawPath(stadium(Offset(x0 + w * 0.565f, y0 + h * 0.66f), Offset(x0 + w * 0.565f, y0 + h * 0.96f), w * 0.09f), ink.copy(alpha = 0.4f), style = stroke)
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
