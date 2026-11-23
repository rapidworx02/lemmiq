/* LEMMIQ V2.13.12 — Q Predict verified access and order-bound QR (native Android). */
package com.lemmiq.app

import android.content.Context
import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject

private val pq12Client = OkHttpClient()

private suspend fun pq12Get(ctx: Context, path: String): JSONObject = withContext(Dispatchers.IO) {
    val request = Request.Builder()
        .url(BuildConfig.API_BASE_URL.trimEnd('/') + path)
        .apply { SessionStore(ctx).token?.let { header("Authorization", "Bearer $it") } }
        .get().build()
    pq12Client.newCall(request).execute().use { response ->
        val data = runCatching { JSONObject(response.body?.string().orEmpty()) }.getOrElse { JSONObject() }
        if (!response.isSuccessful) {
            throw IllegalStateException(data.optString("detail", "HTTP ${response.code}"))
        }
        data
    }
}

@Composable
fun V21312PredictStatusCard() {
    val ctx = LocalContext.current
    var status by remember { mutableStateOf<JSONObject?>(null) }
    LaunchedEffect(Unit) { status = runCatching { pq12Get(ctx, "/v21311/redeem/status") }.getOrNull() }
    val eligible = status?.optBoolean("eligible", false) == true
    if (eligible) {
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text("✓ Verified User Access — Q Predict", fontWeight = FontWeight.Bold)
                Text("Your account is approved for Q Predict testing. Q Economy and Q Predict wallets are separate.", style = MaterialTheme.typography.bodySmall)
                if (status?.optBoolean("buy_allowed", false) != true) Text("USDT purchases are currently disabled.", style = MaterialTheme.typography.bodySmall)
                if (status?.optBoolean("wagering_allowed", false) != true) Text("Real-Q predictions are currently disabled.", style = MaterialTheme.typography.bodySmall)
                if (status?.optBoolean("sell_allowed", false) != true) Text("Withdrawals are currently disabled.", style = MaterialTheme.typography.bodySmall)
                Text("Access approval does not replace separate identity verification or applicable authorisation.", style = MaterialTheme.typography.bodySmall)
            }
        }
    } else if (status != null) {
        V21311VerificationNotice()
    }
}

@Composable
fun V21312PredictBuyStatus(paymentsEnabled: Boolean) {
    val ctx = LocalContext.current
    var status by remember { mutableStateOf<JSONObject?>(null) }
    LaunchedEffect(Unit) { status = runCatching { pq12Get(ctx, "/v21311/redeem/status") }.getOrNull() }
    when {
        status == null -> Text("Checking Q Predict eligibility...", style = MaterialTheme.typography.bodySmall)
        status?.optBoolean("eligible", false) != true -> V21311VerificationNotice()
        paymentsEnabled -> Text("✓ Verified User Access. USDT checkout available subject to applicable permissions.", style = MaterialTheme.typography.bodySmall)
        else -> Text("✓ Verified User Access. USDT purchases are currently disabled for this account or service.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
fun V21312OrderQR(order: JSONObject) {
    val ctx = LocalContext.current
    val orderId = order.optInt("id", -1)
    var qr by remember(orderId) { mutableStateOf<JSONObject?>(null) }
    var error by remember(orderId) { mutableStateOf("") }
    var enlarged by remember { mutableStateOf(false) }
    LaunchedEffect(orderId) {
        if (orderId > 0) {
            try {
                val next = pq12Get(ctx, "/v21312/predict/qr/order/$orderId")
                if (next.optString("receiving_address") != order.optString("receiving_address") ||
                    next.optString("network") != order.optString("network")) {
                    error = "QR receiving address mismatch. Copy the address instead."
                } else qr = next
            } catch (e: Exception) { error = e.message ?: "QR not available" }
        }
    }
    val bitmap = remember(qr) {
        runCatching {
            val bytes = Base64.decode(qr?.optString("qr_png_b64") ?: "", Base64.DEFAULT)
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
        }.getOrNull()
    }
    if (bitmap != null) {
        Column(horizontalAlignment = Alignment.CenterHorizontally,
               verticalArrangement = Arrangement.spacedBy(7.dp),
               modifier = Modifier.fillMaxWidth()) {
            Text("Scan ${order.optString("network")} USDT QR", fontWeight = FontWeight.Bold)
            Image(bitmap = bitmap, contentDescription = "Order receiving address QR",
                modifier = Modifier.size(164.dp).clickable { enlarged = true })
            OutlinedButton(onClick = { enlarged = true }) { Text("Enlarge QR") }
            Text("Always confirm the destination matches the address above and the selected USDT network.",
                 style = MaterialTheme.typography.bodySmall)
        }
        if (enlarged) {
            Dialog(onDismissRequest = { enlarged = false }) {
                Card {
                    Column(Modifier.padding(18.dp).verticalScroll(rememberScrollState()),
                           horizontalAlignment = Alignment.CenterHorizontally,
                           verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("${order.optString("network")} receiving QR", fontWeight = FontWeight.Bold)
                        Image(bitmap = bitmap, contentDescription = "Enlarged USDT payment QR", modifier = Modifier.size(260.dp))
                        Text(order.optString("receiving_address"), style = MaterialTheme.typography.bodySmall)
                        OutlinedButton(onClick = { enlarged = false }) { Text("Close") }
                    }
                }
            }
        }
    } else if (error.isNotBlank()) {
        Text("QR unavailable: $error — use Copy Address instead.", style = MaterialTheme.typography.bodySmall)
    } else {
        Text("Generating order payment QR...", style = MaterialTheme.typography.bodySmall)
    }
}
