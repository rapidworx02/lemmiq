package com.lemmiq.app

import android.app.Application
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import android.webkit.MimeTypeMap
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

import androidx.core.app.NotificationManagerCompat
import java.util.UUID
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import androidx.compose.runtime.*
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

class LemmiqViewModel(app:Application):AndroidViewModel(app){
    private val appCtx=app.applicationContext
    val store=SessionStore(app)
    private val api=Api(store)
    private val gson=Gson()
    private var ws:WebSocket?=null
    val serverUrl:String get()=api.serverUrl

    var authenticated by mutableStateOf(store.token!=null)
    var busy by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var chats by mutableStateOf<List<ChatDto>>(emptyList())
    var users by mutableStateOf<List<UserDto>>(emptyList())
    var messages by mutableStateOf<List<MessageDto>>(emptyList())
    var moments by mutableStateOf<List<MomentDto>>(emptyList())
    var active by mutableStateOf<ChatDto?>(null)
    var suggestion by mutableStateOf<String?>(null)
    var trustResult by mutableStateOf<TrustResult?>(null)
    var trustError by mutableStateOf<String?>(null)
    var trustBusy by mutableStateOf(false)
    var socketStatus by mutableStateOf("offline")
    var agentBrief by mutableStateOf<AgentBrief?>(null)
    var styleProfile by mutableStateOf<StyleProfile?>(null)
    var agentAnswer by mutableStateOf<AgentAnswer?>(null)
    var chatSummary by mutableStateOf<ChatSummary?>(null)
    var memoryResults by mutableStateOf<List<MemorySearchItem>>(emptyList())
    var agentBusy by mutableStateOf(false)
    var notificationCapture by mutableStateOf(NotificationControl.enabled(appCtx))
    var insightSync by mutableStateOf(NotificationControl.sync(appCtx))
    var retentionDays by mutableIntStateOf(NotificationControl.keepDays(appCtx))
    var permittedApps by mutableStateOf(NotificationControl.allowedApps(appCtx))
    var permittedCategories by mutableStateOf(NotificationControl.allowedCategories(appCtx))
    var appChoices by mutableStateOf<List<AppChoice>>(emptyList())
    var localEvents by mutableStateOf<List<PhoneEvent>>(emptyList())
    var remoteInsightBrief by mutableStateOf<InsightBrief?>(null)
    var insightWorking by mutableStateOf(false)
    var externalEnabled by mutableStateOf(ExternalConsent.enabled(appCtx))
    var externalWhatsApp by mutableStateOf(ExternalConsent.source(appCtx,"WhatsApp"))
    var externalSms by mutableStateOf(ExternalConsent.source(appCtx,"SMS"))
    var externalQ by mutableStateOf(ExternalConsent.includeInQ(appCtx))
    var externalDays by mutableIntStateOf(ExternalConsent.days(appCtx))
    var externalMessages by mutableStateOf<List<ExternalSnippet>>(emptyList())
    var externalDraft by mutableStateOf<String?>(null)
    var attachmentBusy by mutableStateOf(false)
    var businessProfile by mutableStateOf(BusinessProfileDto())
    var businessKnowledge by mutableStateOf<List<BusinessKnowledgeDto>>(emptyList())
    var activeBusinessSetting by mutableStateOf(BusinessChatSettingDto())
    var activeBusinessMemory by mutableStateOf(BusinessMemoryDto())
    var businessSuggestion by mutableStateOf<BusinessSuggestionDto?>(null)
    var businessLearnCandidates by mutableStateOf<List<BusinessLearnCandidate>>(emptyList())
    var businessBusy by mutableStateOf(false)

    val listenerGranted:Boolean get()=NotificationControl.hasSystemAccess(appCtx)
    val detectedSpendingCents:Long get()=localEvents.filter{it.category=="MONEY"&&it.direction=="OUT"}.sumOf{it.amount_cents?:0L}
    val detectedIncomingCents:Long get()=localEvents.filter{it.category=="MONEY"&&it.direction=="IN"}.sumOf{it.amount_cents?:0L}


    init{if(authenticated){connect();refreshChats();registerPush();refreshExternal();refreshBusiness()}}

    private fun auth(a:AuthResponse){
        store.token=a.token;store.userId=a.user.id;store.username=a.user.username;store.displayName=a.user.display_name
        authenticated=true;connect();refreshChats();refreshInsights();refreshExternal();refreshBusiness();registerPush()
    }
    fun register(u:String,n:String,p:String)=viewModelScope.launch{action{auth(api.register(u.trim().lowercase(),n.trim(),p))}}
    fun login(u:String,p:String)=viewModelScope.launch{action{auth(api.login(u.trim().lowercase(),p))}}
    fun logout(){
        // Revoke this device token before clearing credentials, best-effort.
        val credential=store.token
        val token=runCatching{FirebaseMessaging.getInstance().token}.getOrNull()
        token?.addOnSuccessListener {t->viewModelScope.launch {runCatching{api.unregisterPush(t,credential)} } }
        ExternalConsent.setEnabled(appCtx,false)
        ExternalConsent.setQ(appCtx,false)
        reloadExternalSettings()
        // Notification consent does not automatically carry across messenger accounts.
        NotificationControl.setCapture(appCtx,false)
        NotificationControl.setSync(appCtx,false)
        reloadNotificationSettings()
        ws?.close(1000,"logout");store.clear();authenticated=false;active=null;chats=emptyList()
        localEvents=emptyList();externalMessages=emptyList();agentAnswer=null;agentBrief=null;remoteInsightBrief=null;businessProfile=BusinessProfileDto();businessKnowledge=emptyList();businessSuggestion=null
    }
    fun refreshChats()=viewModelScope.launch{runCatching{api.chats()}.onSuccess{chats=it}.onFailure{error=it.message}}
    fun search(q:String)=viewModelScope.launch{
        if(q.length<2){users=emptyList();return@launch}
        runCatching{api.search(q)}.onSuccess{users=it.filter{x->x.id!=store.userId}}.onFailure{error=it.message}
    }
    fun start(uid:Int)=viewModelScope.launch{action{
        val c=api.direct(uid);active=c;messages=api.messages(c.id);api.read(c.id);refreshChats()
    }}
    fun open(c:ChatDto)=viewModelScope.launch{
        active=c;suggestion=null;businessSuggestion=null;businessLearnCandidates=emptyList()
        runCatching{messages=api.messages(c.id);api.read(c.id)}
        runCatching{api.businessChat(c.id)}.onSuccess{bundle->activeBusinessSetting=bundle.setting;activeBusinessMemory=bundle.memory}
        refreshChats()
    }
    fun close(){active=null;messages=emptyList();suggestion=null;businessSuggestion=null;businessLearnCandidates=emptyList();refreshChats()}
    fun send(text:String)=viewModelScope.launch{
        val c=active?:return@launch;if(text.isBlank())return@launch
        runCatching{api.send(c.id,text.trim())}.onSuccess{m->
            if(messages.none{it.id==m.id})messages=messages+m
            suggestion=null;refreshChats()
        }.onFailure{error=it.message}
    }
    fun trustCheck(text:String)=viewModelScope.launch{
        if(text.isBlank()||trustBusy)return@launch
        trustResult=null;trustError=null;trustBusy=true
        try {
            val result=api.trustCheck(text)
            trustResult=result
        } catch(e:Exception) {
            trustError=when(e){
                is java.net.SocketTimeoutException -> "Fact Check timed out. Render may be waking up, or the AI/web search took too long. Retry in a moment."
                else -> e.message ?: "Could not complete the Trust check. Please try again."
            }
        } finally { trustBusy=false }
    }
    fun clearTrust(){trustResult=null;trustError=null}
    fun discardSuggestion(){suggestion=null}
    fun suggest()=viewModelScope.launch{
        val c=active?:return@launch
        action{suggestion=api.suggest(c.id).reply}
    }
    fun saveSettings(cat:String,mode:String,tone:String)=viewModelScope.launch{
        val c=active?:return@launch
        action{active=api.settings(c.id,cat,mode,tone);refreshChats()}
    }

    fun registerPush(){
        // Firebase is optional until the developer supplies google-services.json.
        runCatching{FirebaseMessaging.getInstance().token}.getOrNull()?.addOnSuccessListener { token->
            viewModelScope.launch { runCatching{if(authenticated)api.registerPush(token)} }
        }
    }

    fun uploadUri(uri:Uri){
        val cid=active?.id?:return
        viewModelScope.launch {
            attachmentBusy=true;error=null
            try {
                val data=withContext(Dispatchers.IO){
                    val cr=appCtx.contentResolver
                    var name="attachment"
                    cr.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{cursor->
                        if(cursor.moveToFirst())name=cursor.getString(0)?:name
                    }
                    val bytes=cr.openInputStream(uri)?.use{input->
                        val out=java.io.ByteArrayOutputStream()
                        val buffer=ByteArray(65536)
                        while(true){
                            val size=input.read(buffer)
                            if(size<0)break
                            out.write(buffer,0,size)
                            if(out.size()>20*1024*1024)throw IllegalArgumentException("Attachment exceeds 20 MB")
                        }
                        out.toByteArray()
                    }?:throw IllegalArgumentException("Cannot read selected file")
                    val extension=name.substringAfterLast('.' ,"").lowercase()
                    val mime=when(cr.getType(uri)?.lowercase()){
                        "application/octet-stream",null -> when(extension){
                            "jpg","jpeg"->"image/jpeg";"png"->"image/png";"webp"->"image/webp"
                            "mp4"->"video/mp4";"webm"->"video/webm";"mov"->"video/quicktime"
                            "pdf"->"application/pdf";"txt"->"text/plain";"csv"->"text/csv"
                            "zip"->"application/zip";"docx"->"application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            "xlsx"->"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            else->"application/octet-stream"
                        }
                        else->cr.getType(uri)!!.lowercase()
                    }
                    Triple(name,mime,bytes)
                }
                val m=api.upload(cid,data.first,data.second,data.third)
                if(active?.id==cid && messages.none{it.id==m.id})messages=messages+m
                refreshChats()
            }catch(e:Exception){error=e.message?:"Upload failed"}
            finally{attachmentBusy=false}
        }
    }

    fun shareContact(name:String,phone:String){
        val cid=active?.id?:return
        viewModelScope.launch{attachmentBusy=true;error=null
            try{val m=api.shareContact(cid,name,phone)
                if(active?.id==cid && messages.none{it.id==m.id})messages=messages+m
                refreshChats()
            }catch(e:Exception){error=e.message}finally{attachmentBusy=false}
        }
    }
    suspend fun mediaBytes(id:Int)=api.mediaBytes(id)

    fun reloadExternalSettings(){
        externalEnabled=ExternalConsent.enabled(appCtx)
        externalWhatsApp=ExternalConsent.source(appCtx,"WhatsApp")
        externalSms=ExternalConsent.source(appCtx,"SMS")
        externalQ=ExternalConsent.includeInQ(appCtx)
        externalDays=ExternalConsent.days(appCtx)
    }
    fun setExternalEnabled(v:Boolean){ExternalConsent.setEnabled(appCtx,v);if(!v)ExternalConsent.setQ(appCtx,false);reloadExternalSettings();refreshExternal()}
    fun setExternalSource(name:String,v:Boolean){ExternalConsent.setSource(appCtx,name,v);reloadExternalSettings();refreshExternal()}
    fun setExternalQ(v:Boolean){ExternalConsent.setQ(appCtx,v);reloadExternalSettings()}
    fun setExternalDays(days:Int){ExternalConsent.setDays(appCtx,days);reloadExternalSettings();refreshExternal()}
    fun refreshExternal(){
        if(store.userId<1)return
        externalMessages=ExternalChatDb(appCtx).use{it.list(store.userId,externalDays)}
    }
    fun clearExternal(){
        if(store.userId>0)ExternalChatDb(appCtx).use{it.clear(store.userId)}
        externalMessages=emptyList();externalDraft=null
    }
    fun suggestExternal(item:ExternalSnippet){
        viewModelScope.launch{agentBusy=true;error=null;externalDraft=null
            try{
                refreshExternal()
                val recent=externalMessages.filter{it.source==item.source && it.contact==item.contact}
                    .take(15).reversed()
                externalDraft=api.externalSuggest(item.contact,item.source,recent).reply
            }catch(e:Exception){error=e.message}finally{agentBusy=false}
        }
    }
    fun discardExternalDraft(){externalDraft=null}

    fun reloadNotificationSettings(){
        notificationCapture=NotificationControl.enabled(appCtx)
        insightSync=NotificationControl.sync(appCtx)
        permittedApps=NotificationControl.allowedApps(appCtx)
        permittedCategories=NotificationControl.allowedCategories(appCtx)
        retentionDays=NotificationControl.keepDays(appCtx)
    }
    fun loadInstalledApps(){appChoices=NotificationControl.appChoices(appCtx)}
    fun setCapture(v:Boolean){NotificationControl.setCapture(appCtx,v);reloadNotificationSettings()}
    fun setSync(v:Boolean){NotificationControl.setSync(appCtx,v);reloadNotificationSettings();if(v)syncInsights()}
    fun setRetention(v:Int){NotificationControl.setDays(appCtx,v);reloadNotificationSettings();refreshInsights()}
    fun setApp(pkg:String,v:Boolean){NotificationControl.setApp(appCtx,pkg,v);reloadNotificationSettings()}
    fun setApps(packages:Set<String>,v:Boolean){NotificationControl.setApps(appCtx,packages,v);reloadNotificationSettings()}
    fun setCategory(cat:String,v:Boolean){NotificationControl.setCategory(appCtx,cat,v);reloadNotificationSettings()}
    fun refreshInsights(){
        if(store.userId<1)return
        PhoneEventDb(appCtx).use{db->
            db.prune(retentionDays)
            localEvents=db.list(store.userId,retentionDays)
        }
        if(insightSync)syncInsights()
    }
    fun addManualExpense(amount:String,title:String,incoming:Boolean=false){
        val cents=amount.replace(",","").toBigDecimalOrNull()?.multiply(java.math.BigDecimal(100))?.toLong()
        if(cents==null||cents<=0||title.isBlank()) {error="Enter a description and positive amount";return}
        val stamp=SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'",Locale.US).apply{
            timeZone=java.util.TimeZone.getTimeZone("UTC")}.format(Date())
        val e=PhoneEvent(UUID.randomUUID().toString(),"MONEY","Manual entry",title.take(100),
            "Entered by you",cents,if(incoming)"IN" else "OUT",stamp)
        PhoneEventDb(appCtx).use{it.insert(store.userId,e)}
        refreshInsights()
    }
    fun syncInsights()=viewModelScope.launch{
        if(!insightSync||store.userId<1||insightWorking)return@launch
        insightWorking=true
        try {
            val pending=PhoneEventDb(appCtx).use{it.list(store.userId,retentionDays,true).take(30).reversed()}
            for(e in pending){
                api.pushInsight(e)
                PhoneEventDb(appCtx).use{it.markSynced(store.userId,e.client_event_id)}
            }
            remoteInsightBrief=api.insightBrief()
            PhoneEventDb(appCtx).use{localEvents=it.list(store.userId,retentionDays)}
        }catch(e:Exception){error="Insight sync: ${e.message}"}finally{insightWorking=false}
    }
    fun resetInsightData(scope:String)=viewModelScope.launch {
        insightWorking=true;error=null
        try {
            api.clearInsights(scope)
            PhoneEventDb(appCtx).use{db->
                when(scope.uppercase()){
                    "MONEY"->db.clearCategory(store.userId,"MONEY")
                    "ACTIVITY"->db.clearNonMoney(store.userId)
                    else->db.clear(store.userId)
                }
                localEvents=db.list(store.userId,retentionDays)
            }
            remoteInsightBrief=runCatching{api.insightBrief()}.getOrNull()
        }catch(e:Exception){error="Could not reset detected data: ${e.message}"}
        finally{insightWorking=false}
    }

    fun deleteInsights()=resetInsightData("ALL")

    fun deleteInsightEvent(e:PhoneEvent)=viewModelScope.launch{
        insightWorking=true;error=null
        try{
            if(e.synced)api.deleteInsight(e.client_event_id)
            PhoneEventDb(appCtx).use{db->
                db.delete(store.userId,e.client_event_id)
                localEvents=db.list(store.userId,retentionDays)
            }
            remoteInsightBrief=runCatching{api.insightBrief()}.getOrNull()
        }catch(ex:Exception){error="Could not delete detected event: ${ex.message}"}
        finally{insightWorking=false}
    }

    fun editInsightEvent(original:PhoneEvent,category:String,source:String,title:String,detail:String,
                         amountText:String,direction:String,occurredAt:String)=viewModelScope.launch{
        insightWorking=true;error=null
        try{
            val cents=amountText.trim().replace(",","").takeIf{it.isNotBlank()}
                ?.toBigDecimalOrNull()?.multiply(java.math.BigDecimal(100))?.toLong()
            val updated=original.copy(
                category=category,source=source.take(80),title=title.take(100),detail=detail.take(220),
                amount_cents=cents,direction=direction,occurred_at=occurredAt
            )
            if(original.synced)api.updateInsight(updated)
            PhoneEventDb(appCtx).use{db->
                db.update(store.userId,updated)
                localEvents=db.list(store.userId,retentionDays)
            }
            remoteInsightBrief=runCatching{api.insightBrief()}.getOrNull()
        }catch(ex:Exception){error="Could not update detected event: ${ex.message}"}
        finally{insightWorking=false}
    }

    fun refreshAgent()=viewModelScope.launch{
        agentBusy=true
        try{
            agentBrief=api.agentBrief()
            styleProfile=api.agentProfile(30)
        }catch(e:Exception){error=e.message}finally{agentBusy=false}
    }

    fun askAgent(question:String)=viewModelScope.launch{
        if(question.isBlank())return@launch
        agentBusy=true;error=null
        try{
            if(externalQ && externalEnabled)refreshExternal()
            val context=if(externalQ && externalEnabled)externalMessages.take(30).reversed() else emptyList()
            agentAnswer=api.askAgent(question.trim(),30,context)
        }catch(e:Exception){error=e.message}finally{agentBusy=false}
    }

    fun summarizeActiveChat()=viewModelScope.launch{
        val c=active?:return@launch
        agentBusy=true;error=null
        try{chatSummary=api.summarizeChat(c.id)}catch(e:Exception){error=e.message}finally{agentBusy=false}
    }

    fun searchMemory(q:String)=viewModelScope.launch{
        if(q.length<2){memoryResults=emptyList();return@launch}
        try{memoryResults=api.searchMemory(q)}catch(e:Exception){error=e.message}
    }

    fun clearAgentAnswer(){agentAnswer=null}
    fun clearChatSummary(){chatSummary=null}

    fun refreshMoments()=viewModelScope.launch{runCatching{api.moments()}.onSuccess{moments=it}}
    fun postMoment(t:String)=viewModelScope.launch{if(t.isNotBlank())action{api.postMoment(t.trim());moments=api.moments()}}


    fun refreshBusiness()=viewModelScope.launch{
        runCatching{
            businessProfile=api.businessProfile()
            businessKnowledge=api.businessKnowledge()
        }.onFailure{error=it.message}
    }

    fun saveBusinessProfile(p:BusinessProfileDto)=viewModelScope.launch{
        businessBusy=true;error=null
        try{businessProfile=api.saveBusinessProfile(p);businessKnowledge=api.businessKnowledge()}
        catch(e:Exception){error=e.message}finally{businessBusy=false}
    }

    fun addBusinessKnowledge(category:String,title:String,content:String)=viewModelScope.launch{
        if(title.isBlank()||content.isBlank())return@launch
        businessBusy=true;error=null
        try{api.addBusinessKnowledge(category,title.trim(),content.trim());businessKnowledge=api.businessKnowledge()}
        catch(e:Exception){error=e.message}finally{businessBusy=false}
    }

    fun deleteBusinessKnowledge(id:Int)=viewModelScope.launch{
        businessBusy=true;error=null
        try{api.deleteBusinessKnowledge(id);businessKnowledge=api.businessKnowledge()}
        catch(e:Exception){error=e.message}finally{businessBusy=false}
    }

    fun uploadBusinessKnowledge(uri:Uri)=viewModelScope.launch{
        businessBusy=true;error=null
        try{
            val data=withContext(Dispatchers.IO){
                val cr=appCtx.contentResolver
                var name="business_document"
                cr.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{cursor->if(cursor.moveToFirst())name=cursor.getString(0)?:name}
                val bytes=cr.openInputStream(uri)?.use{input->
                    val out=java.io.ByteArrayOutputStream();val buffer=ByteArray(65536)
                    while(true){val n=input.read(buffer);if(n<0)break;out.write(buffer,0,n);if(out.size()>5*1024*1024)throw IllegalArgumentException("Business document exceeds 5 MB")}
                    out.toByteArray()
                }?:throw IllegalArgumentException("Cannot read selected document")
                val ext=name.substringAfterLast('.',"").lowercase()
                val mime=cr.getType(uri)?.lowercase()?:when(ext){"pdf"->"application/pdf";"docx"->"application/vnd.openxmlformats-officedocument.wordprocessingml.document";"csv"->"text/csv";"md"->"text/markdown";else->"text/plain"}
                Triple(name,mime,bytes)
            }
            api.uploadBusinessKnowledge(data.first,data.second,data.third)
            businessKnowledge=api.businessKnowledge()
        }catch(e:Exception){error=e.message?:"Business document upload failed"}finally{businessBusy=false}
    }

    fun refreshBusinessChat()=viewModelScope.launch{
        val cid=active?.id?:return@launch
        runCatching{api.businessChat(cid)}.onSuccess{bundle->activeBusinessSetting=bundle.setting;activeBusinessMemory=bundle.memory}.onFailure{error=it.message}
    }

    fun saveBusinessChat(enabled:Boolean,mode:String,label:String)=viewModelScope.launch{
        val cid=active?.id?:return@launch
        businessBusy=true;error=null
        try{activeBusinessSetting=api.saveBusinessChat(cid,enabled,mode,label)}catch(e:Exception){error=e.message}finally{businessBusy=false}
    }

    fun saveBusinessMemory(notes:String,tags:String)=viewModelScope.launch{
        val cid=active?.id?:return@launch
        businessBusy=true;error=null
        try{activeBusinessMemory=api.saveBusinessMemory(cid,notes,tags)}catch(e:Exception){error=e.message}finally{businessBusy=false}
    }

    fun suggestBusiness()=viewModelScope.launch{
        val cid=active?.id?:return@launch
        businessBusy=true;error=null
        try{businessSuggestion=api.businessSuggest(cid)}catch(e:Exception){error=e.message}finally{businessBusy=false}
    }

    fun discardBusinessSuggestion(){businessSuggestion=null}

    fun learnBusinessFromActiveChat()=viewModelScope.launch{
        val cid=active?.id?:return@launch
        businessBusy=true;error=null
        try{businessLearnCandidates=api.businessLearn(cid).candidates}catch(e:Exception){error=e.message}finally{businessBusy=false}
    }

    fun approveBusinessLearning(x:BusinessLearnCandidate)=viewModelScope.launch{
        businessBusy=true;error=null
        try{
            api.approveBusinessLearning(x)
            businessKnowledge=api.businessKnowledge()
            businessLearnCandidates=businessLearnCandidates.filterNot{it==x}
        }catch(e:Exception){error=e.message}finally{businessBusy=false}
    }

    private suspend fun action(block:suspend()->Unit){busy=true;error=null;try{block()}catch(e:Exception){error=e.message}finally{busy=false}}
    private fun connect(){
        ws?.cancel();socketStatus="connecting"
        ws=api.socket(object:WebSocketListener(){
            override fun onOpen(webSocket:WebSocket,response:Response){socketStatus="online"}
            override fun onMessage(webSocket:WebSocket,text:String){
                val map=runCatching{gson.fromJson(text,Map::class.java)}.getOrNull()?:return
                if(map["type"]?.toString()=="message"){
                    val m=gson.fromJson(gson.toJson(map["data"]),MessageDto::class.java)
                    viewModelScope.launch{
                        active?.let{c->
                            if(c.id==m.chat_id){
                                if(messages.none{it.id==m.id})messages=messages+m
                                if(m.sender_id!=store.userId)runCatching{api.read(c.id)}
                            }
                        }
                        refreshChats()
                    }
                }
            }
            override fun onFailure(webSocket:WebSocket,t:Throwable,response:Response?){
                socketStatus="offline"
                viewModelScope.launch{delay(2500);if(authenticated)connect()}
            }
        })
    }
}
