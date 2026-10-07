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
import java.util.Locale

private val P29Purple=Color(0xFF6C4DFF)
private val P29Pink=Color(0xFFFF4B9C)
private val P29Bg=Color(0xFFF7F7FB)
private val P29Ink=Color(0xFF17182A)
private val P29Muted=Color(0xFF75798D)
private val P29Yes=Color(0xFF179A65)
private val P29No=Color(0xFFD94B63)
private fun pc(v:Double)=String.format(Locale.US,"%,.2f",v).trimEnd('0').trimEnd('.')

@Composable
fun V29PredictScreen(vm:LemmiqViewModel,onAskQ:(String)->Unit){
    LaunchedEffect(Unit){vm.refreshPredict()}
    val h=vm.predictHome
    Column(Modifier.fillMaxSize().background(P29Bg)){
        Box(Modifier.fillMaxWidth().background(Brush.linearGradient(listOf(Color(0xFF17152D),Color(0xFF292157)))).padding(18.dp)){
            Column{Text("LEMMIQ Q PREDICT",color=Color(0xFFC9BFFF),fontSize=10.sp,fontWeight=FontWeight.Bold);Text("Predict what happens next.",color=Color.White,fontSize=25.sp,fontWeight=FontWeight.Black);Spacer(Modifier.height(8.dp));Text("${pc(h?.wallet?.balance_pc?:0.0)} PC",color=Color.White,fontSize=28.sp,fontWeight=FontWeight.Black);Text("Predict Credits · TEST MODE · no Q/cash conversion",color=Color(0xFFCBC7DD),fontSize=10.sp)}
        }
        LazyRow(Modifier.fillMaxWidth().padding(horizontal=12.dp,vertical=8.dp),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            items(h?.categories?:listOf("TRENDING")){cat->FilterChip(selected=vm.predictCategory==cat,onClick={vm.refreshPredict(cat)},label={Text(cat.replace("TECH_AI","Tech & AI").lowercase().replaceFirstChar{it.uppercase()},fontSize=10.sp)})}
        }
        if(vm.predictBusy)LinearProgressIndicator(Modifier.fillMaxWidth(),color=P29Purple)
        LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(12.dp,4.dp,12.dp,100.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
            item{Surface(color=Color(0xFFEEE9FF),shape=RoundedCornerShape(14.dp)){Text(h?.notice?:"Predict Credits are test-only.",Modifier.padding(11.dp),fontSize=10.sp,color=P29Muted)}}
            if((h?.live?:emptyList()).isEmpty())item{Card(shape=RoundedCornerShape(20.dp)){Column(Modifier.padding(20.dp)){Text("No live markets yet",fontWeight=FontWeight.Bold);Text("Q Predict Agent drafts markets for Admin approval.",color=P29Muted,fontSize=11.sp)}}}
            items(h?.live?:emptyList(),key={it.id}){m->PredictCard(m){vm.openPredictMarket(m.id)}}
        }
    }
    vm.predictSelected?.let{m->PredictDetail(vm,m,onAskQ)}
}

@Composable
private fun PredictCard(m:PredictMarketDto,onOpen:()->Unit){
    Card(Modifier.fillMaxWidth().clickable(onClick=onOpen),shape=RoundedCornerShape(20.dp),colors=CardDefaults.cardColors(containerColor=Color.White)){
        Column(Modifier.padding(15.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text(m.category.replace("TECH_AI","TECH & AI"),fontSize=9.sp,fontWeight=FontWeight.Bold,color=P29Purple);Spacer(Modifier.weight(1f));Text("${m.participants} predictors",fontSize=9.sp,color=P29Muted)}
            Text(m.question,fontWeight=FontWeight.Black,fontSize=16.sp,maxLines=3,overflow=TextOverflow.Ellipsis)
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){PredictionPill("YES",m.yes_percent,P29Yes,Modifier.weight(1f));PredictionPill("NO",m.no_percent,P29No,Modifier.weight(1f))}
            LinearProgressIndicator(progress={ (m.yes_percent/100.0).toFloat().coerceIn(0f,1f)},modifier=Modifier.fillMaxWidth(),color=P29Purple,trackColor=Color(0xFFFFDCE9))
            Row(Modifier.fillMaxWidth()){Text("${pc(m.pool_pc)} PC pool",fontSize=10.sp,color=P29Muted);Spacer(Modifier.weight(1f));Text("${m.comments} comments",fontSize=10.sp,color=P29Muted)}
            if(m.my_positions.isNotEmpty())Text("Your position · "+m.my_positions.joinToString(" · "){"${it.outcome} ${pc(it.stake_pc)} PC"},fontSize=10.sp,color=P29Purple,fontWeight=FontWeight.Bold)
        }
    }
}

@Composable private fun PredictionPill(label:String,value:Double,color:Color,modifier:Modifier=Modifier){
    Surface(modifier,shape=RoundedCornerShape(13.dp),color=color.copy(alpha=.09f)){Row(Modifier.padding(horizontal=12.dp,vertical=10.dp),verticalAlignment=Alignment.CenterVertically){Text(label,color=color,fontSize=10.sp,fontWeight=FontWeight.Bold);Spacer(Modifier.weight(1f));Text("${value.toInt()}%",fontSize=20.sp,fontWeight=FontWeight.Black,color=P29Ink)}}
}

@Composable
private fun PredictDetail(vm:LemmiqViewModel,m:PredictMarketDto,onAskQ:(String)->Unit){
    var amount by remember(m.id){mutableStateOf("100")}
    var comment by remember(m.id){mutableStateOf("")}
    AlertDialog(onDismissRequest={vm.closePredictMarket()},title={Text("Q Predict")},text={
        LazyColumn(Modifier.heightIn(max=620.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
            item{Text(m.question,fontWeight=FontWeight.Black,fontSize=20.sp)}
            item{Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){PredictionPill("YES",m.yes_percent,P29Yes,Modifier.weight(1f));PredictionPill("NO",m.no_percent,P29No,Modifier.weight(1f))}}
            item{Text("${pc(m.pool_pc)} PC pool · ${m.participants} predictors",fontSize=11.sp,color=P29Muted)}
            if(m.status=="LIVE")item{OutlinedTextField(amount,{amount=it.filter{ch->ch.isDigit()||ch=='.'}},label={Text("Predict Credits")},singleLine=true,modifier=Modifier.fillMaxWidth());Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){Button(onClick={vm.stakePredict(m.id,"YES",amount.toDoubleOrNull()?:0.0)},modifier=Modifier.weight(1f),colors=ButtonDefaults.buttonColors(containerColor=P29Yes)){Text("Predict YES")};Button(onClick={vm.stakePredict(m.id,"NO",amount.toDoubleOrNull()?:0.0)},modifier=Modifier.weight(1f),colors=ButtonDefaults.buttonColors(containerColor=P29No)){Text("Predict NO")}}}
            item{OutlinedButton(onClick={onAskQ("Analyse both sides of this Q Predict market: ${m.question}. Resolution rule: ${m.resolution_rule}");vm.closePredictMarket()},modifier=Modifier.fillMaxWidth()){Text("Q · Analyse this market")}}
            item{Text("Resolution",fontWeight=FontWeight.Bold);Text(m.resolution_rule,fontSize=11.sp,color=P29Muted);Text("Source: ${m.resolution_source_name}",fontSize=10.sp,color=P29Muted)}
            if(m.my_positions.isNotEmpty())item{Text("Your position",fontWeight=FontWeight.Bold);m.my_positions.forEach{Text("${it.outcome} · ${pc(it.stake_pc)} PC · ${it.status}",fontSize=11.sp)}}
            item{Text("Discussion · ${m.comments}",fontWeight=FontWeight.Bold);OutlinedTextField(comment,{comment=it},label={Text("Share your reasoning")},modifier=Modifier.fillMaxWidth());TextButton(onClick={vm.commentPredict(m.id,comment);comment=""},enabled=comment.isNotBlank()){Text("Post comment")}}
            items(m.discussion,key={it.id}){c->Column(Modifier.fillMaxWidth().padding(vertical=5.dp)){Text(c.user?.display_name?:c.user?.username?:"User",fontWeight=FontWeight.Bold,fontSize=11.sp);Text(c.text,fontSize=11.sp);HorizontalDivider(Modifier.padding(top=7.dp))}}
        }
    },confirmButton={TextButton(onClick={vm.closePredictMarket()}){Text("Close")}},dismissButton={TextButton(onClick={vm.watchPredict(m.id)}){Text(if(m.watched)"★ Watching" else "☆ Watch")}})
}
