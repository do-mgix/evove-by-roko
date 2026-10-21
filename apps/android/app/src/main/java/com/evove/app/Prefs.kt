package com.evove.app

import android.content.Context
import android.content.SharedPreferences

/** What the app keeps on the device: the session, and the small counts that
 *  make the interface change with use. The keys are the ones the web client
 *  kept in localStorage, so the names read the same on both sides. */
object Prefs {
    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        prefs = context.getSharedPreferences("evove", Context.MODE_PRIVATE)
    }

    var token: String?
        get() = prefs.getString("evove_token", null)
        set(v) = prefs.edit().putString("evove_token", v).apply()

    var username: String?
        get() = prefs.getString("evove_username", null)
        set(v) = prefs.edit().putString("evove_username", v).apply()

    fun clearSession() {
        prefs.edit().remove("evove_token").remove("evove_username").apply()
    }

    fun string(key: String): String? = prefs.getString(key, null)
    fun putString(key: String, value: String) = prefs.edit().putString(key, value).apply()
    fun int(key: String, default: Int = 0): Int = prefs.getInt(key, default)
    fun putInt(key: String, value: Int) = prefs.edit().putInt(key, value).apply()
    fun has(key: String): Boolean = prefs.contains(key)
}
