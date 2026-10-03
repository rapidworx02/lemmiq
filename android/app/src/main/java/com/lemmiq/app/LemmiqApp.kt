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
    when{
        !vm.authenticated->Auth(vm)
        vm.active!=null->Chat(vm)
        else->Home(vm)
    }
}

@Composable
private fun Auth(vm:LemmiqViewModel){
    var signup by remember{mutableStateOf(false)}
    var user by remember{mutableStateOf("")}
    var name by remember{mutableStateOf("")}
    var pass by remember{mutableStateOf("")}
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
                }
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(pass,{pass=it},Modifier.fillMaxWidth(),label={Text("Password")},singleLine=true,visualTransformation=PasswordVisualTransformation())
                vm.error?.let{Text(it,color=MaterialTheme.colorScheme.error,fontSize=12.sp,modifier=Modifier.padding(top=8.dp))}
                Spacer(Modifier.height(14.dp))
                Button(
                    onClick={if(signup)vm.register(user,name.ifBlank{user},pass) else vm.login(user,pass)},
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

@Composable
private fun Home(vm:LemmiqViewModel){
    var tab by remember{mutableIntStateOf(0)}
    var newChat by remember{mutableStateOf(false)}
    LaunchedEffect(Unit){vm.refreshChats();vm.refreshMoments()}
    Scaffold(
        containerColor=Bg,
        bottomBar={
            NavigationBar{
                listOf("💬" to "Chats","🔔" to "Activity","Q" to "Agent","💳" to "Money","💼" to "Biz","🙂" to "Me").forEachIndexed{i,x->
                    NavigationBarItem(tab==i,{tab=i},{Text(x.first,fontWeight=FontWeight.Bold)},{Text(x.second)})
                }
            }
        },
        floatingActionButton={
            if(tab==0)FloatingActionButton({newChat=true},containerColor=Purple,contentColor=Color.White){Text("+",fontSize=28.sp)}
        }
    ){p->
        Box(Modifier.padding(p)){
            when(tab){
                0->Inbox(vm)
                1->ActivityScreen(vm)
                2->ChatAgent(vm)
                3->MoneyScreen(vm)
                4->BusinessScreen(vm)
                else->Profile(vm)
            }
        }
    }
    if(newChat)NewChat(vm){newChat=false}
}

@Composable
private fun Header(title:String,sub:String?=null){
    Column(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=16.dp)){
        Text(title,fontSize=29.sp,fontWeight=FontWeight.Black,color=Ink)
        if(sub!=null)Text(sub,color=Muted,fontSize=12.sp)
    }
}

@Composable
private fun Inbox(vm:LemmiqViewModel){
    LaunchedEffect(Unit){vm.refreshAgent()}
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
private fun Avatar(u:UserDto){
    Box(Modifier.size(50.dp).clip(CircleShape).background(Soft),contentAlignment=Alignment.Center){
        Text(u.display_name.firstOrNull()?.uppercase()?:"?",color=Purple,fontWeight=FontWeight.Bold,fontSize=18.sp)
    }
}
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
    var draft by remember{mutableStateOf("")}
    var settings by remember{mutableStateOf(false)}
    var businessSettings by remember{mutableStateOf(false)}
    var showAttach by remember{mutableStateOf(false)}
    val ctx=LocalContext.current
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
    // Reverse layout pins the latest message to the composer. Typing never changes scroll state.
    val messageListState=rememberLazyListState()
    LaunchedEffect(c.id,vm.messages.lastOrNull()?.id){
        if(vm.messages.isNotEmpty() && messageListState.firstVisibleItemIndex<=1){
            messageListState.scrollToItem(0)
        }
    }
    Scaffold(
        containerColor=Bg,
        topBar={
            Surface(shadowElevation=1.dp){
                Row(Modifier.fillMaxWidth().padding(8.dp),verticalAlignment=Alignment.CenterVertically){
                    Text("‹",fontSize=36.sp,modifier=Modifier.clickable{vm.close()}.padding(8.dp))
                    Avatar(c.other_user);Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)){
                        Text(c.other_user.display_name,fontWeight=FontWeight.Bold)
                        Text("@${c.other_user.username} · ${catEmoji(c.category)} ${pretty(c.category)} · ${pretty(c.ai_mode)}",color=Muted,fontSize=10.sp)
                    }
                    if(c.ai_mode!="OFF")Text("Q",color=Purple,fontWeight=FontWeight.Black,fontSize=22.sp,modifier=Modifier.clickable{vm.suggest()}.padding(10.dp))
                    if(vm.businessProfile.enabled)Text("💼",fontSize=18.sp,modifier=Modifier.clickable{businessSettings=true}.padding(8.dp))
                    Text("⚙",fontSize=19.sp,modifier=Modifier.clickable{settings=true}.padding(10.dp))
                }
            }
        },
        bottomBar={
            // Keep composer above the keyboard without re-scrolling on every character.
            Column(Modifier.background(Color.White).imePadding()){
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
                    Spacer(Modifier.width(8.dp))
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
            if(vm.messages.isEmpty())Empty("👋","Start the conversation","Messages appear here in real time.")
            else LazyColumn(
                modifier=Modifier.fillMaxSize(),
                state=messageListState,
                reverseLayout=true,
                contentPadding=PaddingValues(14.dp),
                verticalArrangement=Arrangement.spacedBy(7.dp)
            ){
                // Messages are stored oldest-first; reverse items to show newest at the bottom.
                // The message list does not depend on the draft field, preventing typing-induced jumps.
                items(vm.messages.asReversed(),key={it.id}){m->
                    Bubble(m,vm.store.userId,vm){vm.trustCheck(m.text)}
                }
            }
        }
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
            onDismissRequest={},
            title={Text("🛡 LEMMIQ Trust")},
            text={Column(verticalArrangement=Arrangement.spacedBy(12.dp)){
                LinearProgressIndicator(Modifier.fillMaxWidth(),color=Purple)
                Text("Checking this message. Searching for evidence may take a little while.")
            }},
            confirmButton={}
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
    vm.chatSummary?.let{s->ChatSummaryDialog(s){vm.clearChatSummary()}}
}

@Composable
private fun Bubble(m:MessageDto,me:Int,vm:LemmiqViewModel,onTrust:()->Unit){
    val mine=m.sender_id==me
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var mediaError by remember(m.id){mutableStateOf<String?>(null)}
    val mediaId=m.attachment?.media_id
    var bitmap by remember(mediaId){mutableStateOf<android.graphics.Bitmap?>(null)}
    // Only photo content is fetched for inline display; videos/docs download on tap.
    LaunchedEffect(mediaId,m.attachment?.kind){
        if(mediaId!=null && m.attachment?.kind=="PHOTO") {
            try{
                val bytes=withContext(Dispatchers.IO){vm.mediaBytes(mediaId)}
                val bounds=BitmapFactory.Options().apply{inJustDecodeBounds=true}
                BitmapFactory.decodeByteArray(bytes,0,bytes.size,bounds)
                var sample=1
                while(bounds.outWidth/sample>1400 || bounds.outHeight/sample>1400)sample*=2
                val options=BitmapFactory.Options().apply{inSampleSize=sample}
                bitmap=BitmapFactory.decodeByteArray(bytes,0,bytes.size,options)
            }catch(e:Exception){mediaError=e.message}
        }
    }
    Column(Modifier.fillMaxWidth(),horizontalAlignment=if(mine)Alignment.End else Alignment.Start){
        Surface(color=if(mine)Purple else Color.White,shape=RoundedCornerShape(18.dp),shadowElevation=if(mine)0.dp else 1.dp){
            Column(Modifier.widthIn(max=300.dp).padding(12.dp)){
                if(m.ai_generated)Text("✨ AI AUTO",color=if(mine)Color(0xFFE0D9FF) else Purple,fontSize=9.sp,fontWeight=FontWeight.Bold)
                val a=m.attachment
                if(a!=null){
                    if(a.kind=="PHOTO"){
                        bitmap?.let{bmp->
                            Image(bmp.asImageBitmap(),contentDescription="Shared photo",
                                modifier=Modifier.fillMaxWidth().heightIn(max=260.dp).clip(RoundedCornerShape(12.dp)),
                                contentScale=ContentScale.Fit)
                        }?:Text(if(mediaError==null)"🖼 Loading photo…" else "🖼 Photo unavailable",color=if(mine)Color.White else Ink)
                    }
                    if(a.kind=="CONTACT"){
                        Text("👤 ${a.contact_name.orEmpty()}",fontWeight=FontWeight.Bold,color=if(mine)Color.White else Ink)
                        Text(a.contact_phone.orEmpty(),color=if(mine)Color.White else Ink)
                    }else if(a.media_id!=null){
                        Text("${if(a.kind=="VIDEO")"🎬" else if(a.kind=="PHOTO")"🖼" else "📄"} ${a.name.orEmpty()}",
                            color=if(mine)Color.White else Ink,fontSize=12.sp)
                        TextButton(onClick={
                            scope.launch {
                                mediaError=null
                                try{
                                    val bytes=vm.mediaBytes(a.media_id)
                                    val safeName=(a.name?:"attachment").replace(Regex("[^A-Za-z0-9._-]"),"_")
                                    val dir=File(ctx.cacheDir,"share").apply{mkdirs()}
                                    val file=File(dir,"${m.id}_$safeName")
                                    withContext(Dispatchers.IO){file.writeBytes(bytes)}
                                    val uri=FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",file)
                                    val intent=Intent(Intent.ACTION_VIEW).apply{
                                        setDataAndType(uri,a.mime_type?:"application/octet-stream")
                                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                    }
                                    ctx.startActivity(Intent.createChooser(intent,"Open attachment"))
                                }catch(e:Exception){mediaError=e.message?:"Cannot open media"}
                            }
                        }){Text("Open / share",color=if(mine)Color.White else Purple)}
                    }
                }else Text(m.text,color=if(mine)Color.White else Ink)
                if(mediaError!=null)Text(mediaError.orEmpty(),fontSize=10.sp,color=if(mine)Color.White else Color.Red)
                if(mine)Text(if(m.read_at!=null)"✓✓" else "✓",color=Color(0xFFDCD6FF),fontSize=10.sp,modifier=Modifier.align(Alignment.End))
                else if(a==null) TextButton(onClick=onTrust,modifier=Modifier.align(Alignment.Start).heightIn(min=44.dp),
                    contentPadding=PaddingValues(horizontal=0.dp,vertical=2.dp)){
                    Text("🛡 Fact / Scam Check",color=Purple,fontSize=12.sp,fontWeight=FontWeight.Bold)
                }
            }
        }
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
    var search by remember{mutableStateOf("")}
    LaunchedEffect(Unit){vm.refreshAgent()}
    LazyColumn(
        Modifier.fillMaxSize().background(Bg),
        contentPadding=PaddingValues(bottom=24.dp)
    ){
        item{Header("Ask Q","Messages + your opt-in phone insights")}
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=6.dp)){
                Row(Modifier.padding(12.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text("Include WhatsApp/SMS previews in Q",fontWeight=FontWeight.Bold,fontSize=13.sp)
                        Text("Off by default. Up to 30 selected recent snippets are sent only when you press Ask Q.",
                            color=Muted,fontSize=10.sp)
                    }
                    Switch(checked=vm.externalQ && vm.externalEnabled,
                        onCheckedChange={vm.setExternalQ(it)},enabled=vm.externalEnabled)
                }
            }
        }
        item{
            Card(
                Modifier.fillMaxWidth().padding(horizontal=20.dp),
                colors=CardDefaults.cardColors(containerColor=Ink),
                shape=RoundedCornerShape(22.dp)
            ){
                Column(Modifier.padding(18.dp)){
                    Text("Q  Your Chat Brief",color=Color.White,fontWeight=FontWeight.Black,fontSize=18.sp)
                    Text(vm.agentBrief?.summary ?: "Analysing your recent conversations…",color=Color(0xFFDDDBE8),modifier=Modifier.padding(top=8.dp))
                    if(vm.agentBusy)LinearProgressIndicator(Modifier.fillMaxWidth().padding(top=12.dp))
                }
            }
        }

        vm.agentBrief?.needs_reply?.take(5)?.let{itemsToReply->
            if(itemsToReply.isNotEmpty()){
                item{Text("Needs reply",fontSize=18.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(20.dp,20.dp,20.dp,8.dp))}
                items(itemsToReply){x->
                    Card(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=4.dp)){
                        Column(Modifier.padding(14.dp)){
                            Text("${catEmoji(x.category)} ${x.contact.display_name}",fontWeight=FontWeight.Bold)
                            Text(x.message,maxLines=2,overflow=TextOverflow.Ellipsis,color=Muted,fontSize=12.sp,modifier=Modifier.padding(top=4.dp))
                        }
                    }
                }
            }
        }

        item{
            Column(Modifier.padding(20.dp,18.dp,20.dp,0.dp)){
                Text("Ask about your messages & synced insights",fontSize=18.sp,fontWeight=FontWeight.Bold)
                Text(if(vm.insightSync)"Selected structured phone events are available to Q." else
                    "Phone events stay on-device. Enable optional sync in Activity to include them in Q.",
                    fontSize=11.sp,color=Muted)
                OutlinedTextField(
                    value=q,onValueChange={q=it},modifier=Modifier.fillMaxWidth().padding(top=8.dp),
                    placeholder={Text("e.g. Who did I promise to call?")},
                    minLines=2,maxLines=4,shape=RoundedCornerShape(18.dp)
                )
                Button(
                    onClick={vm.askAgent(q)},
                    enabled=q.isNotBlank()&&!vm.agentBusy,
                    modifier=Modifier.fillMaxWidth().padding(top=8.dp)
                ){Text("Ask Q")}
            }
        }

        vm.agentAnswer?.let{a->
            item{
                Card(Modifier.fillMaxWidth().padding(20.dp,12.dp),colors=CardDefaults.cardColors(containerColor=Soft)){
                    Column(Modifier.padding(16.dp)){
                        Text("Q Answer",color=Purple,fontWeight=FontWeight.Black)
                        Text(a.answer,modifier=Modifier.padding(top=8.dp))
                        if(a.references.isNotEmpty()){
                            Text("Based on",fontWeight=FontWeight.Bold,fontSize=12.sp,modifier=Modifier.padding(top=12.dp))
                            a.references.take(5).forEach{r->
                                Text("• ${r.contact}: ${r.text}",fontSize=11.sp,color=Muted,maxLines=3,overflow=TextOverflow.Ellipsis,modifier=Modifier.padding(top=4.dp))
                            }
                        }
                    }
                }
            }
        }

        item{
            Column(Modifier.padding(20.dp,10.dp,20.dp,0.dp)){
                Text("Search chat memory",fontSize=18.sp,fontWeight=FontWeight.Bold)
                OutlinedTextField(
                    search,{search=it;vm.searchMemory(it)},Modifier.fillMaxWidth().padding(top=8.dp),
                    placeholder={Text("Invoice, Saturday, address…")},singleLine=true
                )
            }
        }
        items(vm.memoryResults.take(15)){m->
            Card(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=4.dp)){
                Column(Modifier.padding(12.dp)){
                    Text("${m.contact} · ${m.sender}",fontWeight=FontWeight.Bold,fontSize=12.sp)
                    Text(m.text,fontSize=12.sp,color=Muted,modifier=Modifier.padding(top=4.dp))
                }
            }
        }

        item{
            Text("Personal communication profile",fontSize=18.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(20.dp,20.dp,20.dp,8.dp))
        }
        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=20.dp)){
                Column(Modifier.padding(16.dp)){
                    Text(vm.styleProfile?.summary ?: "Building your style profile from your recent sent messages.",fontSize=13.sp)
                    vm.styleProfile?.signals?.forEach{s->Text("• $s",fontSize=11.sp,color=Muted,modifier=Modifier.padding(top=5.dp))}
                    Text("The profile focuses on writing style only, not sensitive personal traits.",fontSize=10.sp,color=Muted,modifier=Modifier.padding(top=10.dp))
                }
            }
        }
    }
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
    Column{
        Header("Me","@${vm.store.username.orEmpty()}")
        Card(Modifier.fillMaxWidth().padding(20.dp)){Column(Modifier.padding(18.dp)){Text(vm.store.displayName.orEmpty(),fontSize=20.sp,fontWeight=FontWeight.Bold);Text("@${vm.store.username.orEmpty()}",color=Muted)}}
        Row(Modifier.padding(horizontal=20.dp,vertical=8.dp),verticalAlignment=Alignment.CenterVertically){
            BrandMark(48.dp);Spacer(Modifier.width(10.dp));Text("LEMMIQ V${BuildConfig.VERSION_NAME}",fontWeight=FontWeight.Bold)
        }
        TextButton({showMoments=true},modifier=Modifier.padding(horizontal=20.dp)){Text("✨ Open 24-hour Moments")}
        Text("🧠 AI memory: recent 50-message context",Modifier.padding(horizontal=20.dp,vertical=6.dp))
        Text("🔒 Private beta: messenger and synced events are server-readable, not E2EE.",
            Modifier.padding(horizontal=20.dp,vertical=6.dp),fontSize=12.sp,color=Muted)
        OutlinedButton(onClick={
            if(Build.VERSION.SDK_INT>=33 && ContextCompat.checkSelfPermission(ctx,Manifest.permission.POST_NOTIFICATIONS)
                !=PackageManager.PERMISSION_GRANTED)notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            else vm.registerPush()
        }){Text("🔔 Enable / refresh message push alerts")}
        Text("FCM needs Firebase setup; background delivery can be delayed on sleeping Render services.",fontSize=10.sp,color=Muted)
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
        items(vm.localEvents.take(25)){e->EventCard(e)}
        item{
            OutlinedButton(onClick={deleteConfirm=true},modifier=Modifier.fillMaxWidth().padding(horizontal=18.dp)){
                Text("Delete all my phone insight data")
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
      title={Text("Delete your detected events?")},
      text={Text("This clears your local records and your synced desktop copy. If the desktop is offline, deletion must be retried.")},
      confirmButton={Button({vm.deleteInsights();deleteConfirm=false}){Text("Delete data")}},
      dismissButton={TextButton({deleteConfirm=false}){Text("Cancel")}})
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
                Switch(checked=vm.externalEnabled,onCheckedChange={vm.setExternalEnabled(it)})
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
                    listOf(1,7,30).forEach{n->FilterChip(vm.externalDays==n,{vm.setExternalDays(n)},
                        {Text(if(n==1)"24h" else "$n days")})}
                }
                Row(verticalAlignment=Alignment.CenterVertically){
                    Text("Allow Q to use selected snippets",Modifier.weight(1f),fontSize=12.sp)
                    Switch(vm.externalQ,{vm.setExternalQ(it)})
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

@Composable private fun EventCard(e:PhoneEvent){
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
            if(e.amount_cents!=null)Text("${if(e.direction=="IN")"+" else "−"}${moneyString(e.amount_cents)}",
                fontWeight=FontWeight.Black,fontSize=12.sp,color=if(e.direction=="IN")Mint else Ink)
        }
    }
}

private fun moneyString(cents:Long):String = String.format(java.util.Locale.US,"$%,.2f",cents/100.0)

@Composable private fun MoneyScreen(vm:LemmiqViewModel){
    var amount by remember{mutableStateOf("")}
    var description by remember{mutableStateOf("")}
    var incoming by remember{mutableStateOf(false)}
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
        item{Text("Recent detected payments",Modifier.padding(horizontal=20.dp),fontSize=19.sp,fontWeight=FontWeight.Bold)}
        if(transactions.isEmpty())item{
            Text("No transactions detected yet.",Modifier.padding(horizontal=20.dp),color=Muted)
        }
        items(transactions.take(35)){e->EventCard(e)}
    }
}
