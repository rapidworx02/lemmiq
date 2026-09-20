package com.lemmiq.app

import android.app.Application
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
    val listenerGranted:Boolean get()=NotificationControl.hasSystemAccess(appCtx)
    val detectedSpendingCents:Long get()=localEvents.filter{it.category=="MONEY"&&it.direction=="OUT"}.sumOf{it.amount_cents?:0L}
    val detectedIncomingCents:Long get()=localEvents.filter{it.category=="MONEY"&&it.direction=="IN"}.sumOf{it.amount_cents?:0L}


    init{if(authenticated){connect();refreshChats()}}

    private fun auth(a:AuthResponse){
        store.token=a.token;store.userId=a.user.id;store.username=a.user.username;store.displayName=a.user.display_name
        authenticated=true;connect();refreshChats();refreshInsights()
    }
    fun register(u:String,n:String,p:String)=viewModelScope.launch{action{auth(api.register(u.trim().lowercase(),n.trim(),p))}}
    fun login(u:String,p:String)=viewModelScope.launch{action{auth(api.login(u.trim().lowercase(),p))}}
    fun logout(){
        // Notification consent does not automatically carry across messenger accounts.
        NotificationControl.setCapture(appCtx,false)
        NotificationControl.setSync(appCtx,false)
        reloadNotificationSettings()
        ws?.close(1000,"logout");store.clear();authenticated=false;active=null;chats=emptyList()
        localEvents=emptyList();agentAnswer=null;agentBrief=null;remoteInsightBrief=null
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
        active=c;suggestion=null
        runCatching{messages=api.messages(c.id);api.read(c.id)}
        refreshChats()
    }
    fun close(){active=null;messages=emptyList();suggestion=null;refreshChats()}
    fun send(text:String)=viewModelScope.launch{
        val c=active?:return@launch;if(text.isBlank())return@launch
        runCatching{api.send(c.id,text.trim())}.onSuccess{m->
            if(messages.none{it.id==m.id})messages=messages+m
            suggestion=null;refreshChats()
        }.onFailure{error=it.message}
    }
    fun trustCheck(text:String)=viewModelScope.launch{
        if(text.isBlank())return@launch
        trustBusy=true;error=null
        try{trustResult=api.trustCheck(text)}catch(e:Exception){error=e.message}finally{trustBusy=false}
    }
    fun clearTrust(){trustResult=null}
    fun suggest()=viewModelScope.launch{
        val c=active?:return@launch
        action{suggestion=api.suggest(c.id).reply}
    }
    fun saveSettings(cat:String,mode:String,tone:String)=viewModelScope.launch{
        val c=active?:return@launch
        action{active=api.settings(c.id,cat,mode,tone);refreshChats()}
    }

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
    fun deleteInsights()=viewModelScope.launch {
        insightWorking=true
        try {
            // Delete server copy before deleting local copy; repeatable if network fails.
            api.clearInsights()
            PhoneEventDb(appCtx).use{it.clear(store.userId)}
            localEvents=emptyList();remoteInsightBrief=null
        }catch(e:Exception){error="Could not clear synced events: ${e.message}"}
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
        try{agentAnswer=api.askAgent(question.trim(),30)}catch(e:Exception){error=e.message}finally{agentBusy=false}
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
