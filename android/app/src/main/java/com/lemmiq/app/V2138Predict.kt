// V2138_COMBINED - Demo USDT Q Predict. Real USDT operations are intentionally locked.
package com.lemmiq.app

import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.ClickableText
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.Locale
import java.util.UUID

private val predictClientV2138=OkHttpClient()
private fun formatDemoV2138(value:Double):String=String.format(Locale.US,"%,.2f",value)

private suspend fun predictApiV2138(ctx:Context,path:String,body:JSONObject?=null):JSONObject=withContext(Dispatchers.IO){
    val url=BuildConfig.API_BASE_URL.trimEnd('/')+path
    val builder=Request.Builder().url(url).apply{
        SessionStore(ctx).token?.let{header("Authorization","Bearer $it")}
    }
    if(body!=null)builder.post(body.toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
    val request=builder.build()
    predictClientV2138.newCall(request).execute().use{response->
        val str=response.body?.string().orEmpty()
        val json=runCatching{JSONObject(str)}.getOrElse{JSONObject()}
        if(!response.isSuccessful)throw IllegalStateException(json.optString("detail","HTTP ${response.code}"))
        json
    }
}

@Composable
fun V2138PredictScreen(){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var home by remember{mutableStateOf<JSONObject?>(null)}
    var admin by remember{mutableStateOf<JSONObject?>(null)}
    var busy by remember{mutableStateOf(false)}
    var message by remember{mutableStateOf("")}
    var selected by remember{mutableStateOf<JSONObject?>(null)}
    var amount by remember{mutableStateOf("10")}
    var requestedReal by remember{mutableStateOf(false)}
    var grant by remember{mutableStateOf("1000")}
    var fee by remember{mutableStateOf("10")}
    var depositFee by remember{mutableStateOf("1")}
    var withdrawalFee by remember{mutableStateOf("1")}
    fun refresh(){scope.launch{
        busy=true
        try{
            home=predictApiV2138(ctx,"/v2138/predict/home")
            admin=runCatching{predictApiV2138(ctx,"/v2138/predict/admin/config")}.getOrNull()
            admin?.let{
                requestedReal=it.optString("requested_mode")=="REAL_PENDING"
                grant=it.optString("demo_starting_credit","1000")
                fee=it.optString("profit_fee_percent","10")
                depositFee=it.optString("deposit_fee","1")
                withdrawalFee=it.optString("withdrawal_fee","1")
            }
            message=""
        }catch(e:Exception){message=e.message?:"Unable to load Demo USDT wallet"}
        finally{busy=false}
    }}
    LaunchedEffect(Unit){refresh()}
    val markets=remember(home){val a=home?.optJSONArray("markets");if(a==null)emptyList() else (0 until a.length()).mapNotNull{a.optJSONObject(it)}}
    val history=remember(home){val a=home?.optJSONArray("history");if(a==null)emptyList() else (0 until a.length()).mapNotNull{a.optJSONObject(it)}}
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(horizontal=13.dp,vertical=10.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{
            Card(colors=CardDefaults.cardColors(containerColor=Color(0xFF262058)),shape=RoundedCornerShape(20.dp)){
                Column(Modifier.fillMaxWidth().padding(20.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
                    Text("LEMMIQ · Q PREDICT",color=Color(0xFFE0D9FF),fontSize=12.sp,fontWeight=FontWeight.Bold)
                    Text("Demo Mode",color=Color.White,fontSize=25.sp,fontWeight=FontWeight.Black)
                    Text("${formatDemoV2138(home?.optDouble("available",0.0)?:0.0)} Demo USDT",color=Color.White,fontSize=29.sp,fontWeight=FontWeight.Bold)
                    Text("Locked: ${formatDemoV2138(home?.optDouble("locked",0.0)?:0.0)} · Virtual credits have no cash value.",color=Color(0xFFDFDAFB),fontSize=11.sp)
                    Text("Real USDT: LOCKED · No deposits or withdrawals",color=Color(0xFFFFD7D7),fontSize=11.sp)
                    OutlinedButton(onClick={refresh()}){Text("Refresh Demo Wallet",color=Color.White)}
                }
            }
        }
        if(busy)item{LinearProgressIndicator(Modifier.fillMaxWidth())}
        if(message.isNotBlank())item{Text(message,color=Color(0xFFB42318),fontSize=12.sp)}
        item{V2137CricketFixtures()}
        item{Text("Open demo prediction markets",fontSize=19.sp,fontWeight=FontWeight.Bold)}
        if(markets.isEmpty())item{
            Card{Text("No live markets yet. Q Predict Admin must review and publish fixture drafts before Demo USDT predictions can be placed.",Modifier.padding(16.dp),fontSize=13.sp)}
        }
        items(markets,key={it.optInt("id")}){market->
            Card(Modifier.fillMaxWidth().clickable{selected=market}){
                Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                    Text(market.optString("category","SPORTS"),fontSize=10.sp,color=Color(0xFF6C4DFF),fontWeight=FontWeight.Bold)
                    Text(market.optString("question"),fontSize=15.sp,fontWeight=FontWeight.Bold)
                    Text("Demo pool ${formatDemoV2138(market.optDouble("yes_pool")+market.optDouble("no_pool"))}",fontSize=11.sp)
                    OutlinedButton(onClick={selected=market}){Text("Predict YES / NO")}
                }
            }
        }
        item{Text("Recent demo wallet activity",fontWeight=FontWeight.Bold)}
        items(history.take(12)){entry->
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){
                Text(entry.optString("kind"),fontSize=12.sp)
                Text("${entry.optString("direction")} ${formatDemoV2138(entry.optDouble("amount"))}",fontSize=12.sp)
            }
        }
        if(admin!=null){
            item{HorizontalDivider();Text("Master Admin · Demo / Real Mode",fontSize=19.sp,fontWeight=FontWeight.Bold)}
            item{
                Card{Column(Modifier.fillMaxWidth().padding(15.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
                    Text("Effective mode: DEMO",fontWeight=FontWeight.Bold)
                    Text("Real Mode is locked in this release. A request cannot activate USDT deposits, withdrawals or betting.",fontSize=12.sp)
                    Row{Checkbox(checked=requestedReal,onCheckedChange={requestedReal=it});Text("Request Real Mode for future review",Modifier.padding(top=12.dp),fontSize=12.sp)}
                    OutlinedTextField(grant,{grant=it},label={Text("New user Demo USDT grant")},modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(fee,{fee=it},label={Text("Winning profit fee (%)")},modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(depositFee,{depositFee=it},label={Text("Future deposit fee (USDT)")},modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(withdrawalFee,{withdrawalFee=it},label={Text("Future withdrawal fee (USDT)")},modifier=Modifier.fillMaxWidth())
                    Button(onClick={scope.launch{
                        busy=true
                        try{
                            val payload=JSONObject().put("requested_mode",if(requestedReal)"REAL" else "DEMO")
                              .put("grant",grant.toDouble()).put("profit_fee_percent",fee.toDouble())
                              .put("deposit_fee",depositFee.toDouble()).put("withdrawal_fee",withdrawalFee.toDouble())
                            predictApiV2138(ctx,"/v2138/predict/admin/config",payload)
                            message="Admin settings saved. Real Mode remains LOCKED."
                        }catch(e:Exception){message=e.message?:"Update failed"}
                        finally{busy=false}
                    }},enabled=!busy){Text("Save Demo / Real settings")}
                    OutlinedButton(onClick={scope.launch{
                        busy=true
                        try{val r=predictApiV2138(ctx,"/v2137/cricket/admin/draft",JSONObject());message="${r.optInt("drafted",0)} cricket market draft(s) imported for review."}
                        catch(e:Exception){message="Import failed: ${e.message}"}finally{busy=false}
                    }},enabled=!busy){Text("Import cricket review drafts")}
                }}
            }
        }
        item{Spacer(Modifier.height(90.dp))}
    }
    selected?.let{m->
        AlertDialog(onDismissRequest={selected=null},title={Text("Demo prediction")},
            text={Column(verticalArrangement=Arrangement.spacedBy(10.dp)){
                Text(m.optString("question"),fontWeight=FontWeight.Bold)
                Text("Virtual credits only. Not redeemable, transferable or cryptocurrency.",fontSize=12.sp)
                OutlinedTextField(amount,{amount=it},label={Text("Stake (1–250 Demo USDT)")})
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    listOf("YES","NO").forEach{side->
                        Button(onClick={scope.launch{
                            busy=true
                            try{
                                val a=amount.toDoubleOrNull()?:0.0
                                require(a>=1&&a<=250&&kotlin.math.round(a*100)==a*100){"Enter 1–250 with up to two decimal places"}
                                val body=JSONObject().put("market_id",m.optInt("id")).put("outcome",side)
                                    .put("amount",a).put("request_key",UUID.randomUUID().toString().replace("-","_"))
                                predictApiV2138(ctx,"/v2138/predict/demo/stake",body)
                                selected=null;message="Demo prediction placed";refresh()
                            }catch(e:Exception){message=e.message?:"Prediction failed"}
                            finally{busy=false}
                        }},enabled=!busy){Text(side)}
                    }
                }
            }},confirmButton={TextButton(onClick={selected=null}){Text("Close")}})
    }
}

/** Safe plain-text http(s) links inside user messages. */
@Composable
fun V2138LinkedText(text:String,color:Color){
    val uri=LocalUriHandler.current
    val regex=remember{Regex("""(?:https?://|www\.)[^\s<>\"']+""",RegexOption.IGNORE_CASE)}
    val display=remember(text){
        buildAnnotatedString{
            var from=0
            regex.findAll(text).forEach{m->
                val cleaned=m.value.trimEnd('.',',',':',';','!', '?', ')',']','}')
                if(cleaned.isNotEmpty()){
                    append(text.substring(from,m.range.first))
                    val target=if(cleaned.startsWith("www.",true))"https://$cleaned" else cleaned
                    if(target.startsWith("https://",true)||target.startsWith("http://",true)){
                        pushStringAnnotation("URL",target)
                        pushStyle(SpanStyle(color=Color(0xFF169CD6),textDecoration=TextDecoration.Underline))
                        append(cleaned)
                        pop();pop()
                        append(m.value.substring(cleaned.length))
                    }else append(m.value)
                    from=m.range.last+1
                }
            }
            append(text.substring(from))
        }
    }
    ClickableText(text=display,style=TextStyle(color=color,fontSize=14.sp),onClick={offset->
        display.getStringAnnotations("URL",offset,offset).firstOrNull()?.let{link->
            runCatching{uri.openUri(link.item)}
        }
    })
}
