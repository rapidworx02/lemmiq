package com.lemmiq.app

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

class SessionStore(context:Context){
    private val p=context.getSharedPreferences("lemmiq",Context.MODE_PRIVATE)
    var token:String?; get()=p.getString("token",null); set(v){p.edit().putString("token",v).apply()}
    var userId:Int; get()=p.getInt("uid",-1); set(v){p.edit().putInt("uid",v).apply()}
    var username:String?; get()=p.getString("username",null); set(v){p.edit().putString("username",v).apply()}
    var displayName:String?; get()=p.getString("display",null); set(v){p.edit().putString("display",v).apply()}
    fun clear(){p.edit().clear().apply()}
}

class Api(private val store:SessionStore){
    private val client=OkHttpClient()
    private val mediaClient=client.newBuilder()
        .connectTimeout(25,TimeUnit.SECONDS)
        .readTimeout(120,TimeUnit.SECONDS)
        .callTimeout(180,TimeUnit.SECONDS)
        .build()
    private val trustClient=client.newBuilder()
        .connectTimeout(25,TimeUnit.SECONDS)
        .readTimeout(90,TimeUnit.SECONDS)
        .callTimeout(105,TimeUnit.SECONDS)
        .build()
    private val gson=Gson()
    private val json="application/json; charset=utf-8".toMediaType()
    private val base=BuildConfig.API_BASE_URL.trimEnd('/')
    val serverUrl:String get()=base

    private fun b(url:String):Request.Builder{
        val x=Request.Builder().url(url)
        store.token?.let{x.header("Authorization","Bearer $it")}
        return x
    }
    private suspend fun req(r:Request,forTrust:Boolean=false):String=withContext(Dispatchers.IO){
        (if(forTrust)trustClient else client).newCall(r).execute().use{
            val body=it.body?.string().orEmpty()
            if(!it.isSuccessful) throw IOException(
                runCatching{gson.fromJson(body,Map::class.java)["detail"]?.toString()}.getOrNull()
                    ?: "HTTP ${it.code}"
            )
            body
        }
    }
    suspend fun register(u:String,n:String,p:String):AuthResponse{
        val rb=gson.toJson(mapOf("username" to u,"display_name" to n,"password" to p)).toRequestBody(json)
        return gson.fromJson(req(Request.Builder().url("$base/register").post(rb).build()),AuthResponse::class.java)
    }
    suspend fun login(u:String,p:String):AuthResponse{
        val rb=gson.toJson(mapOf("username" to u,"password" to p)).toRequestBody(json)
        return gson.fromJson(req(Request.Builder().url("$base/login").post(rb).build()),AuthResponse::class.java)
    }
    suspend fun me():UserDto = gson.fromJson(req(b("$base/me").get().build()),UserDto::class.java)
    suspend fun chats():List<ChatDto>{
        val t=req(b("$base/chats").get().build())
        return gson.fromJson(t,object:TypeToken<List<ChatDto>>(){}.type)
    }
    suspend fun search(q:String):List<UserDto>{
        val t=req(b("$base/users/search?q=${URLEncoder.encode(q,"UTF-8")}").get().build())
        return gson.fromJson(t,object:TypeToken<List<UserDto>>(){}.type)
    }
    suspend fun direct(uid:Int):ChatDto{
        val rb=gson.toJson(mapOf("user_id" to uid)).toRequestBody(json)
        return gson.fromJson(req(b("$base/chats/direct").post(rb).build()),ChatDto::class.java)
    }
    suspend fun messages(cid:Int):List<MessageDto>{
        val t=req(b("$base/chats/$cid/messages").get().build())
        return gson.fromJson(t,object:TypeToken<List<MessageDto>>(){}.type)
    }
    suspend fun send(cid:Int,text:String):MessageDto{
        val rb=gson.toJson(mapOf("text" to text)).toRequestBody(json)
        return gson.fromJson(req(b("$base/chats/$cid/messages").post(rb).build()),MessageDto::class.java)
    }
    suspend fun read(cid:Int){
        req(b("$base/chats/$cid/read").post("{}".toRequestBody(json)).build())
    }
    suspend fun settings(cid:Int,cat:String,mode:String,tone:String):ChatDto{
        val rb=gson.toJson(mapOf("category" to cat,"ai_mode" to mode,"tone" to tone)).toRequestBody(json)
        return gson.fromJson(req(b("$base/chats/$cid/settings").put(rb).build()),ChatDto::class.java)
    }
    suspend fun suggest(cid:Int):SuggestResponse{
        return gson.fromJson(req(b("$base/chats/$cid/suggest").post("{}".toRequestBody(json)).build()),SuggestResponse::class.java)
    }
    suspend fun moments():List<MomentDto>{
        val t=req(b("$base/moments").get().build())
        return gson.fromJson(t,object:TypeToken<List<MomentDto>>(){}.type)
    }
    suspend fun postMoment(text:String):MomentDto{
        val rb=gson.toJson(mapOf("text" to text)).toRequestBody(json)
        return gson.fromJson(req(b("$base/moments").post(rb).build()),MomentDto::class.java)
    }
    suspend fun trustCheck(text:String):TrustResult{
        val rb=gson.toJson(mapOf("text" to text)).toRequestBody(json)
        return gson.fromJson(req(b("$base/trust/check").post(rb).build(),forTrust=true),TrustResult::class.java)
    }

    suspend fun agentBrief():AgentBrief {
        return gson.fromJson(req(b("$base/agent/brief").get().build()),AgentBrief::class.java)
    }

    suspend fun agentProfile(days:Int=30):StyleProfile {
        return gson.fromJson(
            req(b("$base/agent/profile?days=$days").get().build()),
            StyleProfile::class.java
        )
    }

    suspend fun askAgent(question:String,days:Int=30,external:List<ExternalSnippet> = emptyList()):AgentAnswer {
        val rb=gson.toJson(mapOf("question" to question,"days" to days,"external_context" to external)).toRequestBody(json)
        return gson.fromJson(
            req(b("$base/agent/ask").post(rb).build()),
            AgentAnswer::class.java
        )
    }

    suspend fun summarizeChat(cid:Int):ChatSummary {
        return gson.fromJson(
            req(b("$base/agent/chats/$cid/summary").get().build()),
            ChatSummary::class.java
        )
    }

    suspend fun searchMemory(q:String):List<MemorySearchItem> {
        val encoded=URLEncoder.encode(q,"UTF-8")
        val t=req(b("$base/agent/search?q=$encoded").get().build())
        return gson.fromJson(t,object:TypeToken<List<MemorySearchItem>>(){}.type)
    }

    suspend fun qDailyBrief():QDailyBriefDto =
        gson.fromJson(req(b("$base/v26/q/brief").get().build()),QDailyBriefDto::class.java)

    suspend fun qDo(question:String):QDoResponseDto {
        val rb=gson.toJson(mapOf("question" to question)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v26/q/do").post(rb).build()),QDoResponseDto::class.java)
    }

    suspend fun qCoordination():QCoordinationListDto =
        gson.fromJson(req(b("$base/v26/q/coordination").get().build()),QCoordinationListDto::class.java)

    suspend fun createQCoordination(targetIds:List<Int>,kind:String,prompt:String,options:List<String>):QCoordinationCreateDto {
        val rb=gson.toJson(mapOf(
            "target_user_ids" to targetIds,"kind" to kind,"prompt" to prompt,"options" to options
        )).toRequestBody(json)
        return gson.fromJson(req(b("$base/v26/q/coordination").post(rb).build()),QCoordinationCreateDto::class.java)
    }

    suspend fun respondQCoordination(id:Int,choice:String,note:String):QCoordinationDto {
        val rb=gson.toJson(mapOf("choice" to choice,"note" to note)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v26/q/coordination/$id/respond").post(rb).build()),QCoordinationDto::class.java)
    }


    suspend fun pushInsight(e:PhoneEvent){
        val payload=mapOf(
            "client_event_id" to e.client_event_id, "category" to e.category,
            "source" to e.source, "title" to e.title, "detail" to e.detail,
            "amount_cents" to e.amount_cents, "direction" to e.direction,
            "occurred_at" to e.occurred_at)
        req(b("$base/insights/events").post(gson.toJson(payload).toRequestBody(json)).build())
    }
    suspend fun insightBrief():InsightBrief {
        return gson.fromJson(req(b("$base/insights/brief").get().build()),InsightBrief::class.java)
    }
    suspend fun updateInsight(e:PhoneEvent):PhoneEvent {
        val payload=mapOf(
            "category" to e.category,"source" to e.source,"title" to e.title,"detail" to e.detail,
            "amount_cents" to e.amount_cents,"direction" to e.direction,"occurred_at" to e.occurred_at
        )
        val id=URLEncoder.encode(e.client_event_id,"UTF-8")
        return gson.fromJson(
            req(b("$base/insights/client-events/$id").put(gson.toJson(payload).toRequestBody(json)).build()),
            PhoneEvent::class.java
        )
    }
    suspend fun deleteInsight(clientEventId:String){
        val id=URLEncoder.encode(clientEventId,"UTF-8")
        req(b("$base/insights/client-events/$id").delete().build())
    }
    suspend fun clearInsights(scope:String="ALL"){
        req(b("$base/insights/events?scope=${URLEncoder.encode(scope,"UTF-8")}").delete().build())
    }

    suspend fun upload(cid:Int,name:String,mime:String,bytes:ByteArray):MessageDto {
        val body=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file",name,bytes.toRequestBody(mime.toMediaType()))
            .build()
        return gson.fromJson(withContext(Dispatchers.IO){
            mediaClient.newCall(b("$base/chats/$cid/attachments").post(body).build()).execute().use{res->
                val response=res.body?.string().orEmpty()
                if(!res.isSuccessful)throw IOException("Upload HTTP ${res.code}: ${response.take(220)}")
                response
            }
        },MessageDto::class.java)
    }

    suspend fun shareContact(cid:Int,name:String,phone:String):MessageDto {
        val jsonBody=gson.toJson(mapOf("display_name" to name,"phone" to phone)).toRequestBody(json)
        return gson.fromJson(req(b("$base/chats/$cid/contacts").post(jsonBody).build()),MessageDto::class.java)
    }

    suspend fun mediaBytes(id:Int):ByteArray=withContext(Dispatchers.IO){
        mediaClient.newCall(b("$base/media/$id").get().build()).execute().use { response->
            if(!response.isSuccessful)throw IOException("Media HTTP ${response.code}")
            response.body?.bytes()?:throw IOException("Empty attachment")
        }
    }

    suspend fun registerPush(token:String){
        val reqBody=gson.toJson(mapOf("token" to token)).toRequestBody(json)
        req(b("$base/push/register").post(reqBody).build())
    }
    suspend fun pushStatus():PushStatusDto {
        return gson.fromJson(req(b("$base/push/status").get().build()),PushStatusDto::class.java)
    }

    suspend fun unregisterPush(token:String,bearer:String?=null){
        val reqBody=gson.toJson(mapOf("token" to token)).toRequestBody(json)
        val builder=Request.Builder().url("$base/push/unregister")
        (bearer?:store.token)?.let{builder.header("Authorization","Bearer $it")}
        req(builder.delete(reqBody).build())
    }

    suspend fun externalSuggest(contact:String,source:String,context:List<ExternalSnippet>):SuggestResponse {
        val reqBody=gson.toJson(mapOf("source" to source,"contact" to contact,"messages" to context,"tone" to "Natural")).toRequestBody(json)
        return gson.fromJson(req(b("$base/external/suggest").post(reqBody).build()),SuggestResponse::class.java)
    }



    suspend fun businessProfile():BusinessProfileDto {
        return gson.fromJson(req(b("$base/business/profile").get().build()),BusinessProfileDto::class.java)
    }

    suspend fun saveBusinessProfile(p:BusinessProfileDto):BusinessProfileDto {
        val body=gson.toJson(p).toRequestBody(json)
        return gson.fromJson(req(b("$base/business/profile").put(body).build()),BusinessProfileDto::class.java)
    }

    suspend fun businessKnowledge():List<BusinessKnowledgeDto> {
        val t=req(b("$base/business/knowledge").get().build())
        return gson.fromJson(t,object:TypeToken<List<BusinessKnowledgeDto>>(){}.type)
    }

    suspend fun addBusinessKnowledge(category:String,title:String,content:String,source:String="Manual"):BusinessKnowledgeDto {
        val body=gson.toJson(mapOf("category" to category,"title" to title,"content" to content,"source" to source,
            "approved" to true,"active" to true)).toRequestBody(json)
        return gson.fromJson(req(b("$base/business/knowledge").post(body).build()),BusinessKnowledgeDto::class.java)
    }

    suspend fun deleteBusinessKnowledge(id:Int){
        req(b("$base/business/knowledge/$id").delete().build())
    }

    suspend fun uploadBusinessKnowledge(name:String,mime:String,bytes:ByteArray):BusinessKnowledgeDto {
        val body=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file",name,bytes.toRequestBody(mime.toMediaType())).build()
        val text=withContext(Dispatchers.IO){
            mediaClient.newCall(b("$base/business/knowledge/upload").post(body).build()).execute().use{res->
                val response=res.body?.string().orEmpty()
                if(!res.isSuccessful)throw IOException("Knowledge upload HTTP ${res.code}: ${response.take(220)}")
                response
            }
        }
        return gson.fromJson(text,BusinessKnowledgeDto::class.java)
    }

    suspend fun businessChat(cid:Int):BusinessChatBundle {
        return gson.fromJson(req(b("$base/business/chats/$cid").get().build()),BusinessChatBundle::class.java)
    }

    suspend fun saveBusinessChat(cid:Int,enabled:Boolean,mode:String,label:String):BusinessChatSettingDto {
        val rb=gson.toJson(mapOf("enabled" to enabled,"mode" to mode,"customer_label" to label)).toRequestBody(json)
        return gson.fromJson(req(b("$base/business/chats/$cid").put(rb).build()),BusinessChatSettingDto::class.java)
    }

    suspend fun saveBusinessMemory(cid:Int,notes:String,tags:String):BusinessMemoryDto {
        val rb=gson.toJson(mapOf("notes" to notes,"tags" to tags)).toRequestBody(json)
        return gson.fromJson(req(b("$base/business/chats/$cid/memory").put(rb).build()),BusinessMemoryDto::class.java)
    }

    suspend fun businessSuggest(cid:Int):BusinessSuggestionDto {
        return gson.fromJson(req(b("$base/business/chats/$cid/suggest").post("{}".toRequestBody(json)).build()),BusinessSuggestionDto::class.java)
    }

    suspend fun businessLearn(cid:Int):BusinessLearnResponse {
        return gson.fromJson(req(b("$base/business/chats/$cid/learn").post("{}".toRequestBody(json)).build()),BusinessLearnResponse::class.java)
    }

    suspend fun approveBusinessLearning(x:BusinessLearnCandidate):BusinessKnowledgeDto {
        val rb=gson.toJson(x).toRequestBody(json)
        return gson.fromJson(req(b("$base/business/learn/approve").post(rb).build()),BusinessKnowledgeDto::class.java)
    }


    // ---------- LEMMIQ V2.4 ----------
    suspend fun groups():List<GroupDto>{
        val t=req(b("$base/v24/groups").get().build())
        return gson.fromJson(t,object:TypeToken<List<GroupDto>>(){}.type)
    }
    suspend fun group(gid:Int):GroupDto =
        gson.fromJson(req(b("$base/v24/groups/$gid").get().build()),GroupDto::class.java)
    suspend fun createGroup(name:String,memberIds:List<Int>):GroupDto{
        val rb=gson.toJson(mapOf("name" to name,"member_ids" to memberIds)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/groups").post(rb).build()),GroupDto::class.java)
    }
    suspend fun groupMessages(gid:Int):List<GroupMessageDto>{
        val t=req(b("$base/v24/groups/$gid/messages").get().build())
        return gson.fromJson(t,object:TypeToken<List<GroupMessageDto>>(){}.type)
    }
    suspend fun readGroup(gid:Int){req(b("$base/v24/groups/$gid/read").post("{}".toRequestBody(json)).build())}
    suspend fun sendGroup(gid:Int,text:String):GroupMessageDto{
        val rb=gson.toJson(mapOf("text" to text)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/groups/$gid/messages").post(rb).build()),GroupMessageDto::class.java)
    }
    suspend fun groupSuggest(gid:Int):SuggestResponse =
        gson.fromJson(req(b("$base/v24/groups/$gid/suggest").post("{}".toRequestBody(json)).build()),SuggestResponse::class.java)
    suspend fun groupSummary(gid:Int):GroupSummaryDto =
        gson.fromJson(req(b("$base/v24/groups/$gid/summary").post("{}".toRequestBody(json)).build()),GroupSummaryDto::class.java)
    suspend fun groupAsk(gid:Int,question:String):GroupAskDto{
        val rb=gson.toJson(mapOf("question" to question)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/groups/$gid/ask").post(rb).build()),GroupAskDto::class.java)
    }
    suspend fun uploadGroupPhoto(gid:Int,name:String,mime:String,bytes:ByteArray):GroupDto{
        val body=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file",name,bytes.toRequestBody(mime.toMediaType())).build()
        val text=withContext(Dispatchers.IO){
            mediaClient.newCall(b("$base/v24/groups/$gid/photo").post(body).build()).execute().use{res->
                val response=res.body?.string().orEmpty()
                if(!res.isSuccessful)throw IOException("Group photo HTTP ${res.code}: ${response.take(220)}")
                response
            }
        }
        return gson.fromJson(text,GroupDto::class.java)
    }
    suspend fun saveGroupSettings(gid:Int,mode:String,tone:String):GroupDto{
        val rb=gson.toJson(mapOf("ai_mode" to mode,"tone" to tone)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/groups/$gid/settings").put(rb).build()),GroupDto::class.java)
    }
    suspend fun addGroupMember(gid:Int,uid:Int):GroupDto{
        val rb=gson.toJson(mapOf("user_id" to uid)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/groups/$gid/members").post(rb).build()),GroupDto::class.java)
    }
    suspend fun setGroupRole(gid:Int,uid:Int,role:String):GroupDto{
        val rb=gson.toJson(mapOf("role" to role)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/groups/$gid/members/$uid").put(rb).build()),GroupDto::class.java)
    }
    suspend fun removeGroupMember(gid:Int,uid:Int){req(b("$base/v24/groups/$gid/members/$uid").delete().build())}
    suspend fun uploadGroup(gid:Int,name:String,mime:String,bytes:ByteArray):GroupMessageDto{
        val body=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file",name,bytes.toRequestBody(mime.toMediaType())).build()
        val text=withContext(Dispatchers.IO){
            mediaClient.newCall(b("$base/v24/groups/$gid/attachments").post(body).build()).execute().use{res->
                val response=res.body?.string().orEmpty()
                if(!res.isSuccessful)throw IOException("Group upload HTTP ${res.code}: ${response.take(220)}")
                response
            }
        }
        return gson.fromJson(text,GroupMessageDto::class.java)
    }
    suspend fun groupMediaBytes(id:Int):ByteArray=withContext(Dispatchers.IO){
        mediaClient.newCall(b("$base/v24/group-media/$id").get().build()).execute().use{res->
            if(!res.isSuccessful)throw IOException("Group media HTTP ${res.code}")
            res.body?.bytes()?:throw IOException("Empty group media")
        }
    }

    suspend fun sendVoice(cid:Int,bytes:ByteArray,durationMs:Int):MessageDto{
        val body=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("duration_ms",durationMs.toString())
            .addFormDataPart("file","voice-note.m4a",bytes.toRequestBody("audio/mp4".toMediaType())).build()
        val text=withContext(Dispatchers.IO){
            mediaClient.newCall(b("$base/v24/chats/$cid/voice").post(body).build()).execute().use{res->
                val response=res.body?.string().orEmpty()
                if(!res.isSuccessful)throw IOException("Voice HTTP ${res.code}: ${response.take(220)}")
                response
            }
        }
        return gson.fromJson(text,MessageDto::class.java)
    }
    suspend fun sendGroupVoice(gid:Int,bytes:ByteArray,durationMs:Int):GroupMessageDto{
        val body=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("duration_ms",durationMs.toString())
            .addFormDataPart("file","voice-note.m4a",bytes.toRequestBody("audio/mp4".toMediaType())).build()
        val text=withContext(Dispatchers.IO){
            mediaClient.newCall(b("$base/v24/groups/$gid/voice").post(body).build()).execute().use{res->
                val response=res.body?.string().orEmpty()
                if(!res.isSuccessful)throw IOException("Group voice HTTP ${res.code}: ${response.take(220)}")
                response
            }
        }
        return gson.fromJson(text,GroupMessageDto::class.java)
    }
    suspend fun voiceAi(mid:Int):VoiceAiDto =
        gson.fromJson(req(b("$base/v24/voice/$mid/ai").post("{}".toRequestBody(json)).build()),VoiceAiDto::class.java)

    suspend fun callStatus():CallStatusDto =
        gson.fromJson(req(b("$base/v24/calls/status").get().build()),CallStatusDto::class.java)
    suspend fun callDetail(id:String):CallDto =
        gson.fromJson(req(b("$base/v24/calls/$id").get().build()),CallDto::class.java)
    suspend fun startCall(cid:Int):CallJoinDto{
        val rb=gson.toJson(mapOf("chat_id" to cid)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/calls/start").post(rb).build()),CallJoinDto::class.java)
    }
    suspend fun joinCall(id:String):CallJoinDto =
        gson.fromJson(req(b("$base/v24/calls/$id/join").post("{}".toRequestBody(json)).build()),CallJoinDto::class.java)
    suspend fun declineCall(id:String){req(b("$base/v24/calls/$id/decline").post("{}".toRequestBody(json)).build())}
    suspend fun endCall(id:String){req(b("$base/v24/calls/$id/end").post("{}".toRequestBody(json)).build())}
    suspend fun chatCalls(cid:Int):List<CallDto>{
        val t=req(b("$base/v24/chats/$cid/calls").get().build())
        return gson.fromJson(t,object:TypeToken<List<CallDto>>(){}.type)
    }
    suspend fun callHistory():List<CallDto>{
        val t=req(b("$base/v24/calls").get().build())
        return gson.fromJson(t,object:TypeToken<List<CallDto>>(){}.type)
    }

    suspend fun statuses():List<StatusDto>{
        val t=req(b("$base/v24/status").get().build())
        return gson.fromJson(t,object:TypeToken<List<StatusDto>>(){}.type)
    }
    suspend fun postStatusText(text:String):StatusDto{
        val rb=gson.toJson(mapOf("text" to text)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/status/text").post(rb).build()),StatusDto::class.java)
    }
    suspend fun postStatusMedia(name:String,mime:String,bytes:ByteArray,caption:String=""):StatusDto{
        val body=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("caption",caption)
            .addFormDataPart("file",name,bytes.toRequestBody(mime.toMediaType())).build()
        val text=withContext(Dispatchers.IO){
            mediaClient.newCall(b("$base/v24/status/media").post(body).build()).execute().use{res->
                val response=res.body?.string().orEmpty()
                if(!res.isSuccessful)throw IOException("Status upload HTTP ${res.code}: ${response.take(220)}")
                response
            }
        }
        return gson.fromJson(text,StatusDto::class.java)
    }
    suspend fun viewStatus(id:Int):StatusDto =
        gson.fromJson(req(b("$base/v24/status/$id/view").post("{}".toRequestBody(json)).build()),StatusDto::class.java)
    suspend fun deleteStatus(id:Int){req(b("$base/v24/status/$id").delete().build())}
    suspend fun statusMediaBytes(id:Int):ByteArray=withContext(Dispatchers.IO){
        mediaClient.newCall(b("$base/v24/status/$id/media").get().build()).execute().use{res->
            if(!res.isSuccessful)throw IOException("Status media HTTP ${res.code}")
            res.body?.bytes()?:throw IOException("Empty status media")
        }
    }


    suspend fun trustCheckV24(text:String,refresh:Boolean=false):TrustHistoryDto{
        val rb=gson.toJson(mapOf("text" to text)).toRequestBody(json)
        return gson.fromJson(req(b("$base/trust/check${if(refresh)"?refresh=true" else ""}").post(rb).build(),forTrust=true),TrustHistoryDto::class.java)
    }
    suspend fun trustHistory(q:String=""):List<TrustHistoryDto>{
        val url="$base/trust/history"+if(q.isBlank())"" else "?q=${URLEncoder.encode(q,"UTF-8")}"
        val t=req(b(url).get().build())
        return gson.fromJson(t,object:TypeToken<List<TrustHistoryDto>>(){}.type)
    }
    suspend fun deleteTrustHistory(id:Int){req(b("$base/trust/history/$id").delete().build())}
    suspend fun clearTrustHistory(){req(b("$base/trust/history").delete().build())}

    suspend fun socialBrief():SocialBriefDto =
        gson.fromJson(req(b("$base/v24/social-iq/brief").get().build()),SocialBriefDto::class.java)
    suspend fun scanSocial():SocialScanDto =
        gson.fromJson(req(b("$base/v24/social-iq/scan").post("{}".toRequestBody(json)).build()),SocialScanDto::class.java)
    suspend fun deleteSocialMemory(id:Int){req(b("$base/v24/social-iq/memories/$id").delete().build())}

    suspend fun uploadProfilePhoto(name:String,mime:String,bytes:ByteArray):UserDto{
        val body=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file",name,bytes.toRequestBody(mime.toMediaType())).build()
        val text=withContext(Dispatchers.IO){
            mediaClient.newCall(b("$base/v24/profile/avatar").post(body).build()).execute().use{res->
                val response=res.body?.string().orEmpty()
                if(!res.isSuccessful)throw IOException("Profile photo HTTP ${res.code}: ${response.take(220)}")
                response
            }
        }
        return gson.fromJson(text,UserDto::class.java)
    }
    suspend fun removeProfilePhoto():UserDto =
        gson.fromJson(req(b("$base/v24/profile/avatar").delete().build()),UserDto::class.java)

    suspend fun editMessage(mid:Int,text:String):MessageDto{
        val rb=gson.toJson(mapOf("text" to text)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/messages/$mid").put(rb).build()),MessageDto::class.java)
    }
    suspend fun deleteMessage(mid:Int,scope:String){req(b("$base/v24/messages/$mid?scope=$scope").delete().build())}
    suspend fun reactMessage(mid:Int,emoji:String):MessageDto{
        val rb=gson.toJson(mapOf("emoji" to emoji)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/messages/$mid/reaction").post(rb).build()),MessageDto::class.java)
    }
    suspend fun replyMessage(cid:Int,text:String,replyTo:Int):MessageDto{
        val rb=gson.toJson(mapOf("text" to text,"reply_to_message_id" to replyTo)).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/chats/$cid/reply").post(rb).build()),MessageDto::class.java)
    }
    suspend fun forwardMessage(mid:Int,chatIds:List<Int>){
        val rb=gson.toJson(mapOf("chat_ids" to chatIds)).toRequestBody(json)
        req(b("$base/v24/messages/$mid/forward").post(rb).build())
    }
    suspend fun searchChat(cid:Int,q:String):List<MessageDto>{
        val t=req(b("$base/v24/chats/$cid/search?q=${URLEncoder.encode(q,"UTF-8")}").get().build())
        return gson.fromJson(t,object:TypeToken<List<MessageDto>>(){}.type)
    }
    suspend fun chatPreferences(cid:Int):ChatPrefDto =
        gson.fromJson(req(b("$base/v24/chats/$cid/preferences").get().build()),ChatPrefDto::class.java)
    suspend fun updateChatPreferences(cid:Int,payload:Map<String,Any?>):ChatPrefDto{
        val rb=gson.toJson(payload).toRequestBody(json)
        return gson.fromJson(req(b("$base/v24/chats/$cid/preferences").put(rb).build()),ChatPrefDto::class.java)
    }
    suspend fun privacy():PrivacyDto =
        gson.fromJson(req(b("$base/v24/privacy").get().build()),PrivacyDto::class.java)
    suspend fun savePrivacy(p:PrivacyDto):PrivacyDto =
        gson.fromJson(req(b("$base/v24/privacy").put(gson.toJson(p).toRequestBody(json)).build()),PrivacyDto::class.java)
    suspend fun blockUser(uid:Int){req(b("$base/v24/users/$uid/block").post("{}".toRequestBody(json)).build())}
    suspend fun unblockUser(uid:Int){req(b("$base/v24/users/$uid/block").delete().build())}
    suspend fun reportUser(uid:Int,details:String){
        val rb=gson.toJson(mapOf("reason" to "OTHER","details" to details)).toRequestBody(json)
        req(b("$base/v24/users/$uid/report").post(rb).build())
    }

    fun socket(listener:WebSocketListener):WebSocket{
        val u="$base/ws?token=${store.token.orEmpty()}".replace("http://","ws://").replace("https://","wss://")
        return client.newWebSocket(Request.Builder().url(u).build(),listener)
    }
}
