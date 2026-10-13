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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.net.Uri
import java.util.Locale
import java.time.OffsetDateTime
import java.time.ZoneOffset

private val Q28Bg=Color(0xFFF7F7FB)
private val Q28Purple=Color(0xFF6F52ED)
private val Q28Muted=Color(0xFF6D7285)
private val Q28Mint=Color(0xFF179A65)

private fun q28Q(v:Double)=String.format(Locale.US,"%,.2f",v).trimEnd('0').trimEnd('.')
private fun q28Usd(v:Double)=String.format(Locale.US,"US$%,.2f",v)

@Composable
fun V28QEconomyScreen(vm:LemmiqViewModel){
    var tab by remember{mutableIntStateOf(0)}
    var buyPlan by remember{mutableStateOf<QPlanDto?>(null)}
    var disputeOrder by remember{mutableStateOf<QMarketOrderDto?>(null)}
    LaunchedEffect(Unit){vm.refreshQEconomy()}

    Column(Modifier.fillMaxSize().background(Q28Bg)){
        val w=vm.qWallet
        Surface(color=Color(0xFF15142A),modifier=Modifier.fillMaxWidth()){
            Column(Modifier.padding(18.dp)){
                Text("LEMMIQ Q",color=Color(0xFFC9BFFF),fontSize=11.sp,fontWeight=FontWeight.Bold)
                Text("Q Economy",color=Color.White,fontSize=28.sp,fontWeight=FontWeight.Black)
                Spacer(Modifier.height(8.dp))
                Text("${q28Q(w?.balance_q?:0.0)} Q",color=Color.White,fontSize=30.sp,fontWeight=FontWeight.Black)
                Text("≈ ${q28Usd(w?.balance_usd_reference?:0.0)} reference · 1 Q ≈ ${q28Usd(w?.q_reference_usd?:0.05)}",color=Color(0xFFC4C1D2),fontSize=11.sp)
                Text(
                    if(vm.qWithdrawalConfig.enabled)"Q → USDT withdrawal is available" else "Q → USDT withdrawal is currently OFF",
                    color=if(vm.qWithdrawalConfig.enabled)Color(0xFF77E1B7) else Color(0xFFFFC763),fontSize=10.sp,modifier=Modifier.padding(top=5.dp)
                )
            }
        }
        LazyRow(Modifier.fillMaxWidth().padding(horizontal=8.dp,vertical=8.dp),horizontalArrangement=Arrangement.spacedBy(6.dp),contentPadding=PaddingValues(end=8.dp)){
            items(listOf("Wallet","Packages","Market","Refer","Activity")){label->
                val i=listOf("Wallet","Packages","Market","Refer","Activity").indexOf(label)
                FilterChip(selected=tab==i,onClick={tab=i},label={Text(label,fontSize=11.sp,maxLines=1)},modifier=Modifier.widthIn(min=92.dp))
            }
        }
        if(vm.qEconomyBusy)LinearProgressIndicator(Modifier.fillMaxWidth(),color=Q28Purple)
        vm.error?.takeIf{it.isNotBlank()}?.let{msg->
            Surface(color=Color(0xFFFFE8EC),modifier=Modifier.fillMaxWidth()){Text(msg,Modifier.padding(horizontal=14.dp,vertical=8.dp),color=Color(0xFFA2263B),fontSize=10.sp)}
        }
        Box(Modifier.weight(1f)){
            when(tab){
                0->Q28WalletTab(vm)
                1->Q28PackagesTab(vm){buyPlan=it}
                2->Q28MarketTab(vm){disputeOrder=it}
                3->Q28ReferralTab(vm)
                else->Q28ActivityTab(vm)
            }
        }
    }

    buyPlan?.let{p->
        AlertDialog(
            onDismissRequest={buyPlan=null},
            title={Text(p.name)},
            text={Column{
                Text("Pay ${p.price_usd.toInt()} USDT. Select the exact network you will use.")
                Spacer(Modifier.height(8.dp))
                Text("Package rate: ${p.daily_rate_percent}% daily · 200% package ceiling · 365-day validity",fontSize=12.sp,color=Q28Muted)
                Spacer(Modifier.height(16.dp))
                Button(onClick={buyPlan=null;vm.qCreatePaymentOrder(p.code,"TRC20")},modifier=Modifier.fillMaxWidth()){Text("USDT TRC20")}
                Spacer(Modifier.height(9.dp))
                OutlinedButton(onClick={buyPlan=null;vm.qCreatePaymentOrder(p.code,"BEP20")},modifier=Modifier.fillMaxWidth()){Text("USDT BEP20")}
                Spacer(Modifier.height(10.dp))
                Text("⚠ Send only on the selected network. Sending on another network may result in loss of funds.",fontSize=10.sp,color=Color(0xFFB7791F))
            }},
            confirmButton={},
            dismissButton={TextButton(onClick={buyPlan=null}){Text("Cancel")}}
        )
    }

    vm.activeQPaymentOrder?.let{o->Q28PaymentDialog(vm,o)}
    disputeOrder?.let{o->
        var note by remember(o.id){mutableStateOf("")}
        AlertDialog(
            onDismissRequest={disputeOrder=null},
            title={Text("Open marketplace dispute")},
            text={OutlinedTextField(note,{note=it},label={Text("Describe the issue")},modifier=Modifier.fillMaxWidth(),minLines=3)},
            confirmButton={Button(onClick={vm.qMarketDispute(o.id,note);disputeOrder=null},enabled=note.length>=3){Text("Submit dispute")}},
            dismissButton={TextButton(onClick={disputeOrder=null}){Text("Cancel")}}
        )
    }
}

@Composable
private fun Q28WalletTab(vm:LemmiqViewModel){
    val w=vm.qWallet
    val withdrawCfg=vm.qWithdrawalConfig
    var user by remember{mutableStateOf("")}
    var amount by remember{mutableStateOf("")}
    var period by remember{mutableStateOf("TODAY")}
    var showWithdraw by remember{mutableStateOf(false)}
    var withdrawQ by remember{mutableStateOf("")}
    var withdrawNetwork by remember(withdrawCfg.networks){mutableStateOf(withdrawCfg.networks.firstOrNull()?:"TRC20")}
    var withdrawAddress by remember{mutableStateOf("")}
    val now=OffsetDateTime.now(ZoneOffset.UTC)
    val cutoff=when(period){
        "TODAY"->now.toLocalDate().atStartOfDay().atOffset(ZoneOffset.UTC)
        "WEEK"->now.minusDays(7)
        "MONTH"->now.minusMonths(1)
        "YEAR"->now.minusYears(1)
        else->null
    }
    val recentRows=vm.qLedger.filter{x->
        if(cutoff==null)true else runCatching{OffsetDateTime.parse(x.created_at)}.getOrNull()?.let{!it.isBefore(cutoff)}?:true
    }
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(14.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
        item{
            Card(shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(16.dp)){
                    Text("Basic Q mining",fontWeight=FontWeight.Bold,fontSize=18.sp)
                    Text(if(w?.basic_claimed_today==true)"Today's basic Q is claimed." else "Claim up to ${q28Q(w?.basic_daily_q?:0.0)} Q today.",color=Q28Muted,fontSize=12.sp)
                    Spacer(Modifier.height(10.dp))
                    Button(onClick={vm.qClaimDaily()},enabled=w?.basic_claimed_today!=true&&!vm.qEconomyBusy){Text(if(w?.basic_claimed_today==true)"Claimed" else "Claim daily Q")}
                }
            }
        }
        if(vm.qWeeklyActive.enabled)item{
            Card(shape=RoundedCornerShape(18.dp),colors=CardDefaults.cardColors(containerColor=Color(0xFFF0ECFF))){
                Column(Modifier.padding(16.dp)){
                    Text("Weekly active Q",fontWeight=FontWeight.Bold,fontSize=17.sp)
                    Text("${q28Q(vm.qWeeklyActive.weekly_q)} Q · ${vm.qWeeklyActive.week_key}",color=Q28Muted,fontSize=11.sp)
                    Spacer(Modifier.height(8.dp))
                    Button(onClick={vm.qClaimWeeklyActive()},enabled=!vm.qWeeklyActive.claimed&&!vm.qEconomyBusy){Text(if(vm.qWeeklyActive.claimed)"Claimed this week" else "Claim weekly Q")}
                }
            }
        }
        item{
            Card(shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(16.dp)){
                    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                        Column(Modifier.weight(1f)){
                            Text("Q → USDT withdrawal",fontWeight=FontWeight.Bold,fontSize=18.sp)
                            Text(if(withdrawCfg.enabled)"Available · ${q28Q(withdrawCfg.fee_percent)}% fee" else "Currently turned off by Admin",color=if(withdrawCfg.enabled)Q28Mint else Q28Muted,fontSize=11.sp)
                        }
                        Surface(shape=RoundedCornerShape(999.dp),color=if(withdrawCfg.enabled)Color(0xFFE4F8EF) else Color(0xFFECECF2)){
                            Text(if(withdrawCfg.enabled)"ON" else "OFF",Modifier.padding(horizontal=10.dp,vertical=5.dp),fontSize=10.sp,fontWeight=FontWeight.Black,color=if(withdrawCfg.enabled)Q28Mint else Q28Muted)
                        }
                    }
                    if(withdrawCfg.enabled){
                        Text("Minimum final payout ${q28Usd(withdrawCfg.minimum_net_usdt)} · current reference 1 Q ≈ ${q28Usd(withdrawCfg.q_reference_usd)}",fontSize=10.sp,color=Q28Muted,modifier=Modifier.padding(top=6.dp))
                        Spacer(Modifier.height(9.dp))
                        Button(onClick={showWithdraw=true},modifier=Modifier.fillMaxWidth(),enabled=!vm.qEconomyBusy){Text("Request withdrawal")}
                    }
                    if(vm.qWithdrawals.isNotEmpty()){
                        HorizontalDivider(Modifier.padding(vertical=10.dp))
                        Text("Recent withdrawals",fontWeight=FontWeight.Bold,fontSize=12.sp)
                        vm.qWithdrawals.take(4).forEach{x->
                            Row(Modifier.fillMaxWidth().padding(vertical=5.dp),verticalAlignment=Alignment.CenterVertically){
                                Column(Modifier.weight(1f)){
                                    Text("${q28Q(x.requested_q)} Q → ${q28Q(x.payout_usdt)} USDT",fontSize=11.sp,fontWeight=FontWeight.Bold)
                                    Text("${x.network} · ${x.request_id} · ${x.status}",fontSize=9.sp,color=Q28Muted,maxLines=1,overflow=TextOverflow.Ellipsis)
                                }
                                if(x.status=="PENDING")TextButton(onClick={vm.qCancelWithdrawal(x.id)},enabled=!vm.qEconomyBusy){Text("Cancel",fontSize=10.sp)}
                            }
                        }
                    }
                }
            }
        }
        if(vm.qFeatureCatalog.isNotEmpty())item{
            Card(shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(16.dp)){
                    val charging=vm.qFeatureCatalog.any{it.charging_enabled}
                    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                        Column(Modifier.weight(1f)){Text("AI feature Q rates",fontWeight=FontWeight.Bold,fontSize=18.sp);Text("One global price for every package",fontSize=10.sp,color=Q28Muted)}
                        Text(if(charging)"CHARGING ON" else "CHARGING OFF",fontSize=9.sp,fontWeight=FontWeight.Black,color=if(charging)Q28Mint else Color(0xFFB7791F))
                    }
                    vm.qFeatureCatalog.filter{it.enabled}.take(12).forEach{f->
                        Row(Modifier.fillMaxWidth().padding(top=7.dp),verticalAlignment=Alignment.CenterVertically){
                            Text(f.feature_name,modifier=Modifier.weight(1f),fontSize=11.sp)
                            Text("${q28Q(if(f.configured_q_cost>0)f.configured_q_cost else f.q_cost)} Q",fontWeight=FontWeight.Bold,fontSize=11.sp,color=Q28Purple)
                        }
                    }
                    Text(if(charging)"The Q fee is deducted from your main Q Wallet when a paid AI action succeeds." else "Rates are configured but real AI Q charging is currently OFF.",fontSize=9.sp,color=Q28Muted,modifier=Modifier.padding(top=8.dp))
                }
            }
        }
        item{
            Card(shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(16.dp)){
                    Text("Send Q",fontWeight=FontWeight.Bold,fontSize=18.sp)
                    OutlinedTextField(user,{user=it},label={Text("@username")},singleLine=true,modifier=Modifier.fillMaxWidth())
                    Spacer(Modifier.height(7.dp))
                    OutlinedTextField(amount,{amount=it},label={Text("Q amount")},singleLine=true,modifier=Modifier.fillMaxWidth())
                    Spacer(Modifier.height(9.dp))
                    Button(onClick={vm.qTransfer(user,amount.toDoubleOrNull()?:0.0);amount=""},enabled=user.isNotBlank()&&(amount.toDoubleOrNull()?:0.0)>0){Text("Send Q")}
                }
            }
        }
        item{Text("Recent activity",fontWeight=FontWeight.Black,fontSize=19.sp)}
        item{
            LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                items(listOf("TODAY" to "Today","WEEK" to "Week","MONTH" to "Month","YEAR" to "Year","ALL" to "All")){(key,label)->
                    FilterChip(selected=period==key,onClick={period=key},label={Text(label,fontSize=10.sp,maxLines=1)})
                }
            }
        }
        if(recentRows.isEmpty())item{Text("No Q transactions in this period.",color=Q28Muted)}
        items(recentRows.take(100),key={it.id}){x->
            Card(shape=RoundedCornerShape(16.dp)){
                Row(Modifier.fillMaxWidth().padding(13.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text(x.kind.replace("_"," "),fontWeight=FontWeight.Bold)
                        Text(x.note.ifBlank{x.created_at.take(16).replace("T"," ")},color=Q28Muted,fontSize=10.sp)
                    }
                    Text("${if(x.direction=="IN") "+" else "−"}${q28Q(x.amount_q)} Q",fontWeight=FontWeight.Black,color=if(x.direction=="IN")Q28Mint else Color(0xFFD94B63))
                }
            }
        }
    }

    if(showWithdraw){
        val gross=withdrawQ.toDoubleOrNull()?:0.0
        val fee=gross*withdrawCfg.fee_percent/100.0
        val net=(gross-fee).coerceAtLeast(0.0)
        val payout=net*withdrawCfg.q_reference_usd
        AlertDialog(
            onDismissRequest={showWithdraw=false},
            title={Text("Withdraw Q to USDT")},
            text={LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp)){
                item{Text("The reference rate is locked when you submit the request. Admin manually reviews and sends USDT.",fontSize=11.sp,color=Q28Muted)}
                item{OutlinedTextField(withdrawQ,{withdrawQ=it.filter{ch->ch.isDigit()||ch=='.'}},label={Text("Q amount")},singleLine=true,modifier=Modifier.fillMaxWidth())}
                item{Text("Network",fontWeight=FontWeight.Bold,fontSize=12.sp);Row(horizontalArrangement=Arrangement.spacedBy(7.dp)){(withdrawCfg.networks.ifEmpty{listOf("TRC20","BEP20")}).forEach{n->FilterChip(selected=withdrawNetwork==n,onClick={withdrawNetwork=n},label={Text(n)})}}}
                item{OutlinedTextField(withdrawAddress,{withdrawAddress=it.trim()},label={Text("Your USDT $withdrawNetwork wallet address")},singleLine=true,modifier=Modifier.fillMaxWidth())}
                item{Card(colors=CardDefaults.cardColors(containerColor=Color(0xFFF4F1FF))){Column(Modifier.padding(12.dp)){Text("Requested: ${q28Q(gross)} Q",fontSize=11.sp);Text("Fee (${q28Q(withdrawCfg.fee_percent)}%): ${q28Q(fee)} Q",fontSize=11.sp);Text("Net converted: ${q28Q(net)} Q",fontSize=11.sp);Text("You receive ≈ ${q28Q(payout)} USDT",fontWeight=FontWeight.Black,fontSize=15.sp,color=Q28Purple)}}}
                item{Text("Minimum final payout: ${q28Usd(withdrawCfg.minimum_net_usdt)}. Requested Q is locked immediately and released if the request is cancelled/rejected/failed.",fontSize=9.sp,color=Q28Muted)}
            }},
            confirmButton={Button(onClick={vm.qCreateWithdrawal(gross,withdrawNetwork,withdrawAddress);showWithdraw=false;withdrawQ="";withdrawAddress=""},enabled=gross>0&&payout+1e-9>=withdrawCfg.minimum_net_usdt&&withdrawAddress.length>=20&&!vm.qEconomyBusy){Text("Submit request")}},
            dismissButton={TextButton(onClick={showWithdraw=false}){Text("Cancel")}}
        )
    }
}


@Composable
private fun Q28ActivityTab(vm:LemmiqViewModel){
    var filter by remember{mutableStateOf("ALL")}
    var period by remember{mutableStateOf("TODAY")}
    val now=OffsetDateTime.now(ZoneOffset.UTC)
    val cutoff=when(period){
        "TODAY"->now.toLocalDate().atStartOfDay().atOffset(ZoneOffset.UTC)
        "WEEK"->now.minusDays(7)
        "MONTH"->now.minusMonths(1)
        "YEAR"->now.minusYears(1)
        else->null
    }
    fun inPeriod(x:QLedgerDto):Boolean{
        if(cutoff==null)return true
        val at=runCatching{OffsetDateTime.parse(x.created_at)}.getOrNull()?:return true
        return !at.isBefore(cutoff)
    }
    val periodRows=vm.qLedger.filter(::inPeriod)
    val rows=when(filter){
        "IN"->periodRows.filter{it.direction.equals("IN",true)}
        "OUT"->periodRows.filter{it.direction.equals("OUT",true)}
        else->periodRows
    }
    val incoming=periodRows.filter{it.direction.equals("IN",true)}.sumOf{it.amount_q}
    val outgoing=periodRows.filter{it.direction.equals("OUT",true)}.sumOf{it.amount_q}
    val featureUses=periodRows.count{it.kind.contains("FEATURE",true)||!it.feature_key.isNullOrBlank()}

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding=PaddingValues(14.dp,8.dp,14.dp,100.dp),
        verticalArrangement=Arrangement.spacedBy(10.dp)
    ){
        item{
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                Card(Modifier.weight(1f),shape=RoundedCornerShape(16.dp)){Column(Modifier.padding(12.dp)){Text("Incoming",fontSize=10.sp,color=Q28Muted);Text("+${q28Q(incoming)} Q",fontWeight=FontWeight.Black,color=Q28Mint)}}
                Card(Modifier.weight(1f),shape=RoundedCornerShape(16.dp)){Column(Modifier.padding(12.dp)){Text("Outgoing",fontSize=10.sp,color=Q28Muted);Text("−${q28Q(outgoing)} Q",fontWeight=FontWeight.Black,color=Color(0xFFD94B63))}}
            }
        }
        item{
            LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                items(listOf("TODAY" to "Today","WEEK" to "Week","MONTH" to "Month","YEAR" to "Year","ALL" to "All")){(key,label)->
                    FilterChip(selected=period==key,onClick={period=key},label={Text(label,fontSize=10.sp,maxLines=1)})
                }
            }
        }
        item{
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)){
                listOf("ALL" to "All","IN" to "Incoming","OUT" to "Outgoing").forEach{(key,label)->
                    FilterChip(selected=filter==key,onClick={filter=key},label={Text(label,fontSize=10.sp)},modifier=Modifier.weight(1f))
                }
            }
        }
        item{
            Text("Q activity",fontWeight=FontWeight.Black,fontSize=19.sp)
            Text("Mining, rewards, packages, marketplace, transfers, Q Predict and feature usage are tracked here.",fontSize=10.sp,color=Q28Muted)
            if(featureUses>0)Text("$featureUses feature usage event${if(featureUses==1)"" else "s"}",fontSize=10.sp,color=Q28Purple,modifier=Modifier.padding(top=3.dp))
        }
        if(rows.isEmpty())item{Text("No Q activity in this period.",color=Q28Muted)}
        items(rows.take(300),key={it.id}){x->
            val isIn=x.direction.equals("IN",true)
            val amount=if(x.amount_q==0.0)"0 Q" else "${if(isIn)"+" else "−"}${q28Q(x.amount_q)} Q"
            val title=when{
                !x.feature_key.isNullOrBlank()->x.feature_key.replace("_"," ")
                x.kind.isNotBlank()->x.kind.replace("_"," ")
                else->"Q activity"
            }
            Card(shape=RoundedCornerShape(16.dp)){
                Row(Modifier.fillMaxWidth().padding(13.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text(title,fontWeight=FontWeight.Bold)
                        if(x.note.isNotBlank())Text(x.note,color=Q28Muted,fontSize=10.sp,maxLines=2,overflow=TextOverflow.Ellipsis)
                        Text(x.created_at.take(16).replace("T"," "),color=Q28Muted,fontSize=9.sp)
                    }
                    Text(amount,fontWeight=FontWeight.Black,color=when{ x.amount_q==0.0->Q28Purple; isIn->Q28Mint; else->Color(0xFFD94B63) })
                }
            }
        }
    }
}

@Composable
private fun Q28PackagesTab(vm:LemmiqViewModel,onBuy:(QPlanDto)->Unit){
    var rebuyPlan by remember{mutableStateOf<QRebuyPlanDto?>(null)}
    var rebuyQ by remember{mutableStateOf("")}
    var rebuyNetwork by remember(vm.qRebuyOptions.networks){mutableStateOf(vm.qRebuyOptions.networks.firstOrNull()?:"TRC20")}
    val cycles=if(vm.qEarningCycles.cycles.isNotEmpty())vm.qEarningCycles.cycles else (vm.qWallet?.packages?:emptyList())
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(14.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
        item{Text("Q subscription packages",fontWeight=FontWeight.Black,fontSize=20.sp)}
        items(vm.qWallet?.plans?:emptyList(),key={it.code}){p->
            Card(shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(16.dp)){
                    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.Top){
                        Column(Modifier.weight(1f)){Text(p.name,fontWeight=FontWeight.Black,fontSize=18.sp);Text("${p.daily_rate_percent}% daily package accrual",color=Q28Purple,fontSize=12.sp)}
                        Text("US$${p.price_usd.toInt()}",fontWeight=FontWeight.Black,fontSize=21.sp)
                    }
                    Spacer(Modifier.height(7.dp))
                    Text("≈ ${q28Q(p.daily_q_at_current_reference)} Q/day at current Q reference",fontSize=12.sp)
                    Text("200% earning capacity: ${q28Usd(p.cap_usd)} · valid up to 365 days",fontSize=11.sp,color=Q28Muted)
                    Spacer(Modifier.height(9.dp))
                    Button(onClick={onBuy(p)},modifier=Modifier.fillMaxWidth()){Text("Buy with USDT")}
                }
            }
        }

        item{Text("My active & previous packages",fontWeight=FontWeight.Black,fontSize=20.sp,modifier=Modifier.padding(top=5.dp))}
        if(cycles.isEmpty())item{Text("No paid Q packages yet.",color=Q28Muted)}
        items(cycles,key={it.id}){p->
            val cap=if(p.earning_cap_usd>0)p.earning_cap_usd else p.cap_usd
            val used=if(p.earning_cap_usd>0)p.earning_cap_used_usd else p.accrued_usd_reference
            val remaining=if(p.earning_cap_usd>0)p.earning_cap_remaining_usd else p.remaining_cap_usd
            val progress=if(cap>0)(used/cap).toFloat().coerceIn(0f,1f) else 0f
            Card(shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(15.dp)){
                    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                        Text(p.package_name,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f))
                        Text(p.status,color=if(p.status=="ACTIVE")Q28Mint else if(p.status=="COMPLETED")Q28Purple else Q28Muted,fontSize=11.sp,fontWeight=FontWeight.Bold)
                    }
                    Text("${q28Q(p.accrued_q)} Q accumulated",fontSize=12.sp,modifier=Modifier.padding(top=4.dp))
                    Text("Earning capacity: ${q28Usd(used)} / ${q28Usd(cap)}",fontSize=11.sp,color=Q28Muted)
                    LinearProgressIndicator(progress={progress},modifier=Modifier.fillMaxWidth().padding(vertical=7.dp),color=Q28Purple)
                    Text("${String.format(Locale.US,"%.1f",progress*100)}% of the 200% cycle used · ${q28Usd(remaining)} remaining",fontSize=10.sp,color=Q28Muted)
                    if(p.earning_cap_breakdown.isNotEmpty()){
                        HorizontalDivider(Modifier.padding(vertical=8.dp))
                        p.earning_cap_breakdown.entries.sortedByDescending{it.value.usd_reference}.forEach{(source,v)->
                            Row(Modifier.fillMaxWidth().padding(vertical=2.dp)){Text(source.replace("_"," ").lowercase().replaceFirstChar{it.uppercase()},fontSize=9.sp,color=Q28Muted,modifier=Modifier.weight(1f));Text("${q28Q(v.q)} Q · ${q28Usd(v.usd_reference)}",fontSize=9.sp,fontWeight=FontWeight.Bold)}
                        }
                    }
                    Text("Started ${p.started_at.take(10)} · expires ${p.expires_at.take(10)}",fontSize=9.sp,color=Q28Muted,modifier=Modifier.padding(top=5.dp))
                }
            }
        }
        if(vm.qEarningCycles.unassigned_rewards_q>0)item{
            Surface(color=Color(0xFFFFF5D9),shape=RoundedCornerShape(14.dp)){
                Text("${q28Q(vm.qEarningCycles.unassigned_rewards_q)} Q of qualifying rewards are waiting for the next package earning cycle.",Modifier.padding(12.dp),fontSize=10.sp,color=Color(0xFF795A16))
            }
        }

        item{
            Card(shape=RoundedCornerShape(18.dp),colors=CardDefaults.cardColors(containerColor=Color(0xFFF0ECFF))){
                Column(Modifier.padding(16.dp)){
                    Text("Rebuy / Upgrade with Q + USDT",fontWeight=FontWeight.Black,fontSize=18.sp)
                    when{
                        !vm.qRebuyOptions.enabled->Text("Hybrid rebuy is currently disabled.",fontSize=11.sp,color=Q28Muted)
                        vm.qRebuyOptions.blocked_by_active_cycle->Text("Complete your current earning cycle before rebuying or upgrading.",fontSize=11.sp,color=Q28Muted)
                        !vm.qRebuyOptions.can_rebuy->Text("A completed or expired package is required before using Q + USDT rebuy.",fontSize=11.sp,color=Q28Muted)
                        else->{
                            Text("Use accumulated Q for part of a new package and pay the balance in USDT. The old package stays in history.",fontSize=10.sp,color=Q28Muted,modifier=Modifier.padding(bottom=8.dp))
                            vm.qRebuyOptions.plans.forEach{plan->
                                Row(Modifier.fillMaxWidth().padding(vertical=4.dp),verticalAlignment=Alignment.CenterVertically){
                                    Column(Modifier.weight(1f)){Text("${plan.action.lowercase().replaceFirstChar{it.uppercase()}} · ${plan.name}",fontWeight=FontWeight.Bold,fontSize=11.sp);Text("US$${q28Q(plan.price_usd)} · up to ${q28Q(plan.max_q_percent)}% in Q",fontSize=9.sp,color=Q28Muted)}
                                    OutlinedButton(onClick={rebuyPlan=plan;rebuyQ=""}){Text(if(plan.action=="UPGRADE")"Upgrade" else "Rebuy",fontSize=10.sp)}
                                }
                            }
                        }
                    }
                }
            }
        }
        if(vm.qRebuyOrders.isNotEmpty()){
            item{Text("Q + USDT rebuy orders",fontWeight=FontWeight.Black,fontSize=17.sp,modifier=Modifier.padding(top=4.dp))}
            items(vm.qRebuyOrders.take(20),key={"rebuy-${it.id}"}){o->
                Card(shape=RoundedCornerShape(16.dp)){Column(Modifier.padding(13.dp)){
                    Row(Modifier.fillMaxWidth()){Text("${o.action} · ${o.target_package_name}",fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));Text(o.status,fontSize=10.sp,fontWeight=FontWeight.Bold)}
                    Text("${q28Q(o.q_locked)} Q + ${q28Q(o.usdt_due)} USDT · ${o.rebuy_code}",fontSize=10.sp,color=Q28Muted)
                    if(o.status in listOf("CREATED"))TextButton(onClick={vm.qCancelRebuyOrder(o.id)},enabled=!vm.qEconomyBusy){Text("Cancel & release Q",fontSize=10.sp)}
                }}
            }
        }

        item{Text("USDT payment orders",fontWeight=FontWeight.Black,fontSize=20.sp,modifier=Modifier.padding(top=5.dp))}
        if(vm.qPaymentOrders.isEmpty())item{Text("No payment orders.",color=Q28Muted)}
        items(vm.qPaymentOrders,key={it.id}){o->
            Card(shape=RoundedCornerShape(16.dp)){Column(Modifier.padding(13.dp)){
                Row(Modifier.fillMaxWidth()){Text(o.package_name,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));Text(o.status,fontWeight=FontWeight.Bold,fontSize=11.sp)}
                Text("${q28Q(o.expected_usdt)} USDT · ${o.network} · ${o.order_code}",fontSize=10.sp,color=Q28Muted)
                if(o.status in listOf("CREATED","REJECTED"))TextButton(onClick={vm.activeQPaymentOrder=o}){Text("Open payment order",fontSize=10.sp)}
            }}
        }
    }

    rebuyPlan?.let{plan->
        val qAmount=rebuyQ.toDoubleOrNull()?:0.0
        val qUsd=qAmount*vm.qRebuyOptions.q_reference_usd
        val due=(plan.price_usd-qUsd).coerceAtLeast(0.0)
        AlertDialog(
            onDismissRequest={rebuyPlan=null},
            title={Text("${plan.action.lowercase().replaceFirstChar{it.uppercase()}} ${plan.name}")},
            text={Column(verticalArrangement=Arrangement.spacedBy(8.dp)){
                Text("Package price ${q28Usd(plan.price_usd)}",fontWeight=FontWeight.Bold)
                Text("Wallet balance: ${q28Q(vm.qRebuyOptions.wallet_balance_q)} Q · 1 Q ≈ ${q28Usd(vm.qRebuyOptions.q_reference_usd)}",fontSize=10.sp,color=Q28Muted)
                OutlinedTextField(rebuyQ,{rebuyQ=it.filter{ch->ch.isDigit()||ch=='.'}},label={Text("Q to use (max ${q28Q(plan.max_q_at_current_reference)} Q)")},singleLine=true,modifier=Modifier.fillMaxWidth())
                Text("Network",fontWeight=FontWeight.Bold,fontSize=12.sp)
                Row(horizontalArrangement=Arrangement.spacedBy(7.dp)){(vm.qRebuyOptions.networks.ifEmpty{listOf("TRC20","BEP20")}).forEach{n->FilterChip(selected=rebuyNetwork==n,onClick={rebuyNetwork=n},label={Text(n)})}}
                Card(colors=CardDefaults.cardColors(containerColor=Color(0xFFF7F7FB))){Column(Modifier.padding(12.dp)){Text("Q applied: ${q28Q(qAmount)} Q ≈ ${q28Usd(qUsd)}",fontSize=11.sp);Text("USDT to pay: ${q28Q(due)} USDT",fontSize=15.sp,fontWeight=FontWeight.Black,color=Q28Purple);Text("A new independent 200% earning cycle starts after Admin approves the USDT payment.",fontSize=9.sp,color=Q28Muted,modifier=Modifier.padding(top=5.dp))}}
            }},
            confirmButton={Button(onClick={vm.qCreateRebuyOrder(plan.package_code,rebuyNetwork,qAmount);rebuyPlan=null},enabled=qAmount>0&&qAmount<=plan.max_q_at_current_reference+1e-9&&qAmount<=vm.qRebuyOptions.wallet_balance_q+1e-9&&due>0&&!vm.qEconomyBusy){Text("Create payment order")}},
            dismissButton={TextButton(onClick={rebuyPlan=null}){Text("Cancel")}}
        )
    }
}

@Composable
private fun Q28PaymentDialog(vm:LemmiqViewModel,o:QPaymentOrderDto){
    var tx by remember(o.id){mutableStateOf(o.tx_hash?:"")}
    var copied by remember(o.id){mutableStateOf("")}
    var enlarged by remember(o.id){mutableStateOf(false)}
    val clipboard=LocalClipboardManager.current
    val pending=o.status!="CREATED"&&o.status!="REJECTED"
    AlertDialog(
        onDismissRequest={vm.qDismissPayment()},
        title={Text(if(pending)"Payment submitted" else "Pay ${o.expected_usdt} USDT")},
        text={
            Column(horizontalAlignment=Alignment.CenterHorizontally){
                Text("${o.network} · ${o.order_code}",fontSize=12.sp,color=Q28Muted)
                Spacer(Modifier.height(8.dp))
                o.wallet?.let{w->
                    AsyncImage(
                        model=vm.serverUrl+w.qr_url,contentDescription="USDT payment QR",
                        modifier=Modifier.size(260.dp).clickable{enlarged=true}
                    )
                    Text("Tap QR to enlarge",fontSize=10.sp,color=Q28Muted)
                    Spacer(Modifier.height(7.dp))
                    Text("Wallet address",fontSize=10.sp,color=Q28Muted,modifier=Modifier.fillMaxWidth())
                    Text(w.address,fontSize=10.sp,modifier=Modifier.fillMaxWidth().padding(vertical=5.dp),color=Color(0xFF303040))
                    OutlinedButton(onClick={clipboard.setText(AnnotatedString(w.address));copied="Address copied ✓"},modifier=Modifier.fillMaxWidth()){Text("Copy address")}
                }
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(7.dp)){
                    OutlinedButton(onClick={clipboard.setText(AnnotatedString(o.expected_usdt.toString()));copied="Amount copied ✓"},modifier=Modifier.weight(1f)){Text("Copy amount",fontSize=11.sp)}
                    OutlinedButton(onClick={clipboard.setText(AnnotatedString(o.order_code));copied="Order ID copied ✓"},modifier=Modifier.weight(1f)){Text("Copy order",fontSize=11.sp)}
                }
                if(copied.isNotBlank())Text(copied,color=Q28Mint,fontSize=10.sp,modifier=Modifier.padding(top=4.dp))
                Text("⚠ Send USDT using ${o.network} only.",fontSize=10.sp,color=Color(0xFFB7791F),modifier=Modifier.padding(vertical=8.dp))
                if(!pending){
                    OutlinedTextField(tx,{tx=it},label={Text("Transaction hash")},modifier=Modifier.fillMaxWidth(),singleLine=true)
                    Text("Admin manually verifies network, address and amount before activation.",fontSize=10.sp,color=Q28Muted,modifier=Modifier.padding(top=7.dp))
                }else Text("Status: ${o.status}. Package activates after admin verification.",fontSize=12.sp)
            }
        },
        confirmButton={
            if(!pending)Button(onClick={vm.qSubmitPayment(o.id,tx)},enabled=tx.length>=20){Text("Submit for verification")}
            else Button(onClick={vm.qDismissPayment()}){Text("Close")}
        },
        dismissButton={if(!pending)TextButton(onClick={vm.qDismissPayment()}){Text("Cancel")}}
    )
    if(enlarged){
        Dialog(onDismissRequest={enlarged=false},properties=DialogProperties(usePlatformDefaultWidth=false)){
            Box(Modifier.fillMaxSize().background(Color(0xEE070812)).clickable{enlarged=false},contentAlignment=Alignment.Center){
                Card(Modifier.fillMaxWidth().padding(18.dp).clickable{/* consume taps inside QR card */},shape=RoundedCornerShape(22.dp),colors=CardDefaults.cardColors(containerColor=Color.White)){
                    Column(Modifier.padding(16.dp),horizontalAlignment=Alignment.CenterHorizontally){
                        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text("USDT ${o.network} QR",fontWeight=FontWeight.Black,fontSize=20.sp,modifier=Modifier.weight(1f));TextButton(onClick={enlarged=false}){Text("✕")}}
                        o.wallet?.let{w->
                            AsyncImage(model=vm.serverUrl+w.qr_url,contentDescription="Large payment QR",modifier=Modifier.fillMaxWidth().aspectRatio(1f).padding(8.dp))
                            Text(w.address,fontSize=10.sp,color=Q28Muted,modifier=Modifier.fillMaxWidth().padding(vertical=8.dp))
                            Button(onClick={clipboard.setText(AnnotatedString(w.address));enlarged=false},modifier=Modifier.fillMaxWidth()){Text("Copy address")}}
                        Text("Tap outside or ✕ to close",fontSize=9.sp,color=Q28Muted,modifier=Modifier.padding(top=8.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun Q28MarketTab(vm:LemmiqViewModel,onDispute:(QMarketOrderDto)->Unit){
    var title by remember{mutableStateOf("")}
    var desc by remember{mutableStateOf("")}
    var price by remember{mutableStateOf("")}
    var showSell by remember{mutableStateOf(false)}
    var editListing by remember{mutableStateOf<QMarketListingDto?>(null)}
    var selectedListing by remember{mutableStateOf<QMarketListingDto?>(null)}
    var selectedMedia by remember{mutableStateOf<List<Uri>>(emptyList())}
    val context=LocalContext.current
    val uriHandler=LocalUriHandler.current
    val mediaPicker=rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()){uris->selectedMedia=uris.take(10)}

    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(14.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
        item{
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                Column(Modifier.weight(1f)){Text("Q Market",fontWeight=FontWeight.Black,fontSize=22.sp);Text("Buy and sell goods or services using Q escrow.",fontSize=11.sp,color=Q28Muted)}
                Button(onClick={showSell=!showSell}){Text(if(showSell)"Close" else "Sell")}
            }
        }
        if(showSell)item{
            Card(shape=RoundedCornerShape(18.dp)){Column(Modifier.padding(15.dp)){
                Text("Create listing",fontWeight=FontWeight.Bold)
                OutlinedTextField(title,{title=it},label={Text("Product or service")},modifier=Modifier.fillMaxWidth())
                OutlinedTextField(desc,{desc=it},label={Text("Description")},modifier=Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick={mediaPicker.launch(arrayOf("image/*","video/*","application/pdf","text/plain","text/csv","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))},modifier=Modifier.fillMaxWidth()){Text("Add photos, videos or files")}
                if(selectedMedia.isNotEmpty()){
                    Text("${selectedMedia.size} attachment(s) selected",fontSize=11.sp,color=Q28Muted,modifier=Modifier.padding(vertical=6.dp))
                    TextButton(onClick={selectedMedia=emptyList()}){Text("Clear selected files")}
                }
                OutlinedTextField(price,{price=it},label={Text("Price in Q")},modifier=Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                Button(onClick={
                    vm.qCreateListingWithMedia(title,desc,price.toDoubleOrNull()?:0.0,1,selectedMedia)
                    title="";desc="";price="";selectedMedia=emptyList();showSell=false
                },enabled=title.isNotBlank()&&(price.toDoubleOrNull()?:0.0)>0&&!vm.qEconomyBusy){Text(if(vm.qEconomyBusy)"Uploading…" else "List for Q")}
                Text("Up to 10 attachments · images/files 20 MB · videos 100 MB",fontSize=9.sp,color=Q28Muted,modifier=Modifier.padding(top=6.dp))
            }}
        }
        items(vm.qMarketListings,key={"market-${it.id}"}){x->
            Card(Modifier.fillMaxWidth().clickable{selectedListing=x},shape=RoundedCornerShape(20.dp)){
                Column{
                    x.media.firstOrNull{it.kind=="PHOTO"}?.let{m->
                        AsyncImage(model=vm.serverUrl+m.media_url,contentDescription=x.title,modifier=Modifier.fillMaxWidth().height(210.dp),contentScale=androidx.compose.ui.layout.ContentScale.Crop)
                    }
                    Column(Modifier.padding(13.dp)){
                        Text("${q28Q(x.price_q)} Q",fontWeight=FontWeight.Black,fontSize=22.sp)
                        Text(x.title,fontWeight=FontWeight.Bold,fontSize=15.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
                        Text("@${x.seller?.username?:"seller"} · ${x.inventory} available",fontSize=10.sp,color=Q28Muted,modifier=Modifier.padding(top=3.dp))
                        if(x.seller?.id!=vm.store.userId)Row(Modifier.fillMaxWidth().padding(top=9.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                            OutlinedButton(onClick={vm.qMarketChat(x)},modifier=Modifier.weight(1f)){Text("Chat seller")}
                            Button(onClick={vm.qBuyListing(x.id)},modifier=Modifier.weight(1f)){Text("Buy with Q")}
                        }
                    }
                }
            }
        }
        item{Text("My listings",fontWeight=FontWeight.Black,fontSize=19.sp,modifier=Modifier.padding(top=7.dp))}
        if(vm.qMyListings.isEmpty())item{Text("No listings yet.",color=Q28Muted)}
        items(vm.qMyListings,key={"mine-${it.id}"}){x->
            Card(shape=RoundedCornerShape(17.dp)){Row(Modifier.fillMaxWidth().padding(14.dp),verticalAlignment=Alignment.CenterVertically){
                Column(Modifier.weight(1f)){Text(x.title,fontWeight=FontWeight.Bold);Text("${q28Q(x.price_q)} Q · ${x.inventory} available · ${x.media.size} attachment(s) · ${if(x.active)"Active" else "Paused"}",fontSize=10.sp,color=Q28Muted)}
                TextButton(onClick={editListing=x}){Text("Edit")}
            }}
        }
        item{Text("My Q Market orders",fontWeight=FontWeight.Black,fontSize=19.sp,modifier=Modifier.padding(top=7.dp))}
        if(vm.qMarketOrders.isEmpty())item{Text("No marketplace orders yet.",color=Q28Muted)}
        items(vm.qMarketOrders,key={it.id}){o->
            val seller=o.seller_id==vm.store.userId
            Card(shape=RoundedCornerShape(17.dp)){Column(Modifier.padding(14.dp)){
                Row(Modifier.fillMaxWidth()){Text(o.listing?.title?:"Order",fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));Text(o.status,fontSize=10.sp,fontWeight=FontWeight.Bold)}
                Text("${q28Q(o.total_q)} Q · ${o.order_code}",fontSize=11.sp,color=Q28Muted)
                Row(horizontalArrangement=Arrangement.spacedBy(5.dp),modifier=Modifier.padding(top=7.dp)){
                    if(seller&&o.status=="PAID")TextButton(onClick={vm.qMarketAction(o.id,"accept")}){Text("Accept")}
                    if(seller&&(o.status=="PAID"||o.status=="ACCEPTED"))TextButton(onClick={vm.qMarketAction(o.id,"delivered")}){Text("Delivered")}
                    if(!seller&&(o.status=="ACCEPTED"||o.status=="DELIVERED"))Button(onClick={vm.qMarketAction(o.id,"complete")}){Text("Complete")}
                    if(!seller&&o.status=="PAID")TextButton(onClick={vm.qMarketAction(o.id,"cancel")}){Text("Cancel")}
                    if(o.status in listOf("PAID","ACCEPTED","DELIVERED"))TextButton(onClick={onDispute(o)}){Text("Dispute")}
                }
            }}
        }
    }
    selectedListing?.let{x->
        AlertDialog(
            onDismissRequest={selectedListing=null},
            title={Text(x.title)},
            text={LazyColumn(verticalArrangement=Arrangement.spacedBy(9.dp)){
                x.media.firstOrNull{it.kind=="PHOTO"}?.let{m->item{AsyncImage(model=vm.serverUrl+m.media_url,contentDescription=x.title,modifier=Modifier.fillMaxWidth().height(240.dp),contentScale=androidx.compose.ui.layout.ContentScale.Crop)}}
                item{Text("${q28Q(x.price_q)} Q",fontSize=25.sp,fontWeight=FontWeight.Black);Text("≈ ${q28Usd(x.price_usd_reference)} reference",fontSize=10.sp,color=Q28Muted)}
                if(x.description.isNotBlank())item{Text("Description",fontWeight=FontWeight.Bold);Text(x.description,fontSize=12.sp)}
                item{Text("Seller @${x.seller?.username?:"seller"} · ${x.inventory} available",fontSize=10.sp,color=Q28Muted)}
            }},
            confirmButton={if(x.seller?.id!=vm.store.userId)Button(onClick={selectedListing=null;vm.qMarketChat(x)}){Text("Chat seller")}else TextButton(onClick={selectedListing=null}){Text("Close")}},
            dismissButton={if(x.seller?.id!=vm.store.userId){TextButton(onClick={selectedListing=null;vm.qBuyListing(x.id)}){Text("Buy with Q")}}}
        )
    }
    editListing?.let{x->
        var etitle by remember(x.id){mutableStateOf(x.title)}
        var edesc by remember(x.id){mutableStateOf(x.description)}
        var eprice by remember(x.id){mutableStateOf(x.price_q.toString())}
        var einventory by remember(x.id){mutableStateOf(x.inventory.toString())}
        var eactive by remember(x.id){mutableStateOf(x.active)}
        AlertDialog(
            onDismissRequest={editListing=null},title={Text("Edit Q Market listing")},
            text={Column{
                OutlinedTextField(etitle,{etitle=it},label={Text("Title")},modifier=Modifier.fillMaxWidth())
                OutlinedTextField(edesc,{edesc=it},label={Text("Description")},modifier=Modifier.fillMaxWidth())
                OutlinedTextField(eprice,{eprice=it},label={Text("Price in Q")},modifier=Modifier.fillMaxWidth())
                OutlinedTextField(einventory,{einventory=it},label={Text("Inventory")},modifier=Modifier.fillMaxWidth())
                Row(verticalAlignment=Alignment.CenterVertically){Checkbox(checked=eactive,onCheckedChange={eactive=it});Text("Listing active")}
                if(x.media.isNotEmpty()){
                    Text("Attachments",fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=8.dp))
                    x.media.take(6).forEach{m->Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text("${if(m.kind=="PHOTO")"🖼" else if(m.kind=="VIDEO")"🎥" else "📎"} ${m.name.take(20)}",fontSize=10.sp,modifier=Modifier.weight(1f));if(m.kind=="PHOTO"&&!m.is_cover)TextButton(onClick={vm.qSetListingCover(x.id,m.id)}){Text("Cover",fontSize=9.sp)};TextButton(onClick={vm.qDeleteListingMedia(x.id,m.id)}){Text("Remove",fontSize=9.sp)}}}
                }
            }},
            confirmButton={Button(onClick={vm.qUpdateListing(x,etitle,edesc,eprice.toDoubleOrNull()?:0.0,einventory.toIntOrNull()?:1,eactive);editListing=null},enabled=etitle.isNotBlank()&&(eprice.toDoubleOrNull()?:0.0)>0&&(einventory.toIntOrNull()?:0)>0){Text("Save")}},
            dismissButton={TextButton(onClick={editListing=null}){Text("Cancel")}}
        )
    }
}

@Composable
private fun Q28ReferralTab(vm:LemmiqViewModel){
    val clipboard=LocalClipboardManager.current
    var code by remember{mutableStateOf("")}
    val r=vm.qReferrals
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(14.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
        item{
            Card(shape=RoundedCornerShape(18.dp)){Column(Modifier.padding(16.dp)){
                Text("Refer & Earn",fontWeight=FontWeight.Black,fontSize=21.sp)
                Text("Your code",fontSize=11.sp,color=Q28Muted)
                Text(vm.qWallet?.referral_code?:"—",fontSize=25.sp,fontWeight=FontWeight.Black,color=Q28Purple,modifier=Modifier.padding(vertical=10.dp))
                Text("Free signup referral: ${q28Q(vm.qWallet?.referral_reward_q?:0.0)} Q. Package referrals are paid when the referred user's package payment is approved.",fontSize=11.sp,color=Q28Muted)
                Button(onClick={clipboard.setText(AnnotatedString(vm.qWallet?.referral_code?:""))}){Text("Copy referral code")}
            }}
        }
        item{
            Card(shape=RoundedCornerShape(18.dp)){Column(Modifier.padding(16.dp)){
                Text("Have a referral code?",fontWeight=FontWeight.Bold)
                OutlinedTextField(code,{code=it},label={Text("Q123-ABCDEF")},modifier=Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                Button(onClick={vm.qClaimReferral(code);code=""},enabled=code.isNotBlank()){Text("Claim referral")}
                Text("Referral claims are limited to new accounts and one referral per account.",fontSize=10.sp,color=Q28Muted,modifier=Modifier.padding(top=6.dp))
            }}
        }
        item{
            Card(shape=RoundedCornerShape(18.dp)){Column(Modifier.padding(15.dp)){
                Text("My referrals",fontWeight=FontWeight.Black,fontSize=19.sp)
                Text("${r?.count?:0} referred · ${r?.paid_users?:0} paid subscriber(s)",fontSize=11.sp,color=Q28Muted)
                Text("${q28Q(r?.earned_q?:0.0)} Q earned${if((r?.pending_q?:0.0)>0)" · ${q28Q(r?.pending_q?:0.0)} Q pending" else ""}",fontWeight=FontWeight.Bold,color=Q28Purple,modifier=Modifier.padding(top=4.dp))
            }}
        }
        if((r?.items?:emptyList()).isEmpty())item{Text("No referrals yet.",color=Q28Muted)}
        items(r?.items?:emptyList(),key={it.user_id}){x->
            Card(shape=RoundedCornerShape(16.dp)){Column(Modifier.padding(14.dp)){
                Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){Text(x.display_name.ifBlank{x.username.ifBlank{"User #${x.user_id}"}},fontWeight=FontWeight.Bold);Text("@${x.username} · ${x.current_tier}",fontSize=10.sp,color=Q28Muted)}
                    Column(horizontalAlignment=Alignment.End){Text("${q28Q(x.reward_q)} Q",fontWeight=FontWeight.Black,color=Q28Mint);if(x.pending_q>0)Text("${q28Q(x.pending_q)} pending",fontSize=9.sp,color=Q28Muted)}
                }
                if(x.events.isNotEmpty()){
                    Spacer(Modifier.height(7.dp))
                    x.events.forEach{e->Row(Modifier.fillMaxWidth().padding(vertical=3.dp)){Text(e.label,fontSize=10.sp,modifier=Modifier.weight(1f));Text("+${q28Q(e.reward_q)} Q · ${e.status}",fontSize=10.sp,fontWeight=FontWeight.Bold)}}
                }
            }}
        }
    }
}
