package com.lemmiq.app

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
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

/** V2.12 optional UI: private prompt -> generate -> preview -> user-selected send. */
private class QImageApiV212(private val session: SessionStore) {
    private val gson = Gson()
    private val json = "application/json; charset=utf-8".toMediaType()
    private val base = BuildConfig.API_BASE_URL.trimEnd('/')
    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(165, TimeUnit.SECONDS)
        .callTimeout(185, TimeUnit.SECONDS)
        .build()

    private suspend fun request(path: String, payload: Map<String, Any>? = null): String = withContext(Dispatchers.IO) {
        val builder = Request.Builder().url(base + path)
        val token = session.token ?: error("Please sign in again")
        builder.header("Authorization", "Bearer $token")
        if (payload == null) builder.get()
        else builder.post(gson.toJson(payload).toRequestBody(json))
        client.newCall(builder.build()).execute().use { result ->
            val body = result.body?.string().orEmpty()
            if (!result.isSuccessful) {
                val detail = runCatching { gson.fromJson(body, JsonObject::class.java)
                    ?.get("detail")?.asString }.getOrNull()
                throw IllegalStateException(detail ?: "HTTP ${result.code}: ${body.take(80)}")
            }
            body
        }
    }

    suspend fun config(): JsonObject = gson.fromJson(request("/v212/images/config"), JsonObject::class.java)

    suspend fun generate(prompt: String, size: String): Int {
        val json = gson.fromJson(request("/v212/images/generate", mapOf(
            "prompt" to prompt, "size" to size, "request_id" to UUID.randomUUID().toString()
        )), JsonObject::class.java)
        return json.get("id").asInt
    }

    suspend fun bitmap(id: Int): android.graphics.Bitmap = withContext(Dispatchers.IO) {
        val token = session.token ?: error("Please sign in again")
        client.newCall(Request.Builder().url("$base/v212/images/$id/file")
            .header("Authorization", "Bearer $token").get().build()).execute().use { result ->
            if (!result.isSuccessful) error("Image preview unavailable (${result.code})")
            val bytes = result.body?.bytes() ?: error("Empty preview")
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: error("Cannot decode preview")
        }
    }

    suspend fun send(id: Int, kind: String, targetId: Int) {
        request("/v212/images/$id/send", mapOf(kind to targetId))
    }
}

@Composable
fun V212ImageDialog(
    chatId: Int? = null,
    groupId: Int? = null,
    onClose: () -> Unit,
    onSent: () -> Unit = {}
) {
    val ctx = LocalContext.current
    val store = remember(ctx) { SessionStore(ctx) }
    val service = remember(store) { QImageApiV212(store) }
    val chatApi = remember(store) { Api(store) }
    val scope = rememberCoroutineScope()
    var prompt by remember { mutableStateOf("") }
    var size by remember { mutableStateOf("1024x1024") }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("Loading configuration…") }
    var enabled by remember { mutableStateOf(false) }
    var imageId by remember { mutableStateOf<Int?>(null) }
    var preview by remember { mutableStateOf<android.graphics.Bitmap?>(null) }
    var targets by remember { mutableStateOf<List<Triple<String, Int, String>>>(emptyList()) }
    var chooseDestination by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        runCatching { service.config() }.onSuccess { cfg ->
            enabled = cfg.get("enabled")?.asBoolean == true && cfg.get("configured")?.asBoolean == true
            val cost = cfg.get("q_price")?.asDouble ?: 0.0
            message = if (enabled) "Q image price: $cost Q when feature charging is enabled" else "Image generation is not enabled by the server admin"
        }.onFailure { message = it.message ?: "Could not load feature settings" }
    }

    if (chooseDestination) {
        AlertDialog(
            onDismissRequest = { chooseDestination = false },
            title = { Text("Send generated image") },
            text = {
                Column(Modifier.heightIn(max = 340.dp).verticalScroll(rememberScrollState())) {
                    targets.forEach { (kind, id, label) ->
                        TextButton(onClick = {
                            chooseDestination = false
                            val current = imageId ?: return@TextButton
                            scope.launch {
                                busy = true
                                try { service.send(current, kind, id); onSent(); onClose() }
                                catch (e: Exception) { message = e.message ?: "Cannot send image" }
                                finally { busy = false }
                            }
                        }) { Text(label) }
                    }
                }
            },
            confirmButton = { TextButton({ chooseDestination = false }) { Text("Cancel") } }
        )
    }

    AlertDialog(
        onDismissRequest = { if (!busy) onClose() },
        title = { Text("✨ Create with Q") },
        text = {
            Column(Modifier.heightIn(max = 510.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Describe your image, generate it privately, preview, then send.",fontSize=12.sp)
                OutlinedTextField(value = prompt, onValueChange = { prompt = it.take(1500) },
                    modifier = Modifier.fillMaxWidth(), label={Text("Describe the image")},minLines=2,maxLines=4)
                Row(horizontalArrangement=Arrangement.spacedBy(6.dp)) {
                    listOf("1024x1024" to "Square", "1536x1024" to "Wide", "1024x1536" to "Tall").forEach { (v, title) ->
                        FilterChip(selected=size==v,onClick={size=v},label={Text(title,fontSize=10.sp)})
                    }
                }
                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                Text(message,fontSize=12.sp)
                preview?.let { bitmap ->
                    Image(bitmap=bitmap.asImageBitmap(),contentDescription="Generated image preview",
                        modifier=Modifier.fillMaxWidth().heightIn(max=300.dp),contentScale=ContentScale.Fit)
                }
                if(imageId!=null) {
                    Button(onClick={
                        val current=imageId ?: return@Button
                        if (chatId != null || groupId != null) {
                            scope.launch {
                                busy=true
                                try { service.send(current,if(chatId!=null) "chat_id" else "group_id",chatId ?: groupId!!)
                                    onSent(); onClose() }
                                catch(e:Exception){ message=e.message?:"Send failed" }
                                finally{busy=false}
                            }
                        } else {
                            scope.launch {
                                busy=true
                                try {
                                    targets = chatApi.chats().map { Triple("chat_id", it.id, it.other_user.display_name) } +
                                        chatApi.groups().map { Triple("group_id", it.id, "Group: ${it.name}") }
                                    if(targets.isEmpty())message="Start a chat or join a group before sharing"
                                    else chooseDestination=true
                                } catch(e:Exception){ message=e.message?:"Unable to load chats" }
                                finally{busy=false}
                            }
                        }
                    },enabled=!busy,modifier=Modifier.fillMaxWidth()){Text("Send to chat")}
                }
                Text("No image is sent automatically. Failed image creation should refund any charged Q.",fontSize=10.sp)
            }
        },
        confirmButton = {
            Button(onClick={
                if(prompt.trim().length<5){message="Describe the image in at least 5 characters";return@Button}
                scope.launch {
                    busy=true;preview=null;imageId=null;message="Q is creating your image…"
                    try {
                        val id=service.generate(prompt.trim(),size)
                        imageId=id;preview=service.bitmap(id)
                        message="Image ready. Review before sending."
                    }catch(e:Exception){message=e.message?:"Generation failed"}
                    finally {busy=false}
                }
            },enabled=enabled && !busy){Text(if(imageId==null)"Generate" else "Regenerate")}
        },
        dismissButton = { TextButton(onClick=onClose,enabled=!busy){Text("Close")} }
    )
}
