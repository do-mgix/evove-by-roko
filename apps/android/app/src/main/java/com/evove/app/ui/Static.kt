package com.evove.app.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import kotlinx.coroutines.delay

/** Static: random grey pixels, a dozen frames a second — what is not yet
 *  discovered in the shop, and the face of whoever waits in the journey. */
@Composable
fun Static(modifier: Modifier, opacity: Float = 0.55f) {
    val bitmap = remember { Bitmap.createBitmap(48, 48, Bitmap.Config.ARGB_8888) }
    val pixels = remember { IntArray(48 * 48) }
    var frame by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            for (i in pixels.indices) {
                val v = (Math.random() * 255).toInt()
                pixels[i] = (0xFF shl 24) or (v shl 16) or (v shl 8) or v
            }
            bitmap.setPixels(pixels, 0, 48, 0, 0, 48, 48)
            frame++
            delay(80)
        }
    }
    Box(modifier.background(Color.Black)) {
        // read the frame so each new one is drawn
        val image = remember(frame) { bitmap.asImageBitmap() }
        Image(image, null, Modifier.fillMaxSize().alpha(opacity), contentScale = ContentScale.FillBounds, filterQuality = FilterQuality.None)
    }
}
