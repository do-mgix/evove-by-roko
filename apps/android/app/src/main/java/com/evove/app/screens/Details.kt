package com.evove.app.screens

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.Bus
import com.evove.app.Page
import com.evove.app.api.Action
import com.evove.app.api.Api
import com.evove.app.api.AttrNode
import com.evove.app.api.UserAttribute
import com.evove.app.api.UserState
import com.evove.app.api.formatCode
import com.evove.app.ui.Display
import com.evove.app.ui.MarkBar
import com.evove.app.ui.Paper
import com.evove.app.ui.PaperButton
import com.evove.app.ui.PaperCard
import com.evove.app.ui.PaperError
import com.evove.app.ui.PaperField
import com.evove.app.ui.PaperInline
import com.evove.app.ui.PaperModal
import com.evove.app.ui.PaperPage
import com.evove.app.ui.hex
import com.evove.app.ui.paperMuted
import com.evove.app.ui.paperText
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

// The long lists of the attributes page: what was updated lately, every
// attribute of a degree (or the profile's own), and every action under its
// attribute of a degree (or the patches). A tap opens what it is worth, what
// computes it and what it computes; only what the user created — custom
// attributes and patches — can be edited.

private sealed interface Subject {
    data class Attribute(val key: String) : Subject
    data class Custom(val id: Int) : Subject
    data class Act(val id: String) : Subject
    data class Patch(val id: String) : Subject
}

private const val SEPARATOR = " · "
private val gold = hex("#b08a00")

private fun flatCustom(list: List<UserAttribute>): List<UserAttribute> = list.flatMap { listOf(it) + flatCustom(it.children) }

/** A user attribute in the shape the graph's are drawn in. */
private fun asNode(a: UserAttribute): AttrNode = AttrNode(
    key = "user:${a.id}", name = a.name, isLeaf = a.isLeaf, rank = a.rank, rankIndex = a.rankIndex, marks = a.marks,
    need = a.need, totalMarks = a.totalMarks, max = a.max, custom = true, children = a.children.map(::asNode),
)

/** "ESTUDO · FÍSICA" under the ESTUDO heading reads as "física". */
private fun patchLabel(name: String) = name.split(SEPARATOR).drop(1).joinToString(SEPARATOR).ifEmpty { name }

private fun ago(seconds: Long) = when {
    seconds < 60 -> "agora"
    seconds < 3600 -> "há ${seconds / 60} min"
    seconds < 86400 -> "há ${seconds / 3600} h"
    else -> "há ${seconds / 86400} d"
}

private class Group(val key: String, val title: String, val items: MutableList<Action> = mutableListOf())

@Composable
fun DetailsPage(onBack: () -> Unit) {
    var user by remember { mutableStateOf<UserState?>(null) }
    var roots by remember { mutableStateOf<List<AttrNode>>(emptyList()) }
    var custom by remember { mutableStateOf<List<UserAttribute>>(emptyList()) }
    var actions by remember { mutableStateOf<List<Action>>(emptyList()) }
    var recent by remember { mutableStateOf<List<AttrNode>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var attrView by remember { mutableStateOf("1") }
    var actView by remember { mutableStateOf("1") }
    var subject by remember { mutableStateOf<Subject?>(null) }
    var claimed by remember { mutableStateOf<Pair<String, String>?>(null) }
    var claiming by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        try {
            val u = scope.async { Api.user() }
            val t = scope.async { Api.attributeTree() }
            val c = scope.async { runCatching { Api.userAttributes() }.getOrDefault(emptyList()) }
            val a = scope.async { Api.actions() }
            val r = scope.async { Api.recentAttributes(10) }
            user = u.await(); roots = t.await().roots; custom = c.await(); actions = a.await(); recent = r.await()
        } catch (e: Exception) {
            error = e.message ?: "erro"
        }
    }
    LaunchedEffect(Bus.user) { load() }

    fun claim(n: AttrNode) {
        if (claiming) return
        claiming = true
        scope.launch {
            try {
                val r = Api.claimRank(n.key)
                val parts = mutableListOf("+${r.tokensGained}t", "+${r.skillPointsGained} skill")
                if (r.tokensWasted > 0) parts += "${r.tokensWasted}t além do limite"
                claimed = n.key to parts.joinToString(" · ")
                Bus.bumpUser()
                kotlinx.coroutines.delay(2500)
                claimed = null
            } catch (e: Exception) {
                error = e.message ?: "erro"
            } finally {
                claiming = false
            }
        }
    }

    PaperPage(Page.DETAILS.option, Page.DETAILS.title, onBack) {
        val u = user
        PaperError(error)
        if (u == null) { BasicText("carregando...", style = paperMuted); return@PaperPage }
        Row(verticalAlignment = Alignment.CenterVertically) {
            BasicText("me", Modifier.weight(1f), style = paperText.copy(fontSize = 1.4.rem))
            BasicText(u.rankSymbol, style = paperText.copy(fontFamily = Display, fontSize = 2.4.rem, color = Paper.accent))
            Column(Modifier.padding(start = 8.dp)) {
                BasicText("rank ${u.rankLetter}", style = paperText)
                BasicText("level ${u.level} · ${u.localLevelRoman}/${u.localLevelsTotal}", style = paperMuted)
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                BasicText("marcas", style = paperMuted)
                BasicText("${u.marks}", style = paperText.copy(fontWeight = FontWeight.Bold))
                BasicText("· nível ${u.localLevelRoman}", style = paperMuted)
            }
            MarkBar(u.levelMarks, u.levelCost, height = 22.dp)
        }

        PaperCard("atualizados recentemente") {
            if (recent.isEmpty()) BasicText("nenhum atributo ganhou marcas ainda", style = paperMuted)
            for (r in recent) AttrRow(r, listOfNotNull(r.parent ?: if (r.custom) "custom" else null, ago(r.secondsAgo)).joinToString(" · "))
        }

        PaperCard("atributos") {
            Degree(attrView, if (attrView == "p") "atributos custom" else "grau $attrView") {
                attrView = listOf("1", "2", "3", "p").let { it[(it.indexOf(attrView) + 1) % it.size] }
            }
            val items: List<Pair<AttrNode, Subject>> = if (attrView == "p") flatCustom(custom).map { asNode(it) to Subject.Custom(it.id) }
            else attributesOfDegree(roots, attrView.toInt()).map { it to Subject.Attribute(it.key) }
            if (items.isEmpty()) BasicText(
                if (attrView == "p") "nenhum ainda — crie na loja, em “+ atributo” ou ao montar um patch" else "nenhum atributo de grau $attrView",
                style = paperMuted,
            )
            for ((n, s) in items) AttrRow(
                n, claimed?.takeIf { it.first == n.key }?.second,
                onOpen = { subject = s },
                onClaim = if (attrView == "p") null else ({ claim(n) }),
            )
        }

        PaperCard("ações") {
            Degree(actView, if (actView == "p") "patches" else "por atributo de grau $actView") {
                actView = listOf("1", "2", "p").let { it[(it.indexOf(actView) + 1) % it.size] }
            }
            val groups = if (actView == "p") patchesByBase(actions) else actionsOfDegree(actions, actView.toInt())
            if (groups.isEmpty()) BasicText(
                if (actView == "p") "nenhum patch ainda — monte um na loja, em “+ patch”" else "nenhuma ação ainda — adquira na loja",
                style = paperMuted,
            )
            for (g in groups) {
                BasicText(g.title, Modifier.padding(top = 6.dp), style = paperMuted.copy(fontWeight = FontWeight.Bold))
                for (a in g.items) Column(
                    Modifier.fillMaxWidth().clickable { subject = if (a.baseActionId != null) Subject.Patch(a.id) else Subject.Act(a.id) }.padding(vertical = 4.dp),
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        BasicText(formatCode(a.id), style = paperMuted)
                        BasicText((if (actView == "p") patchLabel(a.name) else a.name).lowercase(), Modifier.weight(1f), style = paperText)
                        BasicText("${a.value}× · ${a.score} marcas", style = paperMuted)
                    }
                    if (actView == "p" && a.attributes.isNotEmpty()) BasicText(a.attributes.joinToString(", ") { it.name }, style = paperMuted.copy(fontSize = 0.7.rem))
                }
            }
        }
    }

    subject?.let { s -> DetailModal(s, roots, custom, actions, onClose = { subject = null }, onChanged = { load() }) }
}

@Composable
private fun Degree(view: String, title: String, onClick: () -> Unit) {
    Row(Modifier.clickable(onClick = onClick).border(1.dp, Paper.line, RoundedCornerShape(3.dp)).padding(horizontal = 8.dp, vertical = 3.dp)) {
        BasicText("★$view · $title", style = paperMuted)
    }
}

/** One attribute: its name, rank and the marks toward the next; with a reward
 *  waiting, a tap takes it instead of opening. */
@Composable
private fun AttrRow(node: AttrNode, note: String?, onOpen: (() -> Unit)? = null, onClaim: (() -> Unit)? = null) {
    val claimable = node.claim != null && onClaim != null
    val tap = if (claimable) onClaim else onOpen
    Column(
        Modifier.fillMaxWidth()
            .then(if (claimable) Modifier.border(1.dp, gold, RoundedCornerShape(6.dp)).padding(horizontal = 0.55.remDp, vertical = 0.4.remDp) else Modifier.padding(vertical = 0.3.remDp))
            .then(if (tap != null) Modifier.clickable(onClick = tap) else Modifier),
        verticalArrangement = Arrangement.spacedBy(0.3.remDp),
    ) {
        if (claimable) node.claim?.let { BasicText("+${it.tokens}t · +${it.skillPoints} skill", Modifier.align(Alignment.End), style = paperMuted.copy(color = gold, fontSize = 0.7.rem)) }
        Row(horizontalArrangement = Arrangement.spacedBy(0.5.remDp)) {
            BasicText(node.name, Modifier.weight(1f), style = paperText.copy(color = if (node.custom) Paper.accent else Paper.text))
            node.weight?.let { BasicText("${(it * 100).roundToInt()}%", style = paperMuted) }
            BasicText(node.rank, style = paperText)
        }
        MarkBar(if (node.max) node.need else node.marks, node.need, gold = true, label = if (node.max) "máx" else null)
        if (note != null) BasicText(note, style = paperMuted.copy(fontSize = 0.7.rem))
    }
}

/** The attributes of one degree, in graph order, each once, where it lives. */
private fun attributesOfDegree(list: List<AttrNode>, degree: Int): List<AttrNode> {
    val out = mutableListOf<AttrNode>()
    val seen = HashSet<String>()
    fun walk(n: AttrNode) {
        if (n.degree == degree) { if (seen.add(n.key)) out += n; return }
        n.children.filter { it.primary != false }.forEach(::walk)
    }
    list.forEach(::walk)
    return out
}

/** Catalog actions under their ancestor of `degree`. Patches have their own view. */
private fun actionsOfDegree(list: List<Action>, degree: Int): List<Group> {
    val groups = LinkedHashMap<String, Group>()
    // a log action is registered under no attribute, so it has no path to group by
    val logged = Group("_log", "registro")
    val loose = Group("", "sem registro")
    for (a in list) {
        if (a.baseActionId != null) continue
        val at = a.path.getOrNull(degree - 1)
        if (at == null) { (if (a.logOnly) logged else loose).items += a; continue }
        groups.getOrPut(at.key) { Group(at.key, a.path.take(degree).joinToString(" › ") { it.name }) }.items += a
    }
    val out = groups.values.sortedWith { x, y -> pt.compare(x.title, y.title) }.toMutableList()
    for (extra in listOf(logged, loose)) if (extra.items.isNotEmpty()) out += extra
    out.forEach { g -> g.items.sortBy { it.id } }
    return out
}

private fun patchesByBase(list: List<Action>): List<Group> {
    val names = list.associate { it.id to it.name }
    val groups = LinkedHashMap<String, Group>()
    for (a in list) {
        val key = a.baseActionId ?: continue
        groups.getOrPut(key) { Group(key, names[key] ?: key) }.items += a
    }
    return groups.values.sortedWith { x, y -> pt.compare(x.title, y.title) }.onEach { g -> g.items.sortBy { it.id } }
}

// ---------------------------------------------------------------- the detail

private class Linked(
    val key: String, val name: String, val note: String? = null, val rank: String? = null, val custom: Boolean = false,
    val weight: Double? = null, val link: Pair<String, Int>? = null, val remove: (() -> Pending)? = null,
)

private class Pending(val title: String, val lines: List<String>, val confirm: String, val run: suspend () -> Unit)

@Composable
private fun DetailModal(
    subject: Subject, roots: List<AttrNode>, custom: List<UserAttribute>, actions: List<Action>,
    onClose: () -> Unit, onChanged: suspend () -> Unit,
) {
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var pending by remember { mutableStateOf<Pending?>(null) }
    var editingName by remember { mutableStateOf(false) }
    var nameDraft by remember { mutableStateOf("") }
    var editingParents by remember { mutableStateOf(false) }
    var editingChildren by remember { mutableStateOf(false) }
    var parentDraft by remember { mutableStateOf<Int?>(null) }
    var parentIdsDraft by remember { mutableStateOf<Set<Int>>(emptySet()) }
    var windowLabel by remember { mutableStateOf("…") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(subject) {
        val id = (subject as? Subject.Act)?.id ?: (subject as? Subject.Patch)?.id ?: return@LaunchedEffect
        windowLabel = runCatching { Api.actionWindow(id) }.map { "${it.windowMarks}/${it.limit} em ${it.hours}h" }.getOrDefault("—")
    }

    // every attribute of the graph once, and the links into each
    val nodes = LinkedHashMap<String, AttrNode>()
    val parentsOf = HashMap<String, MutableList<Triple<AttrNode, Double, Boolean>>>()
    fun visit(n: AttrNode) {
        if (n.key in nodes) return
        nodes[n.key] = n
        for (c in n.children) {
            parentsOf.getOrPut(c.key) { mutableListOf() } += Triple(n, c.weight ?: 1.0, c.primary != false)
            visit(c)
        }
    }
    roots.forEach(::visit)
    val customList = flatCustom(custom)
    val customById = customList.associateBy { it.id }
    val actionById = actions.associateBy { it.id }
    val paths = flattenUserAttributes(custom).associate { it.first to it.third }

    val node = (subject as? Subject.Attribute)?.let { nodes[it.key] }
    val attr = (subject as? Subject.Custom)?.let { customById[it.id] }
    val action = when (subject) { is Subject.Act -> actionById[subject.id]; is Subject.Patch -> actionById[subject.id]; else -> null }
    val kind = when (subject) { is Subject.Attribute -> "atributo"; is Subject.Custom -> "atributo custom"; is Subject.Act -> "ação"; is Subject.Patch -> "patch" }
    val name = node?.name ?: attr?.name ?: action?.let { if (it.baseActionId != null) patchLabel(it.name).lowercase() else it.name.lowercase() } ?: ""
    val renamable = attr != null || action?.baseActionId != null

    fun run(fn: suspend () -> Unit, after: () -> Unit = {}) {
        busy = true
        error = null
        scope.launch {
            try { fn(); onChanged(); after() } catch (e: Exception) { error = e.message ?: "erro" } finally { busy = false }
        }
    }

    fun rankStats(total: Int, marks: Int, need: Int, max: Boolean, rank: String) =
        listOf("marcas totais" to "$total", "marcas atuais" to (if (max) "máx" else "$marks/$need"), "rank" to rank)
    val stats = when {
        node != null -> rankStats(node.totalMarks, node.marks, node.need, node.max, node.rank) + ("grau" to "${node.degree}")
        attr != null -> rankStats(attr.totalMarks, attr.marks, attr.need, attr.max, attr.rank) + ("grau" to "custom")
        action != null -> listOf(
            "marcas totais" to "${action.score}", "marcas atuais" to windowLabel, "execuções" to "${action.value}",
            if (action.baseActionId != null) "base" to (actionById[action.baseActionId]?.name ?: "").lowercase() else "id" to formatCode(action.id),
        )
        else -> emptyList()
    }

    val parents: List<Linked> = when {
        node != null -> (parentsOf[node.key] ?: emptyList()).map { (p, w, primary) -> Linked(p.key, p.name, if (primary) "primário" else "ligação", p.rank, weight = w) }
        attr != null -> attr.parentId?.let { customById[it] }?.let { listOf(Linked("user:${it.id}", it.name, rank = it.rank, custom = true)) } ?: emptyList()
        action?.baseActionId != null -> action.attributes.map { Linked("user:${it.id}", it.name, rank = customById[it.id]?.rank, custom = true, weight = it.weight) }
        action != null -> action.leaves.map { Linked(it.key, it.name, rank = nodes[it.key]?.rank, weight = it.weight) }
        else -> emptyList()
    }
    val children: List<Linked> = when {
        node != null -> node.children.map { Linked(it.key, it.name, if (it.primary == false) "ligação" else null, it.rank, weight = it.weight ?: 1.0) } +
            actions.mapNotNull { a -> a.leaves.find { it.key == node.key }?.let { Linked("action:${a.id}", a.name.lowercase(), if (a.baseActionId != null) "patch" else "ação", weight = it.weight) } }
        attr != null -> attr.children.map { c ->
            Linked("user:${c.id}", c.name, rank = c.rank, custom = true, weight = 1.0 / attr.children.size, remove = {
                Pending("remover filho", listOfNotNull(
                    "${c.name} deixa de ser filho de ${attr.name} e vira um atributo raiz, com as marcas que tem.",
                    "${attr.name} para de computar as marcas de ${c.name} para si.",
                    if (attr.children.size == 1) "${attr.name} fica sem filhos e mantém o total que tem agora." else null,
                ), "remover") { Api.updateUserAttribute(c.id, moveToRoot = true) }
            })
        } + attr.patches.map { p ->
            Linked("patch:${p.id}", p.name.lowercase(), "patch · ${formatCode(p.id)}", weight = p.weight, link = p.id to attr.id, remove = {
                val only = (actionById[p.id]?.attributes?.size ?: 0) <= 1
                Pending("remover filho", listOfNotNull(
                    "${attr.name} para de computar as marcas do patch ${p.name.lowercase()} para si.",
                    if (only) "${p.name.lowercase()} fica sem atributos custom e continua rodando como a ação base." else null,
                ), "remover") { Api.unlinkPatchAttribute(p.id, attr.id) }
            })
        }
        else -> emptyList()
    }

    fun askParents() {
        if (attr != null) {
            if (parentDraft == attr.parentId) { editingParents = false; return }
            val from = attr.parentId?.let { customById[it] }
            val to = parentDraft?.let { customById[it]?.name }
            val target = parentDraft
            pending = Pending("alterar pai", listOfNotNull(
                "${attr.name} passa para ${to ?: "a raiz"}, com as marcas que tem.",
                from?.let { "${it.name} para de computar as marcas de ${attr.name} para si." },
                if (from != null && from.children.size == 1) "${from.name} fica sem filhos e mantém o total que tem agora." else null,
                to?.let { "$it passa a computar as marcas de ${attr.name}." },
            ), "alterar") { if (target == null) Api.updateUserAttribute(attr.id, moveToRoot = true) else Api.updateUserAttribute(attr.id, parentId = target) }
        } else if (action != null) {
            val before = action.attributes.map { it.id }.toSet()
            val removed = before - parentIdsDraft
            val added = parentIdsDraft - before
            if (removed.isEmpty() && added.isEmpty()) { editingParents = false; return }
            fun names(ids: Set<Int>) = ids.joinToString(", ") { customById[it]?.name ?: "$it" }
            val ids = parentIdsDraft.toList()
            pending = Pending("alterar pais", listOfNotNull(
                if (removed.isNotEmpty()) "${names(removed)} ${if (removed.size > 1) "param" else "para"} de computar as marcas deste patch para si." else null,
                if (added.isNotEmpty()) "${names(added)} ${if (added.size > 1) "passam" else "passa"} a computar as marcas deste patch, a 100%." else null,
                if (ids.isEmpty()) "o patch fica sem atributos custom e continua rodando como a ação base." else null,
            ), "alterar") { Api.updatePatch(action.id, attributeIds = ids) }
        }
    }

    PaperModal(kind, onClose) {
        if (node == null && attr == null && action == null) { BasicText("não encontrado", style = paperMuted); return@PaperModal }
        if (editingName) {
            PaperField(nameDraft, { nameDraft = it.take(if (action != null) 48 else 64) }, "nome")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f)) { editingName = false }
                PaperButton("salvar", enabled = !busy, modifier = Modifier.weight(1f)) {
                    val next = nameDraft.trim().replace(Regex("\\s+"), " ").lowercase()
                    if (next.isEmpty() || next == name) { editingName = false; return@PaperButton }
                    run({ if (subject is Subject.Patch) Api.updatePatch(subject.id, name = next) else Api.updateUserAttribute((subject as Subject.Custom).id, name = next) }) { editingName = false }
                }
            }
        } else Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            BasicText(name, Modifier.weight(1f), style = paperText.copy(fontSize = 1.4.rem, letterSpacing = 0.04.em, color = if (attr != null) Paper.accent else Paper.text))
            if (renamable) PaperInline("✎ renomear") { nameDraft = name; editingName = true }
        }
        for ((k, v) in stats) Row {
            BasicText(k, Modifier.width(8.remDp), style = paperMuted)
            BasicText(v, style = paperText)
        }
        PaperError(error)

        Row(verticalAlignment = Alignment.CenterVertically) {
            BasicText("PAIS", Modifier.weight(1f), style = paperMuted.copy(letterSpacing = 0.1.em))
            if (renamable) PaperInline(if (editingParents) "cancelar" else "✎ alterar") {
                if (editingParents) editingParents = false
                else { parentDraft = attr?.parentId; parentIdsDraft = action?.attributes?.map { it.id }?.toSet() ?: emptySet(); editingParents = true }
            }
        }
        if (editingParents && attr != null) {
            // a parent may not be itself or below it, nor a leaf holding marks
            fun subtree(a: UserAttribute): List<Int> = listOf(a.id) + a.children.flatMap(::subtree)
            val blocked = subtree(attr).toSet()
            Pick("nenhum — raiz", parentDraft == null, true) { parentDraft = null }
            for (c in customList) {
                val holds = c.isLeaf && (c.totalMarks > 0 || c.rankIndex > 0)
                Pick(paths[c.id] ?: c.name, parentDraft == c.id, c.id !in blocked && !holds, if (c.id !in blocked && holds) "tem marcas próprias" else null) { parentDraft = c.id }
            }
        } else if (editingParents && action != null) {
            if (customList.isEmpty()) BasicText("nenhum atributo custom — crie na loja", style = paperMuted)
            for (c in customList) Pick(paths[c.id] ?: c.name, c.id in parentIdsDraft, true, check = true) {
                parentIdsDraft = if (c.id in parentIdsDraft) parentIdsDraft - c.id else parentIdsDraft + c.id
            }
        } else {
            if (parents.isEmpty()) BasicText(if (attr != null) "raiz — sem pai" else "sem pais", style = paperMuted)
            for (r in parents) LinkRow(r, false, busy, {}) { }
        }
        if (editingParents) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f)) { editingParents = false }
            PaperButton("salvar", enabled = !busy, modifier = Modifier.weight(1f), onClick = ::askParents)
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            BasicText("FILHOS", Modifier.weight(1f), style = paperMuted.copy(letterSpacing = 0.1.em))
            if (attr != null && children.any { it.remove != null }) PaperInline(if (editingChildren) "pronto" else "✎ editar") { editingChildren = !editingChildren }
        }
        if (children.isEmpty()) BasicText("sem filhos", style = paperMuted)
        for (r in children) LinkRow(r, editingChildren, busy, { units ->
            val link = r.link ?: return@LinkRow
            run({ Api.setPatchWeight(link.first, link.second, units / 10.0) })
        }) { r.remove?.let { pending = it() } }
        if (editingChildren) BasicText("toque numa unidade da barra para mudar o peso de um patch", style = paperMuted)
    }

    pending?.let { p ->
        PaperModal(p.title, { pending = null }) {
            for (l in p.lines) BasicText(l, style = paperText)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f)) { pending = null }
                PaperButton(p.confirm, danger = true, modifier = Modifier.weight(1f)) {
                    pending = null
                    run(p.run) { editingParents = false }
                }
            }
        }
    }
}

@Composable
private fun Pick(text: String, on: Boolean, enabled: Boolean, note: String? = null, check: Boolean = false, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().then(if (enabled) Modifier.clickable(onClick = onClick) else Modifier).padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        val mark = if (check) (if (on) "☑" else "☐") else (if (on) "◉" else "○")
        BasicText(mark, style = paperText.copy(color = if (enabled) Paper.text else Paper.line))
        BasicText(text, Modifier.weight(1f), style = paperText.copy(color = if (enabled) Paper.text else Paper.muted))
        if (note != null) BasicText(note, style = paperMuted.copy(fontSize = 0.7.rem))
    }
}

@Composable
private fun LinkRow(r: Linked, editing: Boolean, busy: Boolean, onWeight: (Int) -> Unit, onRemove: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (editing && r.remove != null) BasicText("−", Modifier.clickable(enabled = !busy, onClick = onRemove).border(1.dp, Paper.error, RoundedCornerShape(3.dp)).padding(horizontal = 8.dp),
                style = paperText.copy(color = Paper.error))
            Column(Modifier.weight(1f)) {
                BasicText(r.name, style = paperText.copy(color = if (r.custom) Paper.accent else Paper.text))
                if (r.note != null) BasicText(r.note, style = paperMuted.copy(fontSize = 0.7.rem))
            }
            if (r.rank != null) BasicText(r.rank, style = paperText)
        }
        r.weight?.let { w ->
            MarkBar((w * 10).roundToInt(), 10, label = "${(w * 100).roundToInt()}%", onPick = if (editing && r.link != null) onWeight else null)
        }
    }
}
