package com.lemmiq.app

import android.content.Context
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.os.Build
import java.io.File

class LemmiqVoiceRecorder(private val ctx:Context){
    private var recorder:MediaRecorder?=null
    private var file:File?=null
    private var started:Long=0

    val recording:Boolean get()=recorder!=null

    fun start(){
        if(recording)return
        val target=File(ctx.cacheDir,"voice_${System.currentTimeMillis()}.m4a")
        val r=if(Build.VERSION.SDK_INT>=31) MediaRecorder(ctx) else @Suppress("DEPRECATION") MediaRecorder()
        r.setAudioSource(MediaRecorder.AudioSource.MIC)
        r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        r.setAudioEncodingBitRate(64000)
        r.setAudioSamplingRate(44100)
        r.setOutputFile(target.absolutePath)
        r.prepare();r.start()
        recorder=r;file=target;started=System.currentTimeMillis()
    }

    fun stop():Pair<File,Int>?{
        val r=recorder?:return null
        val f=file?:return null
        val duration=(System.currentTimeMillis()-started).toInt().coerceAtLeast(0)
        try{r.stop()}finally{r.release();recorder=null;file=null}
        return f to duration
    }

    fun cancel(){
        val r=recorder
        if(r!=null)runCatching{r.stop()};runCatching{r?.release()}
        recorder=null;file?.delete();file=null
    }
}

class LemmiqVoicePlayer(private val file:File){
    private var player:MediaPlayer?=null
    private var speed=1f
    fun play(onDone:()->Unit={}){
        release()
        player=MediaPlayer().apply{
            setDataSource(file.absolutePath)
            prepare()
            if(Build.VERSION.SDK_INT>=23)playbackParams=playbackParams.setSpeed(speed)
            setOnCompletionListener{onDone()}
            start()
        }
    }
    fun setSpeed(next:Float){speed=next;player?.let{if(Build.VERSION.SDK_INT>=23)it.playbackParams=it.playbackParams.setSpeed(speed)}}
    fun release(){runCatching{player?.release()};player=null}
}
