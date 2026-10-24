package com.evove.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp

/** Points and tokens, small, at the top of the frame: a p for the points, a
 *  coin for the tokens. */
@Composable
fun WalletBar(points: Int, tokens: Int, modifier: Modifier = Modifier) {
    val style = TextStyle(fontFamily = Mono, fontSize = 0.6.rem, color = Color.White.copy(alpha = 0.7f))
    Row(modifier.padding(top = 1.dp).testTag("wallet"), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
        BasicText("p", style = style.copy(color = Ink.gold))
        BasicText("$points", style = style)
        Canvas(Modifier.size(9.dp)) {
            drawCircle(Ink.gold, size.minDimension / 2 - 0.7.dp.toPx(), style = Stroke(1.2.dp.toPx()))
            drawLine(Ink.gold, Offset(size.width / 2, size.height * 0.28f), Offset(size.width / 2, size.height * 0.72f), 1.dp.toPx())
        }
        BasicText("$tokens", style = style)
    }
}
