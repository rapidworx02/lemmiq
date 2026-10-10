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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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
import io.livekit.android.compose.VideoRenderer
import io.livekit.android.events.RoomEvent
import io.livekit.android.events.collect
import io.livekit.android.room.Room
import io.livekit.android.room.track.LocalVideoTrack
import io.livekit.android.room.track.Track
import io.livekit.android.room.track.VideoTrack
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class LemmiqCallActivity:ComponentActivity(){
    private var room:Room?=null
    private var callId=""
    private var wsUrl=""
    private var token=""
    private var person="LEMMIQ user"
    private var avatarUrl:String?=null
    private var incoming=false
    private var callType="VOICE"
    private var ringtone:Ringtone?=null
    private var ringback:ToneGenerator?=null
    private var timerJob:Job?=null
    private var timeoutJob:Job?=null
    private var stateJob:Job?=null
    @Volatile private var closing=false
    private val status=mutableStateOf("Preparing call…")
    private val seconds=mutableIntStateOf(0)
    private val muted=mutableStateOf(false)
    private val speaker=mutableStateOf(false)
    private val cameraEnabled=mutableStateOf(false)
    private val remoteVideo=mutableStateOf<VideoTrack?>(null)
    private val localVideo=mutableStateOf<LocalVideoTrack?>(null)

    private val mediaPermission=registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()){grants->
        val micOk=ContextCompat.checkSelfPermission(this,Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED
        val camOk=ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED
        if(!micOk){status.value="Microphone permission is required";return@registerForActivityResult}
        if(isVideoCall()&&!camOk)status.value="Connecting with camera off…"
        connectRoom()
    }

    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState)
        callId=intent.getStringExtra("call_id").orEmpty()
        wsUrl=intent.getStringExtra("ws_url").orEmpty()
        token=intent.getStringExtra("token").orEmpty()
        person=intent.getStringExtra("person")?:"LEMMIQ user"
        avatarUrl=intent.getStringExtra("avatar_url")?.takeIf{it.isNotBlank()}
        incoming=intent.getBooleanExtra("incoming",false)
        callType=intent.getStringExtra("call_type")?.uppercase()?.takeIf{it in setOf("VOICE","VIDEO")}?:"VOICE"
        status.value=if(incoming && token.isBlank())"Incoming ${if(isVideoCall())"video" else "voice"} call" else "Ringing…"

        configureDefaultAudioRoute()
        if(incoming && token.isBlank())startIncomingRingtone() else startOutgoingRingback()
        if(callId.isNotBlank())startCallStateWatch()

        setContent{
            MaterialTheme{
                if(isVideoCall()) VideoCallUi() else VoiceCallUi()
            }
        }

        if(!incoming || token.isNotBlank())ensureMediaPermissions()
    }

    @Composable
    private fun VoiceCallUi(){
        Box(
            Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF17102D),Color(0xFF080A16)))),
            contentAlignment=Alignment.Center
        ){
            Column(horizontalAlignment=Alignment.CenterHorizontally,modifier=Modifier.padding(28.dp)){
                PersonAvatar(92)
                Spacer(Modifier.height(20.dp))
                Text(person,fontSize=28.sp,color=Color.White,fontWeight=FontWeight.Bold)
                Text(status.value,color=Color(0xFFC5C0D7),modifier=Modifier.padding(top=8.dp))
                if(status.value=="Connected")Text(formatSeconds(seconds.intValue),color=Color.White,fontSize=18.sp,modifier=Modifier.padding(top=6.dp))
                Spacer(Modifier.height(34.dp))
                CallControls(video=false)
                Spacer(Modifier.height(22.dp))
                Text("LEMMIQ V${BuildConfig.VERSION_NAME} · LiveKit/WebRTC",color=Color(0xFF8E89A5),fontSize=11.sp)
            }
        }
    }

    @Composable
    private fun VideoCallUi(){
        Box(Modifier.fillMaxSize().background(Color(0xFF090A10))){
            val r=room
            if(r!=null && remoteVideo.value!=null){
                VideoRenderer(room=r,videoTrack=remoteVideo.value,modifier=Modifier.fillMaxSize(),mirror=false)
            }else{
                Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF17102D),Color(0xFF080A16)))),contentAlignment=Alignment.Center){
                    Column(horizontalAlignment=Alignment.CenterHorizontally){
                        PersonAvatar(92)
                        Spacer(Modifier.height(16.dp))
                        Text(person,fontSize=27.sp,color=Color.White,fontWeight=FontWeight.Bold)
                        Text(status.value,color=Color(0xFFC5C0D7),modifier=Modifier.padding(top=7.dp))
                    }
                }
            }
            if(r!=null && localVideo.value!=null && cameraEnabled.value){
                Surface(
                    modifier=Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(14.dp).size(width=116.dp,height=164.dp),
                    shape=RoundedCornerShape(18.dp),shadowElevation=8.dp,color=Color.Black
                ){
                    VideoRenderer(room=r,videoTrack=localVideo.value,modifier=Modifier.fillMaxSize(),mirror=true)
                }
            }
            Column(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().background(Color.Black.copy(alpha=.44f)).navigationBarsPadding().padding(16.dp),
                horizontalAlignment=Alignment.CenterHorizontally
            ){
                Text(status.value,color=Color.White,fontWeight=FontWeight.Bold)
                if(status.value=="Connected")Text(formatSeconds(seconds.intValue),color=Color.White.copy(alpha=.8f),fontSize=12.sp)
                Spacer(Modifier.height(12.dp))
                CallControls(video=true)
            }
        }
    }

    @Composable
    private fun PersonAvatar(size:Int){
        val resolvedAvatar=avatarUrl?.let{if(it.startsWith("http"))it else "${BuildConfig.API_BASE_URL.trimEnd('/')}$it"}
        if(resolvedAvatar!=null){
            AsyncImage(model=resolvedAvatar,contentDescription=person,
                modifier=Modifier.size(size.dp).clip(CircleShape).background(Color(0xFF6C4DFF)))
        }else{
            Box(Modifier.size(size.dp).clip(CircleShape).background(Color(0xFF6C4DFF)),contentAlignment=Alignment.Center){
                Text(person.take(1).uppercase(),fontSize=(size/2.2f).sp,color=Color.White)
            }
        }
    }

    @Composable
    private fun CallControls(video:Boolean){
        if(incoming && token.isBlank()){
            Row(horizontalArrangement=Arrangement.spacedBy(18.dp)){
                Button(onClick={answer()}){Text(if(video)"Answer video" else "Answer")}
                Button(onClick={decline()},colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFD13B50))){Text("Decline")}
            }
            return
        }
        Row(horizontalArrangement=Arrangement.spacedBy(12.dp),verticalAlignment=Alignment.CenterVertically){
            FilledTonalButton(onClick={
                muted.value=!muted.value
                lifecycleScope.launch{room?.localParticipant?.setMicrophoneEnabled(!muted.value)}
            },shape=CircleShape,modifier=Modifier.size(58.dp)){Text(if(muted.value)"🔇" else "🎙",fontSize=18.sp)}
            if(video){
                FilledTonalButton(onClick={toggleCamera()},shape=CircleShape,modifier=Modifier.size(58.dp)){Text(if(cameraEnabled.value)"📷" else "🚫",fontSize=17.sp)}
                FilledTonalButton(onClick={flipCamera()},enabled=cameraEnabled.value,shape=CircleShape,modifier=Modifier.size(58.dp)){Text("🔄",fontSize=17.sp)}
            }
            FilledTonalButton(onClick={toggleSpeaker()},shape=CircleShape,modifier=Modifier.size(58.dp)){Text(if(speaker.value)"🔊" else "📱",fontSize=18.sp)}
            Button(onClick=endCall(),shape=CircleShape,modifier=Modifier.size(58.dp),colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFD13B50))){Text("☎",fontSize=18.sp)}
        }
    }

    private fun isVideoCall()=callType.equals("VIDEO",true)

    private fun answer(){
        if(closing || CallDeclineV2102.isTerminal(callId))return
        stopTones();cancelCallNotification()
        lifecycleScope.launch{
            try{
                val join=Api(SessionStore(this@LemmiqCallActivity)).joinCall(callId)
                wsUrl=join.ws_url;token=join.token;callType=join.call.call_type.uppercase();incoming=false;status.value="Connecting…";ensureMediaPermissions()
            }catch(e:Exception){
                status.value=e.message?:"Call failed"
                if((e.message?:"").contains("declined",true)||(e.message?:"").contains("ended",true)){
                    closing=true;delay(500);finish()
                }
            }
        }
    }

    private fun decline():()->Unit = {
        if(!closing){
            closing=true;status.value="Declined";stopTones();stateJob?.cancel();timerJob?.cancel();timeoutJob?.cancel();cancelCallNotification()
            lifecycleScope.launch{
                CallDeclineV2102.decline(
                    callId=callId,
                    stopRingingImmediately={stopTones();cancelCallNotification()},
                    backendDecline={id->Api(SessionStore(this@LemmiqCallActivity)).declineCall(id)},
                    disconnectRoomAndTracks={disconnectLocalRoom()},
                    releaseAudioFocus={
                        val am=getSystemService(Context.AUDIO_SERVICE) as AudioManager
                        if(Build.VERSION.SDK_INT>=31)runCatching{am.clearCommunicationDevice()}
                        am.mode=AudioManager.MODE_NORMAL
                    },
                    cancelTimersAndListeners={timerJob?.cancel();timeoutJob?.cancel();stateJob?.cancel()},
                    stopCallForegroundService={},closeIncomingCallUi={finish()},onBackendFailure={status.value="Declined"}
                )
            }
        }
    }

    private fun ensureMediaPermissions(){
        val needed=buildList{
            if(ContextCompat.checkSelfPermission(this@LemmiqCallActivity,Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED)add(Manifest.permission.RECORD_AUDIO)
            if(isVideoCall()&&ContextCompat.checkSelfPermission(this@LemmiqCallActivity,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)add(Manifest.permission.CAMERA)
        }
        if(needed.isEmpty())connectRoom() else mediaPermission.launch(needed.toTypedArray())
    }

    private fun connectRoom(){
        if(closing || CallDeclineV2102.isTerminal(callId))return
        if(wsUrl.isBlank()||token.isBlank()){status.value="Call credentials unavailable";return}
        lifecycleScope.launch{
            try{
                room=LiveKit.create(applicationContext)
                val r=room!!
                r.audioSwitchHandler?.preferredDeviceList=listOf(AudioDevice.BluetoothHeadset::class.java,AudioDevice.WiredHeadset::class.java,AudioDevice.Earpiece::class.java,AudioDevice.Speakerphone::class.java)
                launch{
                    r.events.collect{event->
                        when(event){
                            is RoomEvent.ParticipantConnected -> onAnswered()
                            is RoomEvent.TrackSubscribed -> if(event.track is VideoTrack){remoteVideo.value=event.track as VideoTrack;onAnswered()}
                            is RoomEvent.TrackUnsubscribed -> if(event.track===remoteVideo.value)remoteVideo.value=null
                            is RoomEvent.ParticipantDisconnected -> if(status.value=="Connected"){status.value="Call ended";finishAfterRemoteEnd("Call ended")}
                            else -> Unit
                        }
                    }
                }
                r.connect(wsUrl,token)
                r.localParticipant.setMicrophoneEnabled(true)
                if(isVideoCall() && ContextCompat.checkSelfPermission(this@LemmiqCallActivity,Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED){
                    cameraEnabled.value=r.localParticipant.setCameraEnabled(true)
                    localVideo.value=r.localParticipant.getTrackPublication(Track.Source.CAMERA)?.track as? LocalVideoTrack
                }
                remoteVideo.value=r.remoteParticipants.values.firstOrNull()?.getTrackPublication(Track.Source.CAMERA)?.track as? VideoTrack
                if(incoming || r.remoteParticipants.isNotEmpty())onAnswered()
                else{
                    status.value="Ringing…";startOutgoingRingback();timeoutJob?.cancel();timeoutJob=lifecycleScope.launch{
                        delay(45000)
                        if(status.value=="Ringing…"&&!closing){closing=true;status.value="No answer";stopTones();runCatching{Api(SessionStore(this@LemmiqCallActivity)).endCall(callId)};disconnectLocalRoom();delay(700);finish()}
                    }
                }
            }catch(e:Exception){stopTones();status.value=e.message?:"Connection failed"}
        }
    }

    private fun toggleCamera():()->Unit={
        lifecycleScope.launch{
            val r=room?:return@launch
            if(ContextCompat.checkSelfPermission(this@LemmiqCallActivity,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){mediaPermission.launch(arrayOf(Manifest.permission.CAMERA));return@launch}
            val next=!cameraEnabled.value
            cameraEnabled.value=r.localParticipant.setCameraEnabled(next)
            localVideo.value=if(cameraEnabled.value)r.localParticipant.getTrackPublication(Track.Source.CAMERA)?.track as? LocalVideoTrack else null
        }
    }
    private fun flipCamera():()->Unit={
        (room?.localParticipant?.getTrackPublication(Track.Source.CAMERA)?.track as? LocalVideoTrack)?.switchCamera()
    }

    private fun onAnswered(){
        if(closing || CallDeclineV2102.isTerminal(callId) || status.value=="Connected")return
        stopTones();timeoutJob?.cancel();status.value="Connected";seconds.intValue=0
        timerJob?.cancel();timerJob=lifecycleScope.launch{while(true){delay(1000);seconds.intValue++}}
    }

    private fun configureDefaultAudioRoute(){
        val am=getSystemService(Context.AUDIO_SERVICE) as AudioManager
        am.mode=AudioManager.MODE_IN_COMMUNICATION;speaker.value=isVideoCall()
        if(Build.VERSION.SDK_INT>=31){
            val devices=am.availableCommunicationDevices
            val bluetooth=devices.firstOrNull{it.type==AudioDeviceInfo.TYPE_BLUETOOTH_SCO || it.type==AudioDeviceInfo.TYPE_BLE_HEADSET}
            val preferred=if(isVideoCall())devices.firstOrNull{it.type==AudioDeviceInfo.TYPE_BUILTIN_SPEAKER} else devices.firstOrNull{it.type==AudioDeviceInfo.TYPE_BUILTIN_EARPIECE}
            when{bluetooth!=null->am.setCommunicationDevice(bluetooth);preferred!=null->am.setCommunicationDevice(preferred)}
        }else{@Suppress("DEPRECATION") run{am.isSpeakerphoneOn=isVideoCall()}}
    }

    private fun toggleSpeaker(){
        val handler=room?.audioSwitchHandler;speaker.value=!speaker.value
        if(handler!=null){
            if(speaker.value)handler.availableAudioDevices.firstOrNull{it is AudioDevice.Speakerphone}?.let{handler.selectDevice(it)}
            else{handler.selectDevice(null);handler.preferredDeviceList=listOf(AudioDevice.BluetoothHeadset::class.java,AudioDevice.WiredHeadset::class.java,AudioDevice.Earpiece::class.java,AudioDevice.Speakerphone::class.java)}
            return
        }
        val am=getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if(Build.VERSION.SDK_INT>=31){if(speaker.value)am.availableCommunicationDevices.firstOrNull{it.type==AudioDeviceInfo.TYPE_BUILTIN_SPEAKER}?.let{am.setCommunicationDevice(it)} else configureDefaultAudioRoute()}
        else{@Suppress("DEPRECATION") run{am.isSpeakerphoneOn=speaker.value}}
    }

    private fun startIncomingRingtone(){runCatching{ringtone=RingtoneManager.getRingtone(this,RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE));ringtone?.play()}}
    private fun startOutgoingRingback(){if(ringback!=null)return;runCatching{ringback=ToneGenerator(AudioManager.STREAM_VOICE_CALL,65);ringback?.startTone(ToneGenerator.TONE_SUP_RINGTONE)}}
    private fun stopTones(){runCatching{ringtone?.stop()};ringtone=null;runCatching{ringback?.stopTone()};runCatching{ringback?.release()};ringback=null}

    private fun startCallStateWatch(){
        stateJob?.cancel();stateJob=lifecycleScope.launch{
            val api=Api(SessionStore(this@LemmiqCallActivity))
            while(!closing&&callId.isNotBlank()){
                delay(900);val current=runCatching{api.callDetail(callId)}.getOrNull()?:continue
                callType=current.call_type.uppercase()
                when(current.status.uppercase()){
                    "CONNECTED" -> if(!incoming && status.value!="Connected")onAnswered()
                    "DECLINED" -> {finishAfterRemoteEnd("Declined");break}
                    "MISSED" -> {finishAfterRemoteEnd("No answer");break}
                    "ENDED","FAILED" -> {finishAfterRemoteEnd("Call ended");break}
                }
            }
        }
    }

    private fun finishAfterRemoteEnd(label:String){if(closing)return;closing=true;status.value=label;stopTones();timerJob?.cancel();timeoutJob?.cancel();cancelCallNotification();lifecycleScope.launch{disconnectLocalRoom();delay(450);finish()}}

    private suspend fun disconnectLocalRoom(){
        val r=room
        runCatching{r?.localParticipant?.setCameraEnabled(false)}
        runCatching{r?.localParticipant?.setMicrophoneEnabled(false)}
        remoteVideo.value=null;localVideo.value=null;cameraEnabled.value=false
        runCatching{r?.disconnect()};room=null
    }

    private fun cancelCallNotification(){if(callId.isNotBlank())runCatching{getSystemService(android.app.NotificationManager::class.java).cancel(callId.hashCode())}}
    private fun endCall():()->Unit={if(!closing){closing=true;stopTones();timerJob?.cancel();timeoutJob?.cancel();stateJob?.cancel();cancelCallNotification();lifecycleScope.launch{disconnectLocalRoom();if(callId.isNotBlank())runCatching{Api(SessionStore(this@LemmiqCallActivity)).endCall(callId)};finish()}}}

    override fun onDestroy(){stopTones();timerJob?.cancel();timeoutJob?.cancel();stateJob?.cancel();room?.disconnect();room=null;val am=getSystemService(Context.AUDIO_SERVICE) as AudioManager;if(Build.VERSION.SDK_INT>=31)runCatching{am.clearCommunicationDevice()};am.mode=AudioManager.MODE_NORMAL;super.onDestroy()}
    private fun formatSeconds(v:Int)=String.format("%02d:%02d",v/60,v%60)
}
