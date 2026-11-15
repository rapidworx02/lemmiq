package com.lemmiq.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
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
import java.io.IOException
import java.util.concurrent.TimeUnit

/** V2.13.2 — optional recovery for a server-side call record left in progress. */
data class CallRecoveryItemV2132(
    val id: String = "",
    val status: String = "",
    val call_type: String = "VOICE",
    val peer_display_name: String = "",
    val started_at: String = ""
)

data class CallRecoverySnapshotV2132(
    val active_count: Int = 0,
    val active: List<CallRecoveryItemV2132> = emptyList(),
    val resolved_count: Int = 0
)

class CallRecoveryApiV2132(private val store: SessionStore) {
    private val gson = Gson()
    private val json = "application/json; charset=utf-8".toMediaType()
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(25, TimeUnit.SECONDS)
        .build()
    private val base = BuildConfig.API_BASE_URL.trimEnd('/')

    private suspend fun request(path: String, post: Boolean = false, body: String = "{}"): String =
        withContext(Dispatchers.IO) {
            val token = store.token ?: throw IOException("Sign in again")
            val rb = Request.Builder().url("$base$path")
                .header("Authorization", "Bearer $token")
                .header("Cache-Control", "no-store")
            if (post) rb.post(body.toRequestBody(json)) else rb.get()
            client.newCall(rb.build()).execute().use { response ->
                val contents = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    val detail = runCatching {
                        gson.fromJson(contents, JsonObject::class.java)
                            ?.get("detail")?.asString
                    }.getOrNull()
                    throw IOException(detail ?: "Call recovery unavailable (HTTP ${response.code}). Deploy the V2.13.2 backend.")
                }
                contents
            }
        }

    suspend fun check(): CallRecoverySnapshotV2132 = gson.fromJson(
        request("/v2132/calls/reconcile", post = true), CallRecoverySnapshotV2132::class.java
    )

    suspend fun reset(): Int {
        val payload = gson.fromJson(
            request("/v2132/calls/reset", post = true, body = "{\"confirm\":true}"),
            JsonObject::class.java
        )
        return payload.get("ended_count")?.asInt ?: 0
    }
}

@Composable
fun V2132CallRecoveryPanel(vm: LemmiqViewModel) {
    val client = remember(vm.store) { CallRecoveryApiV2132(vm.store) }
    val scope = rememberCoroutineScope()
    var pending by remember { mutableStateOf(false) }
    var confirm by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<CallRecoverySnapshotV2132?>(null) }
    var notice by remember { mutableStateOf("") }
    var failure by remember { mutableStateOf("") }

    fun refresh() {
        scope.launch {
            pending = true
            failure = ""
            try {
                status = client.check()
                if ((status?.resolved_count ?: 0) > 0) {
                    notice = "Cleared ${status?.resolved_count} abandoned call(s)."
                    vm.refreshCalls()
                }
            } catch (e: Exception) {
                failure = e.message ?: "Unable to check call status"
            } finally { pending = false }
        }
    }

    LaunchedEffect(vm.store.token) { refresh() }

    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 7.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Call Recovery", fontWeight = FontWeight.Bold, fontSize = 18.sp)
            Text("Seeing 'already on a call' when you're not? Check the server's active calls or reset a stuck session.",
                fontSize = 12.sp, color = Color(0xFF70738B))
            val count = status?.active_count
            Text(
                if (count == null) "Call status not checked" else if (count == 0) "No active calls on your account" else "$count call(s) registered as active",
                fontWeight = FontWeight.SemiBold, fontSize = 12.sp,
                color = if (count == 0) Color(0xFF16865F) else Color(0xFFAB601A)
            )
            status?.active?.forEach { call ->
                Text("${call.call_type} · ${call.peer_display_name} · ${call.status}",
                    fontSize = 11.sp, color = Color(0xFF70738B))
            }
            if (notice.isNotBlank()) Text(notice, color = Color(0xFF16865F), fontSize = 11.sp)
            if (failure.isNotBlank()) Text(failure, color = Color(0xFFD63C57), fontSize = 11.sp)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { refresh() }, enabled = !pending, modifier = Modifier.weight(1f)) {
                    Text("Check status", fontSize = 12.sp)
                }
                Button(
                    onClick = { confirm = true }, enabled = !pending,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFAF4059))
                ) { Text("Reset stuck call", fontSize = 12.sp) }
            }
            if (pending) LinearProgressIndicator(Modifier.fillMaxWidth())
        }
    }

    if (confirm) {
        AlertDialog(
            onDismissRequest = { confirm = false },
            title = { Text("End all your LEMMIQ calls?") },
            text = { Text("This will end any ongoing voice/video calls on your account, including calls on other devices. The other participant may be disconnected. Only use it if your call status is stuck.") },
            confirmButton = {
                TextButton(onClick = {
                    confirm = false
                    scope.launch {
                        pending = true
                        failure = ""
                        try {
                            val ended = client.reset()
                            notice = if (ended == 0) "No active call sessions were found." else "Reset completed: $ended call(s) ended."
                            status = client.check()
                            vm.refreshCalls()
                        } catch (e: Exception) {
                            failure = e.message ?: "Unable to reset call status"
                        } finally { pending = false }
                    }
                }) { Text("End my calls", color = Color(0xFFD63C57)) }
            },
            dismissButton = { TextButton(onClick = { confirm = false }) { Text("Cancel") } }
        )
    }
}
