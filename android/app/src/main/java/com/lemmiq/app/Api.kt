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
    suspend fun clearInsights(){req(b("$base/insights/events").delete().build())}

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

    fun socket(listener:WebSocketListener):WebSocket{
        val u="$base/ws?token=${store.token.orEmpty()}".replace("http://","ws://").replace("https://","wss://")
        return client.newWebSocket(Request.Builder().url(u).build(),listener)
    }
}
