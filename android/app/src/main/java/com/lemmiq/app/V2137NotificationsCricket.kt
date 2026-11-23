// V2137_NOTIFICATIONS_CRICKET
package com.lemmiq.app


import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.time.OffsetDateTime

private val v2137Client = OkHttpClient()

private suspend fun cricketFixturesV2137(ctx: Context): Pair<String, List<JSONObject>> = withContext(Dispatchers.IO) {
    val url=BuildConfig.API_BASE_URL.trimEnd('/')+"/v2137/cricket/fixtures"
    val req=Request.Builder().url(url).apply{
        SessionStore(ctx).token?.let{header("Authorization","Bearer $it")}
    }.get().build()
    v2137Client.newCall(req).execute().use { r ->
        val body = r.body.string()
        if (!r.isSuccessful) throw IllegalStateException("Cricket API HTTP ${r.code}")
        val data=JSONObject(body)
        val json=data.optJSONArray("fixtures")
        val rows=if(json==null)emptyList() else (0 until minOf(35,json.length())).mapNotNull{json.optJSONObject(it)}
        Pair(data.optString("note","Upcoming fixtures"),rows)
    }
}

@Composable
fun V2137CricketFixtures(){
    val ctx=LocalContext.current
    var data by remember{mutableStateOf<List<JSONObject>>(emptyList())}
    var status by remember{mutableStateOf("Loading fixtures…")}
    var reload by remember{mutableIntStateOf(0)}
    LaunchedEffect(reload){
        try{val (info,items)=cricketFixturesV2137(ctx);data=items;status=if(items.isEmpty())"No fixtures available. Configure a permitted cricket feed." else info}
        catch(e:Exception){status="Unable to load cricket fixtures: ${e.message}"}
    }
    Column(Modifier.fillMaxWidth().padding(10.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
        Text("🏏 Global cricket fixtures",fontWeight=FontWeight.Bold)
        Text(status,style=MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick={reload++}){Text("Refresh fixtures")}
        data.take(18).forEach{m->
            Card(Modifier.fillMaxWidth()){
                Column(Modifier.padding(10.dp),verticalArrangement=Arrangement.spacedBy(3.dp)){
                    Text(m.optString("team_a")+" vs "+m.optString("team_b"),fontWeight=FontWeight.Bold,style=MaterialTheme.typography.bodyMedium)
                    Text(m.optString("series")+" · "+m.optString("format"),style=MaterialTheme.typography.bodySmall)
                    Text(m.optString("start_at"),style=MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
fun V2137NotificationManagement(){
    val ctx=LocalContext.current
    val prefs=remember{ctx.getSharedPreferences("lemmiq_v2137_notifications",Context.MODE_PRIVATE)}
    var version by remember{mutableIntStateOf(0)}
    val items=listOf(
        "chat" to "Direct messages",
        "group" to "Group messages",
        "call" to "Incoming calls",
        "updates" to "Updates / Status",
        "q" to "Q Economy and predictions",
        "preview" to "Show message previews",
    )
    Column(Modifier.fillMaxWidth().padding(horizontal=18.dp,vertical=8.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
        Text("Notification management",style=MaterialTheme.typography.titleMedium,fontWeight=FontWeight.Bold)
        Text("Push tokens register automatically after notification permission is granted. Configure sounds and pop-ups in Android notification channels.",style=MaterialTheme.typography.bodySmall)
        items.forEach { (key, label) ->
            val checked = prefs.getBoolean(key, true)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                Switch(checked = checked, onCheckedChange = {
                    prefs.edit().putBoolean(key, it).apply()
                    version++
                })
            }
        }
        OutlinedButton(
            onClick = {
                val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).apply {
                    putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName)
                }
                runCatching { ctx.startActivity(intent) }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("System notification sounds & channels")
        }
        var pushState by remember{mutableStateOf("")}
        OutlinedButton(onClick={
            if(BuildConfig.FCM_CONFIGURED){
                FirebaseMessaging.getInstance().getToken().addOnCompleteListener{task->
                    if(task.isSuccessful){
                        pushState="FCM device token available. Registering…"
                        val store=SessionStore(ctx)
                        if(store.token!=null){
                            kotlinx.coroutines.CoroutineScope(Dispatchers.IO).launch{
                                runCatching{Api(store).registerPush(task.result)}.onSuccess{pushState="Registration requested"}.onFailure{pushState="Registration failed: ${it.message}"}
                            }
                        }
                    }else pushState="FCM token unavailable"
                }
            }else pushState="Add google-services.json to enable Android push"
        },Modifier.fillMaxWidth()){Text("Refresh push registration")}
        if(pushState.isNotBlank())Text(pushState,style=MaterialTheme.typography.labelSmall)
        Text("Android 13+ also requires notification permission. The app requests it when launched.",style=MaterialTheme.typography.labelSmall)
    }
}
