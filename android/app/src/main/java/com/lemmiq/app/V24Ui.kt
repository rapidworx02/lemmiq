package com.lemmiq.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.OpenableColumns
import android.graphics.BitmapFactory
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.core.content.ContextCompat
import coil.compose.AsyncImage
import coil.request.ImageRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private val V24Purple=Color(0xFF6C4DFF)
private val V24Soft=Color(0xFFF0ECFF)
private val V24Bg=Color(0xFFF7F7FB)
private val V24Muted=Color(0xFF7E8095)
private val V24Ink=Color(0xFF17182A)

@Composable
fun V24Avatar(user:UserDto,size:Int=50){
    val ctx=LocalContext.current
    val url=user.avatar_url?.let{if(it.startsWith("http"))it else "${BuildConfig.API_BASE_URL.trimEnd('/')}$it"}
    Box(Modifier.size(size.dp).clip(CircleShape).background(V24Soft),contentAlignment=Alignment.Center){
        if(url!=null)AsyncImage(model=url,contentDescription=user.display_name,modifier=Modifier.fillMaxSize())
        else Text(user.display_name.firstOrNull()?.uppercase()?:"?",color=V24Purple,fontWeight=FontWeight.Bold,fontSize=(size*.36).sp)
    }
}

@Composable
fun V24GroupAvatar(g:GroupDto,size:Int=50){
    val url=g.photo_url?.let{if(it.startsWith("http"))it else "${BuildConfig.API_BASE_URL.trimEnd('/')}$it"}
    Box(Modifier.size(size.dp).clip(CircleShape).background(V24Purple),contentAlignment=Alignment.Center){
        if(url!=null)AsyncImage(model=url,contentDescription=g.name,modifier=Modifier.fillMaxSize())
        else Text(g.name.firstOrNull()?.uppercase()?:"G",color=Color.White,fontWeight=FontWeight.Bold,fontSize=(size*.36).sp)
    }
}

@Composable
fun V24Inbox(vm:LemmiqViewModel,onNewGroup:()->Unit,onAskQ:(String)->Unit){
    var search by remember{mutableStateOf("")}
    var mode by remember{mutableStateOf("ALL")}
    val conversations=remember(vm.chats,vm.groups,search,mode){
        buildList<Pair<String,Any>>{
            vm.chats.forEach{add("chat" to it)}
            vm.groups.forEach{add("group" to it)}
        }.filter{(kind,data)->
            val hay=when(data){
                is ChatDto->"${data.other_user.display_name} ${data.other_user.username} ${data.last_message.orEmpty()} ${data.draft_text}"
                is GroupDto->"${data.name} ${data.last_message.orEmpty()}"
                else->""
            }.lowercase()
            val unread=when(data){is ChatDto->data.unread;is GroupDto->data.unread;else->0}
            hay.contains(search.lowercase()) && when(mode){"UNREAD"->unread>0;"GROUPS"->kind=="group";else->true}
        }.sortedByDescending{(_,data)->when(data){is ChatDto->data.updated_at.orEmpty();is GroupDto->data.updated_at.orEmpty();else->""}}
    }
    Column(Modifier.fillMaxSize()){
        Column(Modifier.padding(horizontal=18.dp,vertical=12.dp)){
            Text("lemmiq",fontSize=28.sp,fontWeight=FontWeight.Black)
            Text(if(vm.socketStatus=="online")"● connected" else "○ ${vm.socketStatus}",color=V24Muted,fontSize=11.sp)
            Row(Modifier.fillMaxWidth().padding(top=10.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(7.dp)){
                OutlinedTextField(search,{search=it},Modifier.weight(1f),singleLine=true,
                    placeholder={Text("Search chats or ask Q")},shape=RoundedCornerShape(24.dp))
                FilledTonalButton(onClick={onAskQ(search.trim())},contentPadding=PaddingValues(horizontal=14.dp,vertical=12.dp)){Text("Q",fontWeight=FontWeight.Black,color=V24Purple)}
            }
            Row(Modifier.fillMaxWidth().padding(top=8.dp),horizontalArrangement=Arrangement.spacedBy(7.dp)){
                listOf("ALL" to "All","UNREAD" to "Unread","GROUPS" to "Groups").forEach{(value,label)->
                    FilterChip(mode==value,{mode=value},{Text(label)})
                }
                Spacer(Modifier.weight(1f))
                TextButton(onNewGroup){Text("👥 New group")}
            }
        }
        if(conversations.isEmpty()){
            Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Text("No matching conversations.",color=V24Muted)}
        }else LazyColumn(Modifier.fillMaxSize()){
            items(conversations,key={it.first+when(val x=it.second){is ChatDto->x.id;is GroupDto->x.id;else->0}}){(kind,data)->
                if(kind=="chat"){
                    val c=data as ChatDto
                    Row(Modifier.fillMaxWidth().clickable{vm.open(c)}.padding(horizontal=18.dp,vertical=11.dp),verticalAlignment=Alignment.CenterVertically){
                        V24Avatar(c.other_user);Spacer(Modifier.width(11.dp))
                        Column(Modifier.weight(1f)){
                            Text("${if(c.pinned)"📌 " else ""}${if(c.favourite)"⭐ " else ""}${c.other_user.display_name}",fontWeight=FontWeight.Bold)
                            Text(if(c.draft_text.isNotBlank())"Draft: ${c.draft_text}" else c.last_message?:"Start chatting",color=V24Muted,fontSize=12.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
                        }
                        if(c.unread>0)Badge{Text("${c.unread}")}
                    }
                }else{
                    val g=data as GroupDto
                    Row(Modifier.fillMaxWidth().clickable{vm.openGroup(g)}.padding(horizontal=18.dp,vertical=11.dp),verticalAlignment=Alignment.CenterVertically){
                        V24GroupAvatar(g,50)
                        Spacer(Modifier.width(11.dp))
                        Column(Modifier.weight(1f)){Text(g.name,fontWeight=FontWeight.Bold);Text("${g.member_count} members · ${g.last_message?:"New group"}",color=V24Muted,fontSize=12.sp,maxLines=1)}
                        if(g.unread>0)Badge{Text("${g.unread}")}
                    }
                }
            }
        }
    }
}

@Composable
fun V24NewGroupDialog(vm:LemmiqViewModel,dismiss:()->Unit){
    var name by remember{mutableStateOf("")}
    var q by remember{mutableStateOf("")}
    val selected=remember{mutableStateListOf<UserDto>()}
    AlertDialog(onDismissRequest=dismiss,title={Text("👥 New group")},
        text={Column{
            OutlinedTextField(name,{name=it},Modifier.fillMaxWidth(),label={Text("Group name")},singleLine=true)
            OutlinedTextField(q,{q=it;vm.search(it)},Modifier.fillMaxWidth().padding(top=8.dp),label={Text("Search usernames")},singleLine=true)
            if(selected.isNotEmpty())Text("Selected: "+selected.joinToString{"@${it.username}"},fontSize=10.sp,color=V24Muted,modifier=Modifier.padding(top=6.dp))
            LazyColumn(Modifier.heightIn(max=280.dp)){
                items(vm.users,key={it.id}){u->
                    val checked=selected.any{it.id==u.id}
                    Row(Modifier.fillMaxWidth().clickable{if(checked)selected.removeAll{it.id==u.id}else selected.add(u)}.padding(vertical=7.dp),verticalAlignment=Alignment.CenterVertically){
                        Checkbox(checked,{if(it)selected.add(u)else selected.removeAll{x->x.id==u.id}})
                        V24Avatar(u,38);Spacer(Modifier.width(8.dp));Column{Text(u.display_name,fontWeight=FontWeight.Bold);Text("@${u.username}",fontSize=10.sp,color=V24Muted)}
                    }
                }
            }
        }},
        confirmButton={Button({vm.createGroup(name,selected.map{it.id}){g->dismiss();vm.openGroup(g)}},enabled=name.isNotBlank()&&selected.isNotEmpty()){Text("Create")}},
        dismissButton={TextButton(dismiss){Text("Cancel")}})
}

@Composable
fun V24GroupChat(vm:LemmiqViewModel){
    val g=vm.activeGroup?:return
    val ctx=LocalContext.current
    var draft by remember{mutableStateOf("")}
    var settings by remember{mutableStateOf(false)}
    var askQ by remember{mutableStateOf(false)}
    var question by remember{mutableStateOf("")}
    val recorder=remember{LemmiqVoiceRecorder(ctx)}
    var recording by remember{mutableStateOf(false)}
    val mic=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){ok->
        if(ok)runCatching{recorder.start()}.onSuccess{recording=true}.onFailure{vm.error=it.message}
    }
    val filePicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->if(uri!=null)vm.uploadGroupUri(uri)}

    Scaffold(containerColor=V24Bg,
        topBar={Surface(Modifier.fillMaxWidth().statusBarsPadding(),shadowElevation=1.dp){
            Row(Modifier.fillMaxWidth().padding(8.dp),verticalAlignment=Alignment.CenterVertically){
                Text("‹",fontSize=34.sp,modifier=Modifier.clickable{vm.close()}.padding(8.dp))
                V24GroupAvatar(g,44)
                Spacer(Modifier.width(10.dp));Column(Modifier.weight(1f)){Text(g.name,fontWeight=FontWeight.Bold);Text("${g.member_count} members · Q ${g.ai_mode}",fontSize=10.sp,color=V24Muted)}
                Text("Q",color=V24Purple,fontWeight=FontWeight.Black,fontSize=20.sp,modifier=Modifier.clickable{askQ=true}.padding(8.dp))
                Text("⋮",fontSize=24.sp,modifier=Modifier.clickable{settings=true}.padding(8.dp))
            }
        }},
        bottomBar={Column(Modifier.background(Color.White).navigationBarsPadding().imePadding()){
            vm.groupSuggestion?.let{s->Card(Modifier.fillMaxWidth().padding(8.dp),colors=CardDefaults.cardColors(containerColor=V24Soft)){Column(Modifier.padding(10.dp)){
                Text("Q suggested reply",fontWeight=FontWeight.Bold,color=V24Purple);Text(s)
                Row{TextButton({vm.groupSuggestion=null}){Text("Discard")};Spacer(Modifier.weight(1f));TextButton({draft=s;vm.groupSuggestion=null}){Text("Edit")};Button({vm.sendGroup(s);vm.groupSuggestion=null}){Text("Send")}}
            }}}
            Row(Modifier.fillMaxWidth().padding(8.dp),verticalAlignment=Alignment.CenterVertically){
                Text("+",fontSize=28.sp,color=V24Purple,modifier=Modifier.clickable{filePicker.launch("*/*")}.padding(5.dp))
                Surface(Modifier.size(42.dp).clickable{
                    if(recording){recorder.stop()?.let{vm.sendGroupVoiceFile(it.first,it.second)};recording=false}
                    else if(ContextCompat.checkSelfPermission(ctx,Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED)runCatching{recorder.start()}.onSuccess{recording=true}
                    else mic.launch(Manifest.permission.RECORD_AUDIO)
                },shape=CircleShape,color=if(recording)Color(0xFFFFE7EA) else V24Soft){Box(contentAlignment=Alignment.Center){Text(if(recording)"■" else "🎙")}}
                Spacer(Modifier.width(7.dp))
                OutlinedTextField(draft,{draft=it},Modifier.weight(1f),singleLine=true,placeholder={Text("Message group")})
                Spacer(Modifier.width(6.dp));Button({if(draft.isNotBlank()){vm.sendGroup(draft);draft=""}}){Text("➤")}
            }
        }}
    ){p->
        Column(Modifier.fillMaxSize().padding(p)){
            Row(Modifier.fillMaxWidth().padding(10.dp),verticalAlignment=Alignment.CenterVertically){
                if(g.ai_mode=="ASSIST"){FilledTonalButton({vm.suggestGroup()}){Text("✨ Suggest reply")};Spacer(Modifier.width(6.dp))}
                FilledTonalButton({vm.summarizeGroup()}){Text("🧠 Catch me up")}
            }
            if(vm.groupBusy)LinearProgressIndicator(Modifier.fillMaxWidth())
            LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(12.dp),verticalArrangement=Arrangement.spacedBy(6.dp)){
                var previousDay:String?=null
                vm.groupMessages.forEach{m->
                    val day=v24FriendlyDay(m.created_at)
                    if(day!=previousDay){item(key="d_${m.id}"){V24DateSeparator(day)};previousDay=day}
                    item(key=m.id){V24GroupBubble(m,vm)}
                }
            }
        }
    }

    vm.groupSummary?.let{s->AlertDialog(onDismissRequest={vm.groupSummary=null},title={Text("🧠 Catch me up")},
        text={LazyColumn{item{Text(s.summary)};if(s.decisions.isNotEmpty()){item{Text("Decisions",fontWeight=FontWeight.Bold)};items(s.decisions){Text("• $it")}};if(s.actions.isNotEmpty()){item{Text("Follow-ups",fontWeight=FontWeight.Bold)};items(s.actions){Text("• $it")}}}},
        confirmButton={TextButton({vm.groupSummary=null}){Text("Close")}})}
    if(askQ)AlertDialog(onDismissRequest={askQ=false},title={Text("Q · Group")},
        text={Column{OutlinedTextField(question,{question=it},Modifier.fillMaxWidth(),label={Text("Ask about this group")});vm.groupAnswer?.let{Text(it.answer,modifier=Modifier.padding(top=10.dp))}}},
        confirmButton={Button({vm.askGroup(question)}){Text("Ask")}},dismissButton={TextButton({askQ=false;vm.groupAnswer=null}){Text("Close")}})
    if(settings)V24GroupSettings(vm){settings=false}
}

@Composable
private fun V24GroupBubble(m:GroupMessageDto,vm:LemmiqViewModel){
    val mine=m.sender_id==vm.store.userId
    val a=m.attachment
    val isPhoto=isLemmiqImageAttachmentV2102(a)
    val mediaId=a?.media_id
    var bitmap by remember(mediaId){mutableStateOf<android.graphics.Bitmap?>(null)}
    var mediaError by remember(m.id){mutableStateOf<String?>(null)}
    var photoOpen by remember(m.id){mutableStateOf(false)}

    LaunchedEffect(mediaId,isPhoto){
        if(mediaId!=null && isPhoto){
            try{
                val bytes=withContext(Dispatchers.IO){vm.groupMediaBytes(m.id)}
                val bounds=BitmapFactory.Options().apply{inJustDecodeBounds=true}
                BitmapFactory.decodeByteArray(bytes,0,bytes.size,bounds)
                var sample=1
                while(bounds.outWidth/sample>1600 || bounds.outHeight/sample>1600)sample*=2
                bitmap=BitmapFactory.decodeByteArray(bytes,0,bytes.size,BitmapFactory.Options().apply{inSampleSize=sample})
                if(bitmap==null)mediaError="Unable to decode this photo"
            }catch(e:Exception){mediaError=e.message?:"Unable to load this photo"}
        }
    }

    Column(Modifier.fillMaxWidth(),horizontalAlignment=if(mine)Alignment.End else Alignment.Start){
        Surface(color=if(mine)V24Purple else Color.White,shape=RoundedCornerShape(18.dp),shadowElevation=if(mine)0.dp else 1.dp){
            Column(Modifier.widthIn(max=330.dp).padding(if(isPhoto)4.dp else 11.dp)){
                if(!mine)Text(m.sender?.display_name?:"Member",fontSize=9.sp,color=V24Purple,fontWeight=FontWeight.Bold,modifier=Modifier.padding(horizontal=if(isPhoto)6.dp else 0.dp,vertical=if(isPhoto)4.dp else 0.dp))
                when{
                    a?.kind=="VOICE" -> V24VoiceContent(a,m.id,true,vm,mine)
                    isPhoto -> {
                        bitmap?.let{bmp->
                            Image(
                                bmp.asImageBitmap(),
                                contentDescription="Group photo",
                                modifier=Modifier.fillMaxWidth().heightIn(min=150.dp,max=360.dp).clip(RoundedCornerShape(15.dp)).clickable{photoOpen=true},
                                contentScale=ContentScale.Fit
                            )
                        } ?: Surface(
                            color=if(mine)Color.White.copy(alpha=.10f) else V24Soft,
                            shape=RoundedCornerShape(14.dp),
                            modifier=Modifier.fillMaxWidth().height(190.dp)
                        ){
                            Box(contentAlignment=Alignment.Center){
                                if(mediaError==null)CircularProgressIndicator(modifier=Modifier.size(30.dp),strokeWidth=3.dp)
                                else Text("Unable to load this photo",fontSize=11.sp,color=if(mine)Color.White else V24Muted)
                            }
                        }
                        if(m.text.isNotBlank())Text(m.text,color=if(mine)Color.White else V24Ink,modifier=Modifier.padding(horizontal=7.dp,vertical=6.dp))
                    }
                    else -> Text(m.text,color=if(mine)Color.White else V24Ink)
                }
                Text(v24Time(m.created_at),fontSize=9.sp,color=if(mine)Color.White.copy(alpha=.75f) else V24Muted,modifier=Modifier.align(Alignment.End).padding(horizontal=if(isPhoto)7.dp else 0.dp,vertical=if(isPhoto)3.dp else 0.dp))
            }
        }
    }

    if(photoOpen){
        bitmap?.let{bmp->LemmiqFullScreenPhotoV2102(bitmap=bmp,onDismiss={photoOpen=false})}
    }
}

@Composable
private fun V24GroupSettings(vm:LemmiqViewModel,dismiss:()->Unit){
    val g=vm.activeGroup?:return
    val photoPicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->if(uri!=null)vm.uploadGroupPhoto(uri)}
    var mode by remember{mutableStateOf(g.ai_mode)}
    var tone by remember{mutableStateOf(g.tone)}
    var search by remember{mutableStateOf("")}
    AlertDialog(onDismissRequest=dismiss,title={Text("Group settings")},
        text={LazyColumn{
            item{Text("AI mode",fontWeight=FontWeight.Bold);Row{listOf("OFF","ASSIST","SUMMARY").forEach{x->FilterChip(mode==x,{mode=x},{Text(x)},modifier=Modifier.padding(end=4.dp))}};OutlinedTextField(tone,{tone=it},Modifier.fillMaxWidth(),label={Text("Tone")})}
            if(g.role=="ADMIN"){
                item{OutlinedButton({photoPicker.launch("image/*")},Modifier.fillMaxWidth()){Text("🖼 Change group photo")}}
                item{OutlinedTextField(search,{search=it;vm.search(it)},Modifier.fillMaxWidth(),label={Text("Add member by username")})}
                items(vm.users.filter{u->g.members.none{it.id==u.id}}.take(8),key={it.id}){u->Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text("${u.display_name} @${u.username}",Modifier.weight(1f),fontSize=11.sp);TextButton({vm.addGroupMember(u.id)}){Text("Add")}}}
            }
            item{Text("Members",fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=8.dp))}
            items(g.members,key={it.id}){m->Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                V24Avatar(UserDto(m.id,m.username,m.display_name,m.avatar,m.avatar_url),34);Spacer(Modifier.width(7.dp))
                Text("${m.display_name} · ${m.role}",Modifier.weight(1f),fontSize=11.sp)
                if(g.role=="ADMIN"&&m.id!=vm.store.userId&&m.id!=g.created_by){TextButton({vm.setGroupRole(m.id,if(m.role=="ADMIN")"MEMBER" else "ADMIN")}){Text(if(m.role=="ADMIN")"Member" else "Admin",fontSize=9.sp)};TextButton({vm.removeGroupMember(m.id)}){Text("Remove",fontSize=9.sp)}}
            }}
            item{Button({vm.saveGroupSettings(mode,tone);dismiss()},Modifier.fillMaxWidth()){Text("Save")};Text("Group AUTO replies remain disabled.",fontSize=10.sp,color=V24Muted)}
        }},confirmButton={})
}

@Composable
fun V24Updates(vm:LemmiqViewModel){
    var creator by remember{mutableStateOf(false)}
    var text by remember{mutableStateOf("")}
    var opened by remember{mutableStateOf<StatusDto?>(null)}
    val mediaPicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->
        if(uri!=null)vm.uploadStatusUri(uri)
    }
    LaunchedEffect(Unit){vm.refreshStatuses()}

    val mine=vm.statuses.filter{it.user.id==vm.store.userId}.sortedByDescending{it.created_at}
    val recent=vm.statuses.filter{it.user.id!=vm.store.userId}
        .groupBy{it.user.id}.mapNotNull{(_,items)->items.maxByOrNull{it.created_at}}
        .sortedByDescending{it.created_at}

    LazyColumn(
        Modifier.fillMaxSize().background(V24Bg),
        contentPadding=PaddingValues(bottom=28.dp),
        verticalArrangement=Arrangement.spacedBy(8.dp)
    ){
        item{
            Column(Modifier.padding(horizontal=18.dp,vertical=14.dp)){
                Text("Updates",fontSize=30.sp,fontWeight=FontWeight.Black)
                Text("Status · disappears after 24 hours",fontSize=11.sp,color=V24Muted)
                Text("Status",fontSize=21.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=18.dp,bottom=10.dp))
                LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp)){
                    item{V27AddStatusCard(vm){creator=true}}
                    if(mine.isNotEmpty())item{V27StatusCard(mine.first(),vm,true){vm.viewStatus(mine.first().id){opened=it}}}
                    items(recent,key={it.user.id}){s->V27StatusCard(s,vm,false){vm.viewStatus(s.id){opened=it}}}
                }
                Row(Modifier.fillMaxWidth().padding(top=12.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    OutlinedButton(onClick={creator=true},modifier=Modifier.weight(1f)){Text("✎ Text status")}
                    Button(onClick={mediaPicker.launch("*/*")},modifier=Modifier.weight(1f)){Text("📷 Photo / video")}
                }
            }
        }
        if(recent.isNotEmpty()){
            item{Text("Recent updates",fontSize=18.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(horizontal=18.dp,vertical=6.dp))}
            items(recent,key={"recent_"+it.user.id}){s->
                Row(
                    Modifier.fillMaxWidth().clickable{vm.viewStatus(s.id){opened=it}}.padding(horizontal=18.dp,vertical=9.dp),
                    verticalAlignment=Alignment.CenterVertically
                ){
                    Box(
                        Modifier.size(56.dp).clip(CircleShape).background(if(s.viewed)Color(0xFFD9D9E1) else V24Purple).padding(3.dp),
                        contentAlignment=Alignment.Center
                    ){
                        Box(Modifier.fillMaxSize().clip(CircleShape).background(Color.White).padding(2.dp)){V24Avatar(s.user,46)}
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)){
                        Text(s.user.display_name,fontWeight=FontWeight.Bold)
                        Text(v24Time(s.created_at),fontSize=10.sp,color=V24Muted)
                    }
                    Text(if(s.viewed)"Viewed" else "New",fontSize=10.sp,color=if(s.viewed)V24Muted else V24Purple,fontWeight=FontWeight.Bold)
                }
            }
        }else{
            item{
                Card(Modifier.fillMaxWidth().padding(horizontal=18.dp)){
                    Text("No recent updates yet.",modifier=Modifier.padding(16.dp),color=V24Muted)
                }
            }
        }
        if(mine.isNotEmpty()){
            item{Text("My status",fontSize=18.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(horizontal=18.dp,vertical=6.dp))}
            items(mine,key={"mine_"+it.id}){s->
                Row(
                    Modifier.fillMaxWidth().clickable{vm.viewStatus(s.id){opened=it}}.padding(horizontal=18.dp,vertical=9.dp),
                    verticalAlignment=Alignment.CenterVertically
                ){
                    V24Avatar(s.user,50);Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)){
                        Text(s.text.ifBlank{s.kind},fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)
                        Text("${v24Time(s.created_at)} · ${s.view_count?:0} views",fontSize=10.sp,color=V24Muted)
                    }
                    TextButton({vm.deleteStatus(s.id)}){Text("Delete")}
                }
            }
        }
    }

    if(creator){
        AlertDialog(
            onDismissRequest={creator=false},
            title={Text("Add status")},
            text={
                Column(verticalArrangement=Arrangement.spacedBy(10.dp)){
                    OutlinedTextField(value=text,onValueChange={text=it.take(1500)},modifier=Modifier.fillMaxWidth(),placeholder={Text("Type a status…")},minLines=4,maxLines=7)
                    Text("Status disappears automatically after 24 hours.",fontSize=10.sp,color=V24Muted)
                    OutlinedButton(onClick={creator=false;mediaPicker.launch("*/*")},modifier=Modifier.fillMaxWidth()){Text("📷 Choose photo / video")}
                }
            },
            confirmButton={Button(onClick={vm.postStatusText(text);text="";creator=false},enabled=text.isNotBlank()){Text("Post")}},
            dismissButton={TextButton({creator=false}){Text("Cancel")}}
        )
    }

    opened?.let{st->
        V27StatusViewer(st,vm,onClose={opened=null},onReply={
            vm.replyToStatus(st.user.id,st.text.ifBlank{st.kind});opened=null
        },onDelete={vm.deleteStatus(st.id);opened=null})
    }
}

@Composable
private fun V27AddStatusCard(vm:LemmiqViewModel,onClick:()->Unit){
    Card(
        Modifier.width(112.dp).height(170.dp).clickable(onClick=onClick),
        shape=RoundedCornerShape(22.dp),
        colors=CardDefaults.cardColors(containerColor=Color.White)
    ){
        Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){
            Column(horizontalAlignment=Alignment.CenterHorizontally){
                vm.currentUser?.let{V24Avatar(it,62)}
                Box(Modifier.offset(y=(-10).dp).size(24.dp).clip(CircleShape).background(V24Purple),contentAlignment=Alignment.Center){
                    Text("+",color=Color.White,fontWeight=FontWeight.Black)
                }
                Text("Add status",fontSize=11.sp,fontWeight=FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun V27StatusCard(s:StatusDto,vm:LemmiqViewModel,mine:Boolean,onClick:()->Unit){
    val ctx=LocalContext.current
    Card(
        Modifier.width(120.dp).height(170.dp).clickable(onClick=onClick),
        shape=RoundedCornerShape(22.dp),
        colors=CardDefaults.cardColors(containerColor=V24Ink)
    ){
        Box(Modifier.fillMaxSize()){
            if(s.kind=="IMAGE"&&s.media_url!=null){
                val url=if(s.media_url.startsWith("http"))s.media_url else "${BuildConfig.API_BASE_URL.trimEnd('/')}${s.media_url}"
                AsyncImage(
                    model=ImageRequest.Builder(ctx).data(url).addHeader("Authorization","Bearer ${vm.store.token.orEmpty()}").crossfade(true).build(),
                    contentDescription="Status",
                    modifier=Modifier.fillMaxSize()
                )
            }else{
                Box(Modifier.fillMaxSize().background(if(s.kind=="VIDEO")Color(0xFF20243A) else V24Purple),contentAlignment=Alignment.Center){
                    Text(if(s.kind=="VIDEO")"▶" else (s.text.take(22).ifBlank{"Status"}),color=Color.White,fontWeight=FontWeight.Bold,fontSize=if(s.kind=="VIDEO")28.sp else 16.sp,modifier=Modifier.padding(12.dp))
                }
            }
            Box(Modifier.fillMaxWidth().height(58.dp).align(Alignment.BottomCenter).background(Color.Black.copy(alpha=.45f)))
            Box(Modifier.padding(9.dp).size(38.dp).clip(CircleShape).background(if(mine||!s.viewed)V24Purple else Color.Gray).padding(2.dp)){
                Box(Modifier.fillMaxSize().clip(CircleShape).background(Color.White).padding(2.dp)){V24Avatar(s.user,30)}
            }
            Text(if(mine)"My status" else s.user.display_name,color=Color.White,fontWeight=FontWeight.Bold,fontSize=11.sp,modifier=Modifier.align(Alignment.BottomStart).padding(9.dp),maxLines=1,overflow=TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun V27StatusViewer(st:StatusDto,vm:LemmiqViewModel,onClose:()->Unit,onReply:()->Unit,onDelete:()->Unit){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    Dialog(onDismissRequest=onClose){
        Surface(
            Modifier.fillMaxWidth().heightIn(min=520.dp,max=720.dp),
            color=Color(0xFF080A12),
            shape=RoundedCornerShape(24.dp)
        ){
            Column(Modifier.fillMaxSize()){
                Row(Modifier.fillMaxWidth().padding(12.dp),verticalAlignment=Alignment.CenterVertically){
                    V24Avatar(st.user,42);Spacer(Modifier.width(9.dp))
                    Column(Modifier.weight(1f)){
                        Text(st.user.display_name,color=Color.White,fontWeight=FontWeight.Bold)
                        Text(v24Time(st.created_at),color=Color.White.copy(alpha=.65f),fontSize=10.sp)
                    }
                    TextButton(onClose){Text("✕",color=Color.White)}
                }
                Box(Modifier.fillMaxWidth().height(3.dp).padding(horizontal=12.dp).background(Color.White.copy(alpha=.25f))){
                    Box(Modifier.fillMaxSize().background(Color.White))
                }
                Box(Modifier.weight(1f).fillMaxWidth(),contentAlignment=Alignment.Center){
                    if(st.kind=="IMAGE"&&st.media_url!=null){
                        val url=if(st.media_url.startsWith("http"))st.media_url else "${BuildConfig.API_BASE_URL.trimEnd('/')}${st.media_url}"
                        AsyncImage(
                            model=ImageRequest.Builder(ctx).data(url).addHeader("Authorization","Bearer ${vm.store.token.orEmpty()}").build(),
                            contentDescription="Status image",modifier=Modifier.fillMaxSize()
                        )
                    }else if(st.kind=="VIDEO"){
                        Column(horizontalAlignment=Alignment.CenterHorizontally){
                            Text("▶",color=Color.White,fontSize=48.sp)
                            Button(onClick={
                                scope.launch{
                                    try{
                                        val bytes=withContext(Dispatchers.IO){vm.statusMediaBytes(st.id)}
                                        val f=File(ctx.cacheDir,"status/status_${st.id}.mp4").apply{parentFile?.mkdirs()}
                                        withContext(Dispatchers.IO){f.writeBytes(bytes)}
                                        val uri=androidx.core.content.FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",f)
                                        ctx.startActivity(Intent(Intent.ACTION_VIEW).apply{setDataAndType(uri,st.mime_type?:"video/*");addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)})
                                    }catch(e:Exception){vm.error=e.message}
                                }
                            }){Text("Play video")}
                        }
                    }else{
                        Text(st.text,color=Color.White,fontSize=28.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(28.dp))
                    }
                    if(st.kind!="TEXT"&&st.text.isNotBlank()){
                        Surface(color=Color.Black.copy(alpha=.55f),shape=RoundedCornerShape(12.dp),modifier=Modifier.align(Alignment.BottomCenter).padding(16.dp)){
                            Text(st.text,color=Color.White,modifier=Modifier.padding(10.dp))
                        }
                    }
                }
                if(st.user.id==vm.store.userId){
                    Row(Modifier.fillMaxWidth().padding(10.dp),verticalAlignment=Alignment.CenterVertically){
                        Text("${st.view_count?:0} views",color=Color.White.copy(alpha=.7f),fontSize=11.sp,modifier=Modifier.weight(1f))
                        TextButton(onDelete){Text("Delete",color=Color.White)}
                    }
                }else{
                    Button(onClick=onReply,modifier=Modifier.fillMaxWidth().padding(12.dp)){Text("Reply in chat")}
                }
            }
        }
    }
}

@Composable
fun V24Trust(vm:LemmiqViewModel){
    var text by remember{mutableStateOf("")}
    var search by remember{mutableStateOf("")}
    var selected by remember{mutableStateOf<TrustHistoryDto?>(null)}
    LaunchedEffect(Unit){vm.refreshTrustHistory()}
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(18.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
        item{Text("Trust",fontSize=29.sp,fontWeight=FontWeight.Black);Text("Fact / Scam Check with saved history",color=V24Muted,fontSize=11.sp)}
        item{Card(Modifier.fillMaxWidth()){Column(Modifier.padding(14.dp)){OutlinedTextField(text,{text=it},Modifier.fillMaxWidth(),label={Text("Paste a claim or suspicious message")},minLines=3);Button({vm.trustCheck(text);vm.refreshTrustHistory()},enabled=text.isNotBlank()&&!vm.trustBusy,modifier=Modifier.padding(top=8.dp)){Text(if(vm.trustBusy)"Checking…" else "🛡 Check")}}}}
        vm.trustResult?.let{r->item{Card(Modifier.fillMaxWidth(),colors=CardDefaults.cardColors(containerColor=V24Soft)){Column(Modifier.padding(14.dp)){Text(r.status.replace("_"," "),fontWeight=FontWeight.Black,color=V24Purple);Text(r.summary);Text("${r.confidence}% evidence strength",fontSize=10.sp,color=V24Muted)}}}}
        item{Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text("History",fontSize=18.sp,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));TextButton({vm.clearTrustHistory()}){Text("Clear")}};OutlinedTextField(search,{search=it;vm.refreshTrustHistory(it)},Modifier.fillMaxWidth(),placeholder={Text("Search previous checks")},singleLine=true)}
        items(vm.trustHistory,key={it.id}){h->Card(Modifier.fillMaxWidth().clickable{selected=h}){Column(Modifier.padding(12.dp)){Text(h.status.replace("_"," "),fontWeight=FontWeight.Bold);Text(h.checked_text,maxLines=2,overflow=TextOverflow.Ellipsis);Text("${h.confidence}% · ${v24Time(h.checked_at)}",fontSize=10.sp,color=V24Muted)}}}
    }
    selected?.let{h->AlertDialog(onDismissRequest={selected=null},title={Text(h.status.replace("_"," "))},text={LazyColumn{item{Text(h.summary);Text("Evidence strength: ${h.confidence}%",fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=8.dp))};items(h.reasons){Text("• $it",fontSize=12.sp)};items(h.sources){Text("${it.title}\n${it.url}",fontSize=10.sp,color=V24Purple,modifier=Modifier.padding(top=6.dp))}}},confirmButton={TextButton({selected=null}){Text("Close")}},dismissButton={TextButton({vm.deleteTrustHistory(h.id);selected=null}){Text("Delete")}})}
}

@Composable
fun V24SocialIqCard(vm:LemmiqViewModel){
    val b=vm.socialBrief
    Card(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=8.dp)){
        Column(Modifier.padding(14.dp)){
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text("Q · Social IQ Memory",fontWeight=FontWeight.Bold);Text("Explicit commitments, follow-ups and plans",fontSize=10.sp,color=V24Muted)};TextButton({vm.scanSocialIq()}){Text("Scan")}}
            if(b==null)Text("No scan yet.",fontSize=11.sp,color=V24Muted)
            else{
                Text("${b.count} remembered · ${b.promises} promises · ${b.follow_ups} follow-ups",fontSize=11.sp,color=V24Purple)
                b.items.take(5).forEach{m->Row(Modifier.fillMaxWidth().padding(top=7.dp),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text("${m.memory_type} · ${m.title}",fontSize=11.sp,fontWeight=FontWeight.Bold);Text(m.detail,fontSize=10.sp,color=V24Muted,maxLines=2)};TextButton({vm.deleteSocialMemory(m.id)}){Text("×")}}}
            }
        }
    }
}

@Composable
fun V24PrivacyCard(vm:LemmiqViewModel){
    var photo by remember(vm.privacy){mutableStateOf(vm.privacy.profile_photo)}
    var lastSeen by remember(vm.privacy){mutableStateOf(vm.privacy.last_seen)}
    var status by remember(vm.privacy){mutableStateOf(vm.privacy.status_visibility)}
    LaunchedEffect(Unit){vm.refreshPrivacy()}
    Card(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=6.dp)){
        Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text("Privacy",fontWeight=FontWeight.Bold,fontSize=18.sp)
            fun label(v:String)=when(v){"CONTACTS"->"Contacts";"NOBODY"->"Nobody";else->"Everyone"}
            Text("Profile photo · ${label(photo)}",fontSize=11.sp,color=V24Muted)
            Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){listOf("EVERYONE","CONTACTS","NOBODY").forEach{x->FilterChip(photo==x,{photo=x},{Text(label(x),fontSize=9.sp)})}}
            Text("Last seen · ${label(lastSeen)}",fontSize=11.sp,color=V24Muted)
            Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){listOf("EVERYONE","CONTACTS","NOBODY").forEach{x->FilterChip(lastSeen==x,{lastSeen=x},{Text(label(x),fontSize=9.sp)})}}
            Text("Status · ${label(status)}",fontSize=11.sp,color=V24Muted)
            Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){listOf("EVERYONE","CONTACTS","NOBODY").forEach{x->FilterChip(status==x,{status=x},{Text(label(x),fontSize=9.sp)})}}
            Button({vm.savePrivacy(PrivacyDto(photo,lastSeen,status))},Modifier.fillMaxWidth()){Text("Save privacy")}
            Text("These settings are stored in V2.4. Contact-list enforcement will continue to be hardened during beta testing.",fontSize=9.sp,color=V24Muted)
        }
    }
}

@Composable
fun V24ProfilePhotoCard(vm:LemmiqViewModel){
    val picker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->if(uri!=null)vm.uploadProfilePhoto(uri)}
    val u=vm.currentUser?:UserDto(vm.store.userId,vm.store.username.orEmpty(),vm.store.displayName.orEmpty())
    Card(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=6.dp)){
        Row(Modifier.fillMaxWidth().padding(14.dp),verticalAlignment=Alignment.CenterVertically){
            V24Avatar(u,64);Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)){Text("Profile photo",fontWeight=FontWeight.Bold);Text("Shown in chats, groups and calls",fontSize=10.sp,color=V24Muted)}
            Column{TextButton({picker.launch("image/*")}){Text("Change")};TextButton({vm.removeProfilePhoto()}){Text("Remove")}}
        }
    }
}

@Composable
fun V24VoiceContent(a:AttachmentDto,messageId:Int,isGroup:Boolean,vm:LemmiqViewModel,mine:Boolean){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var playing by remember{mutableStateOf(false)}
    var speed by remember{mutableFloatStateOf(1f)}
    var player by remember{mutableStateOf<LemmiqVoicePlayer?>(null)}
    var ai by remember{mutableStateOf<VoiceAiDto?>(null)}
    Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(4.dp)){
        TextButton({
            scope.launch{
                try{
                    if(playing){player?.release();playing=false}else{
                        val bytes=withContext(Dispatchers.IO){if(isGroup)vm.groupMediaBytes(messageId) else vm.mediaBytes(messageId)}
                        val f=File(ctx.cacheDir,"voice_$messageId.m4a");withContext(Dispatchers.IO){f.writeBytes(bytes)}
                        player=LemmiqVoicePlayer(f).also{it.speed(speed);it.play{playing=false}};playing=true
                    }
                }catch(e:Exception){vm.error=e.message}
            }
        }){Text(if(playing)"⏸" else "▶",color=if(mine)Color.White else V24Purple)}
        Text("${((a.duration_ms?:0)/1000)}s",fontSize=10.sp,color=if(mine)Color.White else V24Ink)
        TextButton({speed=when(speed){1f->1.5f;1.5f->2f;else->1f};player?.speed(speed)}){Text("${speed}×",fontSize=10.sp,color=if(mine)Color.White else V24Purple)}
        if(!isGroup)TextButton({vm.voiceAi(messageId){ai=it}}){Text("Q",color=if(mine)Color.White else V24Purple)}
    }
    if(!a.transcript.isNullOrBlank())Text("Transcript: ${a.transcript}",fontSize=9.sp,color=if(mine)Color.White.copy(alpha=.8f) else V24Muted,maxLines=3)
    ai?.let{Text("Q: ${it.summary}\nSuggested: ${it.suggested_reply}",fontSize=9.sp,color=if(mine)Color.White else V24Purple)}
}

@Composable
fun V24DateSeparator(label:String){
    Row(Modifier.fillMaxWidth().padding(vertical=8.dp),horizontalArrangement=Arrangement.Center){Surface(color=V24Soft,shape=RoundedCornerShape(99.dp)){Text(label,Modifier.padding(horizontal=11.dp,vertical=5.dp),fontSize=10.sp,color=V24Muted)}}
}

fun v24Time(iso:String):String=runCatching{
    OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("h:mm a",Locale.getDefault()))
}.getOrElse{""}

fun v24FriendlyDay(iso:String):String=runCatching{
    val d=OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).toLocalDate()
    val now=java.time.LocalDate.now()
    when(d){
        now->"Today"
        now.minusDays(1)->"Yesterday"
        else->if(d.isAfter(now.minusDays(7)))d.format(DateTimeFormatter.ofPattern("EEEE")) else d.format(DateTimeFormatter.ofPattern("d MMMM yyyy"))
    }
}.getOrElse{""}
