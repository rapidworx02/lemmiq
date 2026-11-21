package com.lemmiq.app

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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

/** V2.13.17: compact call history with contact details, filters, new call and opt-in recovery. */
@Composable
fun V21317CallsScreen(vm:LemmiqViewModel,onOpenChat:(Int)->Unit){
    val ctx=LocalContext.current
    val purple=Color(0xFF7053EB)
    val muted=Color(0xFF747687)
    var search by remember{mutableStateOf("")}
    var filter by remember{mutableStateOf("ALL")}
    var selected by remember{mutableStateOf<CallDto?>(null)}
    var newCall by remember{mutableStateOf(false)}
    var recovery by remember{mutableStateOf(false)}
    LaunchedEffect(Unit){vm.refreshCalls()}

    fun placeCall(chatId:Int,contact:UserDto?,video:Boolean){
        if(chatId<=0)return
        val launch:(CallJoinDto)->Unit={join->
            ctx.startActivity(Intent(ctx,LemmiqCallActivity::class.java).apply{
                putExtra("call_id",join.call.id)
                putExtra("ws_url",join.ws_url)
                putExtra("token",join.token)
                putExtra("person",contact?.display_name?:"LEMMIQ user")
                putExtra("avatar_url",contact?.avatar_url)
                putExtra("incoming",false)
                putExtra("call_type",join.call.call_type)
            })
        }
        if(video)vm.startVideoCall(chatId,launch) else vm.startVoiceCall(chatId,launch)
    }

    val filtered=remember(vm.callHistory,search,filter){
        vm.callHistory.filter{c->
            (filter!="MISSED" || c.status.uppercase() in setOf("MISSED","RINGING")) &&
            (search.isBlank() || c.other_user?.display_name.orEmpty().contains(search,true) || c.other_user?.username.orEmpty().contains(search,true))
        }
    }

    Column(Modifier.fillMaxSize().background(Color(0xFFF8F7FC))){
        Row(Modifier.fillMaxWidth().padding(start=19.dp,end=12.dp,top=12.dp,bottom=5.dp),verticalAlignment=Alignment.CenterVertically){
            Text("Calls",fontSize=23.sp,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f))
            TextButton(onClick={recovery=true}){Text("⋮",fontSize=23.sp,color=muted)}
        }
        Row(Modifier.fillMaxWidth().padding(horizontal=16.dp),horizontalArrangement=Arrangement.spacedBy(7.dp)){
            FilterChip(filter=="ALL",{filter="ALL"},label={Text("All")})
            FilterChip(filter=="MISSED",{filter="MISSED"},label={Text("Missed")})
            Spacer(Modifier.weight(1f))
            OutlinedButton(onClick={newCall=true}){Text("＋ New call")}
        }
        OutlinedTextField(value=search,onValueChange={search=it.take(80)},modifier=Modifier.fillMaxWidth().padding(horizontal=17.dp,vertical=6.dp),
            placeholder={Text("Search recent calls")},singleLine=true,shape=RoundedCornerShape(22.dp))
        Text("Recent",fontSize=19.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(start=20.dp,top=14.dp,bottom=6.dp))
        if(filtered.isEmpty()){
            Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Text(if(filter=="MISSED")"No missed calls" else "No recent calls",color=muted)}
        }else LazyColumn(contentPadding=PaddingValues(bottom=28.dp)){
            items(filtered,key={it.id}){call->
                val contact=call.other_user?:UserDto(0,"","LEMMIQ user")
                val status=call.status.uppercase()
                val missed=status=="MISSED" || status=="RINGING"
                val video=call.call_type.equals("VIDEO",true)
                Row(Modifier.fillMaxWidth().clickable{selected=call}.padding(horizontal=18.dp,vertical=11.dp),verticalAlignment=Alignment.CenterVertically){
                    V24Avatar(contact,49)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)){
                        Text(contact.display_name,fontSize=16.sp,fontWeight=FontWeight.SemiBold,
                            color=if(missed)Color(0xFFBD3058) else Color(0xFF202029),maxLines=1,overflow=TextOverflow.Ellipsis)
                        Text("${if(missed)"↙" else if(call.caller_id==vm.store.userId)"↗" else "↙"} " +
                            (if(video)"Video" else "Voice") + " · " + when(status){
                                "MISSED"->"Missed";"RINGING"->"Not answered";"DECLINED"->"Declined";else->"Completed"
                            },fontSize=12.sp,color=if(missed)Color(0xFFBD3058) else muted)
                        Text("${v24FriendlyDay(call.started_at)} · ${v24Time(call.started_at)}" + if(call.duration_seconds>0)" · ${call.duration_seconds/60}m ${call.duration_seconds%60}s" else "",fontSize=10.sp,color=muted)
                    }
                    TextButton(onClick={placeCall(call.chat_id,contact,video)}){
                        Text(if(video)"▣" else "☎",fontSize=23.sp,color=purple)
                    }
                }
                HorizontalDivider(color=Color(0xFFEDEBF2),modifier=Modifier.padding(start=79.dp))
            }
        }
    }

    if(newCall)AlertDialog(
        onDismissRequest={newCall=false},
        title={Text("Start a LEMMIQ call")},
        text={Column{
            Text("Choose a conversation",color=muted,fontSize=12.sp)
            LazyColumn(Modifier.heightIn(max=390.dp)){
                items(vm.chats,key={it.id}){chat->
                    Row(Modifier.fillMaxWidth().padding(vertical=6.dp),verticalAlignment=Alignment.CenterVertically){
                        V24Avatar(chat.other_user,40)
                        Text(chat.other_user.display_name,Modifier.weight(1f).padding(start=8.dp),maxLines=1)
                        TextButton(onClick={newCall=false;placeCall(chat.id,chat.other_user,false)}){Text("☎",fontSize=20.sp,color=purple)}
                        TextButton(onClick={newCall=false;placeCall(chat.id,chat.other_user,true)}){Text("▣",fontSize=20.sp,color=purple)}
                    }
                }
            }
        }},confirmButton={TextButton(onClick={newCall=false}){Text("Close")}})

    selected?.let{call->
        val contact=call.other_user?:UserDto(0,"","LEMMIQ user")
        val related=vm.callHistory.filter{it.other_user?.id==contact.id}.take(25)
        AlertDialog(onDismissRequest={selected=null},title={Text("Call info")},
            text={Column(horizontalAlignment=Alignment.CenterHorizontally){
                V24Avatar(contact,84)
                Text(contact.display_name,fontSize=22.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(top=9.dp))
                Text("@${contact.username}",color=muted,fontSize=12.sp)
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceEvenly){
                    TextButton(onClick={selected=null;onOpenChat(call.chat_id)}){Text("Message")}
                    TextButton(onClick={selected=null;placeCall(call.chat_id,contact,false)}){Text("☎ Voice")}
                    TextButton(onClick={selected=null;placeCall(call.chat_id,contact,true)}){Text("▣ Video")}
                }
                HorizontalDivider()
                LazyColumn(Modifier.heightIn(max=245.dp)){
                    items(related,key={it.id}){entry->
                        Column(Modifier.fillMaxWidth().padding(vertical=7.dp)){
                            Text("${entry.call_type.lowercase().replaceFirstChar{it.uppercase()}} · ${entry.status.lowercase().replace('_',' ')}",fontWeight=FontWeight.Medium,fontSize=12.sp)
                            Text("${v24FriendlyDay(entry.started_at)} · ${v24Time(entry.started_at)}" + if(entry.duration_seconds>0)" · ${entry.duration_seconds}s" else "",color=muted,fontSize=10.sp)
                        }
                    }
                }
            }},confirmButton={TextButton(onClick={selected=null}){Text("Close")}})
    }

    if(recovery)AlertDialog(onDismissRequest={recovery=false},
        title={Text("Troubleshoot calls")},
        text={Column{
            Text("Only use recovery when LEMMIQ incorrectly says you're already on a call.",fontSize=12.sp,color=muted)
            V2132CallRecoveryPanel(vm)
        }},confirmButton={TextButton(onClick={recovery=false}){Text("Close")}})
}
// V300_INSTALLED
