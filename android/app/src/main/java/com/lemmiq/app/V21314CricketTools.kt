/* LEMMIQ V2.13.14 — cricket performance market creator for Q Predict admins.
 * New cricket markets are Demo-only review drafts; manual scorecard verification. */
package com.lemmiq.app

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
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

private val v214Http = OkHttpClient()
private suspend fun v214Request(ctx:Context,path:String,body:JSONObject?=null):JSONObject=withContext(Dispatchers.IO){
    val base=BuildConfig.API_BASE_URL.trimEnd('/')
    val req=Request.Builder().url(base+"/v21314/cricket"+path).apply{
        SessionStore(ctx).token?.let{header("Authorization","Bearer $it")}
        if(body!=null)post(body.toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
    }.build()
    v214Http.newCall(req).execute().use{response->
        val obj=runCatching{JSONObject(response.body?.string().orEmpty())}.getOrElse{JSONObject()}
        if(!response.isSuccessful){
            val raw=obj.opt("detail")
            val err=when(raw){is String->raw; null->"HTTP ${response.code}"; else->raw.toString()}
            throw IllegalStateException(err)
        }
        obj
    }
}

private val v214Templates=listOf(
    "TEAM_INNINGS_RUNS" to "Team innings runs",
    "BATTER_RUNS" to "Batter runs",
    "BOWLER_WICKETS" to "Bowler wickets",
    "PLAYER_CENTURY" to "Any batter scores a century",
    "DAY_WICKETS" to "Test day wickets",
    "FIRST_INNINGS_LEAD" to "First-innings lead",
    "MATCH_DRAW" to "Test draw",
    "DAY_RUNS" to "Test day runs"
)
private fun v214Default(code:String)=when(code){
    "TEAM_INNINGS_RUNS"->"300"
    "BATTER_RUNS"->"50"
    "BOWLER_WICKETS"->"3"
    "PLAYER_CENTURY"->"100"
    "DAY_WICKETS"->"7"
    "DAY_RUNS"->"250"
    else->"0"
}

@Composable
fun V21314CricketAdminCard(){
    val ctx=LocalContext.current
    val scope= rememberCoroutineScope()
    var busy by remember{mutableStateOf(false)}
    var message by remember{mutableStateOf("")}
    var fixtures by remember{mutableStateOf<List<JSONObject>>(emptyList())}
    var selectedFixture by remember{mutableStateOf("")}
    var template by remember{mutableStateOf("TEAM_INNINGS_RUNS")}
    var teamA by remember{mutableStateOf("")}
    var teamB by remember{mutableStateOf("")}
    var series by remember{mutableStateOf("")}
    var format by remember{mutableStateOf("TEST")}
    var startAt by remember{mutableStateOf("")}
    var url by remember{mutableStateOf("")}
    var team by remember{mutableStateOf("")}
    var player by remember{mutableStateOf("")}
    var threshold by remember{mutableStateOf("300")}
    var innings by remember{mutableStateOf("1")}
    var day by remember{mutableStateOf("1")}
    var published by remember{mutableStateOf("")}
    val selected=fixtures.firstOrNull{it.optString("id")==selectedFixture}
    val actualFormat=selected?.optString("format")?:format
    val actualTeamA=selected?.optString("team_a")?:teamA
    val actualTeamB=selected?.optString("team_b")?:teamB
    LaunchedEffect(Unit){
        runCatching{v214Request(ctx,"/admin/fixtures")}.onSuccess{result->
            val a=result.optJSONArray("fixtures")
            fixtures=if(a==null)emptyList() else (0 until a.length()).mapNotNull{a.optJSONObject(it)}
            if(!result.optBoolean("configured",false))message="Cricket feed not configured. Manual fixture entry available."
        }.onFailure{message="Unable to load fixtures: ${it.message}"}
    }
    Card(Modifier.fillMaxWidth()){
        Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
            Text("🏏 Cricket Performance Market Studio",fontSize=17.sp,fontWeight=FontWeight.Bold)
            Text("V2.13.14 · 8 prediction templates · Demo-only · Admin review + official scorecard required",style=MaterialTheme.typography.bodySmall)
            Text("Select an upcoming authorised fixture or enter one manually",fontWeight=FontWeight.Bold,fontSize=12.sp)
            Column(verticalArrangement=Arrangement.spacedBy(4.dp)){
                FilterChip(selectedFixture.isEmpty(),onClick={selectedFixture=""},label={Text("Manual fixture")})
                fixtures.filter{it.optString("format").uppercase(Locale.US).contains("TEST")}.take(7).forEach{f->
                    val id=f.optString("id")
                    FilterChip(selectedFixture==id,onClick={
                        selectedFixture=id;format=f.optString("format");team=f.optString("team_a")
                    },label={Text("${f.optString("team_a")} vs ${f.optString("team_b")} · ${f.optString("start_at").take(10)}",fontSize=11.sp)})
                }
            }
            if(selectedFixture.isEmpty()){
                OutlinedTextField(teamA,{teamA=it},label={Text("Team A")},modifier=Modifier.fillMaxWidth(),singleLine=true)
                OutlinedTextField(teamB,{teamB=it},label={Text("Team B")},modifier=Modifier.fillMaxWidth(),singleLine=true)
                OutlinedTextField(series,{series=it},label={Text("Series name")},modifier=Modifier.fillMaxWidth(),singleLine=true)
                Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(6.dp)){
                    listOf("TEST","ODI","T20").forEach{f->FilterChip(format==f,onClick={format=f},label={Text(f)})}
                }
                OutlinedTextField(startAt,{startAt=it},label={Text("Fixture start ISO UTC (e.g. 2026-12-01T00:00:00Z)")},modifier=Modifier.fillMaxWidth())
            }
            OutlinedTextField(url,{url=it},label={Text("Verified official scorecard URL (https://)")},modifier=Modifier.fillMaxWidth())
            Text("Choose a market template",fontWeight=FontWeight.Bold,fontSize=12.sp)
            v214Templates.filter{actualFormat.uppercase(Locale.US).startsWith("TEST")||it.first !in listOf("DAY_WICKETS","FIRST_INNINGS_LEAD","MATCH_DRAW","DAY_RUNS")}.forEach{(code,title)->
                FilterChip(template==code,onClick={template=code;threshold=v214Default(code)},label={Text(title,fontSize=12.sp)})
            }
            if(template in listOf("TEAM_INNINGS_RUNS","BATTER_RUNS","BOWLER_WICKETS","PLAYER_CENTURY","FIRST_INNINGS_LEAD")){
                Text("Team",fontSize=12.sp)
                Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(6.dp)){
                    listOf(actualTeamA,actualTeamB).filter{it.isNotBlank()}.forEach{n->
                        FilterChip(team==n,onClick={team=n},label={Text(n,fontSize=11.sp)})
                    }
                }
            }
            if(template=="BATTER_RUNS"||template=="BOWLER_WICKETS"){
                OutlinedTextField(player,{player=it},label={Text("Player (verify playing XI)")},modifier=Modifier.fillMaxWidth())
            }
            if(template in listOf("TEAM_INNINGS_RUNS","BATTER_RUNS","BOWLER_WICKETS","DAY_WICKETS","DAY_RUNS"))
                OutlinedTextField(threshold,{threshold=it},label={Text("At least runs / wickets")},modifier=Modifier.fillMaxWidth())
            if(template in listOf("DAY_WICKETS","DAY_RUNS")){
                Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(6.dp)){
                    (1..5).forEach{n->FilterChip(day=="$n",onClick={day="$n"},label={Text("Day $n")})}
                }
            }
            if(template in listOf("TEAM_INNINGS_RUNS","BATTER_RUNS","BOWLER_WICKETS","PLAYER_CENTURY")){
                Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                    FilterChip(innings=="1",onClick={innings="1"},label={Text("First innings")})
                    FilterChip(innings=="2",onClick={innings="2"},label={Text("Second innings")})
                }
            }
            Button(enabled=!busy&&url.trim().startsWith("https://"),onClick={scope.launch{
                busy=true;message=""
                try{
                    val payload=JSONObject()
                        .put("match_id",selectedFixture)
                        .put("team_a",actualTeamA).put("team_b",actualTeamB)
                        .put("series",selected?.optString("series")?:series)
                        .put("format",actualFormat)
                        .put("start_at",selected?.optString("start_at")?:startAt.trim())
                        .put("official_url",url.trim())
                        .put("template",template).put("team",team).put("player",player)
                        .put("threshold",threshold.toIntOrNull()?:0)
                        .put("innings",innings.toIntOrNull()?:1).put("day",day.toIntOrNull()?:1)
                    val result=v214Request(ctx,"/admin/draft",payload)
                    published="Draft #${result.optInt("id")}: ${result.optString("question")}";
                    message="Review-only draft created. Publish from Q Predict Admin on PWA. No real-value wagering enabled."
                }catch(e:Exception){message="Draft failed: ${e.message}"}
                finally{busy=false}
            }}){Text("Create cricket review draft")}
            OutlinedButton(enabled=!busy&&url.trim().startsWith("https://"),onClick={scope.launch{
                busy=true
                try{
                    val result=v214Request(ctx,"/admin/import-tests",JSONObject()
                        .put("official_url",url.trim()).put("match_id",selectedFixture).put("max_fixtures",1))
                    message="${result.optInt("drafted")} Test markets imported for review. Check official fixture and publish manually on PWA."
                }catch(e:Exception){message="Test import failed: ${e.message}"}
                finally{busy=false}
            }}){Text("Import TEST fixture review drafts")}
            if(published.isNotBlank())Text(published,style=MaterialTheme.typography.bodySmall,fontWeight=FontWeight.Bold)
            if(message.isNotBlank())Text(message,style=MaterialTheme.typography.bodySmall)
            Text("Settlement: PWA Q Admin → Cricket Performance Market Studio, using official scorecard evidence. No automatic result verification.",style=MaterialTheme.typography.bodySmall)
        }
    }
}
