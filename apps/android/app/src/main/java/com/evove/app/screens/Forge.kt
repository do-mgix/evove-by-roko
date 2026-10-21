package com.evove.app.screens

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.evove.app.Bus
import com.evove.app.api.Action
import com.evove.app.api.Api
import com.evove.app.api.SuggestionCatalog
import com.evove.app.api.SuggestionNode
import com.evove.app.api.UserAttribute
import com.evove.app.api.fold
import com.evove.app.api.formatCode
import com.evove.app.ui.Paper
import com.evove.app.ui.PaperButton
import com.evove.app.ui.PaperError
import com.evove.app.ui.PaperField
import com.evove.app.ui.PaperInline
import com.evove.app.ui.PaperModal
import com.evove.app.ui.PaperRow
import com.evove.app.ui.paperMuted
import com.evove.app.ui.paperText
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.async
import kotlinx.coroutines.launch

// What the shop makes rather than sells: a patch over an owned action, or an
// attribute of the profile's own. Opened from the shop's first screen.

/** Compare names as the database does: case and accents do not distinguish. */
fun sameName(a: String, b: String) = fold(a).trim() == fold(b).trim()

/** Every user attribute once, with its path, for pickers. */
fun flattenUserAttributes(list: List<UserAttribute>, parent: String = ""): List<Triple<Int, String, String>> =
    list.flatMap { a ->
        val path = if (parent.isNotEmpty()) "$parent › ${a.name}" else a.name
        listOf(Triple(a.id, a.name, path)) + flattenUserAttributes(a.children, path)
    }

private fun allUserAttrs(list: List<UserAttribute>): List<UserAttribute> = list.flatMap { listOf(it) + allUserAttrs(it.children) }

/** Mirrors the server: the base's id plus the lowest free two digits. */
private fun nextFreePatchId(base: Action, all: List<Action>): String {
    val used = all.filter { it.baseActionId == base.id }.map { it.id.drop(base.id.length) }.toSet()
    for (n in 1..99) {
        val suffix = n.toString().padStart(2, '0')
        if (suffix !in used) return base.id + suffix
    }
    return ""
}

@Composable
fun ShopForge(mode: String, onClose: () -> Unit) {
    var costByName by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }
    var points by remember { mutableIntStateOf(0) }
    var actions by remember { mutableStateOf<List<Action>>(emptyList()) }
    var attrs by remember { mutableStateOf<List<UserAttribute>>(emptyList()) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        val c = scope.async { runCatching { Api.shopCatalog() }.getOrDefault(emptyList()) }
        val u = scope.async { runCatching { Api.user() }.getOrNull() }
        val a = scope.async { runCatching { Api.actions() }.getOrDefault(emptyList()) }
        val t = scope.async { runCatching { Api.userAttributes() }.getOrDefault(emptyList()) }
        costByName = c.await().flatMap { g -> g.actions.map { it.name.uppercase() to it.cost } }.toMap()
        points = u.await()?.buildPoints ?: 0
        actions = a.await()
        attrs = t.await()
    }
    val options = flattenUserAttributes(attrs)

    if (mode == "patch") PaperModal("novo patch", onClose) {
        var base by remember { mutableStateOf<Action?>(null) }
        var baseQuery by remember { mutableStateOf("") }
        var name by remember { mutableStateOf("") }
        var ids by remember { mutableStateOf<Set<Int>>(emptySet()) }
        var newNames by remember { mutableStateOf<List<String>>(emptyList()) }
        var newPaths by remember { mutableStateOf<List<List<String>>>(emptyList()) }
        var picker by remember { mutableStateOf(false) }
        var draft by remember { mutableStateOf("") }
        var busy by remember { mutableStateOf(false) }
        var error by remember { mutableStateOf<String?>(null) }

        val bases = actions.filter { it.baseActionId == null }
        val b = base
        val cost = b?.let { costByName[it.name.uppercase()] } ?: 0
        val nextId = b?.let { nextFreePatchId(it, actions) } ?: ""
        // a log action is logged, not trained: its patches only separate entries
        val isLog = b?.logOnly == true
        val ready = b != null && nextId.isNotEmpty() && name.isNotBlank() &&
            (isLog || ids.size + newNames.size + newPaths.size > 0) && points >= cost

        /** A name the profile already has selects that attribute instead of a twin. */
        fun addNamed(label: String, path: List<String>?) {
            val existing = options.find { sameName(it.second, label) }
            if (existing != null) ids = ids + existing.first
            else if ((newNames + newPaths.map { it.last() }).none { sameName(it, label) }) {
                if (path != null) newPaths = newPaths + listOf(path) else newNames = newNames + label
            }
        }

        Step("1 · ação base")
        if (b != null) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(0.6.remDp)) {
            BasicText(formatCode(b.id), style = paperMuted)
            BasicText(b.name.lowercase(), Modifier.weight(1f), style = paperText)
            PaperInline("trocar") { base = null }
        } else if (bases.isEmpty()) {
            BasicText("adquira uma ação na loja primeiro — o patch roda em cima dela", style = paperMuted)
        } else {
            PaperField(baseQuery, { baseQuery = it }, "buscar ação...")
            val q = fold(baseQuery.trim())
            for (a in bases.filter { fold(it.name).contains(q) }.take(30)) {
                Row(Modifier.fillMaxWidth().clickable { base = a }.padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    BasicText(formatCode(a.id), style = paperMuted)
                    BasicText(a.name.lowercase(), style = paperText)
                }
            }
        }
        if (b != null) {
            Step("2 · nome do patch")
            PaperField(name, { name = it.take(48) }, "física")
        }
        if (b != null && name.isNotBlank()) {
            Step("3 · atributos")
            if (isLog) {
                BasicText("${b.name} é registro, não treino: o patch separa as entradas no diário e não treina atributo nenhum.", style = paperMuted)
            } else {
                if (options.isNotEmpty()) for ((id, _, path) in options) {
                    Row(Modifier.fillMaxWidth().clickable { ids = if (id in ids) ids - id else ids + id }.padding(vertical = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        BasicText(if (id in ids) "☑" else "☐", style = paperText)
                        BasicText(path, style = paperText)
                    }
                } else if (newNames.isEmpty() && newPaths.isEmpty()) BasicText("nenhum atributo ainda — crie o primeiro", style = paperMuted)
                for (n in newNames) Row { BasicText("+ $n", Modifier.weight(1f), style = paperText); PaperInline("remover") { newNames = newNames - n } }
                for (p in newPaths) Row { BasicText("+ ${p.last()}", Modifier.weight(1f), style = paperText); PaperInline("remover") { newPaths = newPaths.filter { it !== p } } }
                Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PaperField(draft, { draft = it.take(64) }, "novo atributo", modifier = Modifier.weight(1f))
                    PaperButton("criar", enabled = draft.isNotBlank(), ghost = true, modifier = Modifier.weight(0.4f)) {
                        val n = draft.trim().replace(Regex("\\s+"), " ")
                        if (n.isNotEmpty()) addNamed(n, null)
                        draft = ""
                    }
                }
                PaperInline(if (picker) "fechar catálogo" else "escolher do catálogo") { picker = !picker }
                if (picker) SuggestionPicker(options.map { it.second }) { path -> addNamed(path.last(), path); picker = false }
            }
        }
        if (b != null) {
            PaperRow("id", if (nextId.isNotEmpty()) formatCode(nextId) else "sem ids livres")
            PaperRow("custo", "$cost pts")
            PaperRow("saldo", "$points pts")
        }
        PaperError(error)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f), onClick = onClose)
            PaperButton(if (busy) "..." else if (cost > 0) "criar · $cost pts" else "criar", enabled = ready && !busy, modifier = Modifier.weight(1f)) {
                val bb = base ?: return@PaperButton
                busy = true
                error = null
                scope.launch {
                    try {
                        Api.createPatch(bb.id, name.trim(), if (isLog) emptyList() else ids.toList(), if (isLog) emptyList() else newNames, if (isLog) emptyList() else newPaths)
                        Bus.bumpUser()
                        onClose()
                    } catch (e: Exception) {
                        error = e.message ?: "erro"
                    } finally {
                        busy = false
                    }
                }
            }
        }
    }

    if (mode == "attr") PaperModal("novo atributo", onClose) {
        var catalog by remember { mutableStateOf(true) }
        var name by remember { mutableStateOf("") }
        var parent by remember { mutableStateOf<Int?>(null) }
        var path by remember { mutableStateOf<List<String>>(emptyList()) }
        var withParents by remember { mutableStateOf(true) }
        var busy by remember { mutableStateOf(false) }
        var error by remember { mutableStateOf<String?>(null) }

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Tab("catálogo", catalog, Modifier.weight(1f)) { catalog = true }
            Tab("livre", !catalog, Modifier.weight(1f)) { catalog = false }
        }
        if (catalog) {
            if (path.isNotEmpty()) {
                Step("escolhido")
                Row { BasicText(path.joinToString(" › "), Modifier.weight(1f), style = paperText); PaperInline("trocar") { path = emptyList() } }
                if (path.size > 1) Row(Modifier.clickable { withParents = !withParents }.padding(vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    BasicText(if (withParents) "☑" else "☐", style = paperText)
                    BasicText("criar os níveis acima", style = paperText)
                }
                // a level of the path already a leaf holding marks: taking a child
                // hands them to it, and the level becomes the mean of its children
                val swallows = if (withParents && path.size > 1) allUserAttrs(attrs).find { a ->
                    a.isLeaf && (a.marks > 0 || a.rankIndex > 0) && path.dropLast(1).any { sameName(a.name, it) }
                } else null
                if (swallows != null) BasicText("${swallows.name} já existe e guarda marcas: elas passam para o primeiro filho e ele vira a média dos filhos.", style = paperMuted)
            } else {
                Step("escolher")
                SuggestionPicker(options.map { it.second }) { path = it }
            }
        } else {
            Step("nome")
            PaperField(name, { name = it.take(64) }, "física")
            Step("dentro de (opcional)")
            Row(Modifier.fillMaxWidth().clickable { parent = null }.padding(vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BasicText(if (parent == null) "◉" else "○", style = paperText); BasicText("nenhum", style = paperText)
            }
            for ((id, _, p) in options) Row(Modifier.fillMaxWidth().clickable { parent = id }.padding(vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BasicText(if (parent == id) "◉" else "○", style = paperText); BasicText(p, style = paperText)
            }
        }
        BasicText("fica fora da árvore padrão e só é treinado por patches", style = paperMuted)
        PaperError(error)
        val ready = if (catalog) path.isNotEmpty() else name.isNotBlank()
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f), onClick = onClose)
            PaperButton(if (busy) "..." else "criar", enabled = ready && !busy, modifier = Modifier.weight(1f)) {
                busy = true
                error = null
                scope.launch {
                    try {
                        if (catalog) Api.createUserAttributePath(if (withParents) path else path.takeLast(1))
                        else Api.createUserAttribute(name.trim(), parent)
                        Bus.bumpUser()
                        onClose()
                    } catch (e: Exception) {
                        error = e.message ?: "erro"
                    } finally {
                        busy = false
                    }
                }
            }
        }
    }
}

@Composable
private fun Step(text: String) = BasicText(text, style = paperMuted.copy(fontSize = 0.7.rem))

@Composable
private fun Tab(text: String, on: Boolean, modifier: Modifier, onClick: () -> Unit) {
    BasicText(
        text,
        modifier.border(1.dp, if (on) Paper.text else Paper.line, RoundedCornerShape(3.dp)).clickable(onClick = onClick).padding(vertical = 6.dp),
        style = paperText.copy(fontSize = 0.75.rem, color = if (on) Paper.text else Paper.muted, textAlign = androidx.compose.ui.text.style.TextAlign.Center),
    )
}

/** The suggestion catalog: one level at a time, or the matches of a search,
 *  capped. `onPick` gets the picked node's whole path, root first. */
@Composable
fun SuggestionPicker(existing: List<String>, onPick: (List<String>) -> Unit) {
    var catalogs by remember { mutableStateOf<List<SuggestionCatalog>>(emptyList()) }
    var error by remember { mutableStateOf(false) }
    var active by remember { mutableIntStateOf(0) }
    var query by remember { mutableStateOf("") }
    var openKey by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) { runCatching { Api.attributeSuggestions() }.onSuccess { catalogs = it }.onFailure { error = true } }

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (error) { BasicText("catálogo indisponível — use o campo de texto", style = paperMuted); return@Column }
        if (catalogs.isEmpty()) { BasicText("carregando…", style = paperMuted); return@Column }
        Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            catalogs.forEachIndexed { i, c -> Tab(c.name, i == active, Modifier.weight(1f)) { active = i; openKey = null; query = "" } }
        }
        val catalog = catalogs[active]
        val byKey = remember(catalog) { catalog.nodes.associateBy { it.key } }
        fun pathOf(n: SuggestionNode): List<SuggestionNode> {
            val out = ArrayDeque<SuggestionNode>()
            var cur: SuggestionNode? = n
            while (cur != null) { out.addFirst(cur); cur = cur.parent?.let { byKey[it] } }
            return out
        }
        PaperField(query, { query = it }, "buscar — física, gestão, escrita…")
        val q = fold(query.trim())
        val matches = if (q.isNotEmpty()) catalog.nodes.filter { fold(it.label).contains(q) || fold(it.sourceLabel).contains(q) }
        else catalog.nodes.filter { it.parent == openKey }
        val shown = matches.take(30)
        if (q.isEmpty() && openKey != null) byKey[openKey]?.let { node ->
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                PaperInline("tudo") { openKey = null }
                for (t in pathOf(node)) { BasicText("›", style = paperMuted); PaperInline(t.label) { openKey = t.key } }
            }
        }
        for (n in shown) {
            val path = pathOf(n)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f).clickable { onPick(path.map { it.label }) }.padding(vertical = 5.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        BasicText(n.label, style = paperText)
                        if (existing.any { sameName(it, n.label) }) BasicText("já existe", style = paperMuted.copy(color = Paper.accent))
                    }
                    if (q.isNotEmpty() && path.size > 1) BasicText(path.dropLast(1).joinToString(" › ") { it.label }, style = paperMuted.copy(fontSize = 0.68.rem))
                }
                if (q.isEmpty() && catalog.nodes.any { it.parent == n.key }) {
                    BasicText("›", Modifier.clickable { openKey = n.key }.padding(horizontal = 12.dp, vertical = 4.dp), style = paperText.copy(fontSize = 1.1.rem))
                }
            }
        }
        if (shown.isEmpty()) BasicText("nada com esse nome — use o campo de texto", style = paperMuted)
        if (matches.size > shown.size) BasicText("+${matches.size - shown.size} — refine a busca", style = paperMuted)
        BasicText(catalog.source, style = paperMuted.copy(fontSize = 0.68.rem))
    }
}
