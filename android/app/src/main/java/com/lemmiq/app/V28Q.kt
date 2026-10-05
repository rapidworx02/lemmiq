package com.lemmiq.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import java.util.Locale

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
                if(w?.cashout_enabled!=true)Text("Cash-out is not enabled in V2.8",color=Color(0xFFFFC763),fontSize=10.sp,modifier=Modifier.padding(top=5.dp))
            }
        }
        Row(Modifier.fillMaxWidth().padding(8.dp),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            listOf("Wallet","Packages","Market","Refer").forEachIndexed{i,label->
                FilterChip(selected=tab==i,onClick={tab=i},label={Text(label,fontSize=11.sp)},modifier=Modifier.weight(1f))
            }
        }
        Box(Modifier.weight(1f)){
            when(tab){
                0->Q28WalletTab(vm)
                1->Q28PackagesTab(vm){buyPlan=it}
                2->Q28MarketTab(vm){disputeOrder=it}
                else->Q28ReferralTab(vm)
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
            }},
            confirmButton={Button(onClick={buyPlan=null;vm.qCreatePaymentOrder(p.code,"TRC20")}){Text("USDT TRC20")}},
            dismissButton={Row{TextButton(onClick={buyPlan=null;vm.qCreatePaymentOrder(p.code,"BEP20")}){Text("USDT BEP20")};TextButton(onClick={buyPlan=null}){Text("Cancel")}}}
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
    var user by remember{mutableStateOf("")}
    var amount by remember{mutableStateOf("")}
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
        if(vm.qLedger.isEmpty())item{Text("No Q transactions yet.",color=Q28Muted)}
        items(vm.qLedger.take(100),key={it.id}){x->
            Card(shape=RoundedCornerShape(16.dp)){
                Row(Modifier.fillMaxWidth().padding(13.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text(x.kind.replace("_"," "),fontWeight=FontWeight.Bold)
                        Text(x.note.ifBlank{x.created_at.take(16).replace("T"," ")},color=Q28Muted,fontSize=10.sp)
                    }
                    Text("${if(x.direction=="IN")+"+" else "−"}${q28Q(x.amount_q)} Q",fontWeight=FontWeight.Black,color=if(x.direction=="IN")Q28Mint else Color(0xFFD94B63))
                }
            }
        }
    }
}

@Composable
private fun Q28PackagesTab(vm:LemmiqViewModel,onBuy:(QPlanDto)->Unit){
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
                    Text("Maximum package ceiling: ${q28Usd(p.cap_usd)} · valid up to 365 days",fontSize=11.sp,color=Q28Muted)
                    Spacer(Modifier.height(9.dp))
                    Button(onClick={onBuy(p)},modifier=Modifier.fillMaxWidth()){Text("Buy with USDT")}
                }
            }
        }
        item{Text("My packages",fontWeight=FontWeight.Black,fontSize=20.sp,modifier=Modifier.padding(top=5.dp))}
        if((vm.qWallet?.packages?:emptyList()).isEmpty())item{Text("No paid Q packages yet.",color=Q28Muted)}
        items(vm.qWallet?.packages?:emptyList(),key={it.id}){p->
            Card(shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(15.dp)){
                    Row(Modifier.fillMaxWidth()){Text(p.package_name,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));Text(p.status,color=if(p.status=="ACTIVE")Q28Mint else Q28Muted,fontSize=11.sp,fontWeight=FontWeight.Bold)}
                    Text("${q28Q(p.accrued_q)} Q accrued · ${q28Usd(p.accrued_usd_reference)} / ${q28Usd(p.cap_usd)} reference cap",fontSize=12.sp)
                    Text("Remaining cap: ${q28Usd(p.remaining_cap_usd)} · expires ${p.expires_at.take(10)}",fontSize=10.sp,color=Q28Muted)
                }
            }
        }
        item{Text("USDT payment orders",fontWeight=FontWeight.Black,fontSize=20.sp,modifier=Modifier.padding(top=5.dp))}
        if(vm.qPaymentOrders.isEmpty())item{Text("No payment orders.",color=Q28Muted)}
        items(vm.qPaymentOrders,key={it.id}){o->
            Card(shape=RoundedCornerShape(16.dp)){Column(Modifier.padding(13.dp)){Row(Modifier.fillMaxWidth()){Text(o.package_name,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));Text(o.status,fontWeight=FontWeight.Bold,fontSize=11.sp)};Text("${o.expected_usdt} USDT · ${o.network} · ${o.order_code}",fontSize=10.sp,color=Q28Muted)}}
        }
    }
}

@Composable
private fun Q28PaymentDialog(vm:LemmiqViewModel,o:QPaymentOrderDto){
    var tx by remember(o.id){mutableStateOf(o.tx_hash?:"")}
    val pending=o.status!="CREATED"&&o.status!="REJECTED"
    AlertDialog(
        onDismissRequest={vm.qDismissPayment()},
        title={Text(if(pending)"Payment submitted" else "Pay ${o.expected_usdt} USDT")},
        text={
            Column(horizontalAlignment=Alignment.CenterHorizontally){
                Text("${o.network} · ${o.order_code}",fontSize=11.sp,color=Q28Muted)
                Spacer(Modifier.height(8.dp))
                o.wallet?.let{w->
                    AsyncImage(model=vm.serverUrl+w.qr_url,contentDescription="USDT payment QR",modifier=Modifier.size(180.dp))
                    Text(w.address,fontSize=10.sp,modifier=Modifier.fillMaxWidth().padding(6.dp),color=Q28Muted)
                }
                if(!pending){
                    OutlinedTextField(tx,{tx=it},label={Text("Transaction hash")},modifier=Modifier.fillMaxWidth())
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
}

@Composable
private fun Q28MarketTab(vm:LemmiqViewModel,onDispute:(QMarketOrderDto)->Unit){
    var title by remember{mutableStateOf("")}
    var desc by remember{mutableStateOf("")}
    var price by remember{mutableStateOf("")}
    var showSell by remember{mutableStateOf(false)}
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
                OutlinedTextField(price,{price=it},label={Text("Price in Q")},modifier=Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                Button(onClick={vm.qCreateListing(title,desc,price.toDoubleOrNull()?:0.0);title="";desc="";price="";showSell=false},enabled=title.isNotBlank()&&(price.toDoubleOrNull()?:0.0)>0){Text("List for Q")}
            }}
        }
        items(vm.qMarketListings,key={it.id}){x->
            Card(shape=RoundedCornerShape(18.dp)){
                Column(Modifier.padding(15.dp)){
                    Text(x.title,fontWeight=FontWeight.Black,fontSize=17.sp,maxLines=2,overflow=TextOverflow.Ellipsis)
                    if(x.description.isNotBlank())Text(x.description,color=Q28Muted,fontSize=11.sp,maxLines=3,overflow=TextOverflow.Ellipsis)
                    Text("@${x.seller?.username?:"seller"} · ${x.inventory} available",fontSize=10.sp,color=Q28Muted,modifier=Modifier.padding(top=5.dp))
                    Row(Modifier.fillMaxWidth().padding(top=8.dp),verticalAlignment=Alignment.CenterVertically){
                        Column(Modifier.weight(1f)){Text("${q28Q(x.price_q)} Q",fontWeight=FontWeight.Black,fontSize=20.sp);Text("≈ ${q28Usd(x.price_usd_reference)} reference",fontSize=10.sp,color=Q28Muted)}
                        if(x.seller?.id!=vm.store.userId)Button(onClick={vm.qBuyListing(x.id)}){Text("Buy")}
                    }
                }
            }
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
                Text("Current referrer reward: ${q28Q(vm.qWallet?.referral_reward_q?:0.0)} Q",fontSize=11.sp,color=Q28Muted)
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
        item{Text("${r?.count?:0} referrals · ${q28Q(r?.earned_q?:0.0)} Q earned",fontWeight=FontWeight.Bold)}
        items(r?.items?:emptyList(),key={it.user_id}){x->
            Card(shape=RoundedCornerShape(15.dp)){Row(Modifier.fillMaxWidth().padding(13.dp)){Text("User #${x.user_id}",Modifier.weight(1f));Text("+${q28Q(x.reward_q)} Q",color=Q28Mint,fontWeight=FontWeight.Bold)}}
        }
    }
}
