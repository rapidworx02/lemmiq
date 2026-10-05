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
import java.io.File
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
    var pushStatusText by mutableStateOf("Not checked")
    var pushRegistered by mutableStateOf(false)
    var groups by mutableStateOf<List<GroupDto>>(emptyList())
    var activeGroup by mutableStateOf<GroupDto?>(null)
    var groupMessages by mutableStateOf<List<GroupMessageDto>>(emptyList())
    var groupSuggestion by mutableStateOf<String?>(null)
    var groupSummary by mutableStateOf<GroupSummaryDto?>(null)
    var groupAnswer by mutableStateOf<GroupAskDto?>(null)
    var groupBusy by mutableStateOf(false)
    var statuses by mutableStateOf<List<StatusDto>>(emptyList())
    var trustHistory by mutableStateOf<List<TrustHistoryDto>>(emptyList())
    var socialBrief by mutableStateOf<SocialBriefDto?>(null)
    var callHistory by mutableStateOf<List<CallDto>>(emptyList())
    var activeCalls by mutableStateOf<List<CallDto>>(emptyList())
    var callStatus by mutableStateOf(CallStatusDto())
    var callStarting by mutableStateOf(false)
    var replyTo by mutableStateOf<MessageDto?>(null)
    var insideSearchResults by mutableStateOf<List<MessageDto>>(emptyList())
    var chatFilterMode by mutableStateOf("ALL")
    var chatSearch by mutableStateOf("")
    var privacy by mutableStateOf(PrivacyDto())
    var currentUser by mutableStateOf<UserDto?>(null)

    val listenerGranted:Boolean get()=NotificationControl.hasSystemAccess(appCtx)
    val detectedSpendingCents:Long get()=localEvents.filter{it.category=="MONEY"&&it.direction=="OUT"}.sumOf{it.amount_cents?:0L}
    val detectedIncomingCents:Long get()=localEvents.filter{it.category=="MONEY"&&it.direction=="IN"}.sumOf{it.amount_cents?:0L}


    init{if(authenticated){refreshMe();connect();refreshChats();refreshGroups();refreshStatuses();refreshTrustHistory();refreshSocialIq();registerPush();refreshExternal();refreshBusiness();refreshPrivacy()}}

    private fun auth(a:AuthResponse){
        store.token=a.token;store.userId=a.user.id;store.username=a.user.username;store.displayName=a.user.display_name
        currentUser=a.user;authenticated=true;connect();refreshChats();refreshGroups();refreshStatuses();refreshTrustHistory();refreshSocialIq();refreshInsights();refreshExternal();refreshBusiness();refreshPrivacy();registerPush()
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
        PushControl.clearAll(appCtx)
        ws?.close(1000,"logout");store.clear();authenticated=false;active=null;activeGroup=null;chats=emptyList();groups=emptyList();groupMessages=emptyList();statuses=emptyList();trustHistory=emptyList();socialBrief=null;currentUser=null
        localEvents=emptyList();externalMessages=emptyList();agentAnswer=null;agentBrief=null;remoteInsightBrief=null;businessProfile=BusinessProfileDto();businessKnowledge=emptyList();businessSuggestion=null
    }
    fun refreshMe()=viewModelScope.launch{runCatching{api.me()}.onSuccess{currentUser=it}}
    fun refreshChats()=viewModelScope.launch{runCatching{api.chats()}.onSuccess{chats=it}.onFailure{error=it.message}}
    fun search(q:String)=viewModelScope.launch{
        if(q.length<2){users=emptyList();return@launch}
        runCatching{api.search(q)}.onSuccess{users=it.filter{x->x.id!=store.userId}}.onFailure{error=it.message}
    }
    fun start(uid:Int)=viewModelScope.launch{action{
        val c=api.direct(uid);active=c;messages=api.messages(c.id);api.read(c.id);refreshChats()
    }}
    fun open(c:ChatDto)=viewModelScope.launch{
        activeGroup=null;groupMessages=emptyList();active=c;replyTo=null;suggestion=null;businessSuggestion=null;businessLearnCandidates=emptyList()
        runCatching{messages=api.messages(c.id);activeCalls=api.chatCalls(c.id);api.read(c.id);PushControl.cancelChat(appCtx,c.id)}
        runCatching{api.businessChat(c.id)}.onSuccess{bundle->activeBusinessSetting=bundle.setting;activeBusinessMemory=bundle.memory}
        refreshChats()
    }
    fun close(){active=null;activeGroup=null;messages=emptyList();groupMessages=emptyList();replyTo=null;suggestion=null;businessSuggestion=null;businessLearnCandidates=emptyList();refreshChats();refreshGroups()}
    fun send(text:String)=viewModelScope.launch{
        val c=active?:return@launch;if(text.isBlank())return@launch
        runCatching{
            val target=replyTo
            if(target!=null)api.replyMessage(c.id,text.trim(),target.id) else api.send(c.id,text.trim())
        }.onSuccess{m->
            if(messages.none{it.id==m.id})messages=messages+m
            replyTo=null;suggestion=null
            runCatching{api.updateChatPreferences(c.id,mapOf("draft_text" to ""))}
            refreshChats()
        }.onFailure{error=it.message}
    }
    fun trustCheck(text:String)=viewModelScope.launch{
        if(text.isBlank()||trustBusy)return@launch
        trustResult=null;trustError=null;trustBusy=true
        try {
            val result=api.trustCheck(text)
            trustResult=result
            runCatching{trustHistory=api.trustHistory()}
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
        if(!BuildConfig.FCM_CONFIGURED){
            pushRegistered=false
            pushStatusText="Firebase app config missing: add google-services.json"
            return
        }
        pushStatusText="Registering this phone…"
        val task=runCatching{FirebaseMessaging.getInstance().token}.getOrElse{
            pushRegistered=false;pushStatusText="Firebase token unavailable";return
        }
        task.addOnSuccessListener { token->
            viewModelScope.launch {
                runCatching{
                    if(authenticated)api.registerPush(token)
                    val s=api.pushStatus()
                    pushRegistered=s.firebase_configured && s.registered_devices>0
                    pushStatusText=when{
                        !s.firebase_configured->"Render Firebase credentials are not configured"
                        s.registered_devices<1->"This phone is not registered on the server"
                        else->"Push ready · ${s.registered_devices} registered device${if(s.registered_devices==1)"" else "s"}"
                    }
                }.onFailure{
                    pushRegistered=false
                    pushStatusText="Push registration failed: ${it.message}"
                }
            }
        }.addOnFailureListener{
            pushRegistered=false
            pushStatusText="Firebase token failed: ${it.message}"
        }
    }

    fun refreshPushStatus()=viewModelScope.launch{
        if(!BuildConfig.FCM_CONFIGURED){
            pushRegistered=false
            pushStatusText="Firebase app config missing: add google-services.json"
            return@launch
        }
        runCatching{api.pushStatus()}.onSuccess{s->
            pushRegistered=s.firebase_configured && s.registered_devices>0
            pushStatusText=when{
                !s.firebase_configured->"Render Firebase credentials are not configured"
                s.registered_devices<1->"No phone token registered yet"
                else->"Push ready · ${s.registered_devices} registered device${if(s.registered_devices==1)"" else "s"}"
            }
        }.onFailure{pushStatusText="Push status unavailable: ${it.message}"}
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



    // ---------------- V2.4 Groups ----------------
    fun refreshGroups()=viewModelScope.launch{
        runCatching{api.groups()}.onSuccess{groups=it}.onFailure{error=it.message}
    }
    fun createGroup(name:String,memberIds:List<Int>,onCreated:(GroupDto)->Unit={})=viewModelScope.launch{
        if(name.isBlank()||memberIds.isEmpty())return@launch
        groupBusy=true;error=null
        try{val g=api.createGroup(name.trim(),memberIds);groups=listOf(g)+groups.filterNot{it.id==g.id};onCreated(g)}
        catch(e:Exception){error=e.message}finally{groupBusy=false}
    }
    fun openGroup(g:GroupDto)=viewModelScope.launch{
        active=null;messages=emptyList();activeGroup=g;groupSuggestion=null;groupSummary=null;groupAnswer=null
        groupBusy=true;error=null
        try{activeGroup=api.group(g.id);groupMessages=api.groupMessages(g.id);api.readGroup(g.id)}
        catch(e:Exception){error=e.message}finally{groupBusy=false}
        refreshGroups()
    }
    fun sendGroup(text:String)=viewModelScope.launch{
        val g=activeGroup?:return@launch;if(text.isBlank())return@launch
        runCatching{api.sendGroup(g.id,text.trim())}.onSuccess{m->if(groupMessages.none{it.id==m.id})groupMessages=groupMessages+m;refreshGroups()}.onFailure{error=it.message}
    }
    fun suggestGroup()=viewModelScope.launch{
        val g=activeGroup?:return@launch;groupBusy=true
        try{groupSuggestion=api.groupSuggest(g.id).reply}catch(e:Exception){error=e.message}finally{groupBusy=false}
    }
    fun summarizeGroup()=viewModelScope.launch{
        val g=activeGroup?:return@launch;groupBusy=true
        try{groupSummary=api.groupSummary(g.id)}catch(e:Exception){error=e.message}finally{groupBusy=false}
    }
    fun askGroup(question:String)=viewModelScope.launch{
        val g=activeGroup?:return@launch;if(question.isBlank())return@launch;groupBusy=true
        try{groupAnswer=api.groupAsk(g.id,question.trim())}catch(e:Exception){error=e.message}finally{groupBusy=false}
    }
    fun saveGroupSettings(mode:String,tone:String)=viewModelScope.launch{
        val g=activeGroup?:return@launch
        try{activeGroup=api.saveGroupSettings(g.id,mode,tone);refreshGroups()}catch(e:Exception){error=e.message}
    }
    fun uploadGroupPhoto(uri:Uri)=viewModelScope.launch{
        val g=activeGroup?:return@launch
        try{
            val data=withContext(Dispatchers.IO){
                val cr=appCtx.contentResolver;var name="group.jpg"
                cr.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{c->if(c.moveToFirst())name=c.getString(0)?:name}
                val bytes=cr.openInputStream(uri)?.use{it.readBytes()}?:throw IllegalArgumentException("Cannot read group photo")
                if(bytes.size>5*1024*1024)throw IllegalArgumentException("Group photo exceeds 5 MB")
                Triple(name,cr.getType(uri)?:"image/jpeg",bytes)
            }
            activeGroup=api.uploadGroupPhoto(g.id,data.first,data.second,data.third);refreshGroups()
        }catch(e:Exception){error=e.message}
    }
    fun addGroupMember(uid:Int)=viewModelScope.launch{val g=activeGroup?:return@launch;runCatching{activeGroup=api.addGroupMember(g.id,uid);refreshGroups()}.onFailure{error=it.message}}
    fun setGroupRole(uid:Int,role:String)=viewModelScope.launch{val g=activeGroup?:return@launch;runCatching{activeGroup=api.setGroupRole(g.id,uid,role);refreshGroups()}.onFailure{error=it.message}}
    fun removeGroupMember(uid:Int)=viewModelScope.launch{val g=activeGroup?:return@launch;runCatching{api.removeGroupMember(g.id,uid);activeGroup=api.group(g.id);refreshGroups()}.onFailure{error=it.message}}

    fun uploadGroupUri(uri:Uri)=viewModelScope.launch{
        val g=activeGroup?:return@launch;groupBusy=true;error=null
        try{
            val data=withContext(Dispatchers.IO){
                val cr=appCtx.contentResolver;var name="group_attachment"
                cr.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{c->if(c.moveToFirst())name=c.getString(0)?:name}
                val bytes=cr.openInputStream(uri)?.use{it.readBytes()}?:throw IllegalArgumentException("Cannot read selected file")
                if(bytes.size>20*1024*1024)throw IllegalArgumentException("Attachment exceeds 20 MB")
                Triple(name,cr.getType(uri)?:"application/octet-stream",bytes)
            }
            val m=api.uploadGroup(g.id,data.first,data.second,data.third)
            if(groupMessages.none{it.id==m.id})groupMessages=groupMessages+m
        }catch(e:Exception){error=e.message}finally{groupBusy=false}
    }
    suspend fun groupMediaBytes(id:Int)=api.groupMediaBytes(id)

    // ---------------- Voice notes ----------------
    fun sendVoiceFile(file:File,durationMs:Int)=viewModelScope.launch{
        val c=active?:return@launch;attachmentBusy=true;error=null
        try{
            val m=api.sendVoice(c.id,withContext(Dispatchers.IO){file.readBytes()},durationMs)
            if(messages.none{it.id==m.id})messages=messages+m
            refreshChats()
        }catch(e:Exception){error=e.message}finally{file.delete();attachmentBusy=false}
    }
    fun sendGroupVoiceFile(file:File,durationMs:Int)=viewModelScope.launch{
        val g=activeGroup?:return@launch;groupBusy=true;error=null
        try{
            val m=api.sendGroupVoice(g.id,withContext(Dispatchers.IO){file.readBytes()},durationMs)
            if(groupMessages.none{it.id==m.id})groupMessages=groupMessages+m
            refreshGroups()
        }catch(e:Exception){error=e.message}finally{file.delete();groupBusy=false}
    }
    fun voiceAi(mid:Int,onReady:(VoiceAiDto)->Unit)=viewModelScope.launch{
        agentBusy=true;try{onReady(api.voiceAi(mid))}catch(e:Exception){error=e.message}finally{agentBusy=false}
    }

    // ---------------- Message actions ----------------
    fun setReply(m:MessageDto?){replyTo=m}
    fun editMessage(mid:Int,text:String)=viewModelScope.launch{runCatching{api.editMessage(mid,text)}.onSuccess{updated->messages=messages.map{if(it.id==mid)updated else it}}.onFailure{error=it.message}}
    fun deleteMessage(mid:Int,scope:String)=viewModelScope.launch{runCatching{api.deleteMessage(mid,scope);messages=api.messages(active?.id?:return@launch)}.onFailure{error=it.message}}
    fun reactMessage(mid:Int,emoji:String)=viewModelScope.launch{runCatching{api.reactMessage(mid,emoji)}.onSuccess{updated->messages=messages.map{if(it.id==mid)updated else it}}.onFailure{error=it.message}}
    fun forwardMessage(mid:Int,chatIds:List<Int>)=viewModelScope.launch{
        runCatching{api.forwardMessage(mid,chatIds);refreshChats()}.onFailure{error=it.message}
    }
    fun searchInsideChat(q:String)=viewModelScope.launch{
        val c=active?:return@launch
        if(q.length<2){insideSearchResults=emptyList();return@launch}
        runCatching{api.searchChat(c.id,q)}.onSuccess{insideSearchResults=it}.onFailure{error=it.message}
    }
    fun saveDraft(text:String)=viewModelScope.launch{active?.let{c->runCatching{api.updateChatPreferences(c.id,mapOf("draft_text" to text))}}}
    fun togglePin()=viewModelScope.launch{val c=active?:return@launch;runCatching{api.updateChatPreferences(c.id,mapOf("pinned" to !c.pinned));refreshChats()}.onFailure{error=it.message}}
    fun toggleFavourite()=viewModelScope.launch{val c=active?:return@launch;runCatching{api.updateChatPreferences(c.id,mapOf("favourite" to !c.favourite));refreshChats()}.onFailure{error=it.message}}
    fun toggleArchive()=viewModelScope.launch{val c=active?:return@launch;runCatching{api.updateChatPreferences(c.id,mapOf("archived" to !c.archived));refreshChats()}.onFailure{error=it.message}}
    fun mute8Hours()=viewModelScope.launch{val c=active?:return@launch;runCatching{api.updateChatPreferences(c.id,mapOf("muted_minutes" to 480));refreshChats()}.onFailure{error=it.message}}
    fun blockActiveUser()=viewModelScope.launch{val c=active?:return@launch;runCatching{api.blockUser(c.other_user.id)}.onFailure{error=it.message}}
    fun reportActiveUser(details:String)=viewModelScope.launch{val c=active?:return@launch;runCatching{api.reportUser(c.other_user.id,details)}.onFailure{error=it.message}}

    // ---------------- Status / Trust history / Social IQ ----------------
    fun refreshStatuses()=viewModelScope.launch{runCatching{api.statuses()}.onSuccess{statuses=it}.onFailure{error=it.message}}
    fun postStatusText(text:String)=viewModelScope.launch{if(text.isBlank())return@launch;runCatching{api.postStatusText(text.trim());refreshStatuses()}.onFailure{error=it.message}}
    fun uploadStatusUri(uri:Uri)=viewModelScope.launch{
        try{
            val data=withContext(Dispatchers.IO){
                val cr=appCtx.contentResolver;var name="status_media"
                cr.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{c->if(c.moveToFirst())name=c.getString(0)?:name}
                val bytes=cr.openInputStream(uri)?.use{it.readBytes()}?:throw IllegalArgumentException("Cannot read status media")
                if(bytes.size>20*1024*1024)throw IllegalArgumentException("Status media exceeds 20 MB")
                Triple(name,cr.getType(uri)?:"application/octet-stream",bytes)
            }
            api.postStatusMedia(data.first,data.second,data.third);refreshStatuses()
        }catch(e:Exception){error=e.message}
    }
    suspend fun statusMediaBytes(id:Int)=api.statusMediaBytes(id)
    fun viewStatus(id:Int,onReady:(StatusDto)->Unit)=viewModelScope.launch{
        runCatching{api.viewStatus(id)}.onSuccess{st->onReady(st);refreshStatuses()}.onFailure{error=it.message}
    }
    fun replyToStatus(userId:Int,statusText:String)=viewModelScope.launch{
        try{
            val c=api.direct(userId)
            val draft="Replied to your status: ${statusText.take(240)}"
            api.updateChatPreferences(c.id,mapOf("draft_text" to draft))
            activeGroup=null;active=c.copy(draft_text=draft);messages=api.messages(c.id);activeCalls=api.chatCalls(c.id);api.read(c.id)
            refreshChats()
        }catch(e:Exception){error=e.message}
    }
    fun deleteStatus(id:Int)=viewModelScope.launch{runCatching{api.deleteStatus(id);refreshStatuses()}.onFailure{error=it.message}}
    fun refreshTrustHistory(q:String="")=viewModelScope.launch{runCatching{api.trustHistory(q)}.onSuccess{trustHistory=it}.onFailure{error=it.message}}
    fun deleteTrustHistory(id:Int)=viewModelScope.launch{runCatching{api.deleteTrustHistory(id);refreshTrustHistory()}.onFailure{error=it.message}}
    fun clearTrustHistory()=viewModelScope.launch{runCatching{api.clearTrustHistory();trustHistory=emptyList()}.onFailure{error=it.message}}
    fun refreshSocialIq()=viewModelScope.launch{runCatching{api.socialBrief()}.onSuccess{socialBrief=it}.onFailure{error=it.message}}
    fun scanSocialIq()=viewModelScope.launch{agentBusy=true;try{api.scanSocial();socialBrief=api.socialBrief()}catch(e:Exception){error=e.message}finally{agentBusy=false}}
    fun deleteSocialMemory(id:Int)=viewModelScope.launch{runCatching{api.deleteSocialMemory(id);socialBrief=api.socialBrief()}.onFailure{error=it.message}}

    fun uploadProfilePhoto(uri:Uri)=viewModelScope.launch{
        try{
            val data=withContext(Dispatchers.IO){
                val cr=appCtx.contentResolver;var name="profile.jpg"
                cr.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{c->if(c.moveToFirst())name=c.getString(0)?:name}
                val bytes=cr.openInputStream(uri)?.use{it.readBytes()}?:throw IllegalArgumentException("Cannot read photo")
                if(bytes.size>5*1024*1024)throw IllegalArgumentException("Profile photo exceeds 5 MB")
                Triple(name,cr.getType(uri)?:"image/jpeg",bytes)
            }
            currentUser=api.uploadProfilePhoto(data.first,data.second,data.third)
            refreshChats();refreshGroups();refreshStatuses()
        }catch(e:Exception){error=e.message}
    }
    fun removeProfilePhoto()=viewModelScope.launch{runCatching{currentUser=api.removeProfilePhoto();refreshChats()}.onFailure{error=it.message}}
    fun refreshPrivacy()=viewModelScope.launch{runCatching{api.privacy()}.onSuccess{privacy=it}}
    fun savePrivacy(p:PrivacyDto)=viewModelScope.launch{runCatching{privacy=api.savePrivacy(p)}.onFailure{error=it.message}}

    // ---------------- Calls ----------------
    fun refreshCalls()=viewModelScope.launch{runCatching{callStatus=api.callStatus();callHistory=api.callHistory()}.onFailure{error=it.message}}
    fun startVoiceCall(cid:Int,onReady:(CallJoinDto)->Unit)=viewModelScope.launch{
        if(callStarting){error="A call is already starting";return@launch}
        callStarting=true;busy=true;error=null
        try{onReady(api.startCall(cid))}
        catch(e:Exception){error=e.message}
        finally{busy=false;callStarting=false}
    }

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
                if(map["type"]?.toString()=="message_update"){
                    val m=gson.fromJson(gson.toJson(map["data"]),MessageDto::class.java)
                    viewModelScope.launch{
                        if(active?.id==m.chat_id)messages=messages.map{if(it.id==m.id)m else it}
                        refreshChats()
                    }
                }
                if(map["type"]?.toString()=="group_message"){
                    val gid=(map["group_id"] as? Number)?.toInt()?:return
                    val m=gson.fromJson(gson.toJson(map["data"]),GroupMessageDto::class.java)
                    viewModelScope.launch{
                        if(activeGroup?.id==gid && groupMessages.none{it.id==m.id})groupMessages=groupMessages+m
                        refreshGroups()
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
