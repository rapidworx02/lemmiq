package com.lemmiq.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.Ringtone
import android.media.RingtoneManager
import android.media.ToneGenerator
import android.os.Build
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
import coil.compose.AsyncImage
import com.twilio.audioswitch.AudioDevice
import io.livekit.android.LiveKit
import io.livekit.android.events.RoomEvent
import io.livekit.android.room.Room
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch

class LemmiqCallActivity:ComponentActivity(){
    private var room:Room?=null
    private var callId=""
    private var wsUrl=""
    private var token=""
    private var person="LEMMIQ user"
    private var avatarUrl:String?=null
    private var incoming=false
    private var ringtone:Ringtone?=null
    private var ringback:ToneGenerator?=null
    private var timerJob:Job?=null
    private var timeoutJob:Job?=null
    private val status=mutableStateOf("Preparing call…")
    private val seconds=mutableIntStateOf(0)
    private val muted=mutableStateOf(false)
    private val speaker=mutableStateOf(false)

    private val micPermission=registerForActivityResult(ActivityResultContracts.RequestPermission()){ok->
        if(ok) connectRoom() else status.value="Microphone permission is required"
    }

    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState)
        callId=intent.getStringExtra("call_id").orEmpty()
        wsUrl=intent.getStringExtra("ws_url").orEmpty()
        token=intent.getStringExtra("token").orEmpty()
        person=intent.getStringExtra("person")?:"LEMMIQ user"
        avatarUrl=intent.getStringExtra("avatar_url")?.takeIf{it.isNotBlank()}
        incoming=intent.getBooleanExtra("incoming",false)
        status.value=if(incoming && token.isBlank())"Incoming LEMMIQ call" else "Ringing…"

        configureDefaultAudioRoute()
        if(incoming && token.isBlank())startIncomingRingtone() else startOutgoingRingback()

        setContent{
            MaterialTheme{
                Box(
                    Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF17102D),Color(0xFF080A16)))),
                    contentAlignment=Alignment.Center
                ){
                    Column(horizontalAlignment=Alignment.CenterHorizontally,modifier=Modifier.padding(28.dp)){
                        val resolvedAvatar=avatarUrl?.let{if(it.startsWith("http"))it else "${BuildConfig.API_BASE_URL.trimEnd('/')}$it"}
                        if(resolvedAvatar!=null){
                            AsyncImage(model=resolvedAvatar,contentDescription=person,
                                modifier=Modifier.size(92.dp).background(Color(0xFF6C4DFF),CircleShape))
                        }else{
                            Text(person.take(1).uppercase(),fontSize=42.sp,color=Color.White,
                                modifier=Modifier.background(Color(0xFF6C4DFF),CircleShape).padding(22.dp))
                        }
                        Spacer(Modifier.height(20.dp))
                        Text(person,fontSize=28.sp,color=Color.White,fontWeight=FontWeight.Bold)
                        Text(status.value,color=Color(0xFFC5C0D7),modifier=Modifier.padding(top=8.dp))
                        if(status.value=="Connected")Text(formatSeconds(seconds.intValue),color=Color.White,fontSize=18.sp,modifier=Modifier.padding(top=6.dp))
                        Spacer(Modifier.height(34.dp))

                        if(incoming && token.isBlank()){
                            Row(horizontalArrangement=Arrangement.spacedBy(18.dp)){
                                Button(onClick={answer()}){Text("Answer")}
                                Button(onClick={decline()},colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFD13B50))){Text("Decline")}
                            }
                        }else{
                            Row(horizontalArrangement=Arrangement.spacedBy(14.dp)){
                                FilledTonalButton(onClick={
                                    muted.value=!muted.value
                                    lifecycleScope.launch{room?.localParticipant?.setMicrophoneEnabled(!muted.value)}
                                },shape=CircleShape,modifier=Modifier.size(62.dp)){Text(if(muted.value)"🔇" else "🎙",fontSize=20.sp)}
                                FilledTonalButton(onClick={toggleSpeaker()},shape=CircleShape,modifier=Modifier.size(62.dp)){
                                    Text(if(speaker.value)"🔊" else "📱",fontSize=20.sp)
                                }
                                Button(onClick=endCall(),shape=CircleShape,modifier=Modifier.size(62.dp),
                                    colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFD13B50))){Text("☎",fontSize=20.sp)}
                            }
                        }
                        Spacer(Modifier.height(22.dp))
                        Text("LEMMIQ V2.4 · LiveKit/WebRTC",color=Color(0xFF8E89A5),fontSize=11.sp)
                    }
                }
            }
        }

        if(!incoming || token.isNotBlank())ensureMic()
    }

    private fun answer(){
        stopTones()
        lifecycleScope.launch{
            try{
                val join=Api(SessionStore(this@LemmiqCallActivity)).joinCall(callId)
                wsUrl=join.ws_url;token=join.token;incoming=false;status.value="Connecting…";ensureMic()
            }catch(e:Exception){status.value=e.message?:"Call failed"}
        }
    }

    private fun decline():()->Unit = {
        stopTones()
        lifecycleScope.launch{
            runCatching{Api(SessionStore(this@LemmiqCallActivity)).declineCall(callId)}
            finish()
        }
    }

    private fun ensureMic(){
        if(ContextCompat.checkSelfPermission(this,Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED)connectRoom()
        else micPermission.launch(Manifest.permission.RECORD_AUDIO)
    }

    private fun connectRoom(){
        if(wsUrl.isBlank()||token.isBlank()){status.value="Call credentials unavailable";return}
        lifecycleScope.launch{
            try{
                room=LiveKit.create(applicationContext)
                val r=room!!
                r.audioSwitchHandler?.preferredDeviceList=listOf(
                    AudioDevice.BluetoothHeadset::class.java,
                    AudioDevice.WiredHeadset::class.java,
                    AudioDevice.Earpiece::class.java,
                    AudioDevice.Speakerphone::class.java
                )
                launch{
                    r.events.collect{event->
                        when(event){
                            is RoomEvent.ParticipantConnected -> onAnswered()
                            is RoomEvent.ParticipantDisconnected -> if(status.value=="Connected")status.value="Call ended"
                            else -> Unit
                        }
                    }
                }
                r.connect(wsUrl,token)
                r.localParticipant.setMicrophoneEnabled(true)
                if(incoming || r.remoteParticipants.isNotEmpty())onAnswered()
                else{
                    status.value="Ringing…";startOutgoingRingback()
                    timeoutJob?.cancel();timeoutJob=lifecycleScope.launch{
                        delay(45000)
                        if(status.value=="Ringing…"){
                            status.value="No answer";stopTones()
                            runCatching{Api(SessionStore(this@LemmiqCallActivity)).endCall(callId)}
                            delay(1200);finish()
                        }
                    }
                }
            }catch(e:Exception){stopTones();status.value=e.message?:"Connection failed"}
        }
    }

    private fun onAnswered(){
        if(status.value=="Connected")return
        stopTones();timeoutJob?.cancel();status.value="Connected";seconds.intValue=0
        timerJob?.cancel();timerJob=lifecycleScope.launch{while(true){delay(1000);seconds.intValue++}}
    }

    private fun configureDefaultAudioRoute(){
        val am=getSystemService(Context.AUDIO_SERVICE) as AudioManager
        am.mode=AudioManager.MODE_IN_COMMUNICATION
        speaker.value=false
        if(Build.VERSION.SDK_INT>=31){
            val devices=am.availableCommunicationDevices
            val bluetooth=devices.firstOrNull{it.type==AudioDeviceInfo.TYPE_BLUETOOTH_SCO || it.type==AudioDeviceInfo.TYPE_BLE_HEADSET}
            val earpiece=devices.firstOrNull{it.type==AudioDeviceInfo.TYPE_BUILTIN_EARPIECE}
            when{
                bluetooth!=null->am.setCommunicationDevice(bluetooth)
                earpiece!=null->am.setCommunicationDevice(earpiece)
            }
        }else{
            @Suppress("DEPRECATION") am.isSpeakerphoneOn=false
        }
    }

    private fun toggleSpeaker(){
        val handler=room?.audioSwitchHandler
        speaker.value=!speaker.value
        if(handler!=null){
            if(speaker.value){
                handler.availableAudioDevices.firstOrNull{it is AudioDevice.Speakerphone}?.let{handler.selectDevice(it)}
            }else{
                handler.selectDevice(null)
                handler.preferredDeviceList=listOf(
                    AudioDevice.BluetoothHeadset::class.java,
                    AudioDevice.WiredHeadset::class.java,
                    AudioDevice.Earpiece::class.java,
                    AudioDevice.Speakerphone::class.java
                )
            }
            return
        }
        val am=getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if(Build.VERSION.SDK_INT>=31){
            if(speaker.value)am.availableCommunicationDevices.firstOrNull{it.type==AudioDeviceInfo.TYPE_BUILTIN_SPEAKER}?.let{am.setCommunicationDevice(it)}
            else configureDefaultAudioRoute()
        }else{
            @Suppress("DEPRECATION") run{am.isSpeakerphoneOn=speaker.value}
        }
    }

    private fun startIncomingRingtone(){
        runCatching{
            ringtone=RingtoneManager.getRingtone(this,RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE))
            ringtone?.play()
        }
    }
    private fun startOutgoingRingback(){
        if(ringback!=null)return
        runCatching{
            ringback=ToneGenerator(AudioManager.STREAM_VOICE_CALL,65)
            ringback?.startTone(ToneGenerator.TONE_SUP_RINGTONE)
        }
    }
    private fun stopTones(){
        runCatching{ringtone?.stop()};ringtone=null
        runCatching{ringback?.stopTone()};runCatching{ringback?.release()};ringback=null
    }

    private fun endCall():()->Unit = {
        stopTones();timerJob?.cancel();timeoutJob?.cancel()
        room?.disconnect()
        lifecycleScope.launch{if(callId.isNotBlank())runCatching{Api(SessionStore(this@LemmiqCallActivity)).endCall(callId)}}
        finish()
    }

    override fun onDestroy(){
        stopTones();timerJob?.cancel();timeoutJob?.cancel();room?.disconnect()
        val am=getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if(Build.VERSION.SDK_INT>=31)runCatching{am.clearCommunicationDevice()}
        am.mode=AudioManager.MODE_NORMAL
        super.onDestroy()
    }

    private fun formatSeconds(v:Int)=String.format("%02d:%02d",v/60,v%60)
}
