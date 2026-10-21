package com.evove.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.Bus
import com.evove.app.api.Api
import com.evove.app.api.AttrNode
import com.evove.app.api.UserState
import com.evove.app.sound.Sfx
import com.evove.app.ui.Big
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Display
import com.evove.app.ui.Empty
import com.evove.app.ui.Grow
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.IconView
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.KeyText
import com.evove.app.ui.Label
import com.evove.app.ui.ListRow
import com.evove.app.ui.LocalInk
import com.evove.app.ui.MarkBar
import com.evove.app.ui.Message
import com.evove.app.ui.Small
import com.evove.app.ui.Stats
import com.evove.app.ui.Tag
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import java.text.Collator
import java.util.Locale
import kotlin.math.ceil
import kotlin.math.floor

// The profile's attributes. The ones used most come first; "all" walks the
// graph, an attribute opening onto its children; and every attribute of one
// star level can be listed together — the star level being how many levels an
// attribute gathers, a leaf ★1, Físico far above.

private const val ROW_DP = 46

private enum class View(val icon: Icon, val label: String) {
    USED(Icon.EYE, "mais usados"), ALL(Icon.TREE, "todos"), STAR(Icon.STAR, "por estrela")
}

val pt: Collator = Collator.getInstance(Locale.forLanguageTag("pt-BR"))

private fun kids(n: AttrNode) = n.children.filter { it.primary != false }

/** Every attribute once, by its primary place, keyed. */
private fun flatten(list: List<AttrNode>): Map<String, AttrNode> {
    val out = LinkedHashMap<String, AttrNode>()
    fun walk(n: AttrNode) {
        if (n.key !in out) out[n.key] = n
        kids(n).forEach(::walk)
    }
    list.forEach(::walk)
    return out
}

@Composable
fun MeScreen(onHome: () -> Unit, onProfile: () -> Unit, onDetails: () -> Unit) {
    var user by remember { mutableStateOf<UserState?>(null) }
    var roots by remember { mutableStateOf<List<AttrNode>>(emptyList()) }
    var used by remember { mutableStateOf<List<AttrNode>>(emptyList()) }
    var view by remember { mutableStateOf(View.USED) }
    var path by remember { mutableStateOf<List<AttrNode>>(emptyList()) }
    var star by remember { mutableIntStateOf(1) }
    var page by remember { mutableIntStateOf(0) }
    var detail by remember { mutableStateOf<AttrNode?>(null) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        try {
            val u = scope.async { Api.user() }
            val t = scope.async { Api.attributeTree() }
            val us = scope.async { Api.attributeUsage(30, 24) }
            user = u.await()
            roots = t.await().roots
            used = us.await()
        } catch (e: Exception) {
            message = listOf(e.message ?: "erro")
        }
    }

    var first by remember { mutableStateOf(true) }
    LaunchedEffect(Bus.user) {
        load()
        if (first) Sfx.powerOn()
        first = false
    }

    val all = remember(roots) { flatten(roots) }
    val maxStar = maxOf(1, all.values.maxOfOrNull { it.star } ?: 1)
    val usesOf = used.associate { it.key to it.uses }
    val listed: List<AttrNode> = when (view) {
        View.USED -> used.map { all[it.key] ?: it }
        View.ALL -> if (path.isNotEmpty()) kids(path.last()) else roots
        View.STAR -> all.values.filter { it.star == star }
            .sortedWith(compareByDescending<AttrNode> { it.totalMarks }.thenComparator { a, b -> pt.compare(a.name, b.name) })
    }

    fun press(n: Int = 0) = Sfx.tap(n)
    fun up() { press(1); path = path.dropLast(1); page = 0 }
    fun open(n: AttrNode) {
        press(7)
        message = emptyList()
        if (view == View.ALL && kids(n).isNotEmpty()) { path = path + n; page = 0 } else detail = n
    }
    fun back() {
        if (detail != null) detail = null else if (view == View.ALL && path.isNotEmpty()) up()
    }
    fun claim(n: AttrNode) {
        if (busy || n.claim == null) return
        busy = true
        scope.launch {
            try {
                val r = Api.claimRank(n.key)
                Sfx.gains()
                message = listOf(
                    "${r.ranks} ${if (r.ranks == 1) "rank" else "ranks"}",
                    "+${r.pointsGained} pts · +${r.tokensGained}t · +${r.skillPointsGained} skill",
                )
                Bus.bumpUser()
                detail = n.copy(claim = null)
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    BackHandler(enabled = detail != null || (view == View.ALL && path.isNotEmpty())) { back() }

    // counted by the body, which is laid out after the bar is composed
    var pages by remember { mutableIntStateOf(1) }
    DarkScreen(
        Ink.attributes, display = 0.17f,
        displayContent = {
            val d = detail
            val u = user
            when {
                message.isNotEmpty() -> Message(message)
                d != null -> { Big(d.name); Small("${d.rank} ${d.rankName ?: ""} · ★${d.star} · grau ${d.degree}") }
                u != null -> {
                    BasicText(
                        buildAnnotatedString {
                            append(u.rankSymbol)
                            withStyle(SpanStyle(fontSize = 0.8.rem, letterSpacing = 0.2.em, color = Color.White)) { append("  " + com.evove.app.ui.caps(u.rankName ?: "")) }
                        },
                        style = TextStyle(fontFamily = Display, fontSize = 2.6.rem, lineHeight = 1.em, color = LocalInk.current, textAlign = TextAlign.End),
                    )
                    Small("${u.nickname ?: u.username} · nível ${u.level} · ${u.localLevelRoman}/${u.localLevelsTotal}")
                    Box(Modifier.widthIn(max = 16.remDp).fillMaxWidth()) { MarkBar(u.levelMarks, u.levelCost) }
                }
            }
        },
        bar = {
            if (detail != null) {
                Key({ press(0); back() }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
            } else {
                Key({
                    press(4)
                    view = View.entries[(view.ordinal + 1) % View.entries.size]
                    page = 0; detail = null; message = emptyList()
                    Sfx.powerOn()
                }, Modifier.at(1)) { KeyIcon(view.icon) }
                when (view) {
                    View.STAR -> Key({ press(6); star = (star % maxStar) + 1; page = 0 }, Modifier.at(2)) { KeyText("★$star") }
                    View.ALL -> Key(::up, Modifier.at(2), enabled = path.isNotEmpty()) { KeyIcon(Icon.UP) }
                    View.USED -> {}
                }
                Key({ press(2); page = (page + 1) % pages }, Modifier.at(3), enabled = pages > 1) { KeyIcon(Icon.DOWN) }
                Key({ press(3); onDetails() }, Modifier.at(4)) { KeyIcon(Icon.LIST) }
                Key({ press(5); onProfile() }, Modifier.at(5)) { KeyIcon(Icon.USER) }
            }
            HomeKey { press(0); onHome() }
        },
    ) { info ->
        val d = detail
        if (d != null) {
            Stats(buildList {
                add("rank" to "${d.rank} · ${d.rankName ?: ""}")
                add("marcas" to "${d.marks}/${d.need}")
                add("total" to "${d.totalMarks}")
                add("estrela" to "★${d.star}")
                add("grau" to "${d.degree}")
                add("filhos" to "${kids(d).size}")
                usesOf[d.key]?.takeIf { it > 0 }?.let { add("usos em 30 dias" to "$it") }
            })
            MarkBar(d.marks, d.need, gold = true)
            d.claim?.let { c ->
                Key({ claim(d) }, Modifier.fillMaxWidth().heightIn(min = 2.8.remDp), enabled = !busy) {
                    KeyIcon(Icon.STAR, 16.dp); KeyText("reclamar ${c.ranks} · +${c.points} pts")
                }
            }
            if (kids(d).isNotEmpty()) {
                Key({ press(7); view = View.ALL; path = path + d; detail = null; page = 0 }, Modifier.fillMaxWidth().heightIn(min = 2.8.remDp)) {
                    KeyIcon(Icon.TREE, 16.dp); KeyText("ver filhos")
                }
            }
            return@DarkScreen
        }
        val perPage = maxOf(1, floor((info.height.value - 30) / (ROW_DP + 8)).toInt())
        val count = maxOf(1, ceil(listed.size / perPage.toFloat()).toInt())
        if (pages != count) pages = count
        if (page >= pages) page = pages - 1
        val shown = listed.drop(page * perPage).take(perPage)
        Label(buildString {
            append(view.label)
            if (view == View.ALL && path.isNotEmpty()) append(" · " + path.joinToString(" › ") { it.name })
            if (view == View.STAR) append(" · ★$star")
            if (pages > 1) append(" · ${page + 1}/$pages")
        })
        if (shown.isEmpty()) Empty(if (view == View.USED) "nada usado nos últimos 30 dias — aja" else "nenhum atributo aqui")
        for (n in shown) {
            ListRow({ open(n) }, minHeight = 2.9.remDp) {
                BasicText(n.rank, Modifier.width(1.4.remDp), style = TextStyle(fontFamily = Display, fontSize = 1.05.rem, color = LocalInk.current, textAlign = TextAlign.Center))
                Grow(n.name, upper = true)
                if (n.claim != null) IconView(Icon.STAR, Ink.gold, 12.dp)
                Tag(if (view == View.USED) "${usesOf[n.key] ?: 0}×" else "${n.marks}/${n.need}")
                if (view == View.ALL && kids(n).isNotEmpty()) Tag("›")
            }
        }
    }
}
