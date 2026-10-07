package com.lemmiq.app

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.text.DateFormat
import java.util.Date

 data class LemmiqNoticeV2103(
    val id:String="",
    val type:String="system",
    val title:String="LEMMIQ",
    val body:String="",
    val createdAt:Long=System.currentTimeMillis(),
    val deepLink:String="",
    val read:Boolean=false
)

object LemmiqNotificationLogV2103{
    private const val PREF="lemmiq_notification_center_v2103"
    private const val KEY="items"
    private val gson=Gson()
    private fun prefs(ctx:Context)=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE)
    private fun load(ctx:Context):MutableList<LemmiqNoticeV2103>{
        val raw=prefs(ctx).getString(KEY,"[]")?:"[]"
        val type=object:TypeToken<MutableList<LemmiqNoticeV2103>>(){}.type
        return runCatching{gson.fromJson<MutableList<LemmiqNoticeV2103>>(raw,type)}.getOrNull()?:mutableListOf()
    }
    private fun save(ctx:Context,list:List<LemmiqNoticeV2103>){prefs(ctx).edit().putString(KEY,gson.toJson(list.take(200))).apply()}
    fun add(ctx:Context,item:LemmiqNoticeV2103){
        val list=load(ctx)
        if(list.any{it.id==item.id})return
        list.add(0,item);save(ctx,list)
    }
    fun all(ctx:Context)=load(ctx).toList()
    fun markAllRead(ctx:Context){save(ctx,load(ctx).map{it.copy(read=true)})}
    fun clear(ctx:Context){prefs(ctx).edit().remove(KEY).apply()}
}

@Composable
fun LemmiqNotificationCenterV2103(){
    val ctx=androidx.compose.ui.platform.LocalContext.current
    var rows by remember{mutableStateOf(LemmiqNotificationLogV2103.all(ctx))}
    Column(Modifier.fillMaxSize()){
        Row(Modifier.fillMaxWidth().padding(horizontal=18.dp,vertical=10.dp),horizontalArrangement=Arrangement.SpaceBetween){
            Text("Recent alerts",fontWeight=FontWeight.Bold)
            Row{TextButton({LemmiqNotificationLogV2103.markAllRead(ctx);rows=LemmiqNotificationLogV2103.all(ctx)}){Text("Mark all read")};TextButton({LemmiqNotificationLogV2103.clear(ctx);rows=emptyList()}){Text("Clear")}}
        }
        if(rows.isEmpty())Box(Modifier.fillMaxSize().padding(28.dp)){Text("No LEMMIQ notifications yet.",color=MaterialTheme.colorScheme.onSurfaceVariant)}
        else LazyColumn(contentPadding=PaddingValues(horizontal=14.dp,vertical=4.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            items(rows,key={it.id}){n->
                Card(shape=RoundedCornerShape(18.dp),colors=CardDefaults.cardColors(containerColor=if(n.read)MaterialTheme.colorScheme.surfaceVariant.copy(alpha=.5f) else MaterialTheme.colorScheme.primaryContainer.copy(alpha=.55f))){
                    Column(Modifier.fillMaxWidth().padding(14.dp),verticalArrangement=Arrangement.spacedBy(4.dp)){
                        Text(n.title,fontWeight=FontWeight.Bold)
                        Text(n.body,style=MaterialTheme.typography.bodyMedium)
                        Text(DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT).format(Date(n.createdAt)),style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}
