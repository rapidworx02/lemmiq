package com.lemmiq.app

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

object PushControl {
    const val CHANNEL_ID="lemmiq_messages"
    private const val PREF="lemmiq_push_controls"

    fun ensureChannel(ctx:Context){
        val nm=ctx.getSystemService(NotificationManager::class.java)
        val channel=NotificationChannel(
            CHANNEL_ID,"LEMMIQ messages",NotificationManager.IMPORTANCE_HIGH
        ).apply{
            description="New LEMMIQ chat messages"
            setShowBadge(true)
            enableVibration(true)
        }
        nm.createNotificationChannel(channel)
    }

    fun permissionAsked(ctx:Context)=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE)
        .getBoolean("permission_asked",false)

    fun markPermissionAsked(ctx:Context)=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE)
        .edit().putBoolean("permission_asked",true).apply()

    fun cancelChat(ctx:Context,chatId:Int){
        ctx.getSystemService(NotificationManager::class.java).cancel(chatId)
    }

    fun clearAll(ctx:Context){
        ctx.getSystemService(NotificationManager::class.java).cancelAll()
    }
}

class LemmiqPushService:FirebaseMessagingService(){
    override fun onNewToken(token:String){
        val store=SessionStore(this)
        if(store.token.isNullOrEmpty())return
        CoroutineScope(Dispatchers.IO).launch { runCatching{Api(store).registerPush(token)} }
    }

    override fun onMessageReceived(message:RemoteMessage){
        val store=SessionStore(this)
        if(store.token.isNullOrEmpty())return
        PushControl.ensureChannel(this)

        if(Build.VERSION.SDK_INT>=33 &&
            ContextCompat.checkSelfPermission(this,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return

        val type=message.data["type"].orEmpty()
        val nm=getSystemService(NotificationManager::class.java)

        if(type=="call"){
            val callId=message.data["call_id"].orEmpty()
            val caller=message.data["caller_name"]?.take(60)?.ifBlank{"LEMMIQ user"}?:"LEMMIQ user"
            val callerAvatar=message.data["caller_avatar_url"].orEmpty()
            val intent=Intent(this,LemmiqCallActivity::class.java).apply{
                putExtra("call_id",callId);putExtra("person",caller);putExtra("avatar_url",callerAvatar);putExtra("incoming",true)
            }
            val pending=PendingIntent.getActivity(this,callId.hashCode(),intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification=NotificationCompat.Builder(this,PushControl.CHANNEL_ID)
                .setSmallIcon(R.drawable.lemmiq_icon)
                .setContentTitle("📞 Incoming LEMMIQ call")
                .setContentText(caller)
                .setContentIntent(pending)
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_CALL)
                .setFullScreenIntent(pending,true)
                .build()
            nm.notify(callId.hashCode(),notification)
            return
        }

        if(MainActivity.isVisible)return

        if(type=="group"){
            val gid=message.data["group_id"]?.toIntOrNull()?:return
            val group=message.data["group_name"]?.take(60)?:"LEMMIQ group"
            val sender=message.data["sender_name"]?.take(60)?:"Member"
            val body=message.data["body"]?.take(180)?:"New group message"
            val intent=Intent(this,MainActivity::class.java).apply{
                flags=Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra("group_id",gid)
            }
            val pending=PendingIntent.getActivity(this,100000+gid,intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification=NotificationCompat.Builder(this,PushControl.CHANNEL_ID)
                .setSmallIcon(R.drawable.lemmiq_icon)
                .setContentTitle(group)
                .setContentText("$sender: $body")
                .setAutoCancel(true)
                .setContentIntent(pending)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .build()
            nm.notify(100000+gid,notification)
            return
        }

        if(type!="chat")return
        val chatId=message.data["chat_id"]?.toIntOrNull()?:System.currentTimeMillis().toInt()
        val sender=message.data["sender_name"]?.take(60)?.ifBlank{"LEMMIQ"}?:"LEMMIQ"
        val text=message.data["body"]?.take(180)?.ifBlank{"New message"}?:"New message"
        val unread=message.data["unread_count"]?.toIntOrNull()?.coerceAtLeast(1)?:1

        val intent=Intent(this,MainActivity::class.java).apply{
            flags=Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("chat_id",chatId)
        }
        val pending=PendingIntent.getActivity(this,chatId,intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

        val notification=NotificationCompat.Builder(this,PushControl.CHANNEL_ID)
            .setSmallIcon(R.drawable.lemmiq_icon)
            .setContentTitle(sender)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .setContentIntent(pending)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setBadgeIconType(NotificationCompat.BADGE_ICON_SMALL)
            .setNumber(unread)
            .setGroup("lemmiq_messages")
            .build()
        nm.notify(chatId,notification)
    }
}
