/* LEMMIQ V2.13.11 — Q Predict Sell Q / Withdraw and official announcements */
package com.lemmiq.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.Locale

private val v11Client=OkHttpClient()
private val v11VerifyMsg="""Verification Required

Q Predict Q wallets are fully separate from Q Economy.

Buying Q, staking, selling Q and withdrawing USDT are available only to approved, verified users, subject to applicable authorization.

Your account is not currently enabled for these services. Please contact LEMMIQ Support for eligibility information."""
private fun v11Money(v:Double)=String.format(Locale.US,"%,.2f",v)
private suspend fun v11Api(ctx:Context,path:String,body:JSONObject?=null):JSONObject=withContext(Dispatchers.IO){
    val req=Request.Builder().url(BuildConfig.API_BASE_URL.trimEnd('/')+path).apply{
        SessionStore(ctx).token?.let{header("Authorization","Bearer $it")}
        if(body!=null)post(body.toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
    }.build()
    v11Client.newCall(req).execute().use{res->
        val data=runCatching{JSONObject(res.body?.string().orEmpty())}.getOrElse{JSONObject()}
        if(!res.isSuccessful)throw IllegalStateException(data.optString("detail","Request failed: ${res.code}"))
        data
    }
}
fun v11Support(ctx:Context){
    // Official support is resolved and opened by the authenticated PWA handler.
    ctx.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse("https://app.lemmiq.com/web/#support-chat")))
}

@Composable
fun V21311PredictExtras(onWalletChanged:()->Unit={}){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var status by remember{mutableStateOf<JSONObject?>(null)}
    var open by remember{mutableStateOf(false)}
    var amount by remember{mutableStateOf("1000")}
    var network by remember{mutableStateOf("TRC20")}
    var destination by remember{mutableStateOf("")}
    var quote by remember{mutableStateOf<JSONObject?>(null)}
    var history by remember{mutableStateOf<JSONObject?>(null)}
    var error by remember{mutableStateOf("")}
    var busy by remember{mutableStateOf(false)}
    LaunchedEffect(Unit){
        status=runCatching{v11Api(ctx,"/v21311/redeem/status")}.getOrNull()
        history=runCatching{v11Api(ctx,"/v21311/redeem/mine")}.getOrNull()
    }
    Column(verticalArrangement=Arrangement.spacedBy(9.dp)){
        Text("Q Predict wallet operations",fontWeight=FontWeight.Bold)
        Button(onClick={open=true},modifier=Modifier.fillMaxWidth()) {Text("Sell Q · Withdraw USDT")}
        Text("Payment out: USDT – TRON (TRC20) or USDT – BNB Smart Chain (BEP20). Independent of Q Economy.",style=MaterialTheme.typography.bodySmall)
        history?.optJSONArray("requests")?.let{a->
            if(a.length()>0){
                Text("Recent withdrawal requests",fontWeight=FontWeight.Bold)
                for(i in 0 until minOf(a.length(),3)){
                    val x=a.optJSONObject(i)
                    if(x!=null)Text("${x.optString("code")} · ${x.optString("status")} · ${v11Money(x.optDouble("payout_usdt"))} USDT",style=MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
    if(open){
        AlertDialog(onDismissRequest={open=false},title={Text("Sell Q / Withdraw USDT")},
            text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(10.dp)){
                if(status?.optBoolean("eligible",false)!=true){
                    Text(v11VerifyMsg,style=MaterialTheme.typography.bodySmall)
                    OutlinedButton(onClick={v11Support(ctx)}){Text("Chat with @lemmiq Support")}
                }else if(status?.optBoolean("sell_allowed",false)!=true){
                    Text("✓ Verified User Access. USDT withdrawals are currently disabled for this account or service.",style=MaterialTheme.typography.bodySmall)
                }else{
                    Text("Sell rate = Q reference −5%",style=MaterialTheme.typography.bodySmall)
                    OutlinedTextField(amount,{amount=it;quote=null},label={Text("Q amount")},singleLine=true)
                    Text("Withdraw network",fontWeight=FontWeight.Bold)
                    Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){
                        FilterChip(network=="TRC20",onClick={network="TRC20";quote=null},label={Text("USDT TRON TRC20")})
                        FilterChip(network=="BEP20",onClick={network="BEP20";quote=null},label={Text("USDT BNB BEP20")})
                    }
                    OutlinedTextField(destination,{destination=it},label={Text("Receiving USDT address")})
                    OutlinedButton(enabled=!busy,onClick={scope.launch{
                        busy=true;error=""
                        try{quote=v11Api(ctx,"/v21311/redeem/quote",JSONObject().put("amount_q",amount.toDouble()).put("network",network))}
                        catch(e:Exception){error=e.message?:"Quote failed"}finally{busy=false}
                    }}){Text("Calculate payout")}
                    quote?.let{q->
                        Text("${v11Money(q.optDouble("q_amount"))} Q → ${v11Money(q.optDouble("payout_usdt"))} USDT",fontWeight=FontWeight.Bold)
                        Text("Admin will transfer USDT externally and verify the transaction before marking it paid.",style=MaterialTheme.typography.bodySmall)
                        Button(enabled=!busy,onClick={scope.launch{
                            busy=true;error=""
                            try{
                                v11Api(ctx,"/v21311/redeem/requests",JSONObject().put("network",network).put("amount_q",amount.toDouble()).put("destination",destination.trim()))
                                history=v11Api(ctx,"/v21311/redeem/mine");open=false;onWalletChanged()
                            }catch(e:Exception){error=e.message?:"Withdrawal failed"}finally{busy=false}
                        }}){Text("Request withdrawal")}
                    }
                }
                if(error.isNotBlank())Text(error,color=MaterialTheme.colorScheme.error)
            }},confirmButton={TextButton(onClick={open=false}){Text("Close")}})
    }
}

@Composable
fun V21311AdminBroadcastCard(){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var audience by remember{mutableStateOf("ALL")}
    var kind by remember{mutableStateOf("UPDATE")}
    var content by remember{mutableStateOf("")}
    var preview by remember{mutableStateOf<JSONObject?>(null)}
    var latest by remember{mutableStateOf("")}
    var busy by remember{mutableStateOf(false)}
    Card(modifier=Modifier.fillMaxWidth()){
        Column(Modifier.padding(15.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text("📣 LEMMIQ Official Broadcast",fontWeight=FontWeight.Bold)
            Text("Master Admin only · Message delivered privately from @lemmiq",style=MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){
                FilterChip(audience=="ALL",onClick={audience="ALL"},label={Text("All users")})
                FilterChip(audience=="VERIFIED",onClick={audience="VERIFIED"},label={Text("Verified")})
                FilterChip(audience=="CREATORS",onClick={audience="CREATORS"},label={Text("Creators")})
            }
            OutlinedTextField(content,{content=it},label={Text("Announcement message")},modifier=Modifier.fillMaxWidth(),minLines=3,maxLines=6)
            OutlinedButton(enabled=!busy && content.length>=5,onClick={scope.launch{
                busy=true
                try{preview=v11Api(ctx,"/v21311/admin/broadcasts",JSONObject().put("text",content).put("audience",audience).put("kind",kind));latest="Draft saved; confirm before publishing"}
                catch(e:Exception){latest=e.message?:"Could not save draft"}finally{busy=false}
            }}){Text("Save and preview draft")}
            preview?.let{p->
                Text("Draft #${p.optInt("id")}: ${p.optString("content")}",style=MaterialTheme.typography.bodySmall)
                Button(enabled=!busy,onClick={scope.launch{
                    busy=true
                    try{
                        v11Api(ctx,"/v21311/admin/broadcasts/${p.optInt("id")}/publish",JSONObject())
                        latest="Broadcast queued; monitor its status in Q Admin on PWA"
                        preview=null;content=""
                    }catch(e:Exception){latest=e.message?:"Publish failed"}finally{busy=false}
                }}){Text("Confirm and send")}
            }
            if(latest.isNotBlank())Text(latest,style=MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun V21311VerificationNotice(){
    val ctx=LocalContext.current
    Column(verticalArrangement=Arrangement.spacedBy(8.dp)){
        Text(v11VerifyMsg,style=MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick={v11Support(ctx)}){Text("Chat with @lemmiq Support")}
    }
}
