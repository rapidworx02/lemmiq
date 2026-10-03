package com.lemmiq.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private val V23Purple=Color(0xFF6C4DFF)
private val V23Soft=Color(0xFFF0ECFF)
private val V23Bg=Color(0xFFF7F7FB)
private val V23Ink=Color(0xFF17182A)
private val V23Muted=Color(0xFF7E8095)

@Composable
fun V23GroupChip(g:GroupDto,onClick:()->Unit){
    Card(
        Modifier.width(160.dp).clickable(onClick=onClick),
        shape=RoundedCornerShape(18.dp),
        colors=CardDefaults.cardColors(containerColor=Color.White)
    ){
        Row(Modifier.padding(12.dp),verticalAlignment=Alignment.CenterVertically){
            Box(Modifier.size(40.dp).background(V23Soft,CircleShape),contentAlignment=Alignment.Center){
                Text(g.name.firstOrNull()?.uppercase()?:"G",color=V23Purple,fontWeight=FontWeight.Black)
            }
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)){
                Text(g.name,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)
                Text("${g.member_count} members",fontSize=10.sp,color=V23Muted)
            }
            if(g.unread>0)Box(Modifier.size(20.dp).background(V23Purple,CircleShape),contentAlignment=Alignment.Center){Text("${g.unread}",color=Color.White,fontSize=9.sp)}
        }
    }
}

@Composable
fun V23NewGroupDialog(vm:LemmiqViewModel,dismiss:()->Unit,onCreated:(GroupDto)->Unit){
    var name by remember{mutableStateOf("")}
    var q by remember{mutableStateOf("")}
    val selected=remember{mutableStateListOf<UserDto>()}
    AlertDialog(
        onDismissRequest=dismiss,
        title={Text("👥 New group")},
        text={
            Column(verticalArrangement=Arrangement.spacedBy(8.dp)){
                OutlinedTextField(name,{name=it},Modifier.fillMaxWidth(),label={Text("Group name")},singleLine=true)
                OutlinedTextField(q,{q=it;vm.search(it)},Modifier.fillMaxWidth(),label={Text("Search usernames")},singleLine=true)
                if(selected.isNotEmpty())Text("Selected: "+selected.joinToString{"@${it.username}"},fontSize=10.sp,color=V23Muted)
                LazyColumn(Modifier.heightIn(max=280.dp)){
                    items(vm.users,key={it.id}){u->
                        val chosen=selected.any{it.id==u.id}
                        Row(Modifier.fillMaxWidth().clickable{
                            if(chosen)selected.removeAll{it.id==u.id}else selected.add(u)
                        }.padding(vertical=8.dp),verticalAlignment=Alignment.CenterVertically){
                            Checkbox(chosen,{if(it)selected.add(u)else selected.removeAll{x->x.id==u.id}})
                            Column{Text(u.display_name,fontWeight=FontWeight.Bold);Text("@${u.username}",fontSize=11.sp,color=V23Muted)}
                        }
                    }
                }
            }
        },
        confirmButton={Button({vm.createGroup(name,selected.map{it.id},onCreated)},enabled=name.isNotBlank()&&selected.isNotEmpty()){Text("Create")}},
        dismissButton={TextButton(dismiss){Text("Cancel")}}
    )
}

@Composable
fun V23GroupChat(vm:LemmiqViewModel){
    val g=vm.activeGroup?:return
    val ctx=LocalContext.current
    var draft by remember{mutableStateOf("")}
    var settings by remember{mutableStateOf(false)}
    var qDialog by remember{mutableStateOf(false)}
    var question by remember{mutableStateOf("")}
    val recorder=remember{LemmiqVoiceRecorder(ctx)}
    var recording by remember{mutableStateOf(false)}
    val micPermission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){granted->
        if(granted){runCatching{recorder.start()}.onSuccess{recording=true}.onFailure{vm.error=it.message}}
    }
    val filePicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->if(uri!=null)vm.uploadGroupUri(uri)}
    val groupPhotoPicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->if(uri!=null)vm.uploadGroupPhoto(uri)}
    val state=rememberLazyListState()
    LaunchedEffect(g.id,vm.groupMessages.lastOrNull()?.id){if(vm.groupMessages.isNotEmpty()&&state.firstVisibleItemIndex<=1)state.scrollToItem(0)}
    Scaffold(
        containerColor=V23Bg,
        topBar={
            Surface(Modifier.fillMaxWidth().statusBarsPadding(),shadowElevation=1.dp){
                Row(Modifier.fillMaxWidth().padding(8.dp),verticalAlignment=Alignment.CenterVertically){
                    Text("‹",fontSize=34.sp,modifier=Modifier.clickable{vm.close()}.padding(8.dp))
                    Box(Modifier.size(44.dp).background(V23Soft,CircleShape),contentAlignment=Alignment.Center){
                        Text(g.name.firstOrNull()?.uppercase()?:"G",color=V23Purple,fontWeight=FontWeight.Black)
                    }
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)){Text(g.name,fontWeight=FontWeight.Bold);Text("${g.member_count} members · Q ${g.ai_mode}",fontSize=10.sp,color=V23Muted)}
                    Text("Q",color=V23Purple,fontWeight=FontWeight.Black,fontSize=20.sp,modifier=Modifier.clickable{qDialog=true}.padding(8.dp))
                    Text("⋮",fontSize=24.sp,modifier=Modifier.clickable{settings=true}.padding(8.dp))
                }
            }
        },
        bottomBar={
            Row(Modifier.fillMaxWidth().background(Color.White).navigationBarsPadding().imePadding().padding(8.dp),verticalAlignment=Alignment.CenterVertically){
                Text("+",fontSize=28.sp,color=V23Purple,modifier=Modifier.clickable{filePicker.launch("*/*")}.padding(6.dp))
                Surface(Modifier.size(42.dp).clickable{
                    if(recording){
                        recorder.stop()?.let{(f,d)->vm.sendGroupVoiceFile(f,d)};recording=false
                    }else if(ContextCompat.checkSelfPermission(ctx,Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED){
                        runCatching{recorder.start()}.onSuccess{recording=true}.onFailure{vm.error=it.message}
                    }else micPermission.launch(Manifest.permission.RECORD_AUDIO)
                },shape=CircleShape,color=if(recording)Color(0xFFFFE8EC) else V23Soft){
                    Box(contentAlignment=Alignment.Center){Text(if(recording)"■" else "🎙")}
                }
                Spacer(Modifier.width(7.dp))
                OutlinedTextField(draft,{draft=it},Modifier.weight(1f),singleLine=true,placeholder={Text("Message ${g.name}…")})
                Spacer(Modifier.width(7.dp))
                Button({if(draft.isNotBlank()){vm.sendGroup(draft);draft=""}},contentPadding=PaddingValues(12.dp)){Text("➤")}
            }
        }
    ){p->
        Column(Modifier.fillMaxSize().padding(p)){
            Row(Modifier.fillMaxWidth().padding(10.dp),verticalAlignment=Alignment.CenterVertically){
                if(g.ai_mode=="ASSIST"){
                    FilledTonalButton({vm.suggestGroup()}){Text("✨ Suggest reply")}
                    Spacer(Modifier.width(6.dp))
                }
                FilledTonalButton({vm.summarizeGroup()}){Text("🧠 Catch me up")}
                Spacer(Modifier.width(6.dp))
                Text("No group AUTO in V2.3",fontSize=10.sp,color=V23Muted)
            }
            vm.groupSuggestion?.let{s->
                Card(Modifier.fillMaxWidth().padding(horizontal=12.dp,vertical=4.dp),colors=CardDefaults.cardColors(containerColor=V23Soft)){
                    Column(Modifier.padding(12.dp)){
                        Text("Q · Group suggestion",color=V23Purple,fontWeight=FontWeight.Bold,fontSize=11.sp)
                        Text(s,modifier=Modifier.padding(top=4.dp))
                        Row(Modifier.fillMaxWidth()){
                            TextButton({vm.discardGroupSuggestion()}){Text("Discard")}
                            Spacer(Modifier.weight(1f))
                            TextButton({draft=s;vm.discardGroupSuggestion()}){Text("Edit")}
                            Button({vm.sendGroup(s);vm.discardGroupSuggestion()}){Text("Send")}
                        }
                    }
                }
            }
            if(vm.groupBusy)LinearProgressIndicator(Modifier.fillMaxWidth())
            LazyColumn(Modifier.fillMaxSize(),state=state,reverseLayout=true,contentPadding=PaddingValues(14.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
                items(vm.groupMessages.asReversed(),key={it.id}){m->V23GroupBubble(m,vm)}
            }
        }
    }

    vm.groupSummary?.let{s->
        AlertDialog(onDismissRequest={vm.clearGroupQ()},title={Text("🧠 Catch me up")},
            text={LazyColumn{
                item{Text(s.summary)}
                if(s.decisions.isNotEmpty()){item{Text("Decisions",fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=10.dp))};items(s.decisions){Text("• $it")}}
                if(s.actions.isNotEmpty()){item{Text("Follow-ups",fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=10.dp))};items(s.actions){Text("• $it")}}
            }},confirmButton={TextButton({vm.clearGroupQ()}){Text("Close")}})
    }

    if(qDialog)AlertDialog(onDismissRequest={qDialog=false},title={Text("Q · Group")},
        text={Column{OutlinedTextField(question,{question=it},Modifier.fillMaxWidth(),label={Text("Ask about this group")})
            vm.groupAnswer?.let{Text(it.answer,modifier=Modifier.padding(top=10.dp));it.references.forEach{x->Text("• $x",fontSize=10.sp,color=V23Muted)}}}},
        confirmButton={Button({vm.askGroup(question)}){Text("Ask")}},dismissButton={TextButton({qDialog=false;vm.clearGroupQ()}){Text("Close")}})

    if(settings){
        var mode by remember{mutableStateOf(g.ai_mode)}
        var tone by remember{mutableStateOf(g.tone)}
        var search by remember{mutableStateOf("")}
        AlertDialog(onDismissRequest={settings=false},title={Text("Group settings")},
            text={
                LazyColumn(verticalArrangement=Arrangement.spacedBy(10.dp)){
                    item{
                        Text("AI mode",fontWeight=FontWeight.Bold)
                        Row{listOf("OFF","ASSIST","SUMMARY").forEach{x->FilterChip(mode==x,{mode=x},{Text(x)},modifier=Modifier.padding(end=4.dp))}}
                        OutlinedTextField(tone,{tone=it},Modifier.fillMaxWidth(),label={Text("Tone")})
                        if(g.role=="ADMIN")OutlinedButton({groupPhotoPicker.launch("image/*")},Modifier.fillMaxWidth()){Text("🖼 Change group photo")}
                    }
                    if(g.role=="ADMIN"){
                        item{
                            OutlinedTextField(search,{search=it;vm.search(it)},Modifier.fillMaxWidth(),label={Text("Add member by username")},singleLine=true)
                        }
                        items(vm.users.filter{u->g.members.none{it.id==u.id}}.take(8),key={it.id}){u->
                            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                                Text("${u.display_name} · @${u.username}",Modifier.weight(1f),fontSize=11.sp)
                                TextButton({vm.addGroupMember(u.id);search=""}){Text("Add")}
                            }
                        }
                    }
                    item{Text("Members",fontWeight=FontWeight.Bold)}
                    items(g.members,key={it.id}){m->
                        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                            Text("${m.display_name} · @${m.username} · ${m.role}",Modifier.weight(1f),fontSize=11.sp)
                            if(g.role=="ADMIN" && m.id!=vm.store.userId && m.id!=g.created_by){
                                TextButton({vm.setGroupRole(m.id,if(m.role=="ADMIN")"MEMBER" else "ADMIN")}){Text(if(m.role=="ADMIN")"Member" else "Admin",fontSize=9.sp)}
                                TextButton({vm.removeGroupMember(m.id)}){Text("Remove",fontSize=9.sp)}
                            }
                        }
                    }
                    item{Button({vm.saveGroupSettings(mode,tone);settings=false},Modifier.fillMaxWidth()){Text("Save")}}
                    item{Text("Group AUTO replies are intentionally disabled in V2.3.",fontSize=10.sp,color=V23Muted)}
                }
            },confirmButton={}
        )
    }
}

@Composable
private fun V23GroupBubble(m:GroupMessageDto,vm:LemmiqViewModel){
    val mine=m.sender_id==vm.store.userId
    val a=m.attachment
    Column(Modifier.fillMaxWidth(),horizontalAlignment=if(mine)Alignment.End else Alignment.Start){
        Surface(color=if(mine)V23Purple else Color.White,shape=RoundedCornerShape(18.dp)){
            Column(Modifier.widthIn(max=300.dp).padding(12.dp)){
                if(!mine)Text(m.sender?.display_name?:"Member",fontSize=9.sp,color=V23Purple,fontWeight=FontWeight.Bold)
                if(a?.kind=="VOICE")V23VoiceBubble(a,m.id,true,vm,mine){}
                else{
                    Text(m.text,color=if(mine)Color.White else V23Ink)
                    if(a?.media_id!=null)V23GroupAttachment(a,m.id,vm,mine)
                }
            }
        }
    }
}

@Composable
private fun V23GroupAttachment(a:AttachmentDto,messageId:Int,vm:LemmiqViewModel,mine:Boolean){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var error by remember(messageId){mutableStateOf<String?>(null)}
    TextButton(onClick={
        scope.launch{
            try{
                val bytes=withContext(Dispatchers.IO){vm.groupMediaBytes(messageId)}
                val safe=(a.name?:"group-file").replace(Regex("[^A-Za-z0-9._-]"),"_")
                val dir=File(ctx.cacheDir,"share").apply{mkdirs()}
                val f=File(dir,"group_${messageId}_$safe");withContext(Dispatchers.IO){f.writeBytes(bytes)}
                val uri=FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",f)
                ctx.startActivity(Intent(Intent.ACTION_VIEW).apply{
                    setDataAndType(uri,a.mime_type?:"application/octet-stream")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                })
            }catch(e:Exception){error=e.message}
        }
    }){Text("📎 ${a.name.orEmpty()} · Open",color=if(mine)Color.White else V23Purple,fontSize=11.sp)}
    error?.let{Text(it,fontSize=9.sp,color=if(mine)Color.White else Color.Red)}
}

@Composable
fun V23VoiceBubble(a:AttachmentDto,messageId:Int,isGroup:Boolean,vm:LemmiqViewModel,mine:Boolean,onReply:(String)->Unit){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var playing by remember(messageId){mutableStateOf(false)}
    var speed by remember(messageId){mutableFloatStateOf(1f)}
    var player by remember(messageId){mutableStateOf<LemmiqVoicePlayer?>(null)}
    var ai by remember(messageId){mutableStateOf<VoiceAiDto?>(null)}
    Column{
        Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(6.dp)){
            TextButton({
                scope.launch{
                    try{
                        if(playing){player?.release();playing=false}
                        else{
                            val bytes=withContext(Dispatchers.IO){if(isGroup)vm.groupMediaBytes(messageId) else vm.mediaBytes(messageId)}
                            val f=File(ctx.cacheDir,"voice_play_$messageId.m4a");withContext(Dispatchers.IO){f.writeBytes(bytes)}
                            player=LemmiqVoicePlayer(f).also{it.setSpeed(speed);it.play{playing=false}}
                            playing=true
                        }
                    }catch(e:Exception){vm.error=e.message}
                }
            }){Text(if(playing)"⏸" else "▶",color=if(mine)Color.White else V23Purple)}
            Text("🎙 ${((a.duration_ms?:0)/1000)}s",fontSize=11.sp,color=if(mine)Color.White else V23Ink)
            TextButton({speed=when(speed){1f->1.5f;1.5f->2f;else->1f};player?.setSpeed(speed)}){Text("${speed}×",fontSize=10.sp,color=if(mine)Color.White else V23Purple)}
            if(!isGroup)TextButton({vm.voiceAi(messageId){ai=it}}){Text("Q",color=if(mine)Color.White else V23Purple)}
        }
        if(!a.transcript.isNullOrBlank())Text("Transcript: ${a.transcript}",fontSize=9.sp,color=if(mine)Color.White.copy(alpha=.8f) else V23Muted,maxLines=3,overflow=TextOverflow.Ellipsis)
        ai?.let{x->
            Text("Q summary: ${x.summary}",fontSize=10.sp,color=if(mine)Color.White else V23Ink)
            if(x.suggested_reply.isNotBlank())Text("Suggested: ${x.suggested_reply}",fontSize=10.sp,color=if(mine)Color.White else V23Purple)
        }
    }
}

@Composable
fun V23CallsDialog(vm:LemmiqViewModel,dismiss:()->Unit){
    LaunchedEffect(Unit){vm.refreshCalls()}
    AlertDialog(onDismissRequest=dismiss,title={Text("📞 LEMMIQ Calls")},
        text={LazyColumn(Modifier.heightIn(max=420.dp)){
            item{Text(if(vm.callStatus.configured)"LiveKit voice calling ready" else "LiveKit is not configured yet",fontSize=11.sp,color=V23Muted,modifier=Modifier.padding(bottom=8.dp))}
            items(vm.callHistory,key={it.id}){c->
                Row(Modifier.fillMaxWidth().padding(vertical=8.dp),verticalAlignment=Alignment.CenterVertically){
                    Text("📞",fontSize=20.sp);Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)){Text(c.other_user?.display_name?:"LEMMIQ user",fontWeight=FontWeight.Bold);Text(c.status,fontSize=10.sp,color=V23Muted)}
                }
            }
        }},confirmButton={TextButton(dismiss){Text("Close")}})
}
