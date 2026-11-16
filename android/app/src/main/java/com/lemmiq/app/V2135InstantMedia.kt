package com.lemmiq.app

import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.google.gson.JsonParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okio.BufferedSink
import java.io.File
import java.io.IOException
import java.util.UUID

/** New independent professional media: never uses personal-chat IDs or normal media routes. */
internal data class ProDirectMediaV2135(
    val id:Int=0,val kind:String="FREE",val media_kind:String="PHOTO",val price_q:Double=0.0,
    val unlocked:Boolean=false,val status:String="VISIBLE",val media_url:String?=null
)

internal class ProInstantMediaApiV2135(private val store:SessionStore,private val context:android.content.Context){
    private val base=BuildConfig.API_BASE_URL.trimEnd('/')
    private val http=OkHttpClient.Builder().build()
    private fun builder(path:String):Request.Builder{
        val token=store.token?:throw IOException("Please sign in again")
        return Request.Builder().url(base+path).header("Authorization","Bearer $token")
            .header("Cache-Control","no-store")
    }
    private fun parseError(response:Response):IOException{
        val body=response.body?.string().orEmpty()
        val msg=runCatching { JsonParser.parseString(body).asJsonObject.get("detail")?.asString }.getOrNull()
        return IOException(msg?:"Creator media request failed (${response.code})")
    }
    suspend fun upload(threadId:String,uri:Uri,paid:Boolean,price:Double):Unit=withContext(Dispatchers.IO){
        val cr=context.contentResolver
        val mime=cr.getType(uri)?.substringBefore(';')?.lowercase()?:throw IOException("Unknown media type")
        if(mime !in listOf("image/jpeg","image/png","image/webp","video/mp4","video/webm"))
            throw IOException("Use JPEG, PNG, WebP, MP4 or WebM")
        val limit=if(mime.startsWith("image/"))20L*1024*1024 else 100L*1024*1024
        val length=runCatching{cr.query(uri,arrayOf(OpenableColumns.SIZE),null,null,null)?.use{
            if(it.moveToFirst())it.getLong(0) else -1L}?:-1L}.getOrDefault(-1L)
        if(length>limit)throw IOException("Media exceeds size limit")
        val body=object:RequestBody(){
            override fun contentType()=mime.toMediaType()
            override fun contentLength()=if(length>=0)length else -1L
            override fun writeTo(sink:BufferedSink){
                val input=cr.openInputStream(uri)?:throw IOException("Unable to open media")
                input.use{src->
                    val buffer=ByteArray(65536);var total=0L
                    while(true){val n=src.read(buffer);if(n<0)break
                        total+=n;if(total>limit)throw IOException("Media exceeds size limit")
                        sink.write(buffer,0,n)
                    }
                }
            }
        }
        val form=MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("kind",if(paid)"PPV" else "FREE")
            .addFormDataPart("price_q",if(paid)price.toString() else "0")
            .addFormDataPart("file","creator-media",body).build()
        http.newCall(builder("/v2135/chats/$threadId/media").post(form).build()).execute().use{
            if(!it.isSuccessful)throw parseError(it)
        }
    }
    suspend fun unlock(mediaId:Int):Unit=withContext(Dispatchers.IO){
        val json="{\"request_key\":\"${UUID.randomUUID()}\"}"
        http.newCall(builder("/v2135/media/$mediaId/unlock")
            .post(json.toRequestBody("application/json".toMediaType())).build()).execute().use{
            if(!it.isSuccessful)throw parseError(it)
        }
    }
    suspend fun report(mediaId:Int,reason:String):Unit=withContext(Dispatchers.IO){
        val safe=reason.replace("\\","\\\\").replace("\"","\\\"")
        val json="{\"reason\":\"$safe\"}"
        http.newCall(builder("/v2135/media/$mediaId/report")
            .post(json.toRequestBody("application/json".toMediaType())).build()).execute().use{
            if(!it.isSuccessful)throw parseError(it)
        }
    }
    suspend fun downloadVideo(mediaId:Int):Pair<File,String> = withContext(Dispatchers.IO){
        val dir=File(context.cacheDir,"creator_media").apply{mkdirs()}
        dir.listFiles()?.filter{it.lastModified()<System.currentTimeMillis()-3600000}?.forEach{it.delete()}
        http.newCall(builder("/v2135/media/$mediaId/file").get().build()).execute().use{res->
            if(!res.isSuccessful)throw parseError(res)
            val mime=res.header("Content-Type")?.substringBefore(';')?:"video/mp4"
            if(mime !in listOf("video/mp4","video/webm"))throw IOException("Unexpected video type")
            val f=File.createTempFile("creator_",if(mime=="video/webm")".webm" else ".mp4",dir)
            try{
                f.outputStream().use{output->
                    val src=res.body?.byteStream()?:throw IOException("Empty video")
                    src.use{input->
                        val buf=ByteArray(65536);var total=0L
                        while(true){val n=input.read(buf);if(n<0)break;total+=n
                            if(total>105L*1024*1024)throw IOException("Video too large")
                            output.write(buf,0,n)
                        }
                    }
                }
                f to mime
            }catch(e:Exception){f.delete();throw e}
        }
    }
}

@Composable
internal fun V2135CreatorMediaComposer(store:SessionStore,threadId:String,onSent:()->Unit){
    val ctx=LocalContext.current
    val api=remember(store){ProInstantMediaApiV2135(store,ctx.applicationContext)}
    val scope=rememberCoroutineScope()
    var uri by remember { mutableStateOf<Uri?>(null) }
    var paid by remember { mutableStateOf(false) }
    var price by remember { mutableStateOf("25") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val imagePicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri=it}
    val videoPicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri=it}
    Column(Modifier.fillMaxWidth().padding(horizontal=12.dp, vertical=7.dp)) {
        Row(horizontalArrangement=Arrangement.spacedBy(7.dp)){
            OutlinedButton(onClick={imagePicker.launch("image/*")},modifier=Modifier.weight(1f)){Text("＋ Photo")}
            OutlinedButton(onClick={videoPicker.launch("video/*")},modifier=Modifier.weight(1f)){Text("＋ Video")}
        }
        error?.let{Text(it,color=MaterialTheme.colorScheme.error)}
    }
    if(uri!=null) AlertDialog(onDismissRequest={if(!busy)uri=null},
        title={Text("Send to professional chat")},
        text={Column(verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text("Select free or locked PPV. Only non-explicit content is permitted.")
            Row{FilterChip(!paid,{paid=false},label={Text("Free")});Spacer(Modifier.width(9.dp))
                FilterChip(paid,{paid=true},label={Text("PPV")})}
            if(paid)OutlinedTextField(price,{price=it},label={Text("Price in Q")},singleLine=true)
            Text("Media is stored privately. LEMMIQ moderators can inspect and quarantine uploads.",style=MaterialTheme.typography.bodySmall)
        }},
        confirmButton={Button(enabled=!busy&&(!paid||(price.toDoubleOrNull()?.let{it>0}==true)),onClick={
            val selected=uri?:return@Button
            scope.launch {busy=true;error=null
                try{api.upload(threadId,selected,paid,price.toDoubleOrNull()?:0.0);uri=null;onSent()}
                catch(e:Exception){error=e.message}finally{busy=false}
            }
        }){Text(if(busy)"Uploading…" else "Send media")}},
        dismissButton={TextButton(enabled=!busy,onClick={uri=null}){Text("Cancel")}}
    )
}

@Composable
internal fun V2135DirectMediaBubble(store:SessionStore,media:ProDirectMediaV2135,isCreator:Boolean,onChanged:()->Unit){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    val api=remember(store){ProInstantMediaApiV2135(store,ctx.applicationContext)}
    var loading by remember(media.id){mutableStateOf(false)}
    var error by remember(media.id){mutableStateOf<String?>(null)}
    var reportDialog by remember(media.id){mutableStateOf(false)}
    Column(verticalArrangement=Arrangement.spacedBy(6.dp)) {
        Text("${if(media.kind=="PPV")"🔒 PPV" else "🖼 Free"} ${media.media_kind.lowercase()}")
        if(media.status!="VISIBLE")Text("Unavailable · moderation review")
        else if(media.unlocked){
            if(media.media_kind=="PHOTO"){
                val url=BuildConfig.API_BASE_URL.trimEnd('/')+"/v2135/media/${media.id}/file"
                val model=remember(media.id,store.token){ImageRequest.Builder(ctx).data(url)
                    .addHeader("Authorization","Bearer ${store.token.orEmpty()}").build()}
                AsyncImage(model=model,contentDescription="Creator photo",modifier=Modifier.fillMaxWidth().heightIn(max=320.dp))
            }else TextButton(onClick={scope.launch {loading=true;try{
                val (file,mime)=api.downloadVideo(media.id)
                val u=FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",file)
                ctx.startActivity(Intent(Intent.ACTION_VIEW).apply{setDataAndType(u,mime)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)})
            }catch(e:Exception){error=e.message}finally{loading=false}}}){Text("▶ Play video")}
        }else if(!isCreator){
            Button(enabled=!loading,onClick={scope.launch {loading=true;try{api.unlock(media.id);onChanged()}
                catch(e:Exception){error=e.message}finally{loading=false}}}){Text("Unlock ${media.price_q} Q")}
        }
        if(!isCreator)TextButton(onClick={reportDialog=true}){Text("Report media")}
        error?.let{Text(it,color=MaterialTheme.colorScheme.error)}
    }
    if(reportDialog)AlertDialog(onDismissRequest={reportDialog=false},title={Text("Report media?")},
        text={Text("This media will be quarantined pending moderator review.")},
        confirmButton={TextButton(onClick={scope.launch {try{api.report(media.id,"Reported by recipient");onChanged()}
            catch(e:Exception){error=e.message};reportDialog=false}}){Text("Report")}},
        dismissButton={TextButton(onClick={reportDialog=false}){Text("Cancel")}})
}
