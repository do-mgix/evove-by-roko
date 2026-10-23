package com.evove.app

import android.content.Context
import android.content.SharedPreferences
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

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

    /** Signs out the account in use: it leaves the device's list too, since
     *  its token is no good any more. */
    fun clearSession() {
        val name = username
        prefs.edit().remove("evove_token").remove("evove_username").apply()
        if (name != null) accounts = accounts.filter { it.username != name }
    }

    // ------------------------------------------------------------ accounts

    /** An account kept on the device, signed in: switching to it needs no password. */
    @Serializable
    data class Account(val username: String, val token: String, val test: Boolean = false)

    private val json = Json { ignoreUnknownKeys = true }

    var accounts: List<Account>
        get() = runCatching { json.decodeFromString(ListSerializer(Account.serializer()), prefs.getString("evove_accounts", null) ?: "[]") }
            .getOrDefault(emptyList())
            .ifEmpty { listOfNotNull(token?.let { t -> username?.let { Account(it, t) } }) }
        set(v) = prefs.edit().putString("evove_accounts", json.encodeToString(ListSerializer(Account.serializer()), v)).apply()

    /** Keeps the session as the account in use, first in the list. */
    fun remember(name: String, token: String, test: Boolean = false) {
        val was = accounts.find { it.username == name }
        accounts = listOf(Account(name, token, test || was?.test == true)) + accounts.filter { it.username != name }
    }

    /** Makes a kept account the one in use. */
    fun use(a: Account) {
        prefs.edit().putString("evove_token", a.token).putString("evove_username", a.username).apply()
    }

    /** Takes an account off the device; the one in use stays in use unless it is it. */
    fun forget(name: String) {
        accounts = accounts.filter { it.username != name }
        if (username == name) prefs.edit().remove("evove_token").remove("evove_username").apply()
    }

    fun string(key: String): String? = prefs.getString(key, null)
    fun putString(key: String, value: String) = prefs.edit().putString(key, value).apply()
    fun int(key: String, default: Int = 0): Int = prefs.getInt(key, default)
    fun putInt(key: String, value: Int) = prefs.edit().putInt(key, value).apply()
    fun has(key: String): Boolean = prefs.contains(key)
}
