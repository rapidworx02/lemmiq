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
    const val CH_MESSAGES="lemmiq_messages"
    const val CH_CALLS="lemmiq_calls"
    const val CH_Q_ECONOMY="lemmiq_q_economy"
    const val CH_Q_PREDICT="lemmiq_q_predict"
    const val CH_Q_ASSISTANT="lemmiq_q_assistant"
    const val CH_SYSTEM="lemmiq_system"
    private const val PREF="lemmiq_push_controls"

    fun ensureChannel(ctx:Context)=ensureChannels(ctx)

    fun ensureChannels(ctx:Context){
        val nm=ctx.getSystemService(NotificationManager::class.java)
        listOf(
            NotificationChannel(CH_MESSAGES,"Messages",NotificationManager.IMPORTANCE_HIGH).apply{description="Direct and group messages";setShowBadge(true);enableVibration(true)},
            NotificationChannel(CH_CALLS,"Calls",NotificationManager.IMPORTANCE_HIGH).apply{description="Incoming and missed LEMMIQ calls";setShowBadge(true);enableVibration(true)},
            NotificationChannel(CH_Q_ECONOMY,"Q Economy",NotificationManager.IMPORTANCE_DEFAULT).apply{description="Daily Q, transfers, referrals, packages and Q Market";setShowBadge(true)},
            NotificationChannel(CH_Q_PREDICT,"Q Predict",NotificationManager.IMPORTANCE_DEFAULT).apply{description="Market closes, results, payouts and watched markets";setShowBadge(true)},
            NotificationChannel(CH_Q_ASSISTANT,"Q Assistant",NotificationManager.IMPORTANCE_DEFAULT).apply{description="Q-to-Q, completed analyses and useful Q alerts";setShowBadge(true)},
            NotificationChannel(CH_SYSTEM,"System & Security",NotificationManager.IMPORTANCE_DEFAULT).apply{description="Account, security and system notifications";setShowBadge(true)}
        ).forEach(nm::createNotificationChannel)
    }

    fun permissionAsked(ctx:Context)=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE).getBoolean("permission_asked",false)
    fun markPermissionAsked(ctx:Context)=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE).edit().putBoolean("permission_asked",true).apply()
    fun cancelChat(ctx:Context,chatId:Int){ctx.getSystemService(NotificationManager::class.java).cancel(chatId)}
    fun clearAll(ctx:Context){ctx.getSystemService(NotificationManager::class.java).cancelAll()}
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
        PushControl.ensureChannels(this)
        if(Build.VERSION.SDK_INT>=33 && ContextCompat.checkSelfPermission(this,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return

        val d=message.data
        val type=d["type"].orEmpty().lowercase()
        val title=(d["title"]?:d["sender_name"]?:"LEMMIQ").take(90)
        val body=(d["body"]?:d["message"]?:"You have a new LEMMIQ update").take(280)
        val deepLink=d["deep_link"].orEmpty()
        val eventId=d["event_id"]?:message.messageId?:"$type:${d["chat_id"]}:${System.currentTimeMillis()}"

        LemmiqNotificationLogV2103.add(this,LemmiqNoticeV2103(eventId,type,title,body,System.currentTimeMillis(),deepLink,false))
        val nm=getSystemService(NotificationManager::class.java)

        if(type=="call"){
            val callId=d["call_id"].orEmpty()
            val caller=d["caller_name"]?.take(60)?.ifBlank{"LEMMIQ user"}?:"LEMMIQ user"
            val callerAvatar=d["caller_avatar_url"].orEmpty()
            val intent=Intent(this,LemmiqCallActivity::class.java).apply{putExtra("call_id",callId);putExtra("person",caller);putExtra("avatar_url",callerAvatar);putExtra("incoming",true)}
            val pending=PendingIntent.getActivity(this,callId.hashCode(),intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            nm.notify(callId.hashCode(),NotificationCompat.Builder(this,PushControl.CH_CALLS).setSmallIcon(R.drawable.lemmiq_icon).setContentTitle("📞 Incoming LEMMIQ call").setContentText(caller).setContentIntent(pending).setAutoCancel(true).setPriority(NotificationCompat.PRIORITY_MAX).setCategory(NotificationCompat.CATEGORY_CALL).setFullScreenIntent(pending,true).build())
            return
        }

        if(type=="group" || type=="chat"){
            val isGroup=type=="group"
            val id=if(isGroup)d["group_id"]?.toIntOrNull() else d["chat_id"]?.toIntOrNull()
            if(id==null)return
            val notifId=if(isGroup)100000+id else id
            val display=if(isGroup)(d["group_name"]?:"LEMMIQ group") else (d["sender_name"]?:"LEMMIQ")
            val messageText=if(isGroup)"${d["sender_name"]?:"Member"}: ${d["body"]?:"New message"}" else (d["body"]?:"New message")
            val unread=d["unread_count"]?.toIntOrNull()?.coerceAtLeast(1)?:1
            val intent=Intent(this,MainActivity::class.java).apply{flags=Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP;if(isGroup)putExtra("group_id",id)else putExtra("chat_id",id)}
            val pending=PendingIntent.getActivity(this,notifId,intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val n=NotificationCompat.Builder(this,PushControl.CH_MESSAGES).setSmallIcon(R.drawable.lemmiq_icon).setContentTitle(display).setContentText(messageText).setStyle(NotificationCompat.BigTextStyle().bigText(messageText)).setAutoCancel(true).setContentIntent(pending).setPriority(NotificationCompat.PRIORITY_HIGH).setCategory(NotificationCompat.CATEGORY_MESSAGE).setBadgeIconType(NotificationCompat.BADGE_ICON_SMALL).setNumber(unread).setGroup(if(isGroup)"lemmiq_group_$id" else "lemmiq_chat_$id").build()
            nm.notify(notifId,n)
            return
        }

        val channel=when(type){
            "q_daily_ready","q_credit","q_transfer","q_referral","q_package","q_market"->PushControl.CH_Q_ECONOMY
            "q_predict","q_predict_close","q_predict_result","q_predict_void","q_predict_watch"->PushControl.CH_Q_PREDICT
            "q_assistant","q_to_q","q_analysis"->PushControl.CH_Q_ASSISTANT
            else->PushControl.CH_SYSTEM
        }
        val requestCode=eventId.hashCode()
        val intent=Intent(this,MainActivity::class.java).apply{flags=Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP;putExtra("lemmiq_notification_type",type);putExtra("lemmiq_deep_link",deepLink);d["market_id"]?.toIntOrNull()?.let{putExtra("market_id",it)}}
        val pending=PendingIntent.getActivity(this,requestCode,intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        nm.notify(requestCode,NotificationCompat.Builder(this,channel).setSmallIcon(R.drawable.lemmiq_icon).setContentTitle(title).setContentText(body).setStyle(NotificationCompat.BigTextStyle().bigText(body)).setContentIntent(pending).setAutoCancel(true).setPriority(NotificationCompat.PRIORITY_DEFAULT).setBadgeIconType(NotificationCompat.BADGE_ICON_SMALL).build())
    }
}
