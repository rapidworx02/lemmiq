package com.lemmiq.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

private val support301Client=OkHttpClient()
private fun open301(ctx:Context,url:String){
    runCatching{ctx.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(url)))}.onFailure{Toast.makeText(ctx,"Open app.lemmiq.com in your browser",Toast.LENGTH_LONG).show()}
}
@Composable
fun V301GuestSupportLinks(){
    val ctx=LocalContext.current
    TextButton(onClick={open301(ctx,"https://app.lemmiq.com/web/support.html")}){Text("Forgot password?")}
    TextButton(onClick={open301(ctx,"https://app.lemmiq.com/web/support.html")}){Text("Chat with LEMMIQ Support")}
    Text("No login, email or phone needed. Opens secure web support.",style=MaterialTheme.typography.bodySmall)
}
@Composable
fun V301AdminMoreEntry(onOpen:()->Unit){
    val ctx=LocalContext.current
    val token=SessionStore(ctx).token
    var allowed by remember(token){mutableStateOf(false)}
    LaunchedEffect(token){
        allowed=if(token.isNullOrBlank())false else withContext(Dispatchers.IO){runCatching{
            val r=Request.Builder().url(BuildConfig.API_BASE_URL.trimEnd('/')+"/v301/support/admin/access").header("Authorization","Bearer $token").build()
            support301Client.newCall(r).execute().use{it.isSuccessful}
        }.getOrDefault(false)}
    }
    if(allowed)TextButton(onClick=onOpen,modifier=Modifier.fillMaxWidth().padding(horizontal=12.dp)){Text("📣 Admin · Communication Centre")}
}
@Composable
fun V301CommunicationScreen(){
    val ctx=LocalContext.current
    val token=SessionStore(ctx).token
    var allowed by remember(token){mutableStateOf(false)}
    var checked by remember(token){mutableStateOf(false)}
    LaunchedEffect(token){
        allowed=if(token.isNullOrBlank())false else withContext(Dispatchers.IO){runCatching{
            val r=Request.Builder().url(BuildConfig.API_BASE_URL.trimEnd('/')+"/v301/support/admin/access").header("Authorization","Bearer $token").build()
            support301Client.newCall(r).execute().use{it.isSuccessful}
        }.getOrDefault(false)};checked=true
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
        if(!checked)Text("Checking admin access…") else if(!allowed)Text("Master Admin access required") else {
            V21311AdminBroadcastCard()
            Text("Guest Support Centre and full broadcast history are managed in the PWA Admin Panel.",style=MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick={open301(ctx,"https://app.lemmiq.com/web/#q-admin")}){Text("Open Admin Panel in browser")}
        }
    }
}
