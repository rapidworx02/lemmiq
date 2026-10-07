package com.lemmiq.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private val P29Purple=Color(0xFF6C4DFF)
private val P29Pink=Color(0xFFFF4B9C)
private val P29Bg=Color(0xFFF7F7FB)
private val P29Ink=Color(0xFF17182A)
private val P29Muted=Color(0xFF75798D)
private val P29Yes=Color(0xFF179A65)
private val P29No=Color(0xFFD94B63)
private fun pc(v:Double)=String.format(Locale.US,"%,.2f",v).trimEnd('0').trimEnd('.')

private fun predictTime(raw:String):String{
    if(raw.isBlank())return "Not set"
    return runCatching{
        OffsetDateTime.parse(raw).format(DateTimeFormatter.ofPattern("d MMM yyyy, h:mm a z",Locale.getDefault()))
    }.getOrElse{raw.replace('T',' ').replace("Z"," UTC")}
}

private fun displayQuestion(m:PredictMarketDto):String{
    val phrase="at the Q Predict resolution time"
    return if(m.question.contains(phrase,ignoreCase=true) && m.resolve_after.isNotBlank())
        m.question.replace(phrase,"at ${predictTime(m.resolve_after)}",ignoreCase=true)
    else m.question
}

@Composable
fun V29PredictScreen(vm:LemmiqViewModel,onAskQ:(String)->Unit){
    LaunchedEffect(Unit){vm.refreshPredict()}
    val h=vm.predictHome
    var resultsOpen by remember{mutableStateOf(false)}
    var mineOpen by remember{mutableStateOf(false)}
    var leadersOpen by remember{mutableStateOf(false)}

    Column(Modifier.fillMaxSize().background(P29Bg)){
        Box(Modifier.fillMaxWidth().background(Brush.linearGradient(listOf(Color(0xFF17152D),Color(0xFF292157)))).padding(18.dp)){
            Column{
                Text("LEMMIQ Q PREDICT",color=Color(0xFFC9BFFF),fontSize=10.sp,fontWeight=FontWeight.Bold)
                Text("Predict what happens next.",color=Color.White,fontSize=25.sp,fontWeight=FontWeight.Black)
                Spacer(Modifier.height(8.dp))
                Text("${pc(h?.wallet?.balance_pc?:0.0)} PC",color=Color.White,fontSize=28.sp,fontWeight=FontWeight.Black)
                Text("Predict Credits · TEST MODE · no Q/cash conversion",color=Color(0xFFCBC7DD),fontSize=10.sp)
            }
        }
        LazyRow(Modifier.fillMaxWidth().padding(horizontal=12.dp,vertical=8.dp),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            items(h?.categories?:listOf("TRENDING")){cat->FilterChip(selected=vm.predictCategory==cat,onClick={vm.refreshPredict(cat)},label={Text(cat.replace("TECH_AI","Tech & AI").lowercase().replaceFirstChar{it.uppercase()},fontSize=10.sp)})}
        }
        Row(Modifier.fillMaxWidth().padding(horizontal=12.dp,vertical=2.dp),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            OutlinedButton({mineOpen=true},Modifier.weight(1f),contentPadding=PaddingValues(horizontal=5.dp)){Text("My predictions",fontSize=10.sp)}
            OutlinedButton({resultsOpen=true},Modifier.weight(1f),contentPadding=PaddingValues(horizontal=5.dp)){Text("Recent results",fontSize=10.sp)}
            OutlinedButton({leadersOpen=true;vm.loadPredictLeaderboard()},Modifier.weight(1f),contentPadding=PaddingValues(horizontal=5.dp)){Text("Leaderboard",fontSize=10.sp)}
        }
        if(vm.predictBusy)LinearProgressIndicator(Modifier.fillMaxWidth(),color=P29Purple)
        LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(12.dp,4.dp,12.dp,100.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
            item{Surface(color=Color(0xFFEEE9FF),shape=RoundedCornerShape(14.dp)){Text(h?.notice?:"Predict Credits are test-only.",Modifier.padding(11.dp),fontSize=10.sp,color=P29Muted)}}
            if((h?.live?:emptyList()).isEmpty())item{Card(shape=RoundedCornerShape(20.dp)){Column(Modifier.padding(20.dp)){Text("No live markets yet",fontWeight=FontWeight.Bold);Text("Q Predict Agent drafts markets for Admin approval.",color=P29Muted,fontSize=11.sp)}}}
            items(h?.live?:emptyList(),key={it.id}){m->PredictCard(m){vm.openPredictMarket(m.id)}}
        }
    }
    vm.predictSelected?.let{m->PredictDetail(vm,m)}

    if(resultsOpen)PredictMarketListDialog("Recent results",h?.resolved?:emptyList(),onClose={resultsOpen=false},onOpen={resultsOpen=false;vm.openPredictMarket(it.id)})
    if(mineOpen){
        val mine=(h?.live.orEmpty()+h?.resolved.orEmpty()).filter{it.my_positions.isNotEmpty()}
        PredictMarketListDialog("My predictions",mine,onClose={mineOpen=false},onOpen={mineOpen=false;vm.openPredictMarket(it.id)})
    }
    if(leadersOpen)PredictLeaderboardDialog(vm,onClose={leadersOpen=false})
}

@Composable
private fun PredictCard(m:PredictMarketDto,onOpen:()->Unit){
    Card(Modifier.fillMaxWidth().clickable(onClick=onOpen),shape=RoundedCornerShape(20.dp),colors=CardDefaults.cardColors(containerColor=Color.White)){
        Column(Modifier.padding(15.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text(m.category.replace("TECH_AI","TECH & AI"),fontSize=9.sp,fontWeight=FontWeight.Bold,color=P29Purple);Spacer(Modifier.weight(1f));Text("${m.participants} predictors",fontSize=9.sp,color=P29Muted)}
            Text(displayQuestion(m),fontWeight=FontWeight.Black,fontSize=16.sp,maxLines=3,overflow=TextOverflow.Ellipsis)
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){PredictionPill("YES",m.yes_percent,P29Yes,Modifier.weight(1f));PredictionPill("NO",m.no_percent,P29No,Modifier.weight(1f))}
            LinearProgressIndicator(progress={ (m.yes_percent/100.0).toFloat().coerceIn(0f,1f)},modifier=Modifier.fillMaxWidth(),color=P29Purple,trackColor=Color(0xFFFFDCE9))
            Row(Modifier.fillMaxWidth()){Text("${pc(m.pool_pc)} PC pool",fontSize=10.sp,color=P29Muted);Spacer(Modifier.weight(1f));Text("${m.comments} comments",fontSize=10.sp,color=P29Muted)}
            if(m.close_at.isNotBlank())Text("Closes ${predictTime(m.close_at)}",fontSize=9.sp,color=P29Muted)
            if(m.my_positions.isNotEmpty())Text("Your position · "+m.my_positions.joinToString(" · "){"${it.outcome} ${pc(it.stake_pc)} PC"},fontSize=10.sp,color=P29Purple,fontWeight=FontWeight.Bold)
        }
    }
}

@Composable private fun PredictionPill(label:String,value:Double,color:Color,modifier:Modifier=Modifier){
    Surface(modifier,shape=RoundedCornerShape(13.dp),color=color.copy(alpha=.09f)){Row(Modifier.padding(horizontal=12.dp,vertical=10.dp),verticalAlignment=Alignment.CenterVertically){Text(label,color=color,fontSize=10.sp,fontWeight=FontWeight.Bold);Spacer(Modifier.weight(1f));Text("${value.toInt()}%",fontSize=20.sp,fontWeight=FontWeight.Black,color=P29Ink)}}
}

@Composable
private fun PredictDetail(vm:LemmiqViewModel,m:PredictMarketDto){
    var amount by remember(m.id){mutableStateOf("100")}
    var comment by remember(m.id){mutableStateOf("")}
    var followUp by remember(m.id){mutableStateOf("")}
    val analysis=if(vm.predictAnalysisMarketId==m.id)vm.predictAnalysis else null
    AlertDialog(onDismissRequest={vm.clearPredictAnalysis();vm.closePredictMarket()},title={Text("Q Predict")},text={
        LazyColumn(Modifier.heightIn(max=650.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
            item{Text(displayQuestion(m),fontWeight=FontWeight.Black,fontSize=20.sp)}
            item{Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){PredictionPill("YES",m.yes_percent,P29Yes,Modifier.weight(1f));PredictionPill("NO",m.no_percent,P29No,Modifier.weight(1f))}}
            item{Text("${pc(m.pool_pc)} PC pool · ${m.participants} predictors",fontSize=11.sp,color=P29Muted)}
            if(m.participants<=2)item{Text("Crowd percentages are based on only ${m.participants} predictor${if(m.participants==1)"" else "s"}; they are not Q's probability estimate.",fontSize=10.sp,color=P29Muted)}
            if(m.status=="LIVE")item{OutlinedTextField(amount,{amount=it.filter{ch->ch.isDigit()||ch=='.'}},label={Text("Predict Credits")},singleLine=true,modifier=Modifier.fillMaxWidth());Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){Button(onClick={vm.stakePredict(m.id,"YES",amount.toDoubleOrNull()?:0.0)},modifier=Modifier.weight(1f),colors=ButtonDefaults.buttonColors(containerColor=P29Yes)){Text("Predict YES")};Button(onClick={vm.stakePredict(m.id,"NO",amount.toDoubleOrNull()?:0.0)},modifier=Modifier.weight(1f),colors=ButtonDefaults.buttonColors(containerColor=P29No)){Text("Predict NO")}}}
            item{
                OutlinedButton(onClick={vm.analysePredictMarket(m)},modifier=Modifier.fillMaxWidth(),enabled=!vm.predictAnalysisBusy){
                    Text(if(vm.predictAnalysisBusy&&vm.predictAnalysisMarketId==m.id)"Q is analysing…" else "Q · Analyse this market")
                }
            }
            if(vm.predictAnalysisBusy&&vm.predictAnalysisMarketId==m.id)item{LinearProgressIndicator(Modifier.fillMaxWidth(),color=P29Purple)}
            if(analysis!=null)item{
                Surface(color=Color(0xFFF1EDFF),shape=RoundedCornerShape(16.dp)){
                    Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                        Text("Q Market Analysis",fontWeight=FontWeight.Black,color=P29Ink)
                        Text(analysis.answer,fontSize=12.sp,color=P29Ink)
                        if(analysis.references.isNotEmpty()){
                            Text("Evidence / references",fontWeight=FontWeight.Bold,fontSize=11.sp)
                            analysis.references.take(5).forEach{r->Text("• ${r.contact}: ${r.text}",fontSize=10.sp,color=P29Muted)}
                        }
                        Text("Q analysis is informational. It never controls market settlement.",fontSize=9.sp,color=P29Muted)
                        OutlinedTextField(followUp,{followUp=it},label={Text("Ask Q about this market…")},modifier=Modifier.fillMaxWidth())
                        Button(onClick={vm.analysePredictMarket(m,followUp);followUp=""},enabled=followUp.isNotBlank()&&!vm.predictAnalysisBusy,modifier=Modifier.fillMaxWidth()){Text("Ask Q")}
                    }
                }
            }
            item{
                Text("Market timing",fontWeight=FontWeight.Bold)
                Text("Prediction closes: ${predictTime(m.close_at)}",fontSize=11.sp,color=P29Muted)
                Text("Resolution: ${predictTime(m.resolve_after)}",fontSize=11.sp,color=P29Muted)
                Text("Source: ${m.resolution_source_name}",fontSize=11.sp,color=P29Muted)
                Text("Resolution rule: ${m.resolution_rule}",fontSize=11.sp,color=P29Muted)
            }
            m.resolution?.let{r->item{Surface(color=Color(0xFFE9F8F0),shape=RoundedCornerShape(14.dp)){Column(Modifier.padding(12.dp)){Text("Result · ${r.outcome}",fontWeight=FontWeight.Black);Text("Resolved ${predictTime(r.resolved_at)}",fontSize=10.sp,color=P29Muted);if(r.source_value.isNotBlank())Text("Source value: ${r.source_value}",fontSize=10.sp);if(r.note.isNotBlank())Text(r.note,fontSize=10.sp)}}}}
            if(m.my_positions.isNotEmpty())item{Text("Your position",fontWeight=FontWeight.Bold);m.my_positions.forEach{Text("${it.outcome} · ${pc(it.stake_pc)} PC · ${it.status}${if(it.payout_pc>0)" · payout ${pc(it.payout_pc)} PC" else ""}",fontSize=11.sp)}}
            item{Text("Discussion · ${m.comments}",fontWeight=FontWeight.Bold);OutlinedTextField(comment,{comment=it},label={Text("Share your reasoning")},modifier=Modifier.fillMaxWidth());TextButton(onClick={vm.commentPredict(m.id,comment);comment=""},enabled=comment.isNotBlank()){Text("Post comment")}}
            items(m.discussion,key={it.id}){c->Column(Modifier.fillMaxWidth().padding(vertical=5.dp)){Text(c.user?.display_name?:c.user?.username?:"User",fontWeight=FontWeight.Bold,fontSize=11.sp);Text(c.text,fontSize=11.sp);HorizontalDivider(Modifier.padding(top=7.dp))}}
        }
    },confirmButton={TextButton(onClick={vm.clearPredictAnalysis();vm.closePredictMarket()}){Text("Close")}},dismissButton={TextButton(onClick={vm.watchPredict(m.id)}){Text(if(m.watched)"★ Watching" else "☆ Watch")}})
}

@Composable
private fun PredictMarketListDialog(title:String,markets:List<PredictMarketDto>,onClose:()->Unit,onOpen:(PredictMarketDto)->Unit){
    AlertDialog(onDismissRequest=onClose,title={Text(title)},text={
        if(markets.isEmpty())Text("Nothing to show yet.",color=P29Muted)
        else LazyColumn(Modifier.heightIn(max=500.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            items(markets,key={it.id}){m->
                Card(Modifier.fillMaxWidth().clickable{onOpen(m)},shape=RoundedCornerShape(14.dp)){
                    Column(Modifier.padding(12.dp),verticalArrangement=Arrangement.spacedBy(4.dp)){
                        Text(displayQuestion(m),fontWeight=FontWeight.Bold,fontSize=12.sp)
                        Text("${m.status}${m.result?.let{" · $it"}?:""}",fontSize=10.sp,color=if(m.result=="YES")P29Yes else if(m.result=="NO")P29No else P29Muted)
                        m.resolution?.resolved_at?.takeIf{it.isNotBlank()}?.let{Text("Resolved ${predictTime(it)}",fontSize=9.sp,color=P29Muted)}
                        if(m.my_positions.isNotEmpty())Text("Your position: "+m.my_positions.joinToString{"${it.outcome} ${pc(it.stake_pc)} PC${if(it.payout_pc>0)" → ${pc(it.payout_pc)} PC" else ""}"},fontSize=9.sp,color=P29Purple)
                    }
                }
            }
        }
    },confirmButton={TextButton(onClose){Text("Close")}})
}

@Composable
private fun PredictLeaderboardDialog(vm:LemmiqViewModel,onClose:()->Unit){
    AlertDialog(onDismissRequest=onClose,title={Text("Q Predict leaderboard")},text={
        if(vm.predictLeaderboard.isEmpty())Text("Leaderboard will appear after resolved markets.",color=P29Muted)
        else LazyColumn(Modifier.heightIn(max=500.dp)){
            items(vm.predictLeaderboard,key={it.rank}){r->
                Row(Modifier.fillMaxWidth().padding(vertical=8.dp),verticalAlignment=Alignment.CenterVertically){
                    Text("#${r.rank}",fontWeight=FontWeight.Black,modifier=Modifier.width(42.dp))
                    Column(Modifier.weight(1f)){Text(r.user?.display_name?:r.user?.username?:"User",fontWeight=FontWeight.Bold);Text("${r.accuracy_percent.toInt()}% accuracy · ${r.resolved} resolved",fontSize=10.sp,color=P29Muted)}
                    Text("${pc(r.net_won_pc)} PC",fontSize=10.sp,color=P29Purple)
                }
            }
        }
    },confirmButton={TextButton(onClose){Text("Close")}})
}
