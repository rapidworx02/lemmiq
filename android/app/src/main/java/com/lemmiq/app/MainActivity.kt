package com.lemmiq.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.graphics.Color

data class LemmiqLaunchRouteV2103(val type:String="",val id:Int?=null,val deepLink:String="")
object LemmiqLaunchRouterV2103{
    val route=mutableStateOf<LemmiqLaunchRouteV2103?>(null)
    fun consume(){route.value=null}
}

class MainActivity:ComponentActivity(){
    companion object { @Volatile var isVisible=false }
    override fun onStart(){super.onStart();isVisible=true}
    override fun onStop(){isVisible=false;super.onStop()}

    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState)
        PushControl.ensureChannels(this)
        readRoute(intent)
        setContent{
            MaterialTheme(colorScheme=lightColorScheme(
                primary=Color(0xFF6C4DFF),secondary=Color(0xFFFF4F9A),
                background=Color(0xFFF7F7FB),surface=Color.White
            )){LemmiqApp()}
        }
    }

    override fun onNewIntent(intent:Intent){
        super.onNewIntent(intent)
        setIntent(intent)
        readRoute(intent)
    }

    private fun readRoute(intent:Intent?){
        if(intent==null)return
        intent.getIntExtra("chat_id",-1).takeIf{it>0}?.let{LemmiqLaunchRouterV2103.route.value=LemmiqLaunchRouteV2103("chat",it);return}
        intent.getIntExtra("group_id",-1).takeIf{it>0}?.let{LemmiqLaunchRouterV2103.route.value=LemmiqLaunchRouteV2103("group",it);return}
        intent.getIntExtra("market_id",-1).takeIf{it>0}?.let{LemmiqLaunchRouterV2103.route.value=LemmiqLaunchRouteV2103("q_predict",it);return}
        val type=intent.getStringExtra("lemmiq_notification_type").orEmpty()
        val deep=intent.getStringExtra("lemmiq_deep_link").orEmpty()
        if(type.isNotBlank()||deep.isNotBlank())LemmiqLaunchRouterV2103.route.value=LemmiqLaunchRouteV2103(type,null,deep)
    }
}
