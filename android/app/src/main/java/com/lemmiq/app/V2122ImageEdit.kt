package com.lemmiq.app

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.gson.Gson
import com.google.gson.JsonObject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.UUID
import java.util.concurrent.TimeUnit

/** V2.12.2: Edit a posted image privately; original chat attachment is never modified. */
private class QImageEditServiceV2122(private val store: SessionStore) {
    private val base = BuildConfig.API_BASE_URL.trimEnd('/')
    private val gson = Gson()
    private val json = "application/json; charset=utf-8".toMediaType()
    private val http = OkHttpClient.Builder().connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(175, TimeUnit.SECONDS).callTimeout(195, TimeUnit.SECONDS).build()

    private suspend fun request(path: String, payload: Map<String, Any>? = null): String =
        withContext(Dispatchers.IO) {
            val token = store.token ?: error("Sign in again")
            val r = Request.Builder().url(base + path).header("Authorization", "Bearer $token")
            if (payload != null) r.post(gson.toJson(payload).toRequestBody(json)) else r.get()
            http.newCall(r.build()).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    val reason = runCatching { gson.fromJson(body, JsonObject::class.java)
                        ?.get("detail")?.asString }.getOrNull()
                    error(reason ?: "HTTP ${response.code}: ${body.take(100)}")
                }
                body
            }
        }

    suspend fun config(): JsonObject =
        gson.fromJson(request("/v2122/image-edits/config"), JsonObject::class.java)

    suspend fun edit(kind: String, mid: Int, prompt: String, size: String): Int {
        val payload: Map<String, Any> = mapOf("source_kind" to kind,
            "source_message_id" to mid, "prompt" to prompt, "size" to size,
            "request_id" to UUID.randomUUID().toString())
        val result = gson.fromJson(request("/v2122/image-edits/edit", payload), JsonObject::class.java)
        return result.get("id").asInt
    }

    suspend fun send(imageId: Int, chatId: Int?, groupId: Int?) {
        val payload: Map<String, Any> = if (chatId != null) mapOf("chat_id" to chatId)
            else if (groupId != null) mapOf("group_id" to groupId)
            else error("Chat or group required")
        request("/v212/images/$imageId/send", payload)
    }

    suspend fun photo(path: String): Bitmap = withContext(Dispatchers.IO) {
        val token = store.token ?: error("Sign in again")
        val request = Request.Builder().url(base + path)
            .header("Authorization", "Bearer $token").get().build()
        http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("Photo is unavailable (HTTP ${response.code})")
            val bytes = response.body?.bytes() ?: error("No photo data")
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            var sample = 1
            while (bounds.outWidth / sample > 1600 || bounds.outHeight / sample > 1600) sample *= 2
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size,
                BitmapFactory.Options().apply { inSampleSize = sample }) ?: error("Cannot decode photo")
        }
    }
}

@Composable
fun V2122ImageEditDialog(
    sourceKind: String,
    sourceMessageId: Int,
    chatId: Int? = null,
    groupId: Int? = null,
    onClose: () -> Unit,
    onSent: () -> Unit = {}
) {
    val ctx = LocalContext.current
    val store = remember(ctx) { SessionStore(ctx) }
    val api = remember(store) { QImageEditServiceV2122(store) }
    val scope = rememberCoroutineScope()
    var prompt by remember(sourceMessageId) { mutableStateOf("") }
    var size by remember(sourceMessageId) { mutableStateOf("1024x1024") }
    var busy by remember { mutableStateOf(false) }
    var enabled by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("Checking image-edit availability…") }
    var sourcePreview by remember(sourceMessageId) { mutableStateOf<Bitmap?>(null) }
    var editPreview by remember { mutableStateOf<Bitmap?>(null) }
    var draftId by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(sourceKind, sourceMessageId) {
        val path = if (sourceKind == "group") "/v24/group-media/$sourceMessageId"
            else "/media/$sourceMessageId"
        try { sourcePreview = api.photo(path) } catch (e: Exception) {
            status = e.message ?: "Original photo preview unavailable"
        }
        try {
            val cfg = api.config()
            enabled = cfg.get("enabled")?.asBoolean == true && cfg.get("configured")?.asBoolean == true
            status = if (enabled) "Edit price: ${cfg.get("q_price")?.asDouble ?: 0.0} Q; " +
                (if (cfg.get("charging_enabled")?.asBoolean == true) "charging enabled" else "charging disabled")
                else "Image editing is disabled or not configured by the server admin"
        } catch (e: Exception) { status = e.message ?: "Could not load image editing settings" }
    }

    AlertDialog(
        onDismissRequest = { if (!busy) onClose() },
        title = { Text("✨ Edit with Q") },
        text = {
            Column(Modifier.heightIn(max = 530.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text("Edit this chat photo privately. The original always remains unchanged.", fontSize = 12.sp)
                sourcePreview?.let { bitmap ->
                    Text("Original photo", fontSize = 11.sp)
                    Image(bitmap.asImageBitmap(), contentDescription = "Original posted photo",
                        modifier = Modifier.fillMaxWidth().heightIn(max = 155.dp),
                        contentScale = ContentScale.Fit)
                }
                OutlinedTextField(value = prompt, onValueChange = { prompt = it.take(1500) },
                    modifier = Modifier.fillMaxWidth(), label = { Text("Describe the changes") },
                    placeholder = { Text("Replace the background; keep the person unchanged") },
                    minLines = 2, maxLines = 5)
                Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    listOf("1024x1024" to "Square", "1536x1024" to "Wide", "1024x1536" to "Tall")
                        .forEach { (value, label) ->
                            FilterChip(selected = size == value, onClick = { size = value },
                                label = { Text(label, fontSize = 10.sp) })
                        }
                }
                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                Text(status, fontSize = 12.sp)
                editPreview?.let { bitmap ->
                    Text("Edited image preview", fontSize = 11.sp)
                    Image(bitmap.asImageBitmap(), contentDescription = "Private edited image preview",
                        modifier = Modifier.fillMaxWidth().heightIn(max = 245.dp),
                        contentScale = ContentScale.Fit)
                }
                if (draftId != null) {
                    Button(onClick = {
                        val id = draftId ?: return@Button
                        scope.launch {
                            busy = true
                            try { api.send(id, chatId, groupId); onSent(); onClose() }
                            catch (e: Exception) { status = e.message ?: "Send failed" }
                            finally { busy = false }
                        }
                    }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                        Text("Send edited photo to this chat")
                    }
                }
                Text("This photo is processed by an AI provider; get permission before editing others' photos. No image is sent to a chat automatically. Failed edits refund eligible Q charges.",
                    fontSize = 10.sp)
            }
        },
        confirmButton = {
            Button(onClick = {
                if (prompt.trim().length < 5) {
                    status = "Please describe the edit in at least 5 characters"
                    return@Button
                }
                scope.launch {
                    busy = true; draftId = null; editPreview = null
                    status = "Q is editing the photo…"
                    try {
                        val id = api.edit(sourceKind, sourceMessageId, prompt.trim(), size)
                        val reviewedImage = api.photo("/v212/images/$id/file")
                        editPreview = reviewedImage
                        draftId = id
                        status = "Your private edit is ready. Review it before sending."
                    } catch (e: Exception) { status = e.message ?: "Editing failed" }
                    finally { busy = false }
                }
            }, enabled = enabled && !busy) {
                Text(if (draftId == null) "Generate edit" else "Edit again")
            }
        },
        dismissButton = { TextButton(onClick = onClose, enabled = !busy) { Text("Close") } }
    )
}
