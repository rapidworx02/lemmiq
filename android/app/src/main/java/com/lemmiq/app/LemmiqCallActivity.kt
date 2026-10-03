package com.lemmiq.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import io.livekit.android.LiveKit
import io.livekit.android.room.Room
import kotlinx.coroutines.launch

class LemmiqCallActivity:ComponentActivity(){
    private var room:Room?=null
    private var callId:String=""
    private var pendingWs:String=""
    private var pendingToken:String=""
    private var person:String="LEMMIQ user"
    private var incoming:Boolean=false

    private val status=mutableStateOf("Preparing call…")
    private val muted=mutableStateOf(false)
    private val speaker=mutableStateOf(false)

    private val micPermission=registerForActivityResult(ActivityResultContracts.RequestPermission()){ granted->
        if(granted && pendingWs.isNotBlank() && pendingToken.isNotBlank())connectCall(pendingWs,pendingToken)
        else if(!granted)status.value="Microphone permission is required for a voice call"
    }

    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState)
        callId=intent.getStringExtra("call_id").orEmpty()
        pendingWs=intent.getStringExtra("ws_url").orEmpty()
        pendingToken=intent.getStringExtra("token").orEmpty()
        person=intent.getStringExtra("person")?:"LEMMIQ user"
        incoming=intent.getBooleanExtra("incoming",false)
        status.value=if(incoming && pendingToken.isBlank())"Incoming LEMMIQ call" else "Connecting…"

        setContent{
            MaterialTheme{
                Box(
                    Modifier.fillMaxSize().background(
                        Brush.verticalGradient(listOf(Color(0xFF16112C),Color(0xFF090B17)))
                    ),
                    contentAlignment=Alignment.Center
                ){
                    Column(horizontalAlignment=Alignment.CenterHorizontally,modifier=Modifier.padding(28.dp)){
                        Text("Q",fontSize=54.sp,color=Color(0xFF9D8BFF),fontWeight=FontWeight.Black)
                        Text(person,fontSize=30.sp,color=Color.White,fontWeight=FontWeight.Bold)
                        Text(status.value,color=Color(0xFFBDB9D1),modifier=Modifier.padding(top=8.dp))
                        Spacer(Modifier.height(34.dp))

                        if(incoming && pendingToken.isBlank()){
                            Row(horizontalArrangement=Arrangement.spacedBy(18.dp)){
                                Button(onClick={answerIncoming()}){Text("Answer")}
                                Button(
                                    onClick={declineIncoming()},
                                    colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFD13B50))
                                ){Text("Decline")}
                            }
                        }else{
                            Row(horizontalArrangement=Arrangement.spacedBy(14.dp)){
                                FilledTonalButton(onClick={
                                    muted.value=!muted.value
                                    lifecycleScope.launch{room?.localParticipant?.setMicrophoneEnabled(!muted.value)}
                                },shape=CircleShape,modifier=Modifier.size(62.dp)){Text(if(muted.value)"🔇" else "🎙",fontSize=20.sp)}
                                FilledTonalButton(onClick={
                                    speaker.value=!speaker.value
                                    val am=getSystemService(Context.AUDIO_SERVICE) as AudioManager
                                    @Suppress("DEPRECATION")
                                    run{am.mode=AudioManager.MODE_IN_COMMUNICATION;am.isSpeakerphoneOn=speaker.value}
                                },shape=CircleShape,modifier=Modifier.size(62.dp)){Text("🔊",fontSize=20.sp)}
                                Button(
                                    onClick=endCall(),
                                    shape=CircleShape,modifier=Modifier.size(62.dp),
                                    colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFD13B50))
                                ){Text("☎",fontSize=20.sp)}
                            }
                        }
                        Spacer(Modifier.height(22.dp))
                        Text("LEMMIQ V2.3 voice-call beta · LiveKit/WebRTC",color=Color(0xFF8E89A5),fontSize=11.sp)
                    }
                }
            }
        }

        if(!incoming || pendingToken.isNotBlank())ensureMicAndConnect()
    }

    private fun answerIncoming(){
        lifecycleScope.launch{
            try{
                val join=Api(SessionStore(this@LemmiqCallActivity)).joinCall(callId)
                pendingWs=join.ws_url;pendingToken=join.token
                incoming=false;status.value="Connecting…"
                ensureMicAndConnect()
            }catch(e:Exception){status.value=e.message?:"Call failed"}
        }
    }

    private fun declineIncoming():()->Unit = {
        lifecycleScope.launch{
            runCatching{Api(SessionStore(this@LemmiqCallActivity)).declineCall(callId)}
            finish()
        }
    }

    private fun ensureMicAndConnect(){
        if(ContextCompat.checkSelfPermission(this,Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED)
            connectCall(pendingWs,pendingToken)
        else micPermission.launch(Manifest.permission.RECORD_AUDIO)
    }

    private fun connectCall(ws:String,token:String){
        if(ws.isBlank()||token.isBlank()){status.value="Call credentials unavailable";return}
        lifecycleScope.launch{
            try{
                room?.disconnect()
                room=LiveKit.create(applicationContext)
                room!!.connect(ws,token)
                room!!.localParticipant.setMicrophoneEnabled(true)
                status.value="Connected"
            }catch(e:Exception){status.value=e.message?:"Connection failed"}
        }
    }

    private fun endCall():()->Unit = {
        room?.disconnect()
        lifecycleScope.launch{if(callId.isNotBlank())runCatching{Api(SessionStore(this@LemmiqCallActivity)).endCall(callId)}}
        finish()
    }

    override fun onDestroy(){
        room?.disconnect()
        super.onDestroy()
    }
}
