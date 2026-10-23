package com.evove.app

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.evove.app.sound.Sfx

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // drawn under black bars, light icons on them; the frame keeps clear of
        // the bars and of the keyboard through the window insets
        enableEdgeToEdge(SystemBarStyle.dark(Color.BLACK), SystemBarStyle.dark(Color.BLACK))
        super.onCreate(savedInstanceState)
        // the volume keys move the stream the sounds play on
        volumeControlStream = android.media.AudioManager.STREAM_MUSIC
        Prefs.init(applicationContext)
        Sfx.init(applicationContext)
        setContent { App() }
    }

    // back from the background: the server decides whether it is a new session
    override fun onRestart() {
        super.onRestart()
        if (Prefs.token != null) Evove.visit(cold = false)
    }
}
