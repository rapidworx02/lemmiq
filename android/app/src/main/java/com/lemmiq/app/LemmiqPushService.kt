package com.lemmiq.app

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
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

/** FCM token refresh is handled independently of the activity lifecycle. */
class LemmiqPushService:FirebaseMessagingService(){
    override fun onNewToken(token:String){
        val store=SessionStore(this)
        if(store.token.isNullOrEmpty())return
        CoroutineScope(Dispatchers.IO).launch { runCatching{Api(store).registerPush(token)} }
    }
    override fun onMessageReceived(message:RemoteMessage){
        if(message.data["type"]!="chat" || SessionStore(this).token.isNullOrEmpty() || MainActivity.isVisible)return
        val nm=getSystemService(NotificationManager::class.java)
        val channel="lemmiq_messages"
        nm.createNotificationChannel(NotificationChannel(channel,"LEMMIQ messages",NotificationManager.IMPORTANCE_HIGH))
        if(Build.VERSION.SDK_INT>=33 && ContextCompat.checkSelfPermission(this,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return
        val intent=Intent(this,MainActivity::class.java).apply{
            flags=Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pending=PendingIntent.getActivity(this,0,intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val text=message.data["body"]?.take(100)?:"New message"
        val notification=NotificationCompat.Builder(this,channel)
            .setSmallIcon(R.drawable.lemmiq_icon)
            .setContentTitle("LEMMIQ")
            .setContentText(text)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        val id=message.data["chat_id"]?.toIntOrNull()?:System.currentTimeMillis().toInt()
        nm.notify(id,notification)
    }
}
