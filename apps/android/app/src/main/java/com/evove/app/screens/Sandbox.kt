package com.evove.app.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import com.evove.app.api.Api
import com.evove.app.api.AttrNode
import com.evove.app.sound.Sfx
import com.evove.app.ui.Big
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Empty
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.MarkBar
import com.evove.app.ui.Small
import com.evove.app.ui.Ticks
import com.evove.app.ui.Type
import com.evove.app.ui.caps
import com.evove.app.ui.remDp
import kotlin.math.ceil
import kotlin.math.floor

// The sandbox's attributes: every leaf its free acts reached, the most marked
// first, with its rank there. The real ones stay where they were.

private const val ROW_DP = 52

@Composable
fun SandboxAttributesScreen(onHome: () -> Unit) {
    var list by remember { mutableStateOf<List<AttrNode>?>(null) }
    var page by remember { mutableIntStateOf(0) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            list = Api.sandboxAttributes().filter { it.totalMarks > 0 }
            Sfx.powerOn()
        } catch (e: Exception) {
            error = e.message ?: "erro"
        }
    }

    val all = list.orEmpty()
    DarkScreen(
        Ink.sandbox, display = 0.16f,
        displayContent = {
            Big("atributos")
            Small(error ?: "sandbox · ${all.size} com marcas · os reais não mudam")
        },
        bar = {
            Key({ Sfx.tap(2); page++ }, Modifier.at(1, 2), enabled = all.isNotEmpty()) { KeyIcon(Icon.DOWN) }
            HomeKey { Sfx.tap(0); onHome() }
        },
    ) { info ->
        val perPage = maxOf(1, floor((info.height.value - 16) / (ROW_DP + 8)).toInt())
        val pages = maxOf(1, ceil(all.size / perPage.toFloat()).toInt())
        val at = page % pages
        when {
            list == null -> Empty("…")
            all.isEmpty() -> Empty("nada ainda — aja no sandbox")
            else -> for (a in all.drop(at * perPage).take(perPage)) {
                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(0.3.remDp)) {
                    Row {
                        BasicText(caps(a.name), Modifier.weight(1f), style = Type.row, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        BasicText("${a.rank} · ${a.totalMarks}", style = Type.row.copy(color = Ink.sandbox))
                    }
                    MarkBar(a.marks, a.need, gold = a.max)
                }
            }
        }
        if (pages > 1) Ticks(pages, at)
    }
}
