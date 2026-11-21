// V2138_COMBINED
/* V21360_CREATOR_UX */
/* V21354_CREATOR_AUTOPUBLISH */
package com.lemmiq.app

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.google.gson.Gson
import com.google.gson.JsonParser
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.net.URLEncoder
import java.util.UUID

/* V2.13.4: this UI never opens the personal ChatDto for a creator's fan chat.
   Professional conversations use independent /v2134/chats/{opaque-id} endpoints. */

internal data class ProIdentityV2134(val public_id:String="",val handle:String="",val stage_name:String="",val avatar_url:String?=null)
internal data class ProTermsV2134(val messages:Int=3,val hours:Int=48)
internal data class ProMeV2134(val has_creator_profile:Boolean=false,val creator_status:String?=null,
    val identity:ProIdentityV2134?=null,val terms:ProTermsV2134=ProTermsV2134())
internal data class ProProfileV2134(val public_id:String="",val handle:String="",val stage_name:String="",
    val bio:String="",val category:String="",val avatar_url:String?=null,val chat_q:Double=0.0,
    val monthly_q:Double=0.0,val followers:Int=0)
internal data class ProPassV2134(val status:String="",val max_messages:Int=3,val fan_sent:Int=0,
    val creator_sent:Int=0,val fan_remaining:Int=0,val creator_remaining:Int=0,val expires_at:String="")
internal data class ProFanV2134(val display_name:String="",val username:String="")
internal data class ProRequestV2134(val id:Int=0,val status:String="REQUESTED",val role:String="FAN",
    val creator:ProIdentityV2134?=null,val fan:ProFanV2134?=null,val message:String="",val amount_q:Double=0.0,
    val thread_id:String?=null,val pass_data:ProPassV2134?=null) {
    @com.google.gson.annotations.SerializedName("pass") private val wirePass:ProPassV2134?=null
    val paidPass:ProPassV2134? get()=wirePass?:pass_data
}
internal data class ProOfferV2134(val id:Int=0,val item_id:Int=0,val title:String="",val kind:String="",
    val price_q:Double=0.0,val unlocked:Boolean=false)
internal data class ProMessageV2134(val id:Int=0,val role:String="",val kind:String="TEXT",val body:String="",
    val created_at:String="",val offer:ProOfferV2134?=null,
    val media:ProDirectMediaV2135?=null)
internal data class ProChatV2134(val thread_id:String="",val role:String="FAN",val creator:ProIdentityV2134=ProIdentityV2134(),
    val fan:ProFanV2134?=null,val pass_data:ProPassV2134?=null,val messages:List<ProMessageV2134> = emptyList()) {
    @com.google.gson.annotations.SerializedName("pass") private val wirePass:ProPassV2134?=null
    val paidPass:ProPassV2134? get()=wirePass?:pass_data
}
internal data class ProMessageSentV2134(val message:ProMessageV2134=ProMessageV2134(),val pass_data:ProPassV2134?=null)

internal class ProfessionalApiV2134(private val context:Context,private val session:SessionStore){
    private val gson=Gson()
    private val base=BuildConfig.API_BASE_URL.trimEnd('/')
    private val http=OkHttpClient.Builder().build()
    private val mediaType="application/json; charset=utf-8".toMediaType()
    private inline fun <reified T> from(text:String):T=gson.fromJson(text,object:TypeToken<T>(){}.type)
    private suspend fun call(path:String,method:String="GET",data:Any?=null):String=withContext(Dispatchers.IO){
        val tok=session.token?:throw IOException("Sign in to LEMMIQ again")
        val req=Request.Builder().url(base+"/v2134"+path).header("Authorization","Bearer $tok")
            .header("Cache-Control","no-store")
        when(method){
            "POST"->req.post(gson.toJson(data?: emptyMap<String,Any>()).toRequestBody(mediaType))
            "PUT"->req.put(gson.toJson(data?: emptyMap<String,Any>()).toRequestBody(mediaType))
            else->req.get()
        }
        http.newCall(req.build()).execute().use {response->
            val contents=response.body?.string().orEmpty()
            if(!response.isSuccessful){
                val message=runCatching{JsonParser.parseString(contents).asJsonObject.get("detail")?.asString}.getOrNull()
                throw IOException(message?:"Professional chat HTTP ${response.code}")
            }
            contents
        }
    }
    suspend fun me():ProMeV2134=from(call("/me"))
    suspend fun saveIdentity(handle:String,name:String):ProIdentityV2134=
        from(call("/me","PUT",mapOf("handle" to handle,"stage_name" to name)))
    suspend fun saveTerms(count:Int,hours:Int):ProTermsV2134=
        from(call("/me/terms","PUT",mapOf("messages" to count,"hours" to hours)))
    suspend fun discover(q:String=""):List<ProProfileV2134> = from(call("/discover?qtext="+URLEncoder.encode(q,"UTF-8")))
    suspend fun requests():List<ProRequestV2134> = from(call("/requests"))
    suspend fun inbox():List<ProChatV2134> = from(call("/inbox"))
    suspend fun chat(tid:String):ProChatV2134=from(call("/chats/$tid"))
    suspend fun requestChat(id:String,message:String):ProRequestV2134=from(call("/profiles/$id/requests","POST",
        mapOf("message" to message,"request_key" to UUID.randomUUID().toString())))
    suspend fun act(id:Int,action:String):ProRequestV2134=from(call("/requests/$id/$action","POST"))
    suspend fun send(tid:String,message:String):ProMessageSentV2134=from(call("/chats/$tid/messages","POST",mapOf("text" to message)))
    suspend fun finish(tid:String):ProChatV2134=from(call("/chats/$tid/complete","POST",emptyMap<String,Any>()))
    suspend fun offer(tid:String,itemId:Int,q:Double):ProOfferV2134=from(call("/chats/$tid/offers","POST",
        mapOf("item_id" to itemId,"price_q" to q,"request_key" to UUID.randomUUID().toString())))
    suspend fun unlock(id:Int):Map<String,Any> = from(call("/offers/$id/unlock","POST",
        mapOf("request_key" to UUID.randomUUID().toString())))
    suspend fun uploadAvatar(uri:Uri):Unit=withContext(Dispatchers.IO){
        val tok=session.token?:throw IOException("Sign in to LEMMIQ again")
        val mime=context.contentResolver.getType(uri)?.substringBefore(';')?:throw IOException("Invalid image")
        if(mime !in listOf("image/jpeg","image/png","image/webp"))throw IOException("Choose JPG, PNG or WebP")
        val size=runCatching{context.contentResolver.query(uri,arrayOf(OpenableColumns.SIZE),null,null,null)?.use{
            if(it.moveToFirst())it.getLong(0) else -1L}?:-1L}.getOrDefault(-1L)
        if(size>5*1024*1024)throw IOException("Max 5 MB professional photo")
        val part=object:RequestBody(){
            override fun contentType()=mime.toMediaType()
            override fun contentLength()=if(size>=0)size else -1L
            override fun writeTo(sink:okio.BufferedSink){
                context.contentResolver.openInputStream(uri)?.use{src->
                    val buf=ByteArray(16384);var total=0L
                    while(true){val n=src.read(buf);if(n<0)break;total+=n
                        if(total>5*1024*1024)throw IOException("Max 5 MB")
                        sink.write(buf,0,n)}
                }?:throw IOException("Cannot read photo")
            }
        }
        val form=MultipartBody.Builder().setType(MultipartBody.FORM).addFormDataPart("file","pro-avatar",part).build()
        val request=Request.Builder().url(base+"/v2134/me/avatar").header("Authorization","Bearer $tok").post(form).build()
        http.newCall(request).execute().use{response->if(!response.isSuccessful)throw IOException("Avatar upload HTTP ${response.code}")}
        Unit
    }
}

private val ProPurple=Color(0xFF694ADD)
private val ProMuted=Color(0xFF77798F)

/** One entry point for all user-facing professional chats, creator discovery, and identity settings. */
@Composable
fun V2134ProfessionalHub(vm:LemmiqViewModel,initialTab:Int=0){
    val ctx=androidx.compose.ui.platform.LocalContext.current
    val api=remember(vm.store){ProfessionalApiV2134(ctx.applicationContext,vm.store)}
    val scope=rememberCoroutineScope()
    var tab by remember { mutableIntStateOf(initialTab) }
    var identity by remember { mutableStateOf(ProMeV2134()) }
    var profiles by remember { mutableStateOf<List<ProProfileV2134>>(emptyList()) }
    var requests by remember { mutableStateOf<List<ProRequestV2134>>(emptyList()) }
    var threads by remember { mutableStateOf<List<ProChatV2134>>(emptyList()) }
    var selected by remember { mutableStateOf<String?>(null) }
    var chat by remember { mutableStateOf<ProChatV2134?>(null) }
    var search by remember { mutableStateOf("") }
    var draft by remember { mutableStateOf("") }
    var handle by remember { mutableStateOf("") }
    var stage by remember { mutableStateOf("") }
    var count by remember { mutableStateOf("3") }
    var hours by remember { mutableStateOf("48") }
    var galleryId by remember { mutableStateOf("") }
    var offerQ by remember { mutableStateOf("") }
    var showLegacy by remember { mutableStateOf(false) }
    var showGalleryPicker by remember { mutableStateOf(false) }
    var confirmOp by remember { mutableStateOf<Pair<String,()->Unit>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var refresh by remember { mutableIntStateOf(0) }
    val picker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri:Uri?->
        if(uri!=null)scope.launch{busy=true;try{api.uploadAvatar(uri);refresh++}catch(e:Exception){error=e.message}finally{busy=false}}
    }
    fun reload(){refresh++}
    LaunchedEffect(tab,selected,refresh,showLegacy){
        if(showLegacy)return@LaunchedEffect
        busy=true;error=null
        try{
            identity=api.me()
            if(tab==0)threads=api.inbox()
            if(tab==1)requests=api.requests()
            if(tab==2)profiles=api.discover(search)
            if(tab==3){handle=identity.identity?.handle.orEmpty();stage=identity.identity?.stage_name.orEmpty()
                count=identity.terms.messages.toString();hours=identity.terms.hours.toString()}
            if(selected!=null)chat=api.chat(selected!!)
        }catch(e:Exception){error=e.message?:"Professional inbox unavailable"}
        finally{busy=false}
    }
    // Requests and active creator messages refresh while visible on Android.
    LaunchedEffect(tab,selected,showLegacy){
        while(!showLegacy && (tab==1 || selected!=null)){
            kotlinx.coroutines.delay(25000)
            if(selected==null || draft.isBlank())refresh++
        }
    }
    if(showLegacy){
        Column{TextButton({showLegacy=false;reload()}){Text("‹ Professional account")}
            V2131CreatorsAndroidScreen(vm)}
        return
    }
    Column(Modifier.fillMaxSize().background(Color(0xFFF7F7FB))){
        Row(Modifier.fillMaxWidth().background(Color(0xFF1C1839)).padding(16.dp),verticalAlignment=Alignment.CenterVertically){
            Column(Modifier.weight(1f)){
                Text("✦ Q Creator",color=Color.White,fontWeight=FontWeight.Black,fontSize=21.sp)
                Text("Professional identity · Private from personal chats",color=Color(0xFFD6D0ED),fontSize=11.sp)
            }
            if(identity.identity!=null)Text("@${identity.identity?.handle}",color=Color.White,fontSize=11.sp)
        }
        if(selected==null){
            Row(Modifier.fillMaxWidth().padding(horizontal=10.dp,vertical=4.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                OutlinedButton(onClick={showLegacy=true},modifier=Modifier.weight(1f)) { Text("✦ Creator Studio",fontSize=12.sp) }
                OutlinedButton(onClick={showGalleryPicker=true},modifier=Modifier.weight(1f),enabled=identity.creator_status=="APPROVED") { Text("My Gallery",fontSize=12.sp) }
            }
            androidx.compose.foundation.lazy.LazyRow(Modifier.padding(7.dp),horizontalArrangement=Arrangement.spacedBy(5.dp)){
                items(listOf("Creator Chats","Requests","Discover","My Professional")){name->
                    val i=listOf("Creator Chats","Requests","Discover","My Professional").indexOf(name)
                    FilterChip(selected=tab==i,onClick={tab=i},label={Text(name,fontSize=10.sp)})
                }
            }
        }
        if(busy)LinearProgressIndicator(Modifier.fillMaxWidth())
        error?.let{Text(it,color=Color(0xFFAD3645),modifier=Modifier.padding(12.dp),fontSize=12.sp)}
        if(selected!=null){
            val x=chat
            if(x!=null){
                val isCreator=x.role=="CREATOR";val p=x.paidPass
                val allowed=p?.status=="ACTIVE"&&(if(isCreator)p.creator_remaining>0 else p.fan_remaining>0)
                TextButton({selected=null;chat=null;tab=0;reload()}){Text("‹ Professional Inbox")}
                Column(Modifier.fillMaxWidth().padding(horizontal=16.dp,vertical=8.dp)){
                    Text(if(isCreator)"Fan · ${x.fan?.display_name.orEmpty()}" else x.creator.stage_name,
                        fontWeight=FontWeight.Black,fontSize=21.sp)
                    Text("@${x.creator.handle} · Professional chat only",fontSize=11.sp,color=ProMuted)
                    Text("${p?.fan_sent?:0}/${p?.max_messages?:0} fan messages · ${p?.creator_sent?:0}/${p?.max_messages?:0} replies · ${p?.status?:"READ ONLY"}",
                        fontSize=11.sp,color=ProMuted)
                }
                LazyColumn(Modifier.weight(1f).padding(horizontal=13.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
                    items(x.messages,key={it.id}){msg->
                        val mine=(msg.role=="CREATOR")==isCreator
                        Surface(color=if(mine)Color(0xFFDCD3FF) else Color.White,
                            shape=androidx.compose.foundation.shape.RoundedCornerShape(16.dp),modifier=Modifier.fillMaxWidth()){
                            Column(Modifier.padding(12.dp)){
                                if(msg.kind=="DIRECT_MEDIA"&&msg.media!=null){
                                    V2135DirectMediaBubble(vm.store,msg.media,isCreator){reload()}
                                }else if(msg.kind=="OFFER"&&msg.offer!=null){
                                    val o=msg.offer
                                    Text("🔒 Exclusive ${o.kind}",fontWeight=FontWeight.Bold)
                                    Text(o.title,fontSize=12.sp)
                                    if(o.unlocked)Text("Unlocked in Exclusive Gallery",fontSize=11.sp,color=ProMuted)
                                    else if(!isCreator)Button(onClick={confirmOp="Unlock for ${o.price_q} Q?" to {
                                        scope.launch{busy=true;try{api.unlock(o.id);reload()}catch(e:Exception){error=e.message}finally{busy=false}}}},
                                        enabled=!busy){Text("Unlock ${o.price_q} Q")}
                                }else V2138LinkedText(msg.body,Color(0xFF17182A))
                                if(msg.body.isNotBlank())TextButton(onClick={
                                    val cb=ctx.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                                    cb.setPrimaryClip(android.content.ClipData.newPlainText("LEMMIQ creator message",msg.body))
                                    android.widget.Toast.makeText(ctx,"Message copied",android.widget.Toast.LENGTH_SHORT).show()
                                }){Text("Copy message",fontSize=10.sp)}
                                Text(msg.role,fontSize=9.sp,color=ProMuted)
                            }
                        }
                    }
                }
                if(p?.status=="ACTIVE"){
                    val hint=if(isCreator){
                        if(p.creator_remaining==0)"Waiting for the fan's next message." else "You have ${p.creator_remaining} paid replies to deliver."
                    }else{
                        if(p.fan_remaining==0)"All ${p.max_messages} fan messages used. Waiting for ${p.creator_remaining} creator reply/replies."
                        else "${p.fan_remaining} fan message(s) remaining in this paid pass."
                    }
                    Text(hint,modifier=Modifier.padding(horizontal=16.dp,vertical=5.dp),fontSize=12.sp,color=ProMuted)
                    if(!isCreator && p.fan_sent>0 && p.creator_sent>0 && p.creator_sent==p.fan_sent){
                        OutlinedButton(onClick={confirmOp="Complete this paid conversation and settle its Q payment?" to {
                            scope.launch{busy=true;error=null;try{api.finish(selected!!);reload()}
                            catch(e:Exception){error=e.message}finally{busy=false}}
                        }},modifier=Modifier.fillMaxWidth().padding(horizontal=13.dp)){
                            Text("Complete pass / request another")
                        }
                    }
                }
                // V21342_ANDROID_COMPOSER: gallery above composer; Send never sits beneath the Q orb.
                // V21341: no numeric gallery ID and no personal-chat PPV endpoint.
                if(isCreator){
                    V2135CreatorMediaComposer(vm.store,selected!!){reload()}
                }
                if(isCreator){Card(Modifier.fillMaxWidth().padding(10.dp)){
                    Column(Modifier.padding(12.dp)){
                        Text("Send exclusive photo, video or album",fontSize=12.sp,fontWeight=FontWeight.Bold)
                        Text("Choose published media or upload new media immediately. Admins may audit it.",fontSize=11.sp,color=ProMuted)
                        Button(onClick={showGalleryPicker=true},modifier=Modifier.fillMaxWidth()){
                            Text("🖼 Choose from My Gallery / Upload")
                        }
                    }
                }
                }
                if(allowed){Row(Modifier.fillMaxWidth().padding(horizontal=12.dp,vertical=7.dp).imePadding(),verticalAlignment=Alignment.CenterVertically){
                    OutlinedTextField(draft,{draft=it},Modifier.weight(1f),label={Text(if(isCreator)"Reply as creator" else "Message creator")},maxLines=3)
                    Spacer(Modifier.width(6.dp))
                    Button(onClick={val value=draft.trim();draft="";scope.launch{busy=true;try{api.send(selected!!,value);reload()}
                        catch(e:Exception){error=e.message;draft=value}finally{busy=false}}},enabled=draft.isNotBlank()&&!busy){Text("Send")}
                }}else Card(Modifier.fillMaxWidth().padding(10.dp)){Column(Modifier.padding(12.dp)){
                    Text("🔒 This professional chat is read-only or awaiting a reply",fontSize=12.sp)
                    if(!isCreator && p?.status!="ACTIVE")TextButton({tab=1;selected=null;reload()}){Text("Request another paid chat")}
                }}

            }
        }else when(tab){
            0->LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(12.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                if(threads.isEmpty()&&!busy)item{Text("No professional chats yet. Personal Chats remain separate.",color=ProMuted)}
                items(threads,key={it.thread_id}){t->
                    Card(Modifier.fillMaxWidth().clickable{selected=t.thread_id;reload()}){Column(Modifier.padding(15.dp)){
                        Text(if(t.role=="CREATOR")"Fan · ${t.fan?.display_name.orEmpty()}" else t.creator.stage_name,fontWeight=FontWeight.Bold)
                        Text("@${t.creator.handle} · ${t.paidPass?.status?:"Read only"}",color=ProMuted,fontSize=11.sp)
                        Text("Open professional thread ›",color=ProPurple,fontSize=11.sp)
                    }}
                }
            }
            1->LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(12.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                if(requests.isEmpty()&&!busy)item{Text("No paid chat requests",color=ProMuted)}
                items(requests,key={it.id}){r->Card{Column(Modifier.padding(15.dp)){
                    Text(if(r.role=="FAN")r.creator?.stage_name.orEmpty() else "Fan · ${r.fan?.display_name.orEmpty()}",fontWeight=FontWeight.Bold)
                    Text("${r.amount_q} Q · ${r.status}",fontSize=11.sp,color=ProMuted)
                    Text(r.message,fontSize=12.sp)
                    Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                        if(r.role=="CREATOR"&&r.status=="REQUESTED")Button({confirmOp="Accept professional chat?" to {
                            scope.launch{busy=true;try{api.act(r.id,"accept");reload()}catch(e:Exception){error=e.message}finally{busy=false}}}}){Text("Accept")}
                        if(r.role=="FAN"&&r.status in listOf("ACCEPTED","ACTIVE")&&r.thread_id==null)Button({confirmOp="Start paid professional session?" to {
                            scope.launch{busy=true;try{val result=api.act(r.id,"confirm");selected=result.thread_id;reload()}catch(e:Exception){error=e.message}finally{busy=false}}}}){Text("Confirm & Chat")}
                        if(r.status in listOf("REQUESTED","ACCEPTED"))TextButton({confirmOp="Cancel and refund the held Q?" to {
                            scope.launch{busy=true;try{api.act(r.id,"cancel");reload()}catch(e:Exception){error=e.message}finally{busy=false}}}}){Text("Cancel")}
                        if(r.role=="FAN"&&r.status=="DELIVERED")TextButton({confirmOp="Confirm earlier paid reply and release Q?" to {
                            scope.launch{busy=true;try{api.act(r.id,"legacy-confirm");val result=api.act(r.id,"open");selected=result.thread_id;reload()}
                            catch(e:Exception){error=e.message}finally{busy=false}}}}){Text("Confirm old reply")}
                        if(r.thread_id!=null||r.status=="COMPLETED")TextButton({scope.launch{busy=true;try{
                            val result=api.act(r.id,"open");selected=result.thread_id;reload()
                        }catch(e:Exception){error=e.message}finally{busy=false}}}){Text("View Chat")}
                    }
                }}}
            }
            2->Column(Modifier.fillMaxSize()){
                Row(Modifier.padding(10.dp)){
                    OutlinedTextField(search,{search=it},Modifier.weight(1f),label={Text("Search stage name / @creator")})
                    Button({reload()},modifier=Modifier.padding(start=8.dp)){Text("Search")}
                }
                LazyColumn(Modifier.weight(1f),contentPadding=PaddingValues(10.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
                    items(profiles,key={it.public_id}){c->Card{Column(Modifier.padding(14.dp)){
                        Row(verticalAlignment=Alignment.CenterVertically){
                            val photo=c.avatar_url
                            if(photo!=null)AsyncImage(model=BuildConfig.API_BASE_URL.trimEnd('/')+photo,
                                contentDescription="Creator avatar",modifier=Modifier.size(52.dp))
                            Spacer(Modifier.width(9.dp))
                            Column {Text(c.stage_name,fontWeight=FontWeight.Bold,fontSize=18.sp)
                                Text("@${c.handle} · ${c.category}",fontSize=11.sp,color=ProMuted)}
                        }
                        if(c.bio.isNotBlank())Text(c.bio,fontSize=12.sp,maxLines=3)
                        Text("Chat: ${c.chat_q} Q",color=ProPurple,fontSize=12.sp)
                        Button(onClick={
                            val msg="Hello, I would like to chat with you."
                            confirmOp="Reserve ${c.chat_q} Q for @${c.handle}?" to {
                                scope.launch{busy=true;try{api.requestChat(c.public_id,msg);tab=1;reload()}
                                    catch(e:Exception){error=e.message}finally{busy=false}}}
                        },enabled=c.chat_q>0&&!busy){Text("Request paid chat")}
                    }}}
                }
            }
            else->Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(15.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
                Text("Personal and professional usernames are separate",fontWeight=FontWeight.Bold)
                Text("Professional ID is public to fans; your personal username, profile photo and personal Chats are not shared.",fontSize=12.sp,color=ProMuted)
                Text("Creator approval: ${identity.creator_status?:"Create a profile in Creator Studio first"}",fontSize=12.sp)
                OutlinedTextField(handle,{handle=it},label={Text("Professional @username")},singleLine=true,modifier=Modifier.fillMaxWidth())
                OutlinedTextField(stage,{stage=it},label={Text("Creator / stage name")},modifier=Modifier.fillMaxWidth())
                Button({scope.launch{busy=true;try{api.saveIdentity(handle,stage);reload()}
                    catch(e:Exception){error=e.message}finally{busy=false}}},enabled=handle.length>=3&&stage.length>=2&&!busy){Text("Save Professional Identity")}
                if(identity.identity!=null)OutlinedButton(onClick={picker.launch("image/*")}){Text("Upload separate creator photo")}
                HorizontalDivider()
                Text("Paid Chat Package",fontWeight=FontWeight.Bold)
                Row(horizontalArrangement=Arrangement.spacedBy(7.dp)){
                    OutlinedTextField(count,{count=it},Modifier.weight(1f),label={Text("Messages")})
                    OutlinedTextField(hours,{hours=it},Modifier.weight(1f),label={Text("Hours")})
                }
                Button({scope.launch{busy=true;try{api.saveTerms(count.toInt(),hours.toInt());reload()}
                    catch(e:Exception){error=e.message}finally{busy=false}}},enabled=(count.toIntOrNull()?.let{it in 1..25}==true)&&(hours.toIntOrNull()?.let{it in 1..168}==true)&&!busy){Text("Save Chat Allowance")}
                OutlinedButton({showLegacy=true},modifier=Modifier.fillMaxWidth()){Text("Open Creator Studio / Exclusive Gallery")}
                if(identity.creator_status=="APPROVED")OutlinedButton({showGalleryPicker=true},modifier=Modifier.fillMaxWidth()){Text("🖼 Manage My Media Library & Gallery")}
                Text("Set Q pricing in Creator Studio. Admins can audit or remove content after publishing. Explicit material is not enabled in this Android app.",fontSize=11.sp,color=ProMuted)
            }
        }
    }
    if(showGalleryPicker){
        V21341GalleryPicker(vm,selected,onDismiss={showGalleryPicker=false},
            onSent={showGalleryPicker=false;reload()})
    }
    confirmOp?.let{(question,action)->AlertDialog(onDismissRequest={confirmOp=null},title={Text("Confirm action")},
        text={Text(question)},confirmButton={Button(onClick={confirmOp=null;action()}){Text("Confirm")}},
        dismissButton={TextButton({confirmOp=null}){Text("Cancel")}})}
}
// V300_INSTALLED
