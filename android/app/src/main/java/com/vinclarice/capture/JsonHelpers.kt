package com.vinclarice.capture

import okhttp3.MediaType.Companion.toMediaType
import org.json.JSONArray
import org.json.JSONObject

/**
 * Small org.json/OkHttp conveniences shared by every *Api.kt's manual
 * parsing -- split out once DailyApi.kt's own private copies would
 * otherwise have been duplicated verbatim into AgendaApi.kt.
 */

/** Every *Api.kt's request body content type -- one definition rather than
 *  a `private val JSON` re-declared per file. */
val JSON = "application/json; charset=utf-8".toMediaType()

fun <T> JSONArray.map(transform: (JSONObject) -> T): List<T> =
    (0 until length()).map { transform(getJSONObject(it)) }

/** A JSON integer that may be null -- org.json has no built-in for this. */
fun JSONObject.optIntOrNull(name: String): Int? =
    if (isNull(name) || !has(name)) null else getInt(name)

fun JSONObject.optStringOrNull(name: String): String? =
    if (isNull(name) || !has(name)) null else getString(name)
