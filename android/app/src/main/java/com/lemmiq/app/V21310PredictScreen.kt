/* V21311_RELEASE */
/* LEMMIQ 2.13.10 — dedicated Q Predict Q wallet, USDT buy, demo preserved. */
package com.lemmiq.app

import android.content.Context
import android.content.ClipData
import android.content.ClipboardManager
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.Locale
import java.util.UUID

private val pQClient = OkHttpClient()
private fun pqNumber(n:Double)=String.format(Locale.US,"%,.2f",n)
private suspend fun pqCall(ctx:Context,path:String,body:JSONObject?=null,method:String="GET"):JSONObject=withContext(Dispatchers.IO){
    val r=Request.Builder().url(BuildConfig.API_BASE_URL.trimEnd('/')+path).apply{
        SessionStore(ctx).token?.let {header("Authorization","Bearer $it")}
        if(method=="POST" || body!=null) post((body?:JSONObject()).toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
    }.build()
    pQClient.newCall(r).execute().use{res->
        val raw=res.body?.string().orEmpty()
        val obj=runCatching{JSONObject(raw)}.getOrElse{JSONObject()}
        if(!res.isSuccessful) throw IllegalStateException(obj.optString("detail","API HTTP ${res.code}"))
        obj
    }
}

@Composable
fun V21310PredictScreen(){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var demoMode by remember{mutableStateOf(true)}
    var home by remember{mutableStateOf<JSONObject?>(null)}
    var demo by remember{mutableStateOf<JSONObject?>(null)}
    var busy by remember{mutableStateOf(false)}
    var error by remember{mutableStateOf("")}
    var category by remember{mutableStateOf("ALL")}
    var sportsSub by remember{mutableStateOf("ALL")}
    var selected by remember{mutableStateOf<JSONObject?>(null)}
    var stakeAmount by remember{mutableStateOf("10")}
    var buyOpen by remember{mutableStateOf(false)}
    var amountQ by remember{mutableStateOf("1000")}
    var network by remember{mutableStateOf("TRC20")}
    var quote by remember{mutableStateOf<JSONObject?>(null)}
    var order by remember{mutableStateOf<JSONObject?>(null)}
    var sender by remember{mutableStateOf("")}
    var hash by remember{mutableStateOf("")}
    var showHistory by remember{mutableStateOf(false)}
    var admin by remember{mutableStateOf<JSONObject?>(null)}

    fun refresh(){scope.launch {
        busy=true;error=""
        try{
            home=pqCall(ctx,"/v21310/predict/home")
            demo=pqCall(ctx,"/v2138/predict/home")
            admin=runCatching{pqCall(ctx,"/v21310/predict/admin")}.getOrNull()
        }catch(e:Exception){error=e.message?:"Unable to load wallet"}
        finally{busy=false}
    }}
    fun sendStake(id:Int,side:String){scope.launch{
        busy=true
        try{
            val n=stakeAmount.toDoubleOrNull()?:0.0
            require(n>=1 && n<=250 && kotlin.math.abs(n*100-kotlin.math.round(n*100))<0.0001){"Stake must be 1–250"}
            val payload=JSONObject().put("market_id",id).put("outcome",side)
                .put("request_key",UUID.randomUUID().toString().replace("-","_"))
            if(demoMode)payload.put("amount",n) else payload.put("amount_q",n)
            pqCall(ctx,if(demoMode)"/v2138/predict/demo/stake" else "/v21310/predict/stake",payload,"POST")
            selected=null;refresh()
        }catch(e:Exception){error=e.message?:"Prediction failed"}
        finally{busy=false}
    }}
    LaunchedEffect(Unit){refresh()}
    val source=if(demoMode)demo else home
    val markets=remember(source){
        val a=source?.optJSONArray("markets")
        if(a==null) emptyList() else (0 until a.length()).mapNotNull{a.optJSONObject(it)}
    }
    val filtered=markets.filter{m->
        (category=="ALL"||m.optString("category")==category) &&
        (category!="SPORTS"||sportsSub=="ALL"||demoMode||m.optString("subcategory")==sportsSub)
    }
    val permitted=home?.optBoolean("payments_enabled",false)==true

    LazyColumn(Modifier.fillMaxSize().background(Color(0xFFF7F7FB)),
        contentPadding=PaddingValues(12.dp,12.dp,12.dp,120.dp),verticalArrangement=Arrangement.spacedBy(11.dp)){
        item{
            Card(colors=CardDefaults.cardColors(containerColor=Color(0xFF29215F)),shape=RoundedCornerShape(21.dp)){
                Column(Modifier.fillMaxWidth().padding(19.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                    Text("LEMMIQ Q PREDICT",color=Color(0xFFDCD5FF),fontSize=11.sp,fontWeight=FontWeight.Bold)
                    Text(if(demoMode)"Demo predictions" else "Q Predict Wallet",color=Color.White,fontWeight=FontWeight.Black,fontSize=25.sp)
                    Text(if(demoMode)"${pqNumber(source?.optDouble("available",0.0)?:0.0)} Demo USDT" else "${pqNumber(source?.optDouble("available_q",0.0)?:0.0)} Q",
                        color=Color.White,fontWeight=FontWeight.Black,fontSize=27.sp)
                    Text(if(demoMode)"Virtual credits, no cash value" else "Locked: ${pqNumber(source?.optDouble("locked_q",0.0)?:0.0)} Q · Main Q Economy wallet is separate",
                        color=Color(0xFFEAE4FF),fontSize=11.sp)
                    if(!demoMode)Text("Buy Q +5% · Sell Q −5%",color=Color(0xFFDFD8FF),fontSize=11.sp)
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                        OutlinedButton(onClick={demoMode=true}){Text("Demo",color=Color.White)}
                        OutlinedButton(onClick={demoMode=false}){Text("Q Wallet",color=Color.White)}
                    }
                }
            }
        }
        if(busy)item{LinearProgressIndicator(Modifier.fillMaxWidth())}
        if(error.isNotBlank())item{Text(error,color=Color(0xFFB42318),fontSize=12.sp)}
        if(!demoMode){
            item{
                Column(verticalArrangement=Arrangement.spacedBy(7.dp)){
                    Text("Reference: ${pqNumber(home?.optDouble("reference_usdt_per_q",0.0)?:0.0)} USDT/Q",fontSize=12.sp)
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                        Button(onClick={buyOpen=true}){Text("Buy Q · USDT")}
                        OutlinedButton(onClick={showHistory=true}){Text("Activity")}
                    }
                    V21312PredictStatusCard()
                }
            }
        }
        if(!demoMode)item{V21311PredictExtras(onWalletChanged={refresh()})}
        item{Text("Live prediction markets",fontSize=20.sp,fontWeight=FontWeight.Black)}
        item{
            Column(verticalArrangement=Arrangement.spacedBy(6.dp)){
                androidx.compose.foundation.lazy.LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                    items(listOf("ALL","SPORTS","CRYPTO","ECONOMY","TECH_AI","ENTERTAINMENT","WEATHER","LEMMIQ")){c->
                        FilterChip(category==c,onClick={category=c;sportsSub="ALL"},label={Text(c.replace("_"," & "),fontSize=10.sp)})
                    }
                }
                if(category=="SPORTS"&&!demoMode){
                    androidx.compose.foundation.lazy.LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                        items(listOf("ALL","INTERNATIONAL","DOMESTIC","LEAGUES","OTHER")){c->
                            FilterChip(sportsSub==c,onClick={sportsSub=c},label={Text(c.lowercase().replaceFirstChar{it.uppercase()},fontSize=10.sp)})
                        }
                    }
                }
            }
        }
        if(filtered.isEmpty())item{Card{Text("No eligible live markets in this category.",Modifier.padding(15.dp))}}
        items(filtered.take(30),key={it.optInt("id")}){m->
            Card(Modifier.fillMaxWidth().clickable{selected=m},shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(15.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                    Text(m.optString("category")+" · "+m.optString("subcategory"),fontSize=10.sp,color=Color(0xFF6C4DFF))
                    Text(m.optString("question"),fontWeight=FontWeight.Bold,fontSize=15.sp)
                    OutlinedButton(onClick={selected=m}){Text("Predict YES / NO")}
                }
            }
        }
        item{OutlinedButton(onClick={refresh()}){Text("Refresh wallet and markets")}}
        if(admin!=null)item{V21311AdminBroadcastCard()}
        if(admin!=null)item{
            Card{Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(6.dp)){
                Text("Master Admin · Treasury status",fontWeight=FontWeight.Bold)
                Text("Real payments: ${if(admin?.optBoolean("payments_enabled")==true)"Verified users ON" else "OFF"}. Real staking: ${if(admin?.optBoolean("wagering_enabled")==true)"Verified users ON" else "OFF"}",fontSize=11.sp)
                Text("Configure and review dedicated TRC20/BEP20 receiving wallets in PWA → Q Admin.",fontSize=11.sp)
            }}
        }
    }
    selected?.let{m->
        AlertDialog(onDismissRequest={selected=null},title={Text("Q Predict")},
            text={Column(verticalArrangement=Arrangement.spacedBy(9.dp)){
                Text(m.optString("question"),fontWeight=FontWeight.Bold)
                Text(if(demoMode)"Demo USDT only" else "Q Predict Q balance only · 10% fee on positive winnings",fontSize=12.sp)
                OutlinedTextField(stakeAmount,{stakeAmount=it},label={Text("Stake amount")},singleLine=true)
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    Button(onClick={sendStake(m.optInt("id"),"YES")},enabled=!busy){Text("YES")}
                    OutlinedButton(onClick={sendStake(m.optInt("id"),"NO")},enabled=!busy){Text("NO")}
                }
            }},confirmButton={TextButton(onClick={selected=null}){Text("Close")}})
    }
    if(buyOpen){
        AlertDialog(onDismissRequest={buyOpen=false},title={Text("Buy Q using USDT")},
            text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(10.dp)){
                Text("Separate Q Predict Q only · Reference rate +5%",fontSize=12.sp)
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    FilterChip(network=="TRC20",onClick={network="TRC20";quote=null},label={Text("USDT TRON TRC20")})
                    FilterChip(network=="BEP20",onClick={network="BEP20";quote=null},label={Text("USDT BNB BEP20")})
                }
                OutlinedTextField(amountQ,{amountQ=it},label={Text("Q quantity")},singleLine=true)
                Button(onClick={scope.launch{
                    busy=true
                    try{quote=pqCall(ctx,"/v21310/predict/quote",JSONObject().put("network",network).put("q_amount",amountQ.toDouble()),"POST")}
                    catch(e:Exception){error=e.message?:"Quote failed"}finally{busy=false}
                }},enabled=!busy){Text("Calculate quote")}
                quote?.let{q->
                    Text("Pay ${pqNumber(q.optDouble("expected_usdt"))} USDT for ${pqNumber(q.optDouble("q_amount"))} Q",fontWeight=FontWeight.Bold)
                    Text("Rate locked for 15 minutes when an order is created",fontSize=11.sp)
                    if(permitted) Button(onClick={scope.launch{
                        busy=true
                        try{
                            order=pqCall(ctx,"/v21310/predict/buy/orders",JSONObject().put("network",network).put("q_amount",amountQ.toDouble()),"POST")
                        }catch(e:Exception){error=e.message?:"Cannot create order"}finally{busy=false}
                    }},enabled=!busy){Text("Create payment order")}
                }
                order?.let{o->
                    Text("Pay exactly ${pqNumber(o.optDouble("expected_usdt"))} USDT on ${o.optString("network")}",fontWeight=FontWeight.Bold)
                    Text(o.optString("receiving_address"),fontSize=12.sp)
                     V21312OrderQR(o)
                    OutlinedButton(onClick={
                        val cb=ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        cb.setPrimaryClip(ClipData.newPlainText("LEMMIQ treasury",o.optString("receiving_address")))
                        Toast.makeText(ctx,"Address copied",Toast.LENGTH_SHORT).show()
                    }){Text("Copy receiving address")}
                    OutlinedTextField(sender,{sender=it},label={Text("Your sending wallet address")},singleLine=true)
                    OutlinedButton(onClick={scope.launch{
                        try{order=pqCall(ctx,"/v21310/predict/buy/orders/${o.optInt("id")}/sender",JSONObject().put("address",sender),"POST")}catch(e:Exception){error=e.message?:"Sender error"}
                    }}){Text("Save sender address")}
                    val validHash = if (o.optString("network") == "BEP20")
                        hash.matches(Regex("^0x[0-9a-fA-F]{64}$"))
                    else hash.matches(Regex("^[0-9a-fA-F]{64}$"))
                    OutlinedTextField(hash,{hash=it.trim()},label={Text("On-chain transaction hash")},singleLine=true,
                        isError=hash.isNotBlank() && !validHash)
                    Text(if (o.optString("network") == "BEP20")
                        "BEP20: enter 0x followed by 64 hexadecimal characters."
                        else "TRC20: enter 64 hexadecimal characters. Submit is disabled until valid.",
                        color=if (hash.isNotBlank() && !validHash) MaterialTheme.colorScheme.error
                              else MaterialTheme.colorScheme.onSurfaceVariant, fontSize=11.sp)
                    Button(onClick={scope.launch{
                        try{
                            order=pqCall(ctx,"/v21310/predict/buy/orders/${o.optInt("id")}/submit",JSONObject().put("tx_hash",hash),"POST")
                            buyOpen=false;refresh()
                        }catch(e:Exception){error=e.message?:"Proof error"}
                    }},enabled=validHash && !busy){Text("Submit payment for verification")}
                }
                V21312PredictBuyStatus(paymentsEnabled=permitted)
            }},confirmButton={TextButton({buyOpen=false}){Text("Close")}})
    }
    if(showHistory){
        val entries=home?.optJSONArray("wallet_activity")
        val orders=home?.optJSONArray("orders")
        AlertDialog(onDismissRequest={showHistory=false},title={Text("Q Predict activity")},
            text={LazyColumn(Modifier.heightIn(max=430.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
                if(entries!=null)items(entries.length()){i->entries.optJSONObject(i)?.let{x->
                    Text("${x.optString("kind")} · ${x.optString("direction")} ${pqNumber(x.optDouble("amount_q"))} Q",fontSize=12.sp)
                }}
                if(orders!=null)items(orders.length()){i->orders.optJSONObject(i)?.let{x->
                    Text("${x.optString("code")} · ${x.optString("status")} · ${pqNumber(x.optDouble("expected_usdt"))} USDT",fontSize=11.sp)
                }}
            }},confirmButton={TextButton({showHistory=false}){Text("Close")}})
    }
}
