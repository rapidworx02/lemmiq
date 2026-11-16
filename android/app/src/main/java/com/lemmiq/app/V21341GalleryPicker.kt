package com.lemmiq.app

import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import java.util.Locale

/* V2.13.4.1 — approved professional gallery selector, private upload and new album creator.
   Uses authenticated /v2131 media and /v2134 professional chat endpoints only.
   No personal-chat ID is accepted here and no local Q debit is performed. */
private val GalleryPurpleV21341=Color(0xFF6B50E9)
private val GalleryMutedV21341=Color(0xFF72768A)

@Composable
private fun GalleryThumbV21341(client:CreatorApiV2131,item:CreatorGalleryNative){
    var image by remember(item.id){mutableStateOf<android.graphics.Bitmap?>(null)}
    LaunchedEffect(item.id,item.review){
        if(item.review!="APPROVED" || item.kind=="VIDEO")return@LaunchedEffect
        try{
            val a=client.galleryAssets(item.id).firstOrNull()?:return@LaunchedEffect
            if(a.kind!="PHOTO")return@LaunchedEffect
            val bytes=client.media("/v2131/exclusives/gallery/${item.id}/assets/${a.id}/media",3L*1024*1024)
            val opts=BitmapFactory.Options().apply{inSampleSize=4}
            image=BitmapFactory.decodeByteArray(bytes,0,bytes.size,opts)
        }catch(_:Exception){ /* keep generic thumbnail if file is large or unavailable */ }
    }
    Box(Modifier.size(69.dp).background(Color(0xFFEDEAF9),RoundedCornerShape(12.dp)),contentAlignment=Alignment.Center){
        val b=image
        if(b!=null)Image(bitmap=b.asImageBitmap(),contentDescription="Gallery media thumbnail",
            modifier=Modifier.fillMaxSize(),contentScale=ContentScale.Crop)
        else Text(if(item.kind=="VIDEO")"▶" else if(item.kind=="ALBUM")"▣" else "▧",
            fontSize=26.sp,color=GalleryPurpleV21341)
    }
}

/** Use with [threadId] to send PPV in a professional conversation; null opens the media manager only. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun V21341GalleryPicker(vm:LemmiqViewModel,threadId:String?,onDismiss:()->Unit,onSent:()->Unit){
    val ctx=LocalContext.current
    val client=remember(vm.store){CreatorApiV2131(ctx.applicationContext,vm.store)}
    val professional=remember(vm.store){ProfessionalApiV2134(ctx.applicationContext,vm.store)}
    val scope=rememberCoroutineScope()
    var tab by remember{mutableIntStateOf(0)}
    var gallery by remember{mutableStateOf<List<CreatorGalleryNative>>(emptyList())}
    var library by remember{mutableStateOf<List<CreatorAssetNative>>(emptyList())}
    var chosen by remember{mutableStateOf<Int?>(null)}
    var offerPrice by remember{mutableStateOf("25")}
    var busy by remember{mutableStateOf(false)}
    var error by remember{mutableStateOf<String?>(null)}
    var notice by remember{mutableStateOf("")}
    var revision by remember{mutableIntStateOf(0)}
    var uploadTitle by remember{mutableStateOf("")}
    var uploadLevel by remember{mutableStateOf("MAINSTREAM")}
    var uploadUri by remember{mutableStateOf<Uri?>(null)}
    var publishTitle by remember{mutableStateOf("")}
    var teaser by remember{mutableStateOf("")}
    var kind by remember{mutableStateOf("PHOTO")}
    var visibility by remember{mutableStateOf("PPV")}
    var publishPrice by remember{mutableStateOf("50")}
    var assetsChosen by remember{mutableStateOf<Set<Int>>(emptySet())}
    var confirmSend by remember{mutableStateOf(false)}
    val chooseFile=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri->uploadUri=uri}
    fun refresh(){revision++}
    LaunchedEffect(revision){
        busy=true
        try{
            gallery=client.galleryMine()
            library=client.library()
            if(gallery.none{it.id==chosen&&it.review=="APPROVED"})chosen=null
        }catch(e:Exception){error=e.message?:"Unable to load creator media"}
        finally{busy=false}
    }
    ModalBottomSheet(onDismissRequest=onDismiss){
        Column(Modifier.fillMaxWidth().heightIn(max=745.dp).verticalScroll(rememberScrollState())
            .padding(horizontal=17.dp,vertical=10.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
            Text(if(threadId==null)"Creator Gallery Manager" else "Send locked PPV media",fontSize=21.sp,fontWeight=FontWeight.Bold)
            Text("Only your professional creator identity is used. Approved media only.",fontSize=11.sp,color=GalleryMutedV21341)
            Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                listOf("My Gallery","Upload New","Create Item").forEachIndexed{index,label->
                    FilterChip(tab==index,{tab=index},{Text(label,fontSize=11.sp)})
                }
            }
            if(busy)LinearProgressIndicator(Modifier.fillMaxWidth())
            error?.let{Text(it,color=MaterialTheme.colorScheme.error,fontSize=12.sp)}
            if(notice.isNotBlank())Text(notice,color=Color(0xFF148265),fontSize=12.sp)
            when(tab){
                0->{
                    if(gallery.isEmpty())Text("No items yet. Upload media, await Master Admin approval, then create an exclusive item.",fontSize=12.sp,color=GalleryMutedV21341)
                    gallery.forEach{item->
                        val ready=item.review=="APPROVED"
                        val active=chosen==item.id
                        Card(Modifier.fillMaxWidth().clickable(enabled=ready){
                            chosen=item.id;offerPrice=if(item.price_q>0)item.price_q.toString() else "25"
                        },shape=RoundedCornerShape(14.dp),colors=CardDefaults.cardColors(containerColor=if(active)Color(0xFFE9E1FF) else Color.White)){
                            Row(Modifier.fillMaxWidth().padding(10.dp),verticalAlignment=Alignment.CenterVertically){
                                GalleryThumbV21341(client,item)
                                Spacer(Modifier.width(10.dp))
                                Column(Modifier.weight(1f)){
                                    Text(item.title,fontSize=14.sp,fontWeight=FontWeight.Bold)
                                    Text("${item.kind} · ${item.media_count} file(s)",fontSize=11.sp,color=GalleryMutedV21341)
                                    Text("${if(item.visibility=="PPV")"${item.price_q} Q" else "Subscriber included"} · ${item.review}",fontSize=10.sp,
                                        color=if(ready)GalleryPurpleV21341 else Color(0xFFB6791B))
                                }
                                if(active)Text("✓",color=GalleryPurpleV21341,fontSize=22.sp)
                            }
                        }
                    }
                    if(threadId!=null){
                        OutlinedTextField(offerPrice,{offerPrice=it},label={Text("Private offer price (Q)")},
                            modifier=Modifier.fillMaxWidth(),singleLine=true)
                        val value=offerPrice.toDoubleOrNull()
                        Button(onClick={confirmSend=true},modifier=Modifier.fillMaxWidth(),
                            enabled=!busy&&chosen!=null&&value!=null&&value.isFinite()&&value>0&&value<=100000){Text("🔒 Send approved media to this fan")}
                    }
                    OutlinedButton(onClick={refresh()},modifier=Modifier.fillMaxWidth(),enabled=!busy){Text("Refresh approvals")}
                }
                1->{
                    Text("Upload photo/video to your private media library",fontWeight=FontWeight.Bold)
                    OutlinedTextField(uploadTitle,{uploadTitle=it},label={Text("File title")},modifier=Modifier.fillMaxWidth())
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                        FilterChip(uploadLevel=="MAINSTREAM",{uploadLevel="MAINSTREAM"},{Text("Mainstream")})
                        FilterChip(uploadLevel=="GLAMOUR",{uploadLevel="GLAMOUR"},{Text("Non-explicit glamour")})
                    }
                    OutlinedButton(onClick={chooseFile.launch("*/*")},modifier=Modifier.fillMaxWidth()){
                        Text(uploadUri?.lastPathSegment?.takeLast(35)?:"Choose photo or video")
                    }
                    Text("JPG/PNG/WebP ≤20 MB · MP4/WebM ≤100 MB. Uploaded media remains pending until moderation approval.",fontSize=10.sp,color=GalleryMutedV21341)
                    Button(onClick={scope.launch{
                        busy=true;error=null
                        try{client.uploadAsset(uploadUri!!,uploadTitle.trim(),uploadLevel);uploadTitle="";uploadUri=null
                            notice="Upload submitted — awaiting Master Admin review";refresh()}
                        catch(e:Exception){error=e.message}finally{busy=false}
                    }},modifier=Modifier.fillMaxWidth(),enabled=!busy&&uploadUri!=null&&uploadTitle.trim().length in 3..140){Text("Upload for approval")}
                    Text("My library",fontWeight=FontWeight.Bold)
                    library.forEach{a->Text("${a.title} · ${a.kind} · ${a.review}",fontSize=12.sp,
                        color=if(a.review=="APPROVED")Color(0xFF177F5D) else GalleryMutedV21341)}
                }
                else->{
                    Text("Create one exclusive photo, video or an album",fontWeight=FontWeight.Bold)
                    OutlinedTextField(publishTitle,{publishTitle=it},label={Text("Gallery item title")},modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(teaser,{teaser=it},label={Text("Public teaser")},modifier=Modifier.fillMaxWidth())
                    Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                        listOf("PHOTO","VIDEO","ALBUM").forEach{k->FilterChip(kind==k,{kind=k;assetsChosen=emptySet()},{Text(k.lowercase().replaceFirstChar{it.uppercase()})})}
                    }
                    Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                        FilterChip(visibility=="PPV",{visibility="PPV"},{Text("Pay to unlock")})
                        FilterChip(visibility=="SUBSCRIBERS",{visibility="SUBSCRIBERS"},{Text("Subscribers included")})
                    }
                    if(visibility=="PPV")OutlinedTextField(publishPrice,{publishPrice=it},label={Text("Gallery price in Q")},modifier=Modifier.fillMaxWidth())
                    Text("Select approved files (${assetsChosen.size})",fontWeight=FontWeight.Bold)
                    val choices=library.filter{it.review=="APPROVED"&&(kind=="ALBUM"||it.kind==kind)}
                    if(choices.isEmpty())Text("No approved media available for this item type.",fontSize=12.sp,color=GalleryMutedV21341)
                    choices.forEach{a->Row(Modifier.fillMaxWidth().clickable{
                        assetsChosen=if(a.id in assetsChosen)assetsChosen-a.id else if(kind=="ALBUM")assetsChosen+a.id else setOf(a.id)
                    }.padding(vertical=6.dp),verticalAlignment=Alignment.CenterVertically){
                        Checkbox(checked=a.id in assetsChosen,onCheckedChange={v->
                            assetsChosen=if(v){if(kind=="ALBUM")assetsChosen+a.id else setOf(a.id)}else assetsChosen-a.id
                        })
                        Text("${a.title} · ${a.kind}",fontSize=12.sp)
                    }}
                    val price=if(visibility=="PPV")publishPrice.toDoubleOrNull() else 0.0
                    val validCount=if(kind=="ALBUM")assetsChosen.size in 2..20 else assetsChosen.size==1
                    Button(onClick={scope.launch{
                        busy=true;error=null
                        try{client.createGallery(publishTitle.trim(),teaser.trim(),kind,visibility,price?:0.0,assetsChosen.toList());
                            notice="Gallery item submitted for moderation";assetsChosen=emptySet();publishTitle="";teaser="";tab=0;refresh()}
                        catch(e:Exception){error=e.message}finally{busy=false}
                    }},modifier=Modifier.fillMaxWidth(),enabled=!busy&&publishTitle.trim().length in 3..140&&validCount&&
                        price!=null&&price.isFinite()&&(visibility!="PPV"||price>0)&&price<=100000){Text("Create gallery item for approval")}
                }
            }
            Spacer(Modifier.height(20.dp))
        }
    }
    if(confirmSend&&threadId!=null){
        val item=gallery.firstOrNull{it.id==chosen}
        AlertDialog(onDismissRequest={confirmSend=false},title={Text("Send professional PPV offer?")},
            text={Text("Send ${item?.title.orEmpty()} for ${offerPrice} Q? The fan will see locked media until they pay. No personal username is shared.")},
            confirmButton={Button(onClick={
                confirmSend=false
                scope.launch{busy=true;error=null
                    try{professional.offer(threadId,chosen!!,offerPrice.toDouble());onSent()}
                    catch(e:Exception){error=e.message}finally{busy=false}}
            }){Text("Send locked offer")}},dismissButton={TextButton({confirmSend=false}){Text("Cancel")}})
    }
}
