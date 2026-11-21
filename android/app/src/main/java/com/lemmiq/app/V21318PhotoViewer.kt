package com.lemmiq.app

import android.Manifest
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaScannerConnection
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.util.UUID

private fun imageType(bytes:ByteArray):Pair<String,String> {
    val opts=BitmapFactory.Options().apply{inJustDecodeBounds=true}
    BitmapFactory.decodeByteArray(bytes,0,bytes.size,opts)
    return when(opts.outMimeType){
        "image/png" -> "image/png" to "png"
        "image/jpeg" -> "image/jpeg" to "jpg"
        "image/webp" -> "image/webp" to "webp"
        "image/gif" -> "image/gif" to "gif"
        else -> throw IOException("Unsupported image format")
    }
}

private fun saveOriginal(ctx:Context,bytes:ByteArray) {
    val (mime,ext)=imageType(bytes)
    val name="LEMMIQ_${System.currentTimeMillis()}_${UUID.randomUUID().toString().take(6)}.$ext"
    if(Build.VERSION.SDK_INT>=29){
        val resolver=ctx.contentResolver
        val uri=resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI,ContentValues().apply{
            put(MediaStore.Images.Media.DISPLAY_NAME,name)
            put(MediaStore.Images.Media.MIME_TYPE,mime)
            put(MediaStore.Images.Media.RELATIVE_PATH,"${Environment.DIRECTORY_PICTURES}/LEMMIQ")
            put(MediaStore.Images.Media.IS_PENDING,1)
        })?:throw IOException("Could not create gallery image")
        try{
            resolver.openOutputStream(uri)?.use{it.write(bytes)}?:throw IOException("Gallery unavailable")
            if(resolver.update(uri,ContentValues().apply{put(MediaStore.Images.Media.IS_PENDING,0)},null,null)!=1)
                throw IOException("Could not publish image")
        }catch(e:Exception){resolver.delete(uri,null,null);throw e}
    }else{
        if(ContextCompat.checkSelfPermission(ctx,Manifest.permission.WRITE_EXTERNAL_STORAGE)!=PackageManager.PERMISSION_GRANTED)
            throw IOException("Storage permission required")
        @Suppress("DEPRECATION")
        val folder=File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES),"LEMMIQ")
        if(!folder.exists()&&!folder.mkdirs())throw IOException("Pictures folder unavailable")
        val f=File(folder,name)
        try{f.writeBytes(bytes)}catch(e:Exception){f.delete();throw e}
        MediaScannerConnection.scanFile(ctx,arrayOf(f.absolutePath),arrayOf(mime),null)
    }
}

@Composable
fun V21318PhotoActions(onVision:(()->Unit)?,onEdit:(()->Unit)?,onMenu:(()->Unit)?=null){
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically){
        Row(horizontalArrangement=Arrangement.spacedBy(4.dp)){
            if(onVision!=null) V21318PhotoChip("Q Vision",onVision)
            if(onEdit!=null) V21318PhotoChip("Edit with Q",onEdit)
        }
        if(onMenu!=null)V21318PhotoChip("⋯",onMenu)
    }
}
@Composable
private fun V21318PhotoChip(label:String,action:()->Unit){
    Surface(color=Color.Black.copy(alpha=.72f),shape=RoundedCornerShape(15.dp),modifier=Modifier.heightIn(min=40.dp).clickable(onClick=action)){
        Box(Modifier.padding(horizontal=9.dp,vertical=10.dp),contentAlignment=Alignment.Center){Text(label,color=Color.White,fontSize=11.sp)}
    }
}

@Composable
fun V21318PhotoViewer(preview:Bitmap, sender:String, stamp:String, loadOriginal:suspend ()->ByteArray,
    onDismiss:()->Unit,onVision:(()->Unit)?=null,onEdit:(()->Unit)?=null,onActions:(()->Unit)?=null,
    onForward:(()->Unit)?=null){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    var photo by remember(preview){mutableStateOf(preview)}
    var original by remember{mutableStateOf<ByteArray?>(null)}
    var busy by remember{mutableStateOf(false)}
    var loading by remember{mutableStateOf(false)}
    var failure by remember{mutableStateOf<String?>(null)}
    var menu by remember{mutableStateOf(false)}
    var scale by remember{mutableFloatStateOf(1f)}
    var x by remember{mutableFloatStateOf(0f)}
    var y by remember{mutableFloatStateOf(0f)}
    var rotation by remember{mutableFloatStateOf(0f)}
    var controls by remember{mutableStateOf(true)}
    var retry by remember{mutableIntStateOf(0)}
    LaunchedEffect(retry){
        loading=true;failure=null
        try{
            val bytes=loadOriginal()
            if(bytes.isEmpty()||bytes.size>24*1024*1024)throw IOException("Photo size unavailable")
            val decoded=withContext(Dispatchers.Default){
                val o=BitmapFactory.Options().apply{inJustDecodeBounds=true}
                BitmapFactory.decodeByteArray(bytes,0,bytes.size,o)
                var sample=1
                while(o.outWidth/sample>2048||o.outHeight/sample>2048)sample*=2
                BitmapFactory.decodeByteArray(bytes,0,bytes.size,BitmapFactory.Options().apply{inSampleSize=sample})
                    ?:throw IOException("Cannot decode original photo")
            }
            original=bytes;photo=decoded
        }catch(e:CancellationException){throw e}catch(e:Exception){failure=e.message?:"Unable to load original"}
        finally{loading=false}
    }
    fun save(){
        val bytes=original?:return
        if(busy)return
        busy=true
        scope.launch{
            try{withContext(Dispatchers.IO){saveOriginal(ctx,bytes)};Toast.makeText(ctx,"Photo saved to gallery",Toast.LENGTH_SHORT).show()}
            catch(e:CancellationException){throw e}catch(e:Exception){Toast.makeText(ctx,e.message?:"Save failed",Toast.LENGTH_LONG).show()}
            finally{busy=false}
        }
    }
    val perm=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){granted->
        if(granted)save() else Toast.makeText(ctx,"Storage permission denied",Toast.LENGTH_SHORT).show()
    }
    fun requestSave(){
        if(Build.VERSION.SDK_INT<29&&ContextCompat.checkSelfPermission(ctx,Manifest.permission.WRITE_EXTERNAL_STORAGE)!=PackageManager.PERMISSION_GRANTED)
            perm.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE) else save()
    }
    fun share(){
        val bytes=original?:return
        if(busy)return
        busy=true
        scope.launch{
            try{
                val (type,ext)=imageType(bytes)
                val file=withContext(Dispatchers.IO){File(File(ctx.cacheDir,"share").apply{mkdirs()},"LEMMIQ_${UUID.randomUUID()}.$ext").apply{writeBytes(bytes)}}
                val uri=FileProvider.getUriForFile(ctx,"${ctx.packageName}.files",file)
                val intent=Intent(Intent.ACTION_SEND).apply{this.type=type;putExtra(Intent.EXTRA_STREAM,uri);addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)}
                ctx.startActivity(Intent.createChooser(intent,"Share photo"))
            }catch(e:CancellationException){throw e}catch(e:Exception){Toast.makeText(ctx,e.message?:"Share failed",Toast.LENGTH_LONG).show()}
            finally{busy=false}
        }
    }
    Dialog(onDismissRequest=onDismiss,properties=DialogProperties(usePlatformDefaultWidth=false,dismissOnClickOutside=false)){
        Box(Modifier.fillMaxSize().background(Color.Black)){
            Image(photo.asImageBitmap(),"Chat photo",Modifier.fillMaxSize().graphicsLayer{scaleX=scale;scaleY=scale;translationX=x;translationY=y;rotationZ=rotation}
                .pointerInput(Unit){detectTransformGestures { _,pan,zoom,_->scale=(scale*zoom).coerceIn(1f,5f);if(scale<=1.01f){x=0f;y=0f}else{x+=pan.x;y+=pan.y}}}
                .pointerInput(Unit){detectTapGestures(onTap={controls=!controls},onDoubleTap={if(scale>1f){scale=1f;x=0f;y=0f}else scale=2.5f})},contentScale=ContentScale.Fit)
            if(controls){
                Row(Modifier.align(Alignment.TopCenter).fillMaxWidth().background(Color.Black.copy(alpha=.78f)).statusBarsPadding().padding(6.dp),verticalAlignment=Alignment.CenterVertically){
                    TextButton(onDismiss){Text("‹",color=Color.White,fontSize=24.sp)}
                    Column(Modifier.weight(1f)){Text(sender,color=Color.White);Text(stamp,color=Color.LightGray,fontSize=11.sp)}
                    TextButton({menu=true}){Text("⋮",color=Color.White,fontSize=24.sp)}
                    DropdownMenu(expanded=menu,onDismissRequest={menu=false}){
                        DropdownMenuItem(text={Text("Save to Gallery")},onClick={menu=false;requestSave()},enabled=original!=null&&!busy)
                        DropdownMenuItem(text={Text("Share")},onClick={menu=false;share()},enabled=original!=null&&!busy)
                        if(onForward!=null)DropdownMenuItem(text={Text("Forward")},onClick={menu=false;onDismiss();onForward()})
                        if(onEdit!=null)DropdownMenuItem(text={Text("Edit with Q")},onClick={menu=false;onDismiss();onEdit()})
                        if(onVision!=null)DropdownMenuItem(text={Text("Ask Q Vision")},onClick={menu=false;onDismiss();onVision()})
                        DropdownMenuItem(text={Text("Rotate preview")},onClick={rotation=(rotation+90f)%360f;menu=false})
                        if(onActions!=null)DropdownMenuItem(text={Text("Show in chat / message actions")},onClick={menu=false;onDismiss();onActions()})
                    }
                }
                Column(Modifier.align(Alignment.BottomCenter).fillMaxWidth().background(Color.Black.copy(alpha=.82f)).navigationBarsPadding().padding(8.dp)){
                    if(loading)Text("Loading original photo…",color=Color.LightGray,fontSize=11.sp)
                    failure?.let{Text(it,color=Color.LightGray,fontSize=11.sp);TextButton({retry++}){Text("Retry",color=Color.White)}}
                    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceEvenly){
                        TextButton({requestSave()},enabled=original!=null&&!busy){Text("Save photo",color=if(original!=null)Color.White else Color.Gray)}
                        if(onVision!=null)TextButton({onDismiss();onVision()}){Text("Q Vision",color=Color.White)}
                        if(onEdit!=null)TextButton({onDismiss();onEdit()}){Text("Edit with Q",color=Color.White)}
                    }
                }
            }
        }
    }
}

@Composable
fun V21318ForwardDialog(vm:LemmiqViewModel,mid:Int,sourceKind:String,preview:String,onDismiss:()->Unit){
    val ctx=LocalContext.current
    val scope=rememberCoroutineScope()
    val chats=remember(mid,sourceKind){mutableStateListOf<Int>()}
    val groups=remember(mid,sourceKind){mutableStateListOf<Int>()}
    var busy by remember{mutableStateOf(false)}
    var error by remember{mutableStateOf<String?>(null)}
    AlertDialog(onDismissRequest={if(!busy)onDismiss()},title={Text("Forward message")},text={
        Column{
            Text(preview.ifBlank{"Attachment"},maxLines=2)
            Text("Choose up to 20 conversations",fontSize=11.sp)
            Column(Modifier.heightIn(max=300.dp).verticalScroll(androidx.compose.foundation.rememberScrollState())){
                vm.chats.forEach{c->Row(Modifier.fillMaxWidth().clickable(enabled=!busy){if(c.id in chats)chats.remove(c.id) else if(chats.size+groups.size<20)chats.add(c.id)},verticalAlignment=Alignment.CenterVertically){
                    Checkbox(c.id in chats,{if(it){if(chats.size+groups.size<20)chats.add(c.id)}else chats.remove(c.id)},enabled=!busy)
                    V24Avatar(c.other_user,32);Spacer(Modifier.width(5.dp));Text(c.other_user.display_name)
                }}
                vm.groups.forEach{g->Row(Modifier.fillMaxWidth().clickable(enabled=!busy){if(g.id in groups)groups.remove(g.id) else if(chats.size+groups.size<20)groups.add(g.id)},verticalAlignment=Alignment.CenterVertically){
                    Checkbox(g.id in groups,{if(it){if(chats.size+groups.size<20)groups.add(g.id)}else groups.remove(g.id)},enabled=!busy)
                    V24GroupAvatar(g,32);Spacer(Modifier.width(5.dp));Text(g.name)
                }}
            }
            error?.let{Text(it,color=MaterialTheme.colorScheme.error,fontSize=12.sp)}
        }
    },confirmButton={Button(enabled=!busy&&chats.size+groups.size>0,onClick={busy=true;error=null;scope.launch{
        try{val count=vm.forwardMediaV21318(mid,chats.toList(),groups.toList(),sourceKind);Toast.makeText(ctx,"Forwarded to $count conversation(s)",Toast.LENGTH_SHORT).show();onDismiss()}
        catch(e:CancellationException){throw e}catch(e:Exception){error=e.message?:"Forward failed"}finally{busy=false}
    }}){Text(if(busy)"Forwarding…" else "Forward")}},dismissButton={TextButton(onDismiss,enabled=!busy){Text("Cancel")}})
}
