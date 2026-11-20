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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import java.time.ZoneId

private data class QPrefs317(
    val enabled:Boolean=true,val frequency:String="LOW",
    val quiet_start:Int=22,val quiet_end:Int=8,val timezone_name:String="UTC"
)
private data class QBrief317(val title:String="Your LEMMIQ catch-up",val body:String="",val unread_conversations:Int=0)

private class QAssistantClient317(private val store:SessionStore){
    private val http=OkHttpClient()
    private val gson=Gson()
    private val base=BuildConfig.API_BASE_URL.trimEnd('/')
    private suspend fun request(route:String,method:String="GET",body:String?=null):String=withContext(Dispatchers.IO){
        val builder=Request.Builder().url("$base/v21317/q/$route")
        val token=store.token?:throw IllegalStateException("Please sign in")
        builder.header("Authorization","Bearer $token")
        if(method=="PUT")builder.put((body?:"{}").toRequestBody("application/json; charset=utf-8".toMediaType()))
        http.newCall(builder.build()).execute().use{res->
            if(!res.isSuccessful)throw IllegalStateException("Assistant unavailable (HTTP ${res.code})")
            res.body?.string().orEmpty()
        }
    }
    suspend fun preferences():QPrefs317=gson.fromJson(request("preferences"),QPrefs317::class.java)
    suspend fun save(p:QPrefs317):QPrefs317=gson.fromJson(request("preferences","PUT",gson.toJson(p)),QPrefs317::class.java)
    suspend fun catchup():QBrief317=gson.fromJson(request("catch-up"),QBrief317::class.java)
}

/** An in-app assistant, not an unsolicited push-notification engine. */
@Composable
fun V21317QAssistantControls(vm:LemmiqViewModel){
    val client=remember(vm.store){QAssistantClient317(vm.store)}
    val scope=rememberCoroutineScope()
    var prefs by remember{mutableStateOf(QPrefs317())}
    var settings by remember{mutableStateOf(false)}
    var summary by remember{mutableStateOf<QBrief317?>(null)}
    var busy by remember{mutableStateOf(false)}
    var error by remember{mutableStateOf("")}
    LaunchedEffect(vm.store.userId){
        runCatching{client.preferences()}.onSuccess{prefs=it}.onFailure{error="Assistant preferences unavailable"}
    }
    Card(colors=CardDefaults.cardColors(containerColor=Color(0xFFF2EFFF)),shape=RoundedCornerShape(18.dp)){
        Column(Modifier.fillMaxWidth().padding(14.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text("Q · Your catch-up assistant",fontWeight=FontWeight.Bold,color=Color(0xFF5337BE))
            Text("Useful reminders, not constant notifications. Proactive digests stay inside LEMMIQ.",fontSize=11.sp,color=Color(0xFF6C647C))
            Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                OutlinedButton(onClick={
                    scope.launch{busy=true;error="";runCatching{client.catchup()}.onSuccess{summary=it}.onFailure{error=it.message?:"Couldn't load catch-up"};busy=false}
                },enabled=!busy){Text("Catch me up",fontSize=11.sp)}
                TextButton(onClick={settings=true}){Text("Preferences",fontSize=11.sp)}
            }
            summary?.let{Text(it.body,fontSize=12.sp)}
            if(error.isNotBlank())Text(error,color=Color(0xFFA43C51),fontSize=11.sp)
        }
    }
    if(settings)AlertDialog(onDismissRequest={settings=false},title={Text("Q Assistant preferences")},
        text={Column(verticalArrangement=Arrangement.spacedBy(10.dp)){
            Text("In-app reminders",fontWeight=FontWeight.SemiBold)
            Row{listOf("OFF" to "Off","LOW" to "Low (3 days)","DAILY" to "Daily").forEach{(value,label)->
                FilterChip(selected=prefs.frequency==value,onClick={prefs=prefs.copy(frequency=value,enabled=value!="OFF")},label={Text(label,fontSize=10.sp)},modifier=Modifier.padding(end=3.dp))
            }}
            Text("Quiet hours: ${prefs.quiet_start}:00 – ${prefs.quiet_end}:00",fontSize=12.sp)
            Text("Quiet time begins",fontSize=11.sp)
            Slider(value=prefs.quiet_start.toFloat(),onValueChange={prefs=prefs.copy(quiet_start=it.toInt())},valueRange=0f..23f,steps=22)
            Text("Quiet time ends",fontSize=11.sp)
            Slider(value=prefs.quiet_end.toFloat(),onValueChange={prefs=prefs.copy(quiet_end=it.toInt())},valueRange=0f..23f,steps=22)
            Text("Digests are informational only. No promotional push notifications are sent.",fontSize=11.sp)
        }},confirmButton={Button(onClick={scope.launch{
            busy=true
            val next=prefs.copy(timezone_name=ZoneId.systemDefault().id)
            runCatching{client.save(next)}.onSuccess{prefs=it;settings=false}.onFailure{error=it.message?:"Could not save"}
            busy=false
        }},enabled=!busy){Text("Save")}},dismissButton={TextButton(onClick={settings=false}){Text("Cancel")}})
}
