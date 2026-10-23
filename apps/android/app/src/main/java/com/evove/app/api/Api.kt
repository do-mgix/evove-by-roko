package com.evove.app.api

import com.evove.app.BuildConfig
import com.evove.app.Prefs
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNamingStrategy
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.time.LocalTime

/** A failed call, with the server's `detail` when it gave one. */
class ApiException(message: String, val status: Int = 0) : Exception(message)

/** The evove API: the same backend and the same calls as the web client. */
object Api {
    val BASE: String = BuildConfig.API_BASE

    @OptIn(ExperimentalSerializationApi::class)
    val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false
        namingStrategy = JsonNamingStrategy.SnakeCase
    }

    /** Called when the server rejects the session, so the app can go back to
     *  the login instead of every screen failing on its own. */
    var onUnauthorized: (() -> Unit)? = null

    private class Reply(val status: Int, val body: String)

    /** Answers in place of the server, for rendering the screens in tests. */
    var fake: ((method: String, path: String) -> String)? = null

    private suspend fun send(method: String, path: String, body: JsonElement? = null, auth: Boolean = true, token: String? = null): Reply =
        fake?.let { Reply(200, it(method, path)) } ?: withContext(Dispatchers.IO) {
            val conn = (URL(BASE + path).openConnection() as HttpURLConnection).apply {
                requestMethod = method
                connectTimeout = 15_000
                readTimeout = 20_000
                setRequestProperty("Accept", "application/json")
                if (auth) (token ?: Prefs.token)?.let { setRequestProperty("Authorization", "Bearer $it") }
            }
            try {
                if (body != null) {
                    conn.doOutput = true
                    conn.setRequestProperty("Content-Type", "application/json")
                    conn.outputStream.use { it.write(body.toString().toByteArray()) }
                }
                val status = conn.responseCode
                val stream = if (status in 200..299) conn.inputStream else conn.errorStream
                val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
                Reply(status, text)
            } catch (e: IOException) {
                throw ApiException("sem conexão")
            } finally {
                conn.disconnect()
            }
        }

    private fun detail(text: String): String? = try {
        (json.parseToJsonElement(text) as? JsonObject)?.get("detail")?.let { d ->
            (d as? JsonPrimitive)?.contentOrNull ?: d.toString()
        }
    } catch (_: Exception) {
        null
    }

    /** A JSON call that throws the server's `detail` when it fails. */
    private suspend fun raw(method: String, path: String, body: JsonElement? = null, auth: Boolean = true): String {
        val r = send(method, path, body, auth)
        if (r.status == 401 && auth) {
            Prefs.clearSession()
            onUnauthorized?.invoke()
        }
        if (r.status !in 200..299) throw ApiException(detail(r.body) ?: "falhou (${r.status})", r.status)
        return r.body
    }

    private suspend inline fun <reified T> call(method: String, path: String, body: JsonElement? = null, auth: Boolean = true): T =
        json.decodeFromString(raw(method, path, body, auth))

    private suspend inline fun <reified T> get(path: String): T = call("GET", path)
    private suspend inline fun <reified T> post(path: String, body: JsonElement? = null): T = call("POST", path, body ?: JsonObject(emptyMap()))
    private suspend inline fun <reified T> patch(path: String, body: JsonElement): T = call("PATCH", path, body)
    private suspend inline fun <reified T> put(path: String, body: JsonElement): T = call("PUT", path, body)
    private suspend inline fun <reified T> delete(path: String, body: JsonElement? = null): T = call("DELETE", path, body)

    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8").replace("+", "%20")

    private fun obj(vararg pairs: Pair<String, Any?>): JsonObject = JsonObject(pairs.associate { (k, v) -> k to element(v) })

    private fun element(v: Any?): JsonElement = when (v) {
        null -> JsonNull
        is JsonElement -> v
        is String -> JsonPrimitive(v)
        is Number -> JsonPrimitive(v)
        is Boolean -> JsonPrimitive(v)
        is List<*> -> JsonArray(v.map { element(it) })
        else -> JsonPrimitive(v.toString())
    }

    // ------------------------------------------------------------ auth

    private suspend fun authCall(path: String, username: String, password: String, email: String?): Session {
        val s: Session = call("POST", path, obj("username" to username, "password" to password, "email" to email), auth = false)
        Prefs.token = s.token
        Prefs.username = s.username
        Prefs.remember(s.username, s.token)
        return s
    }

    suspend fun login(username: String, password: String) = authCall("/auth/login", username, password, null)

    /** A throwaway account for trying the evove from its first step: a random
     *  name and password, kept only on this device. */
    suspend fun registerTest(): Session {
        val rng = java.security.SecureRandom()
        val letters = "abcdefghjkmnpqrstuvwxyz"
        val name = "t" + (1..6).map { letters[rng.nextInt(letters.length)] }.joinToString("")
        val password = (1..16).map { (letters + "23456789")[rng.nextInt(letters.length + 8)] }.joinToString("")
        val s = register(name, password, null)
        Prefs.remember(s.username, s.token, test = true, password = password)
        return s
    }
    suspend fun register(username: String, password: String, email: String?) = authCall("/auth/register", username, password, email)

    /** The server answers the same whether or not the profile exists. */
    suspend fun forgotPassword(login: String) {
        raw("POST", "/auth/forgot", obj("login" to login), auth = false)
    }

    suspend fun setRecoveryEmail(email: String, password: String): String? {
        val r = send("PATCH", "/auth/me", obj("email" to email, "password" to password))
        when (r.status) {
            401 -> { Prefs.clearSession(); onUnauthorized?.invoke() }
            403 -> throw ApiException("senha incorreta")
            409 -> throw ApiException("e-mail já usado por outra conta")
            400 -> throw ApiException("e-mail inválido")
        }
        if (r.status !in 200..299) throw ApiException(detail(r.body) ?: "falhou (${r.status})")
        return json.decodeFromString<EmailAnswer>(r.body).email
    }

    suspend fun logout() {
        try { raw("POST", "/auth/logout", JsonObject(emptyMap())) } catch (_: Exception) {} finally { Prefs.clearSession() }
    }

    /** Revokes every session of the profile, on every device. */
    suspend fun logoutEverywhere() {
        try { raw("POST", "/auth/logout-all", JsonObject(emptyMap())) } catch (_: Exception) {} finally { Prefs.clearSession() }
    }

    /** Deletes the profile; a wrong password throws without touching the session. */
    suspend fun deleteAccount(password: String) {
        val r = send("DELETE", "/auth/me", obj("password" to password))
        if (r.status == 403) throw ApiException("senha incorreta")
        if (r.status !in 200..299) throw ApiException("falhou (${r.status})")
        Prefs.clearSession()
        onUnauthorized?.invoke()
    }

    suspend fun sessionInfo(): SessionInfo = get("/auth/me")

    /** Starts a kept account over from nothing — `token` is its session —
     *  and keeps the new session the server answers with in its place. */
    suspend fun resetAccount(token: String, password: String): Session {
        val r = send("POST", "/auth/me/reset", obj("password" to password), token = token)
        if (r.status == 403) throw ApiException("senha incorreta")
        if (r.status !in 200..299) throw ApiException(detail(r.body) ?: "falhou (${r.status})", r.status)
        val s: Session = json.decodeFromString(r.body)
        Prefs.replace(s.username, s.token)
        return s
    }

    /** Deletes a kept account for good, by its session, and takes it off the device. */
    suspend fun deleteAccountOf(a: Prefs.Account, password: String) {
        val r = send("DELETE", "/auth/me", obj("password" to password), token = a.token)
        if (r.status == 403) throw ApiException("senha incorreta")
        if (r.status !in 200..299 && r.status != 401) throw ApiException(detail(r.body) ?: "falhou (${r.status})", r.status)
        Prefs.forget(a.username)
    }

    // ------------------------------------------------------------ acting

    suspend fun actions(): List<Action> = get("/actions")
    suspend fun act(id: String, option: Int, period: String): ActResult =
        post("/actions/$id/act", obj("option" to option, "period" to period))
    suspend fun actionWindow(id: String): ActionWindow = get("/actions/$id/window")
    suspend fun user(): UserState = get("/user")

    // ------------------------------------------------------------ attributes

    suspend fun attributes(): List<AttrNode> = get("/attributes")
    suspend fun attributeTree(): AttributeTree = get("/attributes/tree")
    suspend fun recentAttributes(limit: Int = 10): List<AttrNode> = get("/attributes/recent?limit=$limit")
    suspend fun attributeUsage(days: Int = 30, limit: Int = 12): List<AttrNode> = get("/attributes/usage?days=$days&limit=$limit")
    suspend fun claimRank(key: String): ClaimResult = post("/attributes/${enc(key)}/claim")

    suspend fun userAttributes(): List<UserAttribute> = get("/user-attributes")
    suspend fun createUserAttribute(name: String, parentId: Int?): NamedId =
        post("/user-attributes", obj("name" to name, "parent_id" to parentId))
    suspend fun createUserAttributePath(path: List<String>): NamedId = post("/user-attributes", obj("path" to path))
    suspend fun updateUserAttribute(id: Int, name: String? = null, parentId: Int? = null, moveToRoot: Boolean = false): JsonObject {
        val body = buildJsonObject {
            if (name != null) put("name", name)
            if (parentId != null) put("parent_id", parentId) else if (moveToRoot) put("parent_id", JsonNull)
        }
        return patch("/user-attributes/$id", body)
    }

    /** `newAttributes` holds names, or whole suggestion paths. */
    suspend fun createPatch(baseActionId: String, name: String, attributeIds: List<Int>, newNames: List<String>, newPaths: List<List<String>>): CreatedPatch {
        val body = buildJsonObject {
            put("base_action_id", baseActionId)
            put("name", name)
            putJsonArray("attribute_ids") { attributeIds.forEach { add(JsonPrimitive(it)) } }
            putJsonArray("new_attributes") {
                newNames.forEach { add(JsonPrimitive(it)) }
                newPaths.forEach { p -> add(JsonObject(mapOf("path" to JsonArray(p.map { JsonPrimitive(it) })))) }
            }
        }
        return post("/patches", body)
    }
    suspend fun updatePatch(id: String, name: String? = null, attributeIds: List<Int>? = null): JsonObject =
        patch("/patches/$id", buildJsonObject {
            if (name != null) put("name", name)
            if (attributeIds != null) putJsonArray("attribute_ids") { attributeIds.forEach { add(JsonPrimitive(it)) } }
        })
    suspend fun setPatchWeight(patchId: String, attributeId: Int, weight: Double): JsonObject =
        put("/patches/$patchId/attributes/$attributeId", obj("weight" to weight))
    suspend fun unlinkPatchAttribute(patchId: String, attributeId: Int): Ok = delete("/patches/$patchId/attributes/$attributeId")

    private var suggestions: List<SuggestionCatalog>? = null

    /** The catalog is static and the same for everyone: fetched once. */
    suspend fun attributeSuggestions(): List<SuggestionCatalog> =
        suggestions ?: get<SuggestionCatalogs>("/attribute-suggestions").catalogs.also { suggestions = it }

    // ------------------------------------------------------------ logs and calendar

    suspend fun logs(offset: Int = 0): LogsResponse = get("/logs?offset=$offset")
    suspend fun deleteLog(id: Int): DeletedLog = delete("/logs/$id")
    suspend fun updateLogNote(id: Int, note: String): LogEntry = patch("/logs/$id", obj("note" to note))
    suspend fun setLogPeriod(id: Int, period: String): LogEntry = patch("/logs/$id", obj("period" to period))
    suspend fun shiftLogDay(id: Int, delta: Int): LogEntry = patch("/logs/$id", obj("day_delta" to delta))
    suspend fun reorderLogs(day: Int, ids: List<Int>): JsonObject = post("/logs/reorder", obj("day" to day, "ids" to ids))

    suspend fun calendar(year: Int, month: Int): CalendarMonth = get("/calendar?year=$year&month=$month")
    suspend fun logsByDate(iso: String): LogsByDate = get("/logs/by-date?date=$iso")
    suspend fun createEvent(date: String, label: String, actionId: String?): AgendaItem = post(
        "/agenda",
        obj("start" to "", "end" to null, "day" to "*", "date" to date, "label" to label,
            "label_kind" to (if (actionId != null) "action" else "text"), "label_id" to actionId),
    )

    // ------------------------------------------------------------ agenda

    suspend fun agendaDay(offset: Int = 0): AgendaDay = get("/agenda/day?offset=$offset")
    suspend fun setThought(date: String, content: String, logId: Int?): Said =
        put("/thoughts", obj("date" to date, "content" to content, "log_id" to logId))
    suspend fun journal(date: String): Journal = get("/journal?date=$date")

    suspend fun todos(): List<Todo> = get<Items<Todo>>("/todos").items
    suspend fun createTodo(title: String, actionIds: List<String>, deadline: String?, projectId: String?): Said =
        post("/todos", obj("title" to title, "action_ids" to actionIds, "deadline" to deadline, "project_id" to projectId))
    suspend fun completeTodo(id: Int): Todo = post("/todos/$id/done")
    suspend fun deleteTodo(id: Int): Ok = delete("/todos/$id")

    suspend fun projects(): List<Project> = get<Items<Project>>("/projects").items
    suspend fun createProject(name: String, deadline: String?): Said = post("/projects", obj("name" to name, "deadline" to deadline))
    suspend fun setProjectActive(id: String, active: Boolean): Project = patch("/projects/$id", obj("active" to active))
    suspend fun endProject(id: String): Project = post("/projects/$id/end")
    suspend fun deleteProject(id: String): Ok = delete("/projects/$id")
    suspend fun emblems(): List<Project> = get("/emblems")

    // ------------------------------------------------------------ journey

    suspend fun journey(): JourneyState = get("/journey")
    suspend fun recover(kind: String): RecoverResult = post("/journey/recover", obj("kind" to kind))
    suspend fun boss(): BossState = get("/journey/boss")
    suspend fun fight(): FightResult = post("/journey/boss/fight")
    suspend fun journeyStats(): JourneyStats = get("/journey/stats")
    suspend fun equipment(): Equipment = get("/journey/equipment")
    suspend fun buyEquipment(id: String): Equipment = post("/journey/equipment/$id/buy")
    suspend fun wearEquipment(id: String, on: Boolean): Equipment = post("/journey/equipment/$id/wear", obj("on" to on))

    // ------------------------------------------------------------ shop

    suspend fun shop(): ShopState = get("/shop")
    suspend fun shopCatalog(): List<ShopGroup> = get("/shop/catalog")
    suspend fun discover(): ShopState = post("/shop/discover")
    suspend fun buy(attribute: String, name: String): Bought = post("/shop/actions/buy", obj("attribute" to attribute, "name" to name))

    // ------------------------------------------------------------ entities and allies

    suspend fun entities(): List<Entity> = get("/entities")
    suspend fun talkTo(id: String): EntityTalk = get("/entities/$id/talk")
    suspend fun allies(): Allies = get("/allies")
    suspend fun addAlly(passcode: String): Ally = post("/allies", obj("passcode" to passcode))
    suspend fun removeAlly(nickname: String): Ok = delete("/allies/${enc(nickname)}")
    suspend fun rerollNickname(): Nickname = post("/me/nickname")

    // ------------------------------------------------------------ the engine

    suspend fun engine(): EngineView = get("/engine")
    suspend fun visit(cold: Boolean, turns: Int): EngineView = post("/engine/visit", obj("cold" to cold, "turns" to turns))
    suspend fun engineEvents(events: List<JsonObject>): EngineView = post("/engine/events", obj("events" to JsonArray(events)))
    suspend fun passcode(code: String): EngineView = post("/engine/passcode", obj("code" to code))

    /** Ends a session that is not the one in use: an account kept on the device
     *  and taken off it. */
    suspend fun logoutToken(token: String, everywhere: Boolean = false) {
        withContext(Dispatchers.IO) {
            runCatching {
                val conn = (URL(BASE + if (everywhere) "/auth/logout-all" else "/auth/logout").openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 10_000
                    readTimeout = 10_000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Authorization", "Bearer $token")
                }
                conn.outputStream.use { it.write("{}".toByteArray()) }
                conn.responseCode
                conn.disconnect()
            }
        }
    }
}

/** The part of the day a log is filed under: mo 5–12h, ev 12–18h, ni the rest. */
fun currentPeriod(): String {
    val h = LocalTime.now().hour
    return if (h in 5..11) "mo" else if (h in 12..17) "ev" else "ni"
}

val PERIODS = listOf("mo", "ev", "ni")

/** Case and accents dropped, as the database's collation drops them. */
fun fold(s: String): String =
    java.text.Normalizer.normalize(s, java.text.Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"), "").lowercase()

/** "5010108" -> "5 01 01 08": action · parent class · child class · position. */
fun formatCode(code: String?): String {
    val s = code ?: ""
    if (!Regex("^5\\d{0,8}$").matches(s)) return s
    val parts = listOf(s.take(1), s.drop(1).take(2), s.drop(3).take(2), s.drop(5).take(2)).filter { it.isNotEmpty() }
    val head = parts.joinToString(" ")
    return if (s.length > 7) "$head · ${s.substring(7, minOf(9, s.length))}" else head
}

/** A stat of an entity, as text. */
fun JsonElement.text(): String = (this as? JsonPrimitive)?.contentOrNull ?: toString()
