package com.lemmiq.app

import androidx.compose.foundation.background
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.layout.ContentScale
import android.provider.Settings
import android.content.Intent
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.provider.ContactsContract
import android.graphics.BitmapFactory
import androidx.compose.ui.graphics.asImageBitmap
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

private val Purple=Color(0xFF6C4DFF)
private val Soft=Color(0xFFF0ECFF)
private val Bg=Color(0xFFF7F7FB)
private val Ink=Color(0xFF17182A)
private val Muted=Color(0xFF7E8095)
private val Blue=Color(0xFF2678F4)
private val Pink=Color(0xFFFF4B9C)
private val Mint=Color(0xFF16AB90)
private val BrandGradient=Brush.linearGradient(listOf(Blue,Purple,Pink))

@Composable private fun BrandMark(size:androidx.compose.ui.unit.Dp=46.dp){
    Image(painterResource(R.drawable.lemmiq_brand_icon),contentDescription="LEMMIQ logo",
      modifier=Modifier.size(size).clip(RoundedCornerShape(size*0.24f)),contentScale=ContentScale.Crop)
}
@Composable private fun GradientPanel(title:String,subtitle:String,content:@Composable ColumnScope.()->Unit){
    Box(Modifier.fillMaxWidth().padding(horizontal=18.dp).clip(RoundedCornerShape(26.dp))
        .background(BrandGradient)) {
        Column(Modifier.padding(20.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Row(verticalAlignment=Alignment.CenterVertically){
                BrandMark(42.dp);Spacer(Modifier.width(12.dp))
                Column {Text(title,color=Color.White,fontSize=20.sp,fontWeight=FontWeight.Black)
                    Text(subtitle,color=Color.White.copy(alpha=.8f),fontSize=11.sp)}
            }
            content()
        }
    }
}
@Composable private fun DashboardMetric(label:String,value:String,modifier:Modifier=Modifier){
    Card(modifier,shape=RoundedCornerShape(20.dp),colors=CardDefaults.cardColors(containerColor=Color.White)){
        Column(Modifier.padding(14.dp)){Text(label,color=Muted,fontSize=12.sp)
            Text(value,color=Ink,fontSize=22.sp,fontWeight=FontWeight.Black)}
    }
}

@Composable
fun LemmiqApp(vm:LemmiqViewModel= viewModel()){
    val ctx=LocalContext.current
    val pushPermission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted->
        PushControl.markPermissionAsked(ctx)
        if(granted)vm.registerPush() else vm.pushStatusText="Android notification permission is off"
    }
    LaunchedEffect(vm.authenticated){
        if(vm.authenticated){
            PushControl.ensureChannel(ctx)
            when{
                !BuildConfig.FCM_CONFIGURED -> vm.pushStatusText="Firebase app config missing: add google-services.json"
                Build.VERSION.SDK_INT>=33 &&
                    ContextCompat.checkSelfPermission(ctx,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED &&
                    !PushControl.permissionAsked(ctx) -> pushPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                else -> { vm.registerPush(); vm.refreshPushStatus() }
            }
        }
    }
    when{
        !vm.authenticated->Auth(vm)
        vm.activeGroup!=null->V24GroupChat(vm)
        vm.active!=null->Chat(vm)
        else->Home(vm)
    }
    if(vm.authenticated)V27VisionDialog(vm)
    if(vm.authenticated && (vm.active!=null || vm.activeGroup!=null))V29ConversationQOrb(vm)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun V29ConversationQOrb(vm:LemmiqViewModel){
    var open by remember{mutableStateOf(false)}
    var prompt by remember{mutableStateOf("")}
    Box(Modifier.fillMaxSize(),contentAlignment=Alignment.BottomEnd){
        FloatingActionButton(onClick={open=true},containerColor=Purple.copy(alpha=.68f),contentColor=Color.White,shape=CircleShape,modifier=Modifier.padding(end=18.dp,bottom=92.dp)){
            Text("Q",fontSize=23.sp,fontWeight=FontWeight.Black)
        }
    }
    if(open){
        ModalBottomSheet(onDismissRequest={open=false}){
            Column(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=8.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
                Text("Q · Personal Assistant",fontSize=22.sp,fontWeight=FontWeight.Black)
                Text(if(vm.active!=null)"Ask Q about this conversation or anything in LEMMIQ." else "Ask Q while you are in this group.",fontSize=11.sp,color=Muted)
                OutlinedTextField(prompt,{prompt=it},modifier=Modifier.fillMaxWidth(),placeholder={Text("Ask Q…")},minLines=2)
                Button(onClick={if(prompt.isNotBlank()){vm.askAgent(prompt.trim());prompt=""}},enabled=prompt.isNotBlank()&&!vm.agentBusy,modifier=Modifier.fillMaxWidth()){Text(if(vm.agentBusy)"Q is thinking…" else "Ask Q")}
                vm.agentAnswer?.answer?.takeIf{it.isNotBlank()}?.let{Surface(color=Soft,shape=RoundedCornerShape(16.dp)){Text(it,Modifier.padding(14.dp),fontSize=12.sp,color=Ink)}}
                Spacer(Modifier.height(18.dp))
            }
        }
    }
}

@Composable
private fun Auth(vm:LemmiqViewModel){
    var signup by remember{mutableStateOf(false)}
    var user by remember{mutableStateOf("")}
    var name by remember{mutableStateOf("")}
    var pass by remember{mutableStateOf("")}
    var referral by remember{mutableStateOf("")}
    Box(Modifier.fillMaxSize().background(Bg),contentAlignment=Alignment.Center){
        Card(Modifier.fillMaxWidth().padding(24.dp),shape=RoundedCornerShape(28.dp)){
            Column(Modifier.padding(24.dp),horizontalAlignment=Alignment.CenterHorizontally){
                BrandMark(88.dp)
                Spacer(Modifier.height(12.dp))
                Text("lemmiq",fontSize=36.sp,fontWeight=FontWeight.Black)
                Text("Messaging with social IQ.",color=Muted)
                Spacer(Modifier.height(24.dp))
                OutlinedTextField(user,{user=it.filter{c->c.isLetterOrDigit()||c=='_'}},Modifier.fillMaxWidth(),label={Text("Username")},prefix={Text("@")},singleLine=true)
                if(signup){
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(name,{name=it},Modifier.fillMaxWidth(),label={Text("Display name")},singleLine=true)
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(
                        referral,
                        {referral=it.uppercase().filter{ch->ch.isLetterOrDigit()||ch=='-'}},
                        Modifier.fillMaxWidth(),
                        label={Text("Referral code (optional)")},
                        placeholder={Text("Q123-ABCDEF")},
                        singleLine=true
                    )
                }
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(pass,{pass=it},Modifier.fillMaxWidth(),label={Text("Password")},singleLine=true,visualTransformation=PasswordVisualTransformation())
                vm.error?.let{Text(it,color=MaterialTheme.colorScheme.error,fontSize=12.sp,modifier=Modifier.padding(top=8.dp))}
                Spacer(Modifier.height(14.dp))
                Button(
                    onClick={if(signup)vm.register(user,name.ifBlank{user},pass,referral) else vm.login(user,pass)},
                    enabled=!vm.busy&&user.length>=3&&pass.length>=6&&(!signup||name.isNotBlank()),
                    modifier=Modifier.fillMaxWidth().height(50.dp),
                    shape=RoundedCornerShape(18.dp)
                ){Text(if(vm.busy)"Please wait…" else if(signup)"Create account" else "Log in")}
                TextButton(onClick={signup=!signup}){Text(if(signup)"Already have an account? Log in" else "New to LEMMIQ? Create account")}
                Text("Private beta — not end-to-end encrypted yet.",color=Muted,fontSize=10.sp)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Home(vm:LemmiqViewModel){
    var tab by remember{mutableIntStateOf(0)}
    var morePage by remember{mutableStateOf<String?>(null)}
    var showMore by remember{mutableStateOf(false)}
    var newChat by remember{mutableStateOf(false)}
    var newGroup by remember{mutableStateOf(false)}
    var qSheet by remember{mutableStateOf(false)}
    var qFullScreen by remember{mutableStateOf(false)}
    LaunchedEffect(Unit){
        vm.refreshChats();vm.refreshGroups();vm.refreshStatuses();vm.refreshTrustHistory();vm.refreshSocialIq();vm.refreshMoments();vm.refreshCalls();vm.refreshPredict()
    }
    val launchRoute=LemmiqLaunchRouterV2103.route.value
    LaunchedEffect(launchRoute,vm.chats,vm.groups){
        val r=launchRoute?:return@LaunchedEffect
        when(r.type){
            "chat"->r.id?.let{id->vm.chats.firstOrNull{it.id==id}?.let{tab=0;showMore=false;qFullScreen=false;vm.open(it);LemmiqLaunchRouterV2103.consume()}}
            "group"->r.id?.let{id->vm.groups.firstOrNull{it.id==id}?.let{tab=0;showMore=false;qFullScreen=false;vm.openGroup(it);LemmiqLaunchRouterV2103.consume()}}
            "q_predict","q_predict_result","q_predict_close","q_predict_void","q_predict_watch"->{tab=3;showMore=false;qFullScreen=false;r.id?.let{vm.openPredictMarket(it)};LemmiqLaunchRouterV2103.consume()}
            "q_daily_ready","q_credit","q_transfer","q_referral","q_package","q_market"->{tab=2;showMore=false;qFullScreen=false;LemmiqLaunchRouterV2103.consume()}
            "q_assistant","q_to_q","q_analysis"->{qFullScreen=true;showMore=false;LemmiqLaunchRouterV2103.consume()}
            else->{if(r.type.isNotBlank()){showMore=true;morePage="notifications";qFullScreen=false;LemmiqLaunchRouterV2103.consume()}}
        }
    }
    val nav=listOf(
        "💬" to "Chats",
        "⭕" to "Updates",
        "Q+" to "Q Economy",
        "◈" to "Q Predict",
        "📞" to "Calls",
        "☰" to "More"
    )
    val totalUnread=vm.chats.sumOf{it.unread}+vm.groups.sumOf{it.unread}
    Scaffold(
        containerColor=Bg,
        bottomBar={
            NavigationBar{
                nav.forEachIndexed{i,x->
                    NavigationBarItem(
                        selected=!qFullScreen && if(i==5) showMore else (!showMore && tab==i),
                        onClick={
                            qFullScreen=false
                            morePage=null
                            if(i==5){
                                showMore=true
                            }else{
                                tab=i
                                showMore=false
                            }
                        },
                        icon={
                            if(i==0 && totalUnread>0){
                                BadgedBox(badge={Badge{Text(if(totalUnread>99)"99+" else totalUnread.toString())}}){
                                    Text(x.first,fontWeight=FontWeight.Bold,fontSize=17.sp)
                                }
                            }else Text(x.first,fontWeight=FontWeight.Bold,fontSize=if(i==2)15.sp else 17.sp)
                        },
                        label={Text(x.second,fontSize=8.sp,maxLines=1)},
                        alwaysShowLabel=true
                    )
                }
            }
        },
        floatingActionButton={
            Column(horizontalAlignment=Alignment.End,verticalArrangement=Arrangement.spacedBy(8.dp)){
                if(tab==0&&!showMore&&!qFullScreen)SmallFloatingActionButton({newChat=true},containerColor=Soft,contentColor=Purple){Text("+",fontSize=23.sp)}
                if(!qFullScreen && vm.active==null && vm.activeGroup==null)FloatingActionButton(
                    {qSheet=true},
                    containerColor=Purple.copy(alpha=.68f),
                    contentColor=Color.White,
                    shape=CircleShape
                ){Text("Q",fontSize=24.sp,fontWeight=FontWeight.Black)}
            }
        }
    ){pad->
        Box(Modifier.padding(pad)){
            when{
                qFullScreen->Column(Modifier.fillMaxSize()){
                    Surface(shadowElevation=1.dp){Row(Modifier.fillMaxWidth().padding(8.dp),verticalAlignment=Alignment.CenterVertically){TextButton({qFullScreen=false}){Text("‹ Back")};Text("Q · Personal Assistant",fontWeight=FontWeight.Bold)}}
                    Box(Modifier.weight(1f)){ChatAgent(vm)}
                }
                showMore->when(morePage){
                    "trust"->V241MoreSubPage("Trust / Fact Check",{morePage=null}){V24Trust(vm)}
                    "business"->V241MoreSubPage("Business Agent",{morePage=null}){BusinessScreen(vm)}
                    "activity"->V241MoreSubPage("Activity",{morePage=null}){ActivityScreen(vm)}
                    "money"->V241MoreSubPage("Money",{morePage=null}){MoneyScreen(vm)}
                    "me"->V241MoreSubPage("Me / Profile",{morePage=null}){Profile(vm)}
                    "settings"->V241MoreSubPage("Settings",{morePage=null}){V2102SettingsScreen(vm)}
                    "privacy"->V241MoreSubPage("Privacy & Security",{morePage=null}){V2102PrivacyScreen(vm)}
                    "notifications"->V241MoreSubPage("Notifications",{morePage=null}){LemmiqNotificationCenterV2103()}
                    else->V241MoreMenu{morePage=it}
                }
                else->when(tab){
                    0->V24Inbox(vm,onNewGroup={newGroup=true},onAskQ={prompt->
                        qFullScreen=true
                        if(prompt.isNotBlank())vm.askAgent(prompt)
                    })
                    1->V24Updates(vm)
                    2->V28QEconomyScreen(vm)
                    3->V29PredictScreen(vm){prompt->qFullScreen=true;vm.askAgent(prompt)}
                    4->V241CallsScreen(vm)
                    else->V24Inbox(vm,onNewGroup={newGroup=true},onAskQ={prompt->
                        qFullScreen=true
                        if(prompt.isNotBlank())vm.askAgent(prompt)
                    })
                }
            }
        }
    }
    if(qSheet){
        ModalBottomSheet(onDismissRequest={qSheet=false}){
            Column(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=6.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
                Row(verticalAlignment=Alignment.CenterVertically){Surface(color=Purple,shape=CircleShape){Text("Q",Modifier.padding(horizontal=15.dp,vertical=10.dp),color=Color.White,fontSize=20.sp,fontWeight=FontWeight.Black)};Spacer(Modifier.width(12.dp));Column{Text("Your LEMMIQ assistant",fontSize=21.sp,fontWeight=FontWeight.Black);Text("Available wherever you are in LEMMIQ.",fontSize=11.sp,color=Muted)}}
                listOf("Catch me up","What did I promise?","Which chats need a reply?").forEach{prompt->
                    OutlinedButton(onClick={qSheet=false;qFullScreen=true;vm.askAgent(prompt)},modifier=Modifier.fillMaxWidth()){Text(prompt)}
                }
                Button(onClick={qSheet=false;qFullScreen=true},modifier=Modifier.fillMaxWidth()){Text("Open full Q workspace")}
                Spacer(Modifier.height(18.dp))
            }
        }
    }
    if(newChat)NewChat(vm){newChat=false}
    if(newGroup)V24NewGroupDialog(vm){newGroup=false}
}

@Composable
private fun Header(title:String,sub:String?=null){
    Column(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=16.dp)){
        Text(title,fontSize=29.sp,fontWeight=FontWeight.Black,color=Ink)
        if(sub!=null)Text(sub,color=Muted,fontSize=12.sp)
    }
}


@Composable
private fun V241CallsScreen(vm:LemmiqViewModel){
    val ctx=LocalContext.current
    LaunchedEffect(Unit){vm.refreshCalls()}
    LazyColumn(Modifier.fillMaxSize().background(Bg),contentPadding=PaddingValues(bottom=24.dp)){
        item{Header("Calls","Missed, no-answer and completed LEMMIQ voice calls")}
        if(vm.callHistory.isEmpty()){
            item{Empty("📞","No calls yet","Your LEMMIQ voice call history will appear here.")}
        }else{
            items(vm.callHistory,key={it.id}){c->
                val other=c.other_user?:UserDto(0,"","LEMMIQ user")
                val status=c.status.uppercase()
                val label=when(status){
                    "MISSED"->"Missed voice call"
                    "RINGING"->"No answer"
                    "DECLINED"->"Declined voice call"
                    else->"Voice call"
                }
                val statusColor=when(status){
                    "MISSED"->Color(0xFFD63C57)
                    "RINGING"->Color(0xFF9B6B10)
                    else->Mint
                }
                Card(Modifier.fillMaxWidth().padding(horizontal=18.dp,vertical=5.dp),shape=RoundedCornerShape(18.dp)){
                    Row(Modifier.fillMaxWidth().padding(12.dp),verticalAlignment=Alignment.CenterVertically){
                        V24Avatar(other,46)
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)){
                            Text(other.display_name,fontWeight=FontWeight.Bold)
                            Text(label,color=statusColor,fontSize=11.sp)
                            Text(
                                "${if(c.duration_seconds>0)"${c.duration_seconds/60}m ${c.duration_seconds%60}s · " else ""}${v24FriendlyDay(c.started_at)} · ${v24Time(c.started_at)}",
                                color=Muted,fontSize=10.sp
                            )
                        }
                        FilledTonalButton(onClick={
                            vm.startVoiceCall(c.chat_id){join->
                                ctx.startActivity(Intent(ctx,LemmiqCallActivity::class.java).apply{
                                    putExtra("call_id",join.call.id)
                                    putExtra("ws_url",join.ws_url)
                                    putExtra("token",join.token)
                                    putExtra("person",other.display_name)
                                    putExtra("avatar_url",other.avatar_url)
                                    putExtra("incoming",false)
                                })
                            }
                        }){Text("📞")}
                    }
                }
            }
        }
    }
}

@Composable
private fun V241MoreMenu(onOpen:(String)->Unit){
    val menuItems=listOf(
        Triple("🔔","Notifications","Unread alerts and recent LEMMIQ activity") to "notifications",
        Triple("🛡","Trust / Fact Check","Saved checks and scam/fact verification") to "trust",
        Triple("💼","Business Agent","Business knowledge and customer replies") to "business",
        Triple("◈","Activity","Detected notification intelligence") to "activity",
        Triple("💳","Money","Review detected payment insights") to "money",
        Triple("🙂","Me / Profile","Photo, account and sign out") to "me",
        Triple("⚙","Settings","Notifications, app version and controls") to "settings",
        Triple("🔒","Privacy & Security","Profile, last-seen and status privacy") to "privacy"
    )
    LazyColumn(Modifier.fillMaxSize().background(Bg),contentPadding=PaddingValues(top=8.dp,bottom=24.dp)){
        item{Text("More",fontSize=28.sp,fontWeight=FontWeight.Black,color=Ink,modifier=Modifier.padding(horizontal=20.dp,vertical=10.dp))}
        items(menuItems){entry->
            val info=entry.first
            Card(
                Modifier.fillMaxWidth().padding(horizontal=18.dp,vertical=6.dp).clickable{onOpen(entry.second)},
                shape=RoundedCornerShape(20.dp)
            ){
                Row(Modifier.fillMaxWidth().padding(16.dp),verticalAlignment=Alignment.CenterVertically){
                    Text(info.first,fontSize=26.sp)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)){Text(info.second,fontWeight=FontWeight.Bold,fontSize=16.sp);Text(info.third,color=Muted,fontSize=11.sp)}
                    Text("›",fontSize=28.sp,color=Muted)
                }
            }
        }
    }
}

@Composable
private fun V241MoreSubPage(title:String,onBack:()->Unit,content:@Composable ()->Unit){
    Column(Modifier.fillMaxSize()){
        Surface(shadowElevation=1.dp){
            Row(Modifier.fillMaxWidth().padding(horizontal=8.dp,vertical=6.dp),verticalAlignment=Alignment.CenterVertically){
                Text("‹",fontSize=34.sp,modifier=Modifier.clickable(onClick=onBack).padding(8.dp))
                Text(title,fontWeight=FontWeight.Bold,fontSize=18.sp)
            }
        }
        Box(Modifier.weight(1f)){content()}
    }
}

@Composable
private fun V2102SettingsScreen(vm:LemmiqViewModel){
    val ctx=LocalContext.current
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom=24.dp),
        verticalArrangement=Arrangement.spacedBy(10.dp)
    ){
        Card(Modifier.fillMaxWidth().padding(horizontal=18.dp,vertical=8.dp),shape=RoundedCornerShape(20.dp)){
            Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(6.dp)){
                Text("LEMMIQ app",fontWeight=FontWeight.Bold,fontSize=18.sp)
                Text("Version ${BuildConfig.VERSION_NAME}",color=Muted,fontSize=12.sp)
                Text("Server: ${vm.serverUrl}",color=Muted,fontSize=11.sp)
            }
        }
        Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(20.dp)){
            Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                Text("Notifications",fontWeight=FontWeight.Bold,fontSize=17.sp)
                Text("LEMMIQ push registration refreshes automatically. Android notification permission can be managed in system settings.",fontSize=11.sp,color=Muted)
                OutlinedButton(onClick={
                    val intent=Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).apply{
                        putExtra(Settings.EXTRA_APP_PACKAGE,ctx.packageName)
                    }
                    runCatching{ctx.startActivity(intent)}
                },modifier=Modifier.fillMaxWidth()){Text("Open notification settings")}
            }
        }
        Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(20.dp)){
            Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
                Text("Q & app controls",fontWeight=FontWeight.Bold,fontSize=17.sp)
                Text("Q assistant, Q Economy, Q Predict and Calls remain separate main tabs. Profile, Trust, Business and privacy live under More.",fontSize=11.sp,color=Muted)
            }
        }
    }
}

@Composable
private fun V2102PrivacyScreen(vm:LemmiqViewModel){
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom=24.dp)){
        V24PrivacyCard(vm)
        Card(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=6.dp),shape=RoundedCornerShape(20.dp)){
            Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(6.dp)){
                Text("Security",fontWeight=FontWeight.Bold,fontSize=18.sp)
                Text("LEMMIQ never reads its own notifications. Cross-app intelligence only processes third-party apps that you explicitly permit.",fontSize=11.sp,color=Muted)
                Text("Private beta: messenger and synced events are currently server-readable and are not end-to-end encrypted.",fontSize=11.sp,color=Muted)
            }
        }
    }
}

@Composable
private fun Inbox(vm:LemmiqViewModel){
    LaunchedEffect(Unit){vm.refreshAgent();vm.refreshSocialIq()}
    Column(Modifier.fillMaxSize()){
        Header("lemmiq",if(vm.socketStatus=="online")"● connected" else "○ ${vm.socketStatus}")
        GradientPanel("Q · AI Inbox","Your conversations, intelligently organised"){
                Text("Your inbox",color=Color.White,fontWeight=FontWeight.Bold)
                val unread=vm.chats.sumOf{it.unread}
                Text(if(unread==0)"You're caught up." else "$unread unread message${if(unread==1)"" else "s"} waiting.",color=Color(0xFFDDDBE8),modifier=Modifier.padding(top=6.dp))
                Text("Each chat can be Off, Assist or Auto.",color=Color(0xFFB9AAFF),fontSize=11.sp,modifier=Modifier.padding(top=6.dp))
                vm.agentBrief?.let{b->Text("${b.needs_reply_count} conversations may need a reply.",color=Color.White,fontSize=11.sp)}
        }
        Text("Chats",fontSize=20.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(20.dp,18.dp,20.dp,6.dp))
        if(vm.chats.isEmpty())Empty("💬","No conversations yet","Tap + and search another username.")
        else LazyColumn{items(vm.chats,key={it.id}){c->ChatRow(c){vm.open(c)}}}
    }
}

@Composable
private fun ChatRow(c:ChatDto,click:()->Unit){
    Row(Modifier.fillMaxWidth().clickable(onClick=click).padding(horizontal=20.dp,vertical=12.dp),verticalAlignment=Alignment.CenterVertically){
        Avatar(c.other_user)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)){
            Row{
                Text(c.other_user.display_name,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f))
                Text(catEmoji(c.category))
            }
            Text(c.last_message?:"Start chatting",color=Muted,maxLines=1,overflow=TextOverflow.Ellipsis,fontSize=13.sp)
        }
        Column(horizontalAlignment=Alignment.End){
            Mode(c.ai_mode)
            if(c.unread>0){
                Spacer(Modifier.height(5.dp))
                Box(Modifier.size(20.dp).clip(CircleShape).background(Purple),contentAlignment=Alignment.Center){Text("${c.unread}",color=Color.White,fontSize=10.sp)}
            }
        }
    }
}
@Composable
private fun Avatar(u:UserDto){ V24Avatar(u) }

@Composable
private fun Mode(m:String){
    val label=when(m){"AUTO"->"⚡ Auto";"ASSIST"->"✨ Assist";else->"AI Off"}
    Surface(color=if(m=="AUTO")Color(0xFFE7FFF1) else if(m=="ASSIST")Soft else Color(0xFFF0F0F4),shape=RoundedCornerShape(100.dp)){
        Text(label,Modifier.padding(horizontal=8.dp,vertical=4.dp),color=if(m=="OFF")Muted else Purple,fontSize=10.sp,fontWeight=FontWeight.Bold)
    }
}

@Composable
private fun NewChat(vm:LemmiqViewModel,dismiss:()->Unit){
    var q by remember{mutableStateOf("")}
    AlertDialog(
        onDismissRequest=dismiss,
        title={Text("New message")},
        text={
            Column{
                OutlinedTextField(q,{q=it;vm.search(it)},Modifier.fillMaxWidth(),label={Text("Search username or name")},singleLine=true)
                Spacer(Modifier.height(8.dp))
                LazyColumn(Modifier.heightIn(max=320.dp)){
                    items(vm.users,key={it.id}){u->
                        Row(Modifier.fillMaxWidth().clickable{vm.start(u.id);dismiss()}.padding(vertical=9.dp),verticalAlignment=Alignment.CenterVertically){
                            Avatar(u);Spacer(Modifier.width(10.dp))
                            Column{Text(u.display_name,fontWeight=FontWeight.Bold);Text("@${u.username}",color=Muted,fontSize=12.sp)}
                        }
                    }
                }
            }
        },
        confirmButton={TextButton(dismiss){Text("Close")}}
    )
}

@Composable
private fun Chat(vm:LemmiqViewModel){
    val c=vm.active?:return
    var draft by remember(c.id){mutableStateOf(c.draft_text)}
    var settings by remember{mutableStateOf(false)}
    var businessSettings by remember{mutableStateOf(false)}
    var showAttach by remember{mutableStateOf(false)}
    var showSearch by remember{mutableStateOf(false)}
    var showMore by remember{mutableStateOf(false)}
    var actionMessage by remember{mutableStateOf<MessageDto?>(null)}
    var forwardMessage by remember{mutableStateOf<MessageDto?>(null)}
    val ctx=LocalContext.current
    val voiceRecorder=remember{LemmiqVoiceRecorder(ctx)}
    var voiceRecording by remember{mutableStateOf(false)}
    val micPermission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){granted->
        if(granted){runCatching{voiceRecorder.start()}.onSuccess{voiceRecording=true}.onFailure{vm.error=it.message}}
    }
    var pendingContact by remember{mutableStateOf<Pair<String,String>?>(null)}
    val photoPicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){
        uri->if(uri!=null)vm.uploadUri(uri)
    }
    val videoPicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){
        uri->if(uri!=null)vm.uploadUri(uri)
    }
    val filePicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){
        uri->if(uri!=null)vm.uploadUri(uri)
    }
    val contactPicker=rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()){result->
        val uri=result.data?.data
        if(result.resultCode==android.app.Activity.RESULT_OK && uri!=null){
            runCatching{
                ctx.contentResolver.query(uri,arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER),null,null,null)?.use{cursor->
                    if(cursor.moveToFirst()){
                        val name=cursor.getString(0).orEmpty()
                        val phone=cursor.getString(1).orEmpty()
                        if(name.isNotBlank() && phone.isNotBlank())pendingContact=name to phone
                    }
                }
            }
        }
    }
    val messageListState=rememberLazyListState()
    val timeline=remember(vm.messages,vm.activeCalls){
        buildList<Pair<String,Any>>{
            vm.messages.forEach{add("message" to it)}
            vm.activeCalls.forEach{add("call" to it)}
        }.sortedBy{(_,x)->when(x){is MessageDto->x.created_at;is CallDto->x.started_at;else->""}}
    }
    LaunchedEffect(c.id,timeline.size){
        if(timeline.isNotEmpty())runCatching{messageListState.scrollToItem(timeline.lastIndex)}
    }
    Scaffold(
        containerColor=Bg,
        topBar={
            Surface(
                modifier=Modifier.fillMaxWidth().statusBarsPadding(),
                shadowElevation=1.dp
            ){
                Row(Modifier.fillMaxWidth().padding(horizontal=8.dp,vertical=6.dp),verticalAlignment=Alignment.CenterVertically){
                    Text("‹",fontSize=36.sp,modifier=Modifier.clickable{vm.close()}.padding(8.dp))
                    Avatar(c.other_user);Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)){
                        Text(c.other_user.display_name,fontWeight=FontWeight.Bold)
                        Text("@${c.other_user.username} · ${catEmoji(c.category)} ${pretty(c.category)} · ${pretty(c.ai_mode)}",color=Muted,fontSize=10.sp)
                    }
                    Text("📞",fontSize=18.sp,modifier=Modifier.clickable{
                        vm.startVoiceCall(c.id){join->
                            ctx.startActivity(Intent(ctx,LemmiqCallActivity::class.java).apply{
                                putExtra("call_id",join.call.id);putExtra("ws_url",join.ws_url);putExtra("token",join.token)
                                putExtra("person",c.other_user.display_name);putExtra("avatar_url",c.other_user.avatar_url);putExtra("incoming",false)
                            })
                        }
                    }.padding(8.dp))
                    Text("🔎",fontSize=17.sp,modifier=Modifier.clickable{showSearch=true}.padding(7.dp))
                    Text("⋮",fontSize=22.sp,modifier=Modifier.clickable{showMore=true}.padding(7.dp))
                    if(c.ai_mode!="OFF")Text("Q",color=Purple,fontWeight=FontWeight.Black,fontSize=22.sp,modifier=Modifier.clickable{vm.suggest()}.padding(8.dp))
                    if(vm.businessProfile.enabled)Text("💼",fontSize=18.sp,modifier=Modifier.clickable{businessSettings=true}.padding(6.dp))
                    Text("⚙",fontSize=19.sp,modifier=Modifier.clickable{settings=true}.padding(8.dp))
                }
            }
        },
        bottomBar={
            // Keep composer above the keyboard without re-scrolling on every character.
            Column(Modifier.background(Color.White).navigationBarsPadding().imePadding()){
                vm.replyTo?.let{r->
                    Surface(color=Soft,shape=RoundedCornerShape(14.dp),modifier=Modifier.padding(horizontal=10.dp,vertical=4.dp)){
                        Row(Modifier.fillMaxWidth().padding(8.dp),verticalAlignment=Alignment.CenterVertically){
                            Column(Modifier.weight(1f)){Text("Replying",color=Purple,fontWeight=FontWeight.Bold,fontSize=10.sp);Text(r.text,maxLines=1,overflow=TextOverflow.Ellipsis,fontSize=11.sp)}
                            TextButton({vm.setReply(null)}){Text("×")}
                        }
                    }
                }
                vm.businessSuggestion?.let{bs->
                    Surface(color=Color(0xFFEAF8F2),shape=RoundedCornerShape(18.dp),modifier=Modifier.padding(10.dp,5.dp)){
                        Column(Modifier.padding(12.dp)){
                            Row(verticalAlignment=Alignment.CenterVertically){
                                Text("💼 Business Agent",color=Color(0xFF08775D),fontWeight=FontWeight.Bold,fontSize=12.sp)
                                Spacer(Modifier.weight(1f))
                                Text("${bs.confidence}% grounded",fontSize=10.sp,color=Muted)
                            }
                            Text(bs.reply,modifier=Modifier.padding(top=5.dp))
                            if(bs.reason.isNotBlank())Text(bs.reason,fontSize=10.sp,color=Muted,modifier=Modifier.padding(top=5.dp))
                            if(bs.sources.isNotEmpty())Text("Sources: "+bs.sources.joinToString{it.title},fontSize=10.sp,color=Muted,modifier=Modifier.padding(top=3.dp))
                            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                                TextButton({vm.discardBusinessSuggestion()}){Text("Discard",color=Muted)}
                                Spacer(Modifier.weight(1f))
                                TextButton({draft=bs.reply;vm.discardBusinessSuggestion()}){Text("Edit")}
                                Button({vm.send(bs.reply);vm.discardBusinessSuggestion()}){Text("Send")}
                            }
                        }
                    }
                }
                vm.suggestion?.let{s->
                    Surface(color=Soft,shape=RoundedCornerShape(18.dp),modifier=Modifier.padding(10.dp,5.dp)){
                        Column(Modifier.padding(12.dp)){
                            Text("Q  Suggested reply",color=Purple,fontWeight=FontWeight.Bold,fontSize=11.sp)
                            Text(s,modifier=Modifier.padding(top=4.dp))
                            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                                TextButton(onClick={vm.discardSuggestion()}){Text("Discard",color=Muted)}
                                Spacer(Modifier.weight(1f))
                                TextButton(onClick={draft=s;vm.discardSuggestion()}){Text("Edit")}
                                Button(onClick={vm.send(s)},enabled=!vm.busy){Text("Send")}
                            }
                        }
                    }
                }
                if(vm.busy || vm.attachmentBusy)LinearProgressIndicator(Modifier.fillMaxWidth(),color=Purple)
                vm.error?.let{Text(it,color=MaterialTheme.colorScheme.error,fontSize=11.sp,
                    modifier=Modifier.padding(horizontal=14.dp))}
                if(showAttach){
                    Card(Modifier.fillMaxWidth().padding(horizontal=12.dp,vertical=4.dp),
                        colors=CardDefaults.cardColors(containerColor=Soft)){
                        Column(Modifier.padding(12.dp)){
                            Text("Share in this chat",fontWeight=FontWeight.Bold,color=Purple)
                            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceEvenly){
                                TextButton({photoPicker.launch("image/*");showAttach=false}){Text("🖼 Photo")}
                                TextButton({videoPicker.launch("video/*");showAttach=false}){Text("🎬 Video")}
                            }
                            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceEvenly){
                                TextButton({filePicker.launch("*/*");showAttach=false}){Text("📄 File")}
                                TextButton({
                                    contactPicker.launch(Intent(Intent.ACTION_PICK,
                                        ContactsContract.CommonDataKinds.Phone.CONTENT_URI))
                                    showAttach=false
                                }){Text("👤 Contact")}
                            }
                            Text("Files up to 20 MB. Shared content is not end-to-end encrypted.",fontSize=10.sp,color=Muted)
                        }
                    }
                }
                Row(Modifier.fillMaxWidth().padding(10.dp),verticalAlignment=Alignment.CenterVertically){
                    Text("+",fontWeight=FontWeight.Bold,fontSize=28.sp,color=Purple,
                        modifier=Modifier.clickable{showAttach=!showAttach}.padding(horizontal=5.dp))
                    OutlinedTextField(
                        draft,{draft=it},Modifier.weight(1f),placeholder={Text("Message ${c.other_user.display_name}…")},
                        singleLine=true,shape=RoundedCornerShape(24.dp),
                        keyboardOptions=KeyboardOptions(imeAction=ImeAction.Send),
                        keyboardActions=KeyboardActions(onSend={if(draft.isNotBlank()){vm.send(draft);draft=""}})
                    )
                    Spacer(Modifier.width(6.dp))
                    Surface(Modifier.size(44.dp).clickable{
                        if(voiceRecording){
                            voiceRecorder.stop()?.let{vm.sendVoiceFile(it.first,it.second)}
                            voiceRecording=false
                        }else if(ContextCompat.checkSelfPermission(ctx,Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED){
                            runCatching{voiceRecorder.start()}.onSuccess{voiceRecording=true}.onFailure{vm.error=it.message}
                        }else micPermission.launch(Manifest.permission.RECORD_AUDIO)
                    },color=if(voiceRecording)Color(0xFFFFE7EA) else Soft,shape=CircleShape){
                        Box(contentAlignment=Alignment.Center){Text(if(voiceRecording)"■" else "🎙",color=if(voiceRecording)Color(0xFFC72B48) else Purple)}
                    }
                    Spacer(Modifier.width(6.dp))
                    Surface(Modifier.size(48.dp).clickable{if(draft.isNotBlank()){vm.send(draft);draft=""}},color=Purple,shape=CircleShape){
                        Box(contentAlignment=Alignment.Center){Text("➤",color=Color.White)}
                    }
                }
            }
        }
    ){p->
        Column(Modifier.fillMaxSize().padding(p)){
            if(vm.businessProfile.enabled && vm.activeBusinessSetting.enabled){
                Row(Modifier.fillMaxWidth().padding(12.dp,5.dp),verticalAlignment=Alignment.CenterVertically){
                    FilledTonalButton({vm.suggestBusiness()},enabled=!vm.businessBusy && vm.activeBusinessSetting.mode!="OFF"){Text("💼 Business reply")}
                    Spacer(Modifier.width(6.dp))
                    TextButton({businessSettings=true}){Text("Customer memory")}
                    Spacer(Modifier.weight(1f))
                    Text("${vm.activeBusinessSetting.mode}",fontSize=10.sp,color=Color(0xFF08775D),fontWeight=FontWeight.Bold)
                }
            }
            if(c.ai_mode!="OFF"){
                Row(Modifier.fillMaxWidth().padding(12.dp,7.dp),verticalAlignment=Alignment.CenterVertically){
                    FilledTonalButton({vm.suggest()},enabled=!vm.busy){Text("✨ Suggest reply")}
                    Spacer(Modifier.width(6.dp))
                    TextButton({vm.summarizeActiveChat()}){Text("🧠 Summary")}
                    Spacer(Modifier.weight(1f))
                    if(c.ai_mode=="AUTO")Text("⚡ Auto enabled",color=Color(0xFF11844F),fontSize=11.sp,fontWeight=FontWeight.Bold)
                }
            }
            if(timeline.isEmpty())Empty("👋","Start the conversation","Messages appear here in real time.")
            else LazyColumn(
                modifier=Modifier.fillMaxSize(),
                state=messageListState,
                contentPadding=PaddingValues(14.dp),
                verticalArrangement=Arrangement.spacedBy(7.dp)
            ){
                itemsIndexed(timeline,key={_,item->
                    val x=item.second
                    when(x){is MessageDto->"m_${x.id}";is CallDto->"c_${x.id}";else->item.hashCode().toString()}
                }){index,item->
                    val at=when(val x=item.second){is MessageDto->x.created_at;is CallDto->x.started_at;else->""}
                    val day=v24FriendlyDay(at)
                    val prev=if(index>0)when(val x=timeline[index-1].second){is MessageDto->v24FriendlyDay(x.created_at);is CallDto->v24FriendlyDay(x.started_at);else->""} else null
                    if(day!=prev)V24DateSeparator(day)
                    when(val x=item.second){
                        is MessageDto->Bubble(x,vm.store.userId,vm,{vm.trustCheck(x.text)},{actionMessage=x})
                        is CallDto->{
                            val label=when(x.status){"MISSED"->"Missed voice call";"DECLINED"->"Voice call · declined";"RINGING"->"Voice call · no answer";else->"Voice call"}
                            Card(Modifier.fillMaxWidth(.72f),colors=CardDefaults.cardColors(containerColor=Color.White)){
                                Column(Modifier.padding(10.dp)){Text("📞 $label",fontWeight=FontWeight.Bold);Text((if(x.duration_seconds>0)"${x.duration_seconds/60}m ${x.duration_seconds%60}s · " else "")+v24Time(x.started_at),fontSize=10.sp,color=Muted)}
                            }
                        }
                    }
                }
            }
        }
    }
    if(showSearch){
        var q by remember{mutableStateOf("")}
        AlertDialog(onDismissRequest={showSearch=false;vm.insideSearchResults=emptyList()},title={Text("Search this chat")},
            text={Column{OutlinedTextField(q,{q=it;vm.searchInsideChat(it)},Modifier.fillMaxWidth(),placeholder={Text("Search messages")});LazyColumn(Modifier.heightIn(max=300.dp)){items(vm.insideSearchResults,key={it.id}){m->Column(Modifier.fillMaxWidth().padding(vertical=7.dp)){Text(m.text,maxLines=3);Text(v24FriendlyDay(m.created_at)+" · "+v24Time(m.created_at),fontSize=10.sp,color=Muted)}}}}},
            confirmButton={TextButton({showSearch=false;vm.insideSearchResults=emptyList()}){Text("Close")}})
    }
    if(showMore){
        AlertDialog(onDismissRequest={showMore=false},title={Text(c.other_user.display_name)},
            text={Column{
                TextButton({vm.togglePin();showMore=false}){Text(if(c.pinned)"Unpin chat" else "📌 Pin chat")}
                TextButton({vm.toggleFavourite();showMore=false}){Text(if(c.favourite)"Remove favourite" else "⭐ Favourite")}
                TextButton({vm.toggleArchive();showMore=false}){Text(if(c.archived)"Unarchive" else "Archive")}
                TextButton({vm.mute8Hours();showMore=false}){Text("🔕 Mute 8 hours")}
                TextButton({vm.blockActiveUser();showMore=false}){Text("Block user",color=Color.Red)}
                TextButton({vm.reportActiveUser("Reported from Android V2.4");showMore=false}){Text("Report",color=Color.Red)}
            }},confirmButton={})
    }
    actionMessage?.let{m->
        var editText by remember(m.id){mutableStateOf(m.text)}
        AlertDialog(onDismissRequest={actionMessage=null},title={Text("Message actions")},
            text={Column{
                TextButton({vm.setReply(m);actionMessage=null}){Text("↩ Reply")}
                TextButton({forwardMessage=m;actionMessage=null}){Text("↗ Forward")}
                Row{listOf("👍","❤️","😂","😮","😢","🙏").forEach{e->Text(e,fontSize=24.sp,modifier=Modifier.clickable{vm.reactMessage(m.id,e);actionMessage=null}.padding(5.dp))}}
                if(m.sender_id==vm.store.userId&&!m.deleted_for_everyone){
                    OutlinedTextField(editText,{editText=it},Modifier.fillMaxWidth(),label={Text("Edit message")})
                    TextButton({vm.editMessage(m.id,editText);actionMessage=null}){Text("Save edit")}
                    TextButton({vm.deleteMessage(m.id,"everyone");actionMessage=null}){Text("Delete for everyone",color=Color.Red)}
                }
                TextButton({vm.deleteMessage(m.id,"me");actionMessage=null}){Text("Delete for me",color=Color.Red)}
            }},confirmButton={})
    }

    forwardMessage?.let{m->
        val selected=remember(m.id){mutableStateListOf<Int>()}
        AlertDialog(onDismissRequest={forwardMessage=null},title={Text("Forward message")},
            text={LazyColumn(Modifier.heightIn(max=360.dp)){
                item{Text(m.text,maxLines=3,overflow=TextOverflow.Ellipsis,modifier=Modifier.padding(bottom=8.dp))}
                items(vm.chats,key={it.id}){chat->
                    val checked=selected.contains(chat.id)
                    Row(Modifier.fillMaxWidth().clickable{if(checked)selected.remove(chat.id)else selected.add(chat.id)}.padding(vertical=7.dp),verticalAlignment=Alignment.CenterVertically){
                        Checkbox(checked,{if(it)selected.add(chat.id)else selected.remove(chat.id)})
                        V24Avatar(chat.other_user,38);Spacer(Modifier.width(8.dp));Text(chat.other_user.display_name)
                    }
                }
            }},
            confirmButton={Button({vm.forwardMessage(m.id,selected.toList());forwardMessage=null},enabled=selected.isNotEmpty()){Text("Forward")}},
            dismissButton={TextButton({forwardMessage=null}){Text("Cancel")}})
    }

    if(settings)Settings(c,vm){settings=false}
    if(businessSettings)BusinessChatDialog(c,vm){businessSettings=false}
    if(vm.businessLearnCandidates.isNotEmpty())BusinessLearnDialog(vm)
    pendingContact?.let{(name,phone)->
        AlertDialog(onDismissRequest={pendingContact=null},title={Text("Share this contact?")},
            text={Text("$name\n$phone\n\nThis contact's number will be visible to the recipient.")},
            confirmButton={Button({vm.shareContact(name,phone);pendingContact=null}){Text("Share")}},
            dismissButton={TextButton({pendingContact=null}){Text("Cancel")}})
    }
    if(vm.trustBusy){
        AlertDialog(
            onDismissRequest={vm.cancelTrust()},
            title={Text("🛡 LEMMIQ Trust")},
            text={Column(verticalArrangement=Arrangement.spacedBy(12.dp)){
                LinearProgressIndicator(Modifier.fillMaxWidth(),color=Purple)
                Text("Checking this message. Searching for evidence may take a little while.")
                Text("You can cancel if you selected the wrong message.",fontSize=11.sp,color=Muted)
            }},
            confirmButton={},
            dismissButton={TextButton(onClick={vm.cancelTrust()}){Text("Cancel check")}}
        )
    } else {
        vm.trustError?.let{message->
            AlertDialog(
                onDismissRequest={vm.clearTrust()},
                title={Text("Trust check unavailable")},
                text={Text(message)},
                confirmButton={TextButton(onClick={vm.clearTrust()}){Text("Close")}}
            )
        }
        vm.trustResult?.let{r->TrustDialog(r){vm.clearTrust()}}
    }
    if(vm.visionBusy && vm.visionSourceMessageId!=null){
        AlertDialog(
            onDismissRequest={vm.cancelVision()},
            title={Text("📷 LEMMIQ Q Vision")},
            text={Column(verticalArrangement=Arrangement.spacedBy(12.dp)){
                LinearProgressIndicator(Modifier.fillMaxWidth(),color=Purple)
                Text("Analysing this image…")
                Text("Understanding visual details and preparing your Q response.",fontSize=12.sp,color=Muted)
            }},
            confirmButton={},
            dismissButton={TextButton(onClick={vm.cancelVision()}){Text("Cancel")}}
        )
    }
    vm.chatSummary?.let{s->ChatSummaryDialog(s){vm.clearChatSummary()}}
}

@Composable
private fun Bubble(m:MessageDto,me:Int,vm:LemmiqViewModel,onTrust:()->Unit,onActions:()->Unit){
    val mine=m.sender_id==me
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    val a=m.attachment
    val isPhoto=isLemmiqImageAttachmentV2102(a)
    var mediaError by remember(m.id){mutableStateOf<String?>(null)}
    val mediaId=a?.media_id
    var bitmap by remember(mediaId){mutableStateOf<android.graphics.Bitmap?>(null)}
    var photoOpen by remember(m.id){mutableStateOf(false)}

    // V2.10.2: recognise image MIME/filename too, not only attachment.kind == PHOTO.
    LaunchedEffect(mediaId,isPhoto){
        if(mediaId!=null && isPhoto){
            try{
                val bytes=withContext(Dispatchers.IO){vm.mediaBytes(mediaId)}
                val bounds=BitmapFactory.Options().apply{inJustDecodeBounds=true}
                BitmapFactory.decodeByteArray(bytes,0,bytes.size,bounds)
                var sample=1
                while(bounds.outWidth/sample>1600 || bounds.outHeight/sample>1600)sample*=2
                val options=BitmapFactory.Options().apply{inSampleSize=sample}
                bitmap=BitmapFactory.decodeByteArray(bytes,0,bytes.size,options)
                if(bitmap==null)mediaError="Unable to decode this photo"
            }catch(e:Exception){mediaError=e.message?:"Unable to load this photo"}
        }
    }

    Column(Modifier.fillMaxWidth(),horizontalAlignment=if(mine)Alignment.End else Alignment.Start){
        Surface(
            color=if(mine)Purple else Color.White,
            shape=RoundedCornerShape(18.dp),
            shadowElevation=if(mine)0.dp else 1.dp
        ){
            Column(
                Modifier
                    .widthIn(max=330.dp)
                    .padding(if(isPhoto)4.dp else 12.dp)
            ){
                if(!isPhoto){
                    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                        if(m.ai_generated)Text("✨ AI AUTO",color=if(mine)Color(0xFFE0D9FF) else Purple,fontSize=9.sp,fontWeight=FontWeight.Bold)
                        Spacer(Modifier.weight(1f))
                        Text("⋯",color=if(mine)Color.White else Muted,modifier=Modifier.clickable(onClick=onActions).padding(horizontal=4.dp))
                    }
                }

                m.reply_to?.let{q->
                    Surface(color=if(mine)Color.White.copy(alpha=.12f) else Soft,shape=RoundedCornerShape(8.dp),modifier=Modifier.padding(if(isPhoto)4.dp else 0.dp)){
                        Text(q.text,Modifier.padding(7.dp),fontSize=10.sp,color=if(mine)Color.White else Ink,maxLines=2,overflow=TextOverflow.Ellipsis)
                    }
                }

                if(a!=null){
                    when{
                        a.kind=="VOICE" -> V24VoiceContent(a,m.id,false,vm,mine)

                        isPhoto -> {
                            bitmap?.let{bmp->
                                Box(Modifier.fillMaxWidth()){
                                    Image(
                                        bmp.asImageBitmap(),
                                        contentDescription="Shared photo",
                                        modifier=Modifier
                                            .fillMaxWidth()
                                            .heightIn(min=150.dp,max=360.dp)
                                            .clip(RoundedCornerShape(15.dp))
                                            .clickable{photoOpen=true},
                                        contentScale=ContentScale.Fit
                                    )
                                    Surface(
                                        color=Color.Black.copy(alpha=.36f),
                                        shape=CircleShape,
                                        modifier=Modifier.align(Alignment.TopEnd).padding(6.dp).clickable(onClick=onActions)
                                    ){
                                        Text("⋯",color=Color.White,fontSize=18.sp,modifier=Modifier.padding(horizontal=9.dp,vertical=2.dp))
                                    }
                                    if(m.ai_generated){
                                        Surface(
                                            color=Color.Black.copy(alpha=.38f),
                                            shape=RoundedCornerShape(99.dp),
                                            modifier=Modifier.align(Alignment.TopStart).padding(7.dp)
                                        ){
                                            Text("✨ AI AUTO",color=Color.White,fontSize=8.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(horizontal=7.dp,vertical=3.dp))
                                        }
                                    }
                                }
                            } ?: Surface(
                                color=if(mine)Color.White.copy(alpha=.10f) else Soft,
                                shape=RoundedCornerShape(14.dp),
                                modifier=Modifier.fillMaxWidth().height(190.dp)
                            ){
                                Box(contentAlignment=Alignment.Center){
                                    if(mediaError==null)CircularProgressIndicator(modifier=Modifier.size(30.dp),strokeWidth=3.dp)
                                    else Text("Unable to load this photo",color=if(mine)Color.White else Muted,fontSize=11.sp)
                                }
                            }

                            if(m.text.isNotBlank())Text(
                                m.text,
                                Modifier.padding(horizontal=7.dp,vertical=6.dp),
                                color=if(mine)Color.White else Ink
                            )

                            if(mediaId!=null)TextButton(
                                enabled=!(vm.visionBusy&&vm.visionSourceMessageId==m.id),
                                onClick={scope.launch{
                                    try{
                                        val bytes=vm.mediaBytes(mediaId)
                                        vm.scanVisionBytes(bytes,"Analyse this chat photo and give me the useful details.",m.id)
                                    }catch(e:Exception){mediaError="Unable to load this photo"}
                                }},
                                contentPadding=PaddingValues(horizontal=7.dp,vertical=2.dp)
                            ){
                                Text(
                                    if(vm.visionBusy&&vm.visionSourceMessageId==m.id)"Analysing…"
                                    else if(vm.error?.startsWith("Q Vision")==true)"↻ Retry Q Vision"
                                    else "📷 Ask Q Vision",
                                    color=if(mine)Color.White else Purple,
                                    fontSize=11.sp
                                )
                            }
                        }

                        a.kind=="VIDEO" -> {
                            Surface(color=if(mine)Color.White.copy(alpha=.10f) else Soft,shape=RoundedCornerShape(14.dp),modifier=Modifier.fillMaxWidth().height(170.dp).clickable{
                                if(a.media_id!=null)scope.launch{
                                    try{
                                        val bytes=vm.mediaBytes(a.media_id);val dir=File(ctx.cacheDir,"share").apply{mkdirs()};val file=File(dir,"${m.id}_video.mp4")
                                        withContext(Dispatchers.IO){file.writeBytes(bytes)};val uri=FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",file)
                                        val intent=Intent(Intent.ACTION_VIEW).apply{setDataAndType(uri,a.mime_type?:"video/mp4");addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)}
                                        ctx.startActivity(Intent.createChooser(intent,"Play video"))
                                    }catch(e:Exception){mediaError="Unable to open this video"}
                                }
                            }){Box(contentAlignment=Alignment.Center){Text("▶",fontSize=42.sp,color=if(mine)Color.White else Purple)}}
                            if(m.text.isNotBlank())Text(m.text,Modifier.padding(top=8.dp),color=if(mine)Color.White else Ink)
                        }

                        a.kind=="CONTACT" -> {
                            Text("👤 ${a.contact_name.orEmpty()}",fontWeight=FontWeight.Bold,color=if(mine)Color.White else Ink)
                            Text(a.contact_phone.orEmpty(),color=if(mine)Color.White else Ink)
                        }

                        a.media_id!=null -> {
                            Text("📄 ${a.name.orEmpty()}",color=if(mine)Color.White else Ink,fontSize=12.sp)
                            TextButton(onClick={scope.launch{
                                mediaError=null
                                try{
                                    val bytes=vm.mediaBytes(a.media_id)
                                    val safeName=(a.name?:"attachment").replace(Regex("[^A-Za-z0-9._-]"),"_")
                                    val dir=File(ctx.cacheDir,"share").apply{mkdirs()};val file=File(dir,"${m.id}_$safeName")
                                    withContext(Dispatchers.IO){file.writeBytes(bytes)}
                                    val uri=FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",file)
                                    val intent=Intent(Intent.ACTION_VIEW).apply{setDataAndType(uri,a.mime_type?:"application/octet-stream");addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)}
                                    ctx.startActivity(Intent.createChooser(intent,"Open attachment"))
                                }catch(e:Exception){mediaError="Unable to open this file"}
                            }}){Text("Open / share",color=if(mine)Color.White else Purple)}
                        }
                    }
                }else Text(m.text,color=if(mine)Color.White else Ink)

                if(m.reactions.isNotEmpty())Row(horizontalArrangement=Arrangement.spacedBy(4.dp),modifier=Modifier.padding(horizontal=if(isPhoto)7.dp else 0.dp)){
                    m.reactions.forEach{r->Surface(color=if(mine)Color.White.copy(alpha=.12f) else Soft,shape=RoundedCornerShape(99.dp)){Text("${r.emoji} ${r.count}",Modifier.padding(horizontal=6.dp,vertical=2.dp),fontSize=10.sp)}}
                }
                if(mediaError!=null && !isPhoto)Text(mediaError.orEmpty(),fontSize=10.sp,color=if(mine)Color.White else Color.Red)
                Row(Modifier.align(Alignment.End).padding(horizontal=if(isPhoto)7.dp else 0.dp,vertical=if(isPhoto)3.dp else 0.dp),verticalAlignment=Alignment.CenterVertically){
                    Text(v24Time(m.created_at)+(if(m.edited_at!=null)" · edited" else ""),color=if(mine)Color(0xFFDCD6FF) else Muted,fontSize=9.sp)
                    if(mine)Text(if(m.read_at!=null)"  ✓✓" else "  ✓",color=Color(0xFFDCD6FF),fontSize=10.sp)
                }
                if(!mine && a==null && !m.deleted_for_everyone)TextButton(onClick=onTrust,modifier=Modifier.align(Alignment.Start).heightIn(min=44.dp),contentPadding=PaddingValues(horizontal=0.dp,vertical=2.dp)){
                    Text("🛡 Fact / Scam Check",color=Purple,fontSize=12.sp,fontWeight=FontWeight.Bold)
                }
            }
        }
    }

    if(photoOpen){
        bitmap?.let{bmp->LemmiqFullScreenPhotoV2102(bitmap=bmp,onDismiss={photoOpen=false})}
    }
}

@Composable
private fun TrustDialog(r:TrustResult,dismiss:()->Unit){
    val uriHandler=androidx.compose.ui.platform.LocalUriHandler.current
    val icon=when(r.status){"SUPPORTED"->"✅";"LIKELY_FALSE"->"❌";"MISLEADING"->"⚠️";"SCAM_RISK"->"🚨";"SUSPICIOUS"->"🟠";else->"🟡"}
    AlertDialog(onDismissRequest=dismiss,title={Text("$icon LEMMIQ Trust")},text={
        LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp)){
            item{Text(r.status.replace("_"," "),fontWeight=FontWeight.Black,color=Purple)}
            item{Text("Evidence confidence: ${r.confidence}%")}
            item{LinearProgressIndicator(progress={r.confidence.coerceIn(0,100)/100f},modifier=Modifier.fillMaxWidth())}
            item{Text(r.summary)}
            if(r.reasons.isNotEmpty()){item{Text("Why",fontWeight=FontWeight.Bold)};items(r.reasons){x->Text("• $x",fontSize=12.sp,color=Muted)}}
            if(r.sources.isNotEmpty()){item{Text("Sources",fontWeight=FontWeight.Bold)};items(r.sources){source->
                        Text(
                            "• ${source.title}\n${source.url}",
                            fontSize=11.sp,color=Purple,
                            modifier=Modifier.clickable(enabled=source.url.startsWith("https://")){
                                runCatching{uriHandler.openUri(source.url)}
                            }.padding(vertical=5.dp)
                        )
                    }}
            if(r.advice.isNotBlank())item{Text(r.advice,fontSize=12.sp,fontWeight=FontWeight.SemiBold)}
            item{Text("Confidence reflects available evidence, not certainty.",fontSize=10.sp,color=Muted)}
        }
    },confirmButton={TextButton(dismiss){Text("Close")}})
}

@Composable
private fun Settings(c:ChatDto,vm:LemmiqViewModel,dismiss:()->Unit){
    var cat by remember{mutableStateOf(c.category)}
    var mode by remember{mutableStateOf(c.ai_mode)}
    var tone by remember{mutableStateOf(c.tone)}
    val cats=listOf("PARTNER","DATING","BESTIE","FRIEND","FAMILY","WORK","CUSTOMER","SALES","STUDY","CUSTOM")
    val tones=listOf("Natural","Warm","Casual","Professional","Direct","Playful","Respectful")
    AlertDialog(
        onDismissRequest=dismiss,
        title={Text("Chat intelligence")},
        text={
            LazyColumn(verticalArrangement=Arrangement.spacedBy(10.dp)){
                item{
                    Text("AI mode",fontWeight=FontWeight.Bold)
                    LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){items(listOf("OFF","ASSIST","AUTO")){x->FilterChip(mode==x,{mode=x},{Text(x)})}}
                }
                item{
                    Text("Relationship / category",fontWeight=FontWeight.Bold)
                    LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){items(cats){x->FilterChip(cat==x,{cat=x},{Text("${catEmoji(x)} ${pretty(x)}")})}}
                }
                item{
                    Text("Tone",fontWeight=FontWeight.Bold)
                    LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){items(tones){x->FilterChip(tone==x,{tone=x},{Text(x)})}}
                }
                if(mode=="AUTO")item{Text("Auto Mode pauses on sensitive/high-risk keywords in V1.",color=Color(0xFF795A16),fontSize=11.sp)}
            }
        },
        confirmButton={Button({vm.saveSettings(cat,mode,tone);dismiss()}){Text("Save")}},
        dismissButton={TextButton(dismiss){Text("Cancel")}}
    )
}

@Composable
private fun Moments(vm:LemmiqViewModel){
    var t by remember{mutableStateOf("")}
    LaunchedEffect(Unit){vm.refreshMoments()}
    Column(Modifier.fillMaxSize()){
        Header("Moments","24-hour text Moments")
        Card(Modifier.fillMaxWidth().padding(horizontal=20.dp),shape=RoundedCornerShape(18.dp)){
            Column(Modifier.padding(14.dp)){
                OutlinedTextField(t,{t=it},Modifier.fillMaxWidth(),label={Text("Share a Moment")})
                Button({vm.postMoment(t);t=""},enabled=t.isNotBlank(),modifier=Modifier.padding(top=8.dp)){Text("Post for 24h")}
            }
        }
        LazyColumn(contentPadding=PaddingValues(20.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            items(vm.moments,key={it.id}){m->
                Card{Row(Modifier.fillMaxWidth().padding(14.dp)){Avatar(m.user);Spacer(Modifier.width(10.dp));Column{Text(m.user.display_name,fontWeight=FontWeight.Bold);Text(m.text)}}}
            }
        }
    }
}

@Composable
private fun ChatAgent(vm:LemmiqViewModel){
    var q by remember{mutableStateOf("")}
    var showCoord by remember{mutableStateOf(false)}
    var showVisionHistory by remember{mutableStateOf(false)}
    var coordSearch by remember{mutableStateOf("")}
    var coordPrompt by remember{mutableStateOf("")}
    var coordOptions by remember{mutableStateOf("")}
    var selectedCoordUsers by remember{mutableStateOf<Map<Int,UserDto>>(emptyMap())}
    var visionQuestion by remember{mutableStateOf("")}
    var visionFollowUp by remember{mutableStateOf("")}

    val gallery=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->
        if(uri!=null)vm.scanVisionUri(uri,visionQuestion.ifBlank{"What is in this image? Give me the useful details."})
    }
    val camera=rememberLauncherForActivityResult(ActivityResultContracts.TakePicturePreview()){bmp->
        if(bmp!=null){
            val out=java.io.ByteArrayOutputStream()
            bmp.compress(android.graphics.Bitmap.CompressFormat.JPEG,90,out)
            vm.scanVisionBytes(out.toByteArray(),visionQuestion.ifBlank{"What is in this photo? Give me the useful details."})
        }
    }

    LaunchedEffect(Unit){vm.refreshAgent()}

    LazyColumn(
        Modifier.fillMaxSize().background(Bg),
        contentPadding=PaddingValues(bottom=110.dp),
        verticalArrangement=Arrangement.spacedBy(12.dp)
    ){
        item{
            Column(Modifier.padding(horizontal=20.dp,vertical=14.dp)){
                Text("Q",fontSize=34.sp,fontWeight=FontWeight.Black,color=Ink)
                Text("Your personal LEMMIQ agent",fontSize=13.sp,color=Muted)
            }
        }

        item{
            Card(
                Modifier.fillMaxWidth().padding(horizontal=20.dp),
                shape=RoundedCornerShape(24.dp),
                colors=CardDefaults.cardColors(containerColor=Color.White)
            ){
                Column(Modifier.padding(14.dp)){
                    OutlinedTextField(
                        value=q,onValueChange={q=it},
                        modifier=Modifier.fillMaxWidth(),
                        placeholder={Text("Ask Q anything…")},
                        minLines=2,maxLines=5,
                        shape=RoundedCornerShape(18.dp)
                    )
                    Row(
                        Modifier.fillMaxWidth().padding(top=8.dp),
                        verticalAlignment=Alignment.CenterVertically,
                        horizontalArrangement=Arrangement.spacedBy(8.dp)
                    ){
                        FilledTonalButton(onClick={gallery.launch("image/*")}){Text("＋")}
                        FilledTonalButton(onClick={camera.launch(null)}){Text("📷")}
                        OutlinedButton(onClick={showVisionHistory=true}){Text("Vision")}
                        Spacer(Modifier.weight(1f))
                        Button(onClick={vm.askAgent(q);q=""},enabled=q.isNotBlank()&&!vm.agentBusy){Text("Ask Q")}
                    }
                    if(vm.visionBusy)LinearProgressIndicator(Modifier.fillMaxWidth().padding(top=8.dp))
                }
            }
        }

        item{
            Row(Modifier.fillMaxWidth().padding(horizontal=20.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                OutlinedButton(onClick={vm.askAgent("Catch me up on my important conversations and anything I may have missed.")},modifier=Modifier.weight(1f)){Text("Catch me up",fontSize=11.sp)}
                OutlinedButton(onClick={vm.askAgent("Which chats need a reply and why?")},modifier=Modifier.weight(1f)){Text("Needs reply",fontSize=11.sp)}
            }
            Row(Modifier.fillMaxWidth().padding(horizontal=20.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                OutlinedButton(onClick={vm.askAgent("What did I promise people recently?")},modifier=Modifier.weight(1f)){Text("My promises",fontSize=11.sp)}
                OutlinedButton(onClick={camera.launch(null)},modifier=Modifier.weight(1f)){Text("📷 Q Vision",fontSize=11.sp)}
            }
        }

        item{
            val today=vm.qHome?.today
            Card(Modifier.fillMaxWidth().padding(horizontal=20.dp),shape=RoundedCornerShape(22.dp),colors=CardDefaults.cardColors(containerColor=Ink)){
                Column(Modifier.padding(18.dp)){
                    Text("Today",color=Color.White,fontSize=20.sp,fontWeight=FontWeight.Black)
                    if(today==null){
                        Text("Q is checking your conversations…",color=Color.White.copy(alpha=.75f),fontSize=12.sp,modifier=Modifier.padding(top=8.dp))
                    }else if(today.needs_reply_count==0 && today.follow_ups==0 && today.promises==0){
                        Text("You're caught up ✓",color=Color.White,fontSize=17.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=8.dp))
                    }else{
                        if(today.needs_reply_count>0)Text("${today.needs_reply_count} conversation${if(today.needs_reply_count==1)"" else "s"} may need a reply",color=Color.White,modifier=Modifier.padding(top=8.dp))
                        if(today.follow_ups>0)Text("${today.follow_ups} follow-up${if(today.follow_ups==1)"" else "s"} due",color=Color.White.copy(alpha=.82f),fontSize=12.sp,modifier=Modifier.padding(top=5.dp))
                        if(today.promises>0)Text("${today.promises} promise${if(today.promises==1)"" else "s"} remembered",color=Color.White.copy(alpha=.82f),fontSize=12.sp,modifier=Modifier.padding(top=5.dp))
                    }
                }
            }
        }

        item{
            val pending=vm.qHome?.q_to_q?.pending_count ?: 0
            Card(Modifier.fillMaxWidth().padding(horizontal=20.dp),shape=RoundedCornerShape(20.dp)){
                Row(Modifier.fillMaxWidth().padding(16.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text("Q-to-Q",fontWeight=FontWeight.Bold,fontSize=17.sp)
                        Text(if(pending==0)"Coordinate plans or availability with LEMMIQ contacts." else "$pending active plan${if(pending==1)"" else "s"}",fontSize=11.sp,color=Muted,modifier=Modifier.padding(top=3.dp))
                    }
                    TextButton({coordPrompt="Find a time that works for us.";showCoord=true}){Text(if(pending==0)"Start" else "Open")}
                }
            }
        }

        item{
            val memories=vm.qHome?.memory?.count ?: (vm.socialBrief?.count ?: 0)
            val scans=vm.qHome?.memory?.vision_count ?: vm.visionHistory.size
            Card(Modifier.fillMaxWidth().padding(horizontal=20.dp),shape=RoundedCornerShape(20.dp)){
                Column(Modifier.padding(16.dp)){
                    Text("Q Memory",fontWeight=FontWeight.Bold,fontSize=17.sp)
                    Text("$memories conversation memories · $scans Vision scans",fontSize=11.sp,color=Muted,modifier=Modifier.padding(top=3.dp))
                    Row(Modifier.fillMaxWidth().padding(top=8.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                        TextButton({vm.scanSocialIq()}){Text("Refresh memory")}
                        TextButton({showVisionHistory=true}){Text("Vision history")}
                    }
                }
            }
        }

        val activePlans=vm.qCoordination.outbox.filter{it.status=="PENDING"||it.status=="RESPONDED"}.groupBy{it.request_key}.values.take(3)
        if(activePlans.isNotEmpty()){
            item{Text("Active Q-to-Q",fontSize=16.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(horizontal=20.dp,vertical=4.dp))}
            items(activePlans.toList()){group->
                val first=group.first()
                val names=group.mapNotNull{it.target?.display_name}.distinct().joinToString(", ")
                val responses=group.count{it.status=="RESPONDED"}
                Card(Modifier.fillMaxWidth().padding(horizontal=20.dp)){
                    Row(Modifier.fillMaxWidth().padding(14.dp),verticalAlignment=Alignment.CenterVertically){
                        Column(Modifier.weight(1f)){
                            Text(first.prompt,fontWeight=FontWeight.Bold,fontSize=12.sp,maxLines=2,overflow=TextOverflow.Ellipsis)
                            Text(if(names.isBlank())"$responses/${group.size} responses" else "$names · $responses/${group.size} responses",fontSize=10.sp,color=Muted,modifier=Modifier.padding(top=4.dp))
                        }
                        TextButton({vm.cancelQCoordination(first.request_key)}){Text("Cancel",fontSize=10.sp)}
                    }
                }
            }
        }

        val incoming=vm.qCoordination.inbox.filter{it.status=="PENDING"}.take(3)
        if(incoming.isNotEmpty()){
            item{Text("Waiting for you",fontSize=16.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(horizontal=20.dp,vertical=4.dp))}
            items(incoming,key={it.id}){request->
                Card(Modifier.fillMaxWidth().padding(horizontal=20.dp)){
                    Column(Modifier.padding(14.dp)){
                        Text(request.initiator?.display_name?:"LEMMIQ contact",fontWeight=FontWeight.Bold)
                        Text(request.prompt,fontSize=12.sp,modifier=Modifier.padding(top=4.dp))
                        val choices=if(request.options.isEmpty())listOf("Available","Not available") else request.options.take(2)
                        Row(Modifier.fillMaxWidth().padding(top=8.dp),horizontalArrangement=Arrangement.spacedBy(6.dp)){
                            choices.forEach{choice->
                                FilledTonalButton(onClick={vm.respondQCoordination(request.id,choice)},modifier=Modifier.weight(1f)){Text(choice,fontSize=10.sp,maxLines=1)}
                            }
                        }
                    }
                }
            }
        }

        vm.agentAnswer?.let{a->
            item{
                Card(Modifier.fillMaxWidth().padding(horizontal=20.dp),shape=RoundedCornerShape(20.dp),colors=CardDefaults.cardColors(containerColor=Soft)){
                    Column(Modifier.padding(16.dp)){
                        Text("Q",color=Purple,fontWeight=FontWeight.Black)
                        Text(a.answer,modifier=Modifier.padding(top=7.dp))
                        if(a.references.isNotEmpty()){
                            Text("Based on your LEMMIQ history",fontWeight=FontWeight.Bold,fontSize=10.sp,modifier=Modifier.padding(top=10.dp))
                            a.references.take(3).forEach{r->
                                Text("• ${r.contact}: ${r.text}",fontSize=10.sp,color=Muted,maxLines=2,overflow=TextOverflow.Ellipsis,modifier=Modifier.padding(top=3.dp))
                            }
                        }
                    }
                }
            }
        }
    }

    if(showCoord){
        AlertDialog(
            onDismissRequest={showCoord=false},
            title={Text("Q-to-Q coordination")},
            text={
                Column(verticalArrangement=Arrangement.spacedBy(8.dp)){
                    Text("Use Q-to-Q only for shared plans, availability or polls. Private Q memory is never shared.",fontSize=10.sp,color=Muted)
                    if(selectedCoordUsers.isNotEmpty()){
                        Text("${selectedCoordUsers.size} contact${if(selectedCoordUsers.size==1)"" else "s"} selected",fontSize=11.sp,fontWeight=FontWeight.Bold)
                        Column(Modifier.heightIn(max=120.dp).verticalScroll(rememberScrollState())){
                            selectedCoordUsers.values.forEach{u->
                                Row(Modifier.fillMaxWidth().padding(vertical=2.dp),verticalAlignment=Alignment.CenterVertically){
                                    Text("${u.display_name}  @${u.username}",fontSize=11.sp,modifier=Modifier.weight(1f))
                                    TextButton(onClick={selectedCoordUsers=selectedCoordUsers-u.id}){Text("Remove",fontSize=10.sp)}
                                }
                            }
                        }
                    }
                    OutlinedTextField(
                        value=coordSearch,
                        onValueChange={coordSearch=it;vm.search(it)},
                        label={Text("Search and add contacts")},
                        singleLine=true,modifier=Modifier.fillMaxWidth()
                    )
                    if(coordSearch.length>=2){
                        Column(Modifier.heightIn(max=150.dp).verticalScroll(rememberScrollState())){
                            vm.users.take(10).forEach{u->
                                val checked=u.id in selectedCoordUsers
                                Row(Modifier.fillMaxWidth().clickable{
                                    selectedCoordUsers=if(checked)selectedCoordUsers-u.id else selectedCoordUsers+(u.id to u)
                                    if(!checked){coordSearch="";vm.search("")}
                                }.padding(vertical=4.dp),verticalAlignment=Alignment.CenterVertically){
                                    Checkbox(checked=checked,onCheckedChange={isChecked->
                                        selectedCoordUsers=if(isChecked)selectedCoordUsers+(u.id to u) else selectedCoordUsers-u.id
                                        if(isChecked){coordSearch="";vm.search("")}
                                    })
                                    Text("${u.display_name}  @${u.username}",fontSize=11.sp)
                                }
                            }
                        }
                    }
                    OutlinedTextField(value=coordPrompt,onValueChange={coordPrompt=it},label={Text("What should Q coordinate?")},modifier=Modifier.fillMaxWidth(),minLines=2,maxLines=4)
                    OutlinedTextField(value=coordOptions,onValueChange={coordOptions=it},label={Text("Options / times — one per line")},modifier=Modifier.fillMaxWidth(),minLines=2,maxLines=4)
                }
            },
            confirmButton={
                Button(onClick={
                    vm.createQCoordination(selectedCoordUsers.keys.toList(),if(coordOptions.isBlank())"PLAN" else "AVAILABILITY",coordPrompt,coordOptions.lines().map{it.trim()}.filter{it.isNotBlank()})
                    showCoord=false;selectedCoordUsers=emptyMap();coordSearch="";coordOptions="";vm.search("")
                },enabled=selectedCoordUsers.isNotEmpty()&&coordPrompt.isNotBlank()){Text("Send to ${selectedCoordUsers.size}")}
            },
            dismissButton={TextButton({showCoord=false}){Text("Cancel")}}
        )
    }

    if(showVisionHistory){
        AlertDialog(
            onDismissRequest={showVisionHistory=false},
            title={Text("Q Vision memory")},
            text={
                Column{
                    Text("Saved scans can be reopened later without scanning the image again.",fontSize=10.sp,color=Muted)
                    if(vm.visionHistory.isEmpty())Text("No Vision scans yet.",modifier=Modifier.padding(top=14.dp))
                    else LazyColumn(Modifier.heightIn(max=420.dp).padding(top=8.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
                        items(vm.visionHistory,key={it.id}){v->
                            Card(Modifier.fillMaxWidth().clickable{vm.openVision(v);showVisionHistory=false}){
                                Column(Modifier.padding(11.dp)){
                                    Text("${when(v.category){"DOCUMENT"->"📄";"SCREENSHOT"->"🖥";"PRODUCT"->"🛍";"VEHICLE"->"🚗";"RECEIPT"->"🧾";else->"📷"}} ${v.title}",fontWeight=FontWeight.Bold,fontSize=12.sp)
                                    Text(v.summary,fontSize=10.sp,color=Muted,maxLines=2,overflow=TextOverflow.Ellipsis,modifier=Modifier.padding(top=3.dp))
                                }
                            }
                        }
                    }
                }
            },
            confirmButton={TextButton({showVisionHistory=false}){Text("Close")}}
        )
    }

}

@Composable
private fun V27VisionDialog(vm:LemmiqViewModel){
    val v=vm.activeVision?:return
    var followUp by remember(v.id){mutableStateOf("")}
    AlertDialog(
        onDismissRequest={vm.clearVision()},
        title={Text("📷 ${v.title}")},
        text={
            Column(Modifier.heightIn(max=500.dp).verticalScroll(rememberScrollState())){
                Text(v.category,color=Purple,fontSize=10.sp,fontWeight=FontWeight.Bold)
                Text(v.summary,modifier=Modifier.padding(top=8.dp))
                if(v.extracted_text.isNotBlank()){
                    Text("Extracted text",fontWeight=FontWeight.Bold,fontSize=12.sp,modifier=Modifier.padding(top=12.dp))
                    Text(v.extracted_text,fontSize=11.sp,color=Muted,modifier=Modifier.padding(top=4.dp))
                }
                if(v.history.size>2){
                    Text("Conversation",fontWeight=FontWeight.Bold,fontSize=12.sp,modifier=Modifier.padding(top=12.dp))
                    v.history.takeLast(6).forEach{h->
                        Text("${if(h.role=="q")"Q" else "You"}: ${h.text}",fontSize=10.sp,color=if(h.role=="q")Ink else Muted,modifier=Modifier.padding(top=4.dp))
                    }
                }
                OutlinedTextField(
                    value=followUp,onValueChange={followUp=it},
                    label={Text("Ask another question about this image")},
                    modifier=Modifier.fillMaxWidth().padding(top=12.dp),minLines=2,maxLines=4
                )
                Button(
                    onClick={vm.askVision(followUp);followUp=""},
                    enabled=followUp.isNotBlank()&&!vm.visionBusy,
                    modifier=Modifier.fillMaxWidth().padding(top=8.dp)
                ){Text(if(vm.visionBusy)"Analysing…" else "Ask Q Vision")}
            }
        },
        confirmButton={TextButton({vm.clearVision()}){Text("Done")}},
        dismissButton={TextButton({vm.deleteVision(v.id)}){Text("Delete")}}
    )
}

@Composable
private fun ChatSummaryDialog(s:ChatSummary,dismiss:()->Unit){
    AlertDialog(
        onDismissRequest=dismiss,
        title={Text("🧠 Chat Summary")},
        text={
            LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp)){
                item{Text(s.summary)}
                if(s.key_points.isNotEmpty()){
                    item{Text("Key points",fontWeight=FontWeight.Bold)}
                    items(s.key_points){x->Text("• $x",fontSize=12.sp,color=Muted)}
                }
                if(s.follow_ups.isNotEmpty()){
                    item{Text("Possible follow-ups",fontWeight=FontWeight.Bold)}
                    items(s.follow_ups){x->Text("• $x",fontSize=12.sp,color=Muted)}
                }
            }
        },
        confirmButton={TextButton(dismiss){Text("Close")}}
    )
}

@Composable
private fun Agents(){
    val a=listOf("❤️ Partner","💘 Dating","👯 Bestie","😂 Friend","🏠 Family","💼 Work","🤝 Customer","💰 Sales","🎓 Study","✨ Custom")
    Column{Header("Agents","Different intelligence for every conversation");LazyColumn(contentPadding=PaddingValues(20.dp)){items(a){x->Card(Modifier.fillMaxWidth().padding(bottom=8.dp)){Text(x,Modifier.padding(16.dp),fontWeight=FontWeight.Bold)}}}}
}
@Composable
private fun Profile(vm:LemmiqViewModel){
    val ctx=LocalContext.current
    val notificationPermission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted->
        if(granted)vm.registerPush()
    }
    var showMoments by remember{mutableStateOf(false)}
    if(showMoments){Column{TextButton({showMoments=false}){Text("‹ Back to Me")};Moments(vm)};return}
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())){
        Header("Me","@${vm.store.username.orEmpty()}")
        V24ProfilePhotoCard(vm)
        V24PrivacyCard(vm)
        Card(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=8.dp)){Column(Modifier.padding(18.dp)){Text(vm.store.displayName.orEmpty(),fontSize=20.sp,fontWeight=FontWeight.Bold);Text("@${vm.store.username.orEmpty()}",color=Muted)}}
        Row(Modifier.padding(horizontal=20.dp,vertical=8.dp),verticalAlignment=Alignment.CenterVertically){
            BrandMark(48.dp);Spacer(Modifier.width(10.dp));Text("LEMMIQ V${BuildConfig.VERSION_NAME}",fontWeight=FontWeight.Bold)
        }
        TextButton({showMoments=true},modifier=Modifier.padding(horizontal=20.dp)){Text("✨ Open 24-hour Moments")}
        Text("🧠 Q Memory: smart context + relevant conversation history",Modifier.padding(horizontal=20.dp,vertical=6.dp))
        Text("Q keeps about 100 recent messages ready, can retrieve up to ~200 when useful, and uses rolling summaries for older history.",
            Modifier.padding(horizontal=20.dp,vertical=4.dp),fontSize=10.sp,color=Muted)
        Text("🔒 Private beta: messenger and synced events are server-readable, not E2EE.",
            Modifier.padding(horizontal=20.dp,vertical=6.dp),fontSize=12.sp,color=Muted)
        Row(Modifier.padding(horizontal=20.dp,vertical=8.dp),verticalAlignment=Alignment.CenterVertically){
            val permissionOff=Build.VERSION.SDK_INT>=33 && ContextCompat.checkSelfPermission(ctx,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED
            Text(if(vm.pushRegistered&&!permissionOff)"●" else "○",color=if(vm.pushRegistered&&!permissionOff)Mint else Muted,fontSize=13.sp)
            Spacer(Modifier.width(6.dp))
            Column{
                Text(if(permissionOff)"Notifications disabled" else if(vm.pushRegistered)"Push notifications active" else vm.pushStatusText,fontSize=11.sp,fontWeight=FontWeight.Bold)
                if(permissionOff)Text("Enable notification permission in Android settings.",fontSize=9.sp,color=Muted)
                else Text("Registration and token refresh are automatic.",fontSize=9.sp,color=Muted)
            }
        }
        Text("LEMMIQ never reads its own notifications. Cross-app intelligence only processes permitted third-party apps.",
            fontSize=10.sp,color=Muted,modifier=Modifier.padding(horizontal=20.dp))
        Text("Server: ${vm.serverUrl}",Modifier.padding(horizontal=20.dp,vertical=6.dp),fontSize=11.sp,color=Muted)
        Button({vm.logout()},modifier=Modifier.padding(20.dp)){Text("Log out")}
    }
}
@Composable
private fun SimplePage(title:String,icon:String,sub:String){Column{Header(title);Empty(icon,title,sub)}}
@Composable
private fun Empty(icon:String,title:String,sub:String){
    Column(Modifier.fillMaxSize().padding(32.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.Center){
        Text(icon,fontSize=50.sp);Text(title,fontSize=20.sp,fontWeight=FontWeight.Bold);Text(sub,color=Muted,modifier=Modifier.padding(top=6.dp))
    }
}
private fun catEmoji(c:String)=when(c){"PARTNER"->"❤️";"DATING"->"💘";"BESTIE"->"👯";"FRIEND"->"😂";"FAMILY"->"🏠";"WORK"->"💼";"CUSTOMER"->"🤝";"SALES"->"💰";"STUDY"->"🎓";else->"✨"}
private fun pretty(s:String)=s.lowercase().replaceFirstChar{it.uppercase()}


@Composable
private fun BusinessScreen(vm:LemmiqViewModel){
    var enabled by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.enabled)}
    var name by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.business_name)}
    var type by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.business_type)}
    var description by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.description)}
    var website by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.website)}
    var phone by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.phone)}
    var email by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.email)}
    var hours by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.hours)}
    var area by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.service_area)}
    var tone by remember(vm.businessProfile){mutableStateOf(vm.businessProfile.tone)}
    var threshold by remember(vm.businessProfile){mutableIntStateOf(vm.businessProfile.auto_threshold)}
    var category by remember{mutableStateOf("FAQ")}
    var kbTitle by remember{mutableStateOf("")}
    var kbContent by remember{mutableStateOf("")}
    var showKnowledge by remember{mutableStateOf(true)}
    val docPicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->if(uri!=null)vm.uploadBusinessKnowledge(uri)}
    LaunchedEffect(Unit){vm.refreshBusiness()}
    LazyColumn(Modifier.fillMaxSize().background(Bg),contentPadding=PaddingValues(bottom=30.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{Header("LEMMIQ Business Beta","Teach Q your business, then use grounded customer replies")}
        item{GradientPanel("💼 Business Agent","Optional beta inside your personal LEMMIQ"){
            Text(if(enabled)"Business intelligence enabled" else "Business intelligence is off",color=Color.White,fontSize=20.sp,fontWeight=FontWeight.Black)
            Text("Approved knowledge + customer context + recent chat → grounded reply",color=Color.White.copy(alpha=.85f),fontSize=11.sp)
        }}
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(22.dp)){
                Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
                    Row(verticalAlignment=Alignment.CenterVertically){
                        Column(Modifier.weight(1f)){Text("Enable Business Beta",fontWeight=FontWeight.Bold);Text("You choose which customer chats use it.",fontSize=10.sp,color=Muted)}
                        Switch(enabled,{enabled=it})
                    }
                    OutlinedTextField(name,{name=it},Modifier.fillMaxWidth(),label={Text("Business name")},singleLine=true)
                    OutlinedTextField(type,{type=it},Modifier.fillMaxWidth(),label={Text("Business type")},singleLine=true)
                    OutlinedTextField(description,{description=it},Modifier.fillMaxWidth(),label={Text("What your business does")},minLines=2,maxLines=4)
                    OutlinedTextField(hours,{hours=it},Modifier.fillMaxWidth(),label={Text("Opening hours")},minLines=2,maxLines=4)
                    OutlinedTextField(area,{area=it},Modifier.fillMaxWidth(),label={Text("Service area")},minLines=1,maxLines=3)
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                        OutlinedTextField(phone,{phone=it},Modifier.weight(1f),label={Text("Phone")},singleLine=true)
                        OutlinedTextField(email,{email=it},Modifier.weight(1f),label={Text("Email")},singleLine=true)
                    }
                    OutlinedTextField(website,{website=it},Modifier.fillMaxWidth(),label={Text("Website")},singleLine=true)
                    Text("Reply tone",fontWeight=FontWeight.Bold,fontSize=12.sp)
                    LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){items(listOf("Professional","Friendly","Warm","Direct","Premium","Casual")){x->FilterChip(tone==x,{tone=x},{Text(x)})}}
                    Text("AUTO grounding threshold: $threshold%",fontWeight=FontWeight.Bold,fontSize=12.sp)
                    Slider(value=threshold.toFloat(),onValueChange={threshold=it.toInt()},valueRange=70f..100f,steps=5)
                    Text("AUTO only sends when the Business Agent returns a high-confidence reply that does not require review. Otherwise it waits for you.",fontSize=10.sp,color=Muted)
                    Button({vm.saveBusinessProfile(BusinessProfileDto(enabled,name,type,description,website,phone,email,hours,area,tone,"AUD",threshold))},
                        enabled=!vm.businessBusy && name.isNotBlank(),modifier=Modifier.fillMaxWidth()){Text(if(vm.businessBusy)"Saving…" else "Save Business Profile")}
                }
            }
        }
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(22.dp)){
                Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                    Text("Knowledge Base",fontSize=19.sp,fontWeight=FontWeight.Black)
                    Text("Only approved knowledge is used for customer answers. Uploading a document extracts text; the original file is not used as a public attachment.",fontSize=11.sp,color=Muted)
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                        OutlinedButton({docPicker.launch("*/*")},enabled=!vm.businessBusy){Text("📄 Upload PDF / DOCX / TXT")}
                        TextButton({showKnowledge=!showKnowledge}){Text(if(showKnowledge)"Hide knowledge" else "Show knowledge (${vm.businessKnowledge.size})")}
                    }
                    Text("Add knowledge manually",fontWeight=FontWeight.Bold,fontSize=13.sp)
                    LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){items(listOf("FAQ","SERVICE","PRICING","POLICY","HOURS","AREA","OTHER")){x->FilterChip(category==x,{category=x},{Text(x)})}}
                    OutlinedTextField(kbTitle,{kbTitle=it},Modifier.fillMaxWidth(),label={Text("Title")},singleLine=true)
                    OutlinedTextField(kbContent,{kbContent=it},Modifier.fillMaxWidth(),label={Text("Approved information")},minLines=3,maxLines=7)
                    Button({vm.addBusinessKnowledge(category,kbTitle,kbContent);kbTitle="";kbContent=""},enabled=kbTitle.isNotBlank()&&kbContent.isNotBlank()&&!vm.businessBusy){Text("Add approved knowledge")}
                }
            }
        }
        if(showKnowledge){
            if(vm.businessKnowledge.isEmpty())item{Text("No business knowledge yet.",Modifier.padding(horizontal=20.dp),color=Muted)}
            items(vm.businessKnowledge,key={it.id}){k->
                Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(18.dp)){
                    Column(Modifier.padding(14.dp)){
                        Row{Text(k.category,color=Purple,fontSize=10.sp,fontWeight=FontWeight.Black);Spacer(Modifier.weight(1f));Text(k.source,color=Muted,fontSize=9.sp)}
                        Text(k.title,fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=3.dp))
                        Text(k.content,maxLines=5,overflow=TextOverflow.Ellipsis,fontSize=12.sp,color=Muted,modifier=Modifier.padding(top=4.dp))
                        TextButton({vm.deleteBusinessKnowledge(k.id)},enabled=!vm.businessBusy){Text("Delete",color=MaterialTheme.colorScheme.error)}
                    }
                }
            }
        }
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),colors=CardDefaults.cardColors(containerColor=Soft),shape=RoundedCornerShape(20.dp)){
                Column(Modifier.padding(16.dp)){
                    Text("How to use it",fontWeight=FontWeight.Black,color=Purple)
                    Text("1. Add your business profile and approved knowledge.\n2. Open a customer chat.\n3. Tap 💼 and enable Business Agent for that chat.\n4. Use Business reply in ASSIST, or test guarded AUTO.\n5. Use Learn from chat to review reusable facts before saving them.",fontSize=12.sp,modifier=Modifier.padding(top=7.dp))
                }
            }
        }
        vm.error?.let{item{Text(it,color=MaterialTheme.colorScheme.error,fontSize=11.sp,modifier=Modifier.padding(horizontal=20.dp))}}
    }
}

@Composable
private fun BusinessChatDialog(c:ChatDto,vm:LemmiqViewModel,dismiss:()->Unit){
    var enabled by remember(vm.activeBusinessSetting){mutableStateOf(vm.activeBusinessSetting.enabled)}
    var mode by remember(vm.activeBusinessSetting){mutableStateOf(vm.activeBusinessSetting.mode)}
    var label by remember(vm.activeBusinessSetting){mutableStateOf(vm.activeBusinessSetting.customer_label)}
    var notes by remember(vm.activeBusinessMemory){mutableStateOf(vm.activeBusinessMemory.notes)}
    var tags by remember(vm.activeBusinessMemory){mutableStateOf(vm.activeBusinessMemory.tags)}
    AlertDialog(onDismissRequest=dismiss,title={Text("💼 Business Agent · ${c.other_user.display_name}")},text={
        LazyColumn(verticalArrangement=Arrangement.spacedBy(10.dp)){
            item{Row(verticalAlignment=Alignment.CenterVertically){Text("Use Business Agent",Modifier.weight(1f),fontWeight=FontWeight.Bold);Switch(enabled,{enabled=it})}}
            item{Text("Mode",fontWeight=FontWeight.Bold);LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){items(listOf("OFF","ASSIST","AUTO")){x->FilterChip(mode==x,{mode=x},{Text(x)})}}}
            item{OutlinedTextField(label,{label=it},Modifier.fillMaxWidth(),label={Text("Customer label (optional)")},singleLine=true)}
            item{OutlinedTextField(notes,{notes=it},Modifier.fillMaxWidth(),label={Text("Customer memory / confirmed notes")},minLines=3,maxLines=6)}
            item{OutlinedTextField(tags,{tags=it},Modifier.fillMaxWidth(),label={Text("Tags e.g. lead, ceramic coating")},singleLine=true)}
            item{Text("Memory is owner-controlled. Do not store passwords, OTPs, card numbers or unnecessary sensitive information.",fontSize=10.sp,color=Muted)}
            item{OutlinedButton({vm.learnBusinessFromActiveChat();dismiss()}){Text("🧠 Learn from chat (review first)")}}
            if(mode=="AUTO")item{Text("AUTO will only send when approved business knowledge strongly supports the reply and the confidence threshold is met.",fontSize=10.sp,color=Color(0xFF795A16))}
        }
    },confirmButton={Button({vm.saveBusinessChat(enabled,mode,label);vm.saveBusinessMemory(notes,tags);dismiss()}){Text("Save")}},dismissButton={TextButton(dismiss){Text("Cancel")}})
}

@Composable
private fun BusinessLearnDialog(vm:LemmiqViewModel){
    AlertDialog(onDismissRequest={vm.businessLearnCandidates=emptyList()},title={Text("Review business learning")},text={
        LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp)){
            item{Text("Nothing is learned automatically. Approve only reusable facts that are correct for future customers.",fontSize=11.sp,color=Muted)}
            items(vm.businessLearnCandidates){x->
                Card(colors=CardDefaults.cardColors(containerColor=Soft)){
                    Column(Modifier.padding(12.dp)){
                        Text(x.category,color=Purple,fontSize=10.sp,fontWeight=FontWeight.Black)
                        Text(x.title,fontWeight=FontWeight.Bold)
                        Text(x.content,fontSize=12.sp,modifier=Modifier.padding(top=4.dp))
                        Row{TextButton({vm.businessLearnCandidates=vm.businessLearnCandidates.filterNot{it==x}}){Text("Discard",color=Muted)};Spacer(Modifier.weight(1f));Button({vm.approveBusinessLearning(x)}){Text("Approve")}}
                    }
                }
            }
        }
    },confirmButton={TextButton({vm.businessLearnCandidates=emptyList()}){Text("Close")}})
}

@Composable private fun ActivityScreen(vm:LemmiqViewModel){
    val ctx=LocalContext.current
    var showSources by remember{mutableStateOf(false)}
    var appQuery by remember{mutableStateOf("")}
    var deleteConfirm by remember{mutableStateOf(false)}
    var editEvent by remember{mutableStateOf<PhoneEvent?>(null)}
    var confirmBulkSelection by remember{mutableStateOf(false)}
    val filteredApps=vm.appChoices.filter{
        it.name.contains(appQuery.trim(),ignoreCase=true) ||
            it.pkg.contains(appQuery.trim(),ignoreCase=true)
    }
    val matchingPackages=filteredApps.map{it.pkg}.toSet()
    val selectedMatches=matchingPackages.count{it in vm.permittedApps}
    LaunchedEffect(Unit){vm.reloadNotificationSettings();vm.refreshInsights();vm.loadInstalledApps();vm.reloadExternalSettings();vm.refreshExternal()}
    LazyColumn(Modifier.fillMaxSize().background(Bg),contentPadding=PaddingValues(bottom=28.dp),
        verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{Header("Q Activity","Selected phone notifications · locally processed")}
        item{GradientPanel("Notification Intelligence","Your activity, without banking connections"){
            Text("${vm.localEvents.size} structured alerts retained",color=Color.White,fontSize=25.sp,fontWeight=FontWeight.Black)
            Text("Nothing is captured until you grant Android access, choose apps and enable categories.",
               color=Color.White.copy(alpha=.9f),fontSize=12.sp)
        }}
        item{ExternalChatPanel(vm)}
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(22.dp)){
                Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                    Text("Privacy controls",fontSize=19.sp,fontWeight=FontWeight.Bold)
                    Text(if(vm.listenerGranted)"✓ Android notification access granted" else
                        "1. Grant notification access in Android Settings",fontSize=12.sp,color=Muted)
                    if(!vm.listenerGranted)Button(onClick={
                        ctx.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                    },modifier=Modifier.fillMaxWidth()){Text("Open notification access settings")}
                    Row(verticalAlignment=Alignment.CenterVertically){
                        Column(Modifier.weight(1f)){
                            Text("Capture permitted alerts",fontWeight=FontWeight.Bold)
                            Text("Off by default; future notifications only",fontSize=11.sp,color=Muted)
                        }
                        Switch(checked=vm.notificationCapture,onCheckedChange={vm.setCapture(it)})
                    }
                    Row(verticalAlignment=Alignment.CenterVertically){
                        Column(Modifier.weight(1f)){
                            Text("Include structured events in Q",fontWeight=FontWeight.Bold)
                            Text("Optional sync to your desktop server",fontSize=11.sp,color=Muted)
                        }
                        Switch(checked=vm.insightSync,onCheckedChange={vm.setSync(it)})
                    }
                    Text("Retention",fontWeight=FontWeight.Bold)
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                        listOf(1,7,30).forEach{days->FilterChip(vm.retentionDays==days,{vm.setRetention(days)},
                            {Text(if(days==1)"24h" else "$days days")})}
                    }
                    Text("Codes, password and authentication notifications are excluded. Only selected structured content may sync; this is not E2EE.",fontSize=11.sp,color=Muted)
                }
            }
        }
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(22.dp)){
                Column(Modifier.padding(16.dp)){
                    Text("2. Choose categories",fontSize=18.sp,fontWeight=FontWeight.Bold)
                    Text("Only recognised events in enabled categories are saved.",fontSize=11.sp,color=Muted)
                    NotificationControl.categories.forEach{cat->
                        val label=when(cat){"MONEY"->"💳 Payments";"BILL"->"📅 Bills & renewals";
                            "DELIVERY"->"📦 Deliveries";"WORK"->"💼 Schedules";
                            "TRAVEL"->"✈️ Travel";else->"🛡️ Scam signals"}
                        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                            Text(label,Modifier.weight(1f),fontSize=13.sp)
                            Checkbox(checked=cat in vm.permittedCategories,onCheckedChange={vm.setCategory(cat,it)})
                        }
                    }
                }
            }
        }
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(22.dp)){
                Column(Modifier.padding(16.dp)){
                    Text("3. Select allowed apps",fontSize=18.sp,fontWeight=FontWeight.Bold)
                    Text("${vm.permittedApps.size} apps selected. Only their new alerts are considered.",color=Muted,fontSize=12.sp)
                    OutlinedButton({showSources=!showSources;vm.loadInstalledApps()},modifier=Modifier.fillMaxWidth()){
                        Text(if(showSources)"Hide apps" else "Choose apps")
                    }
                    if(showSources){
                        OutlinedTextField(appQuery,{appQuery=it},label={Text("Find installed app")},
                            modifier=Modifier.fillMaxWidth(),singleLine=true)
                        Text("$selectedMatches of ${filteredApps.size} matching apps selected",color=Muted,fontSize=11.sp)
                        Row(horizontalArrangement=Arrangement.spacedBy(8.dp),verticalAlignment=Alignment.CenterVertically){
                            Button(onClick={confirmBulkSelection=true},
                                modifier=Modifier.weight(1f), enabled=filteredApps.isNotEmpty() && selectedMatches<filteredApps.size){
                                Text(if(appQuery.isBlank())"Select all" else "Select matches",fontSize=12.sp)
                            }
                            OutlinedButton(onClick={vm.setApps(matchingPackages,false)},
                                modifier=Modifier.weight(1f), enabled=selectedMatches>0){
                                Text(if(appQuery.isBlank())"Clear all" else "Clear matches",fontSize=12.sp)
                            }
                        }
                        Text("Scroll down to see the complete app list. Search to narrow the selection.",
                            fontSize=11.sp,color=Muted)
                    }
                }
            }
        }
        // Render each app in the parent LazyColumn: avoids nested-scroll trapping and removes the old 80-app limit.
        if(showSources){
            items(filteredApps,key={"allowed-app-${it.pkg}"}){choice->
                Row(Modifier.fillMaxWidth().padding(horizontal=18.dp,vertical=2.dp)
                    .clip(RoundedCornerShape(14.dp)).background(Color.White)
                    .padding(horizontal=14.dp,vertical=6.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text(choice.name,fontSize=13.sp,fontWeight=FontWeight.SemiBold)
                        Text(choice.pkg,fontSize=10.sp,color=Muted)
                    }
                    Checkbox(checked=choice.pkg in vm.permittedApps,
                        onCheckedChange={vm.setApp(choice.pkg,it)})
                }
            }
            if(filteredApps.isEmpty())item{
                Text("No installed apps match your search.",Modifier.padding(horizontal=24.dp),color=Muted)
            }
        }
        item{
            Row(Modifier.fillMaxWidth().padding(horizontal=18.dp),verticalAlignment=Alignment.CenterVertically){
                Text("Detected events",Modifier.weight(1f),fontSize=19.sp,fontWeight=FontWeight.Bold)
                TextButton({vm.refreshInsights()}){Text("Refresh")}
            }
        }
        if(vm.localEvents.isEmpty())item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp)){
                Text("No detected alerts yet. Enable access, choose a source app and wait for a new notification.",
                    Modifier.padding(18.dp),color=Muted,fontSize=12.sp)
            }
        }
        items(vm.localEvents.take(25)){e->EventCard(e){editEvent=it}}
        item{
            OutlinedButton(onClick={deleteConfirm=true},modifier=Modifier.fillMaxWidth().padding(horizontal=18.dp)){
                Text("Manage / reset detected data")
            }
        }
    }
    if(confirmBulkSelection)AlertDialog(
        onDismissRequest={confirmBulkSelection=false},
        title={Text(if(appQuery.isBlank())"Allow all installed apps?" else "Allow all matching apps?")},
        text={Text("This will allow ${matchingPackages.size} app(s) as notification sources. " +
            "Only new notifications in categories you enable can be processed. " +
            "You can deselect apps anytime.")},
        confirmButton={Button(onClick={vm.setApps(matchingPackages,true);confirmBulkSelection=false}){
            Text("Allow ${matchingPackages.size} apps")
        }},
        dismissButton={TextButton(onClick={confirmBulkSelection=false}){Text("Cancel")}}
    )
    if(deleteConfirm)AlertDialog(onDismissRequest={deleteConfirm=false},
      title={Text("Reset detected data")},
      text={
          Column(verticalArrangement=Arrangement.spacedBy(8.dp)){
              Text("Choose what to clear. Totals recalculate immediately.")
              OutlinedButton({vm.resetInsightData("ACTIVITY");deleteConfirm=false},Modifier.fillMaxWidth()){Text("Reset Activity only")}
              OutlinedButton({vm.resetInsightData("MONEY");deleteConfirm=false},Modifier.fillMaxWidth()){Text("Reset Money only")}
              Button({vm.resetInsightData("ALL");deleteConfirm=false},Modifier.fillMaxWidth()){Text("Reset everything")}
          }
      },
      confirmButton={},
      dismissButton={TextButton({deleteConfirm=false}){Text("Cancel")}})
    editEvent?.let{e->EventEditDialog(vm,e){editEvent=null}}
}

@Composable private fun ExternalChatPanel(vm:LemmiqViewModel){
    val ctx=LocalContext.current
    val clipboard=androidx.compose.ui.platform.LocalClipboardManager.current
    var expanded by remember{mutableStateOf(false)}
    var confirmDelete by remember{mutableStateOf(false)}
    Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(22.dp),
        colors=CardDefaults.cardColors(containerColor=Color.White)){
        Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text("💬 Universal Chat Intelligence",fontSize=18.sp,fontWeight=FontWeight.Bold)
            Text("Optional WhatsApp / SMS incoming notification previews. Not complete conversations; no automatic sending.",fontSize=11.sp,color=Muted)
            Row(verticalAlignment=Alignment.CenterVertically){
                Text("Capture new external previews",Modifier.weight(1f),fontWeight=FontWeight.Bold,fontSize=12.sp)
                Switch(checked=vm.externalEnabled,onCheckedChange={vm.updateExternalEnabled(it)})
            }
            if(vm.externalEnabled){
                Row(verticalAlignment=Alignment.CenterVertically){
                    Text("WhatsApp",Modifier.weight(1f));Checkbox(vm.externalWhatsApp,{vm.setExternalSource("WhatsApp",it)})
                }
                Row(verticalAlignment=Alignment.CenterVertically){
                    Text("SMS / Google Messages",Modifier.weight(1f));Checkbox(vm.externalSms,{vm.setExternalSource("SMS",it)})
                }
                Text("Keep encrypted local context for",fontSize=11.sp,color=Muted)
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    listOf(1,7,30).forEach{n->FilterChip(vm.externalDays==n,{vm.updateExternalDays(n)},
                        {Text(if(n==1)"24h" else "$n days")})}
                }
                Row(verticalAlignment=Alignment.CenterVertically){
                    Text("Allow Q to use selected snippets",Modifier.weight(1f),fontSize=12.sp)
                    Switch(vm.externalQ,{vm.updateExternalQ(it)})
                }
                Text("Q sharing is on demand, when you explicitly ask Q or request a draft. Nothing is automatically sent to contacts.",fontSize=10.sp,color=Muted)
            }
            Row(verticalAlignment=Alignment.CenterVertically){
                OutlinedButton({vm.refreshExternal();expanded=!expanded}){
                    Text(if(expanded)"Hide recent previews" else "View recent previews (${vm.externalMessages.size})")
                }
                TextButton({confirmDelete=true}){Text("Delete",color=Muted)}
            }
            if(expanded){
                if(vm.externalMessages.isEmpty())Text("No permitted new WhatsApp/SMS notifications yet.",fontSize=11.sp,color=Muted)
                vm.externalMessages.take(20).forEach{entry->
                    HorizontalDivider()
                    Text("${entry.source} · ${entry.contact}",fontWeight=FontWeight.SemiBold,fontSize=12.sp)
                    Text(entry.text,maxLines=3,overflow=TextOverflow.Ellipsis,fontSize=12.sp)
                    TextButton({vm.suggestExternal(entry)},enabled=!vm.agentBusy){Text("✨ Suggest reply")}
                }
                vm.externalDraft?.let{draft->
                    Surface(color=Soft,shape=RoundedCornerShape(12.dp)){
                        Column(Modifier.padding(12.dp)){
                            Text("Q draft — review before use",fontWeight=FontWeight.Bold,color=Purple)
                            Text(draft)
                            Row{
                                TextButton({vm.discardExternalDraft()}){Text("Discard")}
                                TextButton({clipboard.setText(androidx.compose.ui.text.AnnotatedString(draft))}){Text("Copy reply")}
                            }
                        }
                    }
                }
                vm.error?.let{Text(it,color=MaterialTheme.colorScheme.error,fontSize=11.sp)}
            }
        }
    }
    if(confirmDelete)AlertDialog(onDismissRequest={confirmDelete=false},title={Text("Delete external chat context?")},
        text={Text("This deletes all locally saved WhatsApp/SMS previews for this LEMMIQ account. It does not delete messages in those apps.")},
        confirmButton={Button({vm.clearExternal();confirmDelete=false}){Text("Delete")}},
        dismissButton={TextButton({confirmDelete=false}){Text("Cancel")}})
}

@Composable private fun EventCard(e:PhoneEvent,onManage:(PhoneEvent)->Unit={}){
    val mark=when(e.category){"MONEY"->"💳";"BILL"->"📅";"DELIVERY"->"📦";
       "TRAVEL"->"✈️";"WORK"->"💼";"TRUST"->"🛡️";else->"🔔"}
    Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(19.dp),
      colors=CardDefaults.cardColors(containerColor=Color.White)){
        Row(Modifier.padding(13.dp),verticalAlignment=Alignment.CenterVertically){
            Surface(color=Soft,shape=RoundedCornerShape(12.dp)){
                Text(mark,Modifier.padding(10.dp),fontSize=22.sp)
            }
            Spacer(Modifier.width(11.dp))
            Column(Modifier.weight(1f)){
                Text(e.title,fontWeight=FontWeight.Bold,fontSize=13.sp)
                Text("${e.source} · ${e.occurred_at.take(16).replace("T"," ")}",fontSize=10.sp,color=Muted)
                if(e.detail.isNotBlank())Text(e.detail,maxLines=2,overflow=TextOverflow.Ellipsis,fontSize=11.sp,color=Muted)
            }
            Column(horizontalAlignment=Alignment.End){
                if(e.amount_cents!=null)Text("${if(e.direction=="IN")"+" else if(e.direction=="OUT")"−" else ""}${moneyString(e.amount_cents)}",
                    fontWeight=FontWeight.Black,fontSize=12.sp,color=if(e.direction=="IN")Mint else Ink)
                TextButton({onManage(e)},contentPadding=PaddingValues(horizontal=4.dp,vertical=2.dp)){Text("Manage",fontSize=10.sp)}
            }
        }
    }
}

@Composable private fun EventEditDialog(vm:LemmiqViewModel,e:PhoneEvent,dismiss:()->Unit){
    var category by remember(e.client_event_id){mutableStateOf(e.category)}
    var source by remember(e.client_event_id){mutableStateOf(e.source)}
    var title by remember(e.client_event_id){mutableStateOf(e.title)}
    var detail by remember(e.client_event_id){mutableStateOf(e.detail)}
    var amount by remember(e.client_event_id){mutableStateOf(e.amount_cents?.let{String.format(java.util.Locale.US,"%.2f",it/100.0)}?:"")}
    var direction by remember(e.client_event_id){mutableStateOf(e.direction)}
    var occurred by remember(e.client_event_id){mutableStateOf(e.occurred_at)}
    var confirmDelete by remember{mutableStateOf(false)}
    AlertDialog(
        onDismissRequest=dismiss,
        title={Text("Manage detected event")},
        text={
            LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp)){
                item{Text("You are the final authority. Correct or remove notification-derived data before using Money totals.",fontSize=11.sp,color=Muted)}
                item{
                    Text("Category",fontWeight=FontWeight.Bold,fontSize=12.sp)
                    Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){
                        listOf("MONEY","BILL","DELIVERY","WORK","TRAVEL","TRUST","GENERAL").take(4).forEach{x->
                            FilterChip(category==x,{category=x},{Text(x,fontSize=9.sp)})
                        }
                    }
                    Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){
                        listOf("TRAVEL","TRUST","GENERAL").forEach{x->FilterChip(category==x,{category=x},{Text(x,fontSize=9.sp)})}
                    }
                }
                item{OutlinedTextField(title,{title=it},Modifier.fillMaxWidth(),label={Text("Title")})}
                item{OutlinedTextField(source,{source=it},Modifier.fillMaxWidth(),label={Text("Source")})}
                item{OutlinedTextField(detail,{detail=it},Modifier.fillMaxWidth(),label={Text("Description")})}
                item{OutlinedTextField(amount,{amount=it.filter{c->c.isDigit()||c=='.'||c==','}},Modifier.fillMaxWidth(),label={Text("Amount in AUD · blank if none")})}
                item{
                    Text("Direction",fontWeight=FontWeight.Bold,fontSize=12.sp)
                    Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                        listOf("OUT","IN","UNKNOWN").forEach{x->FilterChip(direction==x,{direction=x},{Text(x)})}
                    }
                }
                item{OutlinedTextField(occurred,{occurred=it},Modifier.fillMaxWidth(),label={Text("Date/time (ISO)")})}
                item{
                    OutlinedButton({confirmDelete=true},Modifier.fillMaxWidth()){Text("Delete / mark incorrect / duplicate")}
                }
            }
        },
        confirmButton={Button({
            vm.editInsightEvent(e,category,source,title,detail,amount,direction,occurred);dismiss()
        }){Text("Save changes")}},
        dismissButton={TextButton(dismiss){Text("Cancel")}}
    )
    if(confirmDelete)AlertDialog(
        onDismissRequest={confirmDelete=false},
        title={Text("Remove this detected event?")},
        text={Text("Use this for incorrect or duplicate detections. It will be removed from totals and, when synced, from your cloud copy.")},
        confirmButton={Button({vm.deleteInsightEvent(e);confirmDelete=false;dismiss()}){Text("Remove")}},
        dismissButton={TextButton({confirmDelete=false}){Text("Keep")}}
    )
}

private fun moneyString(cents:Long):String = String.format(java.util.Locale.US,"$%,.2f",cents/100.0)

@Composable private fun MoneyScreen(vm:LemmiqViewModel){
    var amount by remember{mutableStateOf("")}
    var description by remember{mutableStateOf("")}
    var incoming by remember{mutableStateOf(false)}
    var editEvent by remember{mutableStateOf<PhoneEvent?>(null)}
    var resetMoney by remember{mutableStateOf(false)}
    LaunchedEffect(Unit){vm.refreshInsights()}
    val transactions=vm.localEvents.filter{it.category=="MONEY"}
    val outgoing=vm.detectedSpendingCents
    val incomingTotal=vm.detectedIncomingCents
    LazyColumn(Modifier.fillMaxSize().background(Bg),contentPadding=PaddingValues(bottom=28.dp),
       verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{Header("LEMMIQ Money","Spending awareness from selected alerts")}
        item{GradientPanel("Money Agent","Your opt-in transaction insights"){
            Text(moneyString(outgoing),color=Color.White,fontSize=32.sp,fontWeight=FontWeight.Black)
            Text("Detected outgoing payments · ${vm.retentionDays}-day retained window",
                color=Color.White.copy(alpha=.86f),fontSize=12.sp)
        }}
        item{
            Row(Modifier.fillMaxWidth().padding(horizontal=18.dp),horizontalArrangement=Arrangement.spacedBy(10.dp)){
                DashboardMetric("Detected income",moneyString(incomingTotal),Modifier.weight(1f))
                DashboardMetric("Payment alerts","${transactions.size}",Modifier.weight(1f))
            }
        }
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(22.dp)){
                Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(6.dp)){
                    Text("Q · Spending insight",fontWeight=FontWeight.Black,color=Purple,fontSize=17.sp)
                    Text(when{
                        transactions.isEmpty()->"Enable banking-app alerts in Activity, or add a manual expense below."
                        outgoing>0->"Detected ${transactions.count{it.direction=="OUT"}} outgoing payment alert(s). Review the amounts and categorisation before using them for budgeting."
                        else->"Incoming alerts detected. This is not a verified balance or complete income statement."
                    },fontSize=13.sp)
                    Text("Notifications may be missing, duplicate, pending or incomplete. No bank account is connected.",
                        color=Muted,fontSize=11.sp)
                }
            }
        }
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=18.dp),shape=RoundedCornerShape(22.dp)){
                Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                    Text("Add a manual transaction",fontWeight=FontWeight.Bold,fontSize=17.sp)
                    OutlinedTextField(description,{description=it},modifier=Modifier.fillMaxWidth(),
                        label={Text("Description")},singleLine=true)
                    OutlinedTextField(amount,{amount=it.filter{c->c.isDigit()||c=='.'||c==','}},
                        modifier=Modifier.fillMaxWidth(),label={Text("Amount in AUD")},singleLine=true)
                    Row(verticalAlignment=Alignment.CenterVertically){
                        Text("Incoming payment",Modifier.weight(1f));Switch(incoming,{incoming=it})
                    }
                    Button(onClick={
                        vm.addManualExpense(amount,description,incoming);amount="";description=""
                    },enabled=description.isNotBlank()&&amount.isNotBlank(),modifier=Modifier.fillMaxWidth()){
                        Text("Save transaction")
                    }
                }
            }
        }
        item{
            Row(Modifier.fillMaxWidth().padding(horizontal=20.dp),verticalAlignment=Alignment.CenterVertically){
                Text("Recent detected payments",Modifier.weight(1f),fontSize=19.sp,fontWeight=FontWeight.Bold)
                TextButton({resetMoney=true}){Text("Reset Money")}
            }
        }
        if(transactions.isEmpty())item{
            Text("No transactions detected yet.",Modifier.padding(horizontal=20.dp),color=Muted)
        }
        items(transactions.take(35)){e->EventCard(e){editEvent=it}}
    }
    editEvent?.let{e->EventEditDialog(vm,e){editEvent=null}}
    if(resetMoney)AlertDialog(
        onDismissRequest={resetMoney=false},
        title={Text("Reset LEMMIQ Money?")},
        text={Text("This removes detected/manual Money events from this account and recalculates totals. Other Activity categories stay intact.")},
        confirmButton={Button({vm.resetInsightData("MONEY");resetMoney=false}){Text("Reset Money")}},
        dismissButton={TextButton({resetMoney=false}){Text("Cancel")}}
    )
}
