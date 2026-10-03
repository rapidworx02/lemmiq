package com.lemmiq.app

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.google.gson.Gson
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Date
import java.util.Locale
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Explicit, separate consent. External messages never enter the Money/Activity cloud sync. */
object ExternalConsent {
    private const val PREF="lemmiq_external_chat_v17"
    private fun p(c:Context)=c.getSharedPreferences(PREF,Context.MODE_PRIVATE)
    fun enabled(c:Context)=p(c).getBoolean("enabled",false)
    fun source(c:Context,name:String)=p(c).getBoolean("source_$name",false)
    fun includeInQ(c:Context)=p(c).getBoolean("q",false)
    fun days(c:Context)=p(c).getInt("days",7)
    fun setEnabled(c:Context,v:Boolean)=p(c).edit().putBoolean("enabled",v).apply()
    fun setSource(c:Context,name:String,v:Boolean)=p(c).edit().putBoolean("source_$name",v).apply()
    fun setQ(c:Context,v:Boolean)=p(c).edit().putBoolean("q",v).apply()
    fun setDays(c:Context,v:Int)=p(c).edit().putInt("days",v.coerceIn(1,30)).apply()
    fun sourceForPackage(pkg:String)=when(pkg){
        "com.whatsapp","com.whatsapp.w4b"->"WhatsApp"
        "com.google.android.apps.messaging","com.samsung.android.messaging","com.android.mms"->"SMS"
        else->null
    }
}

data class ExternalSnippet(
    val source:String,val contact:String,val text:String,val occurred_at:Long
)

/** Encrypted at rest via device Android Keystore. Nothing is uploaded unless user taps Ask/Suggest. */
private object ExternalCipher {
    private const val ALIAS="lemmiq_external_v17"
    private fun key():SecretKey {
        val ks=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
        val existing=ks.getKey(ALIAS,null) as? SecretKey
        if(existing!=null)return existing
        val generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).build())
        return generator.generateKey()
    }
    fun encrypt(value:String):String {
        val cipher=Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE,key())
        val data=cipher.iv+cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(data,Base64.NO_WRAP)
    }
    fun decrypt(value:String):String {
        val data=Base64.decode(value,Base64.NO_WRAP)
        val cipher=Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,data.copyOfRange(0,12)))
        return String(cipher.doFinal(data.copyOfRange(12,data.size)),Charsets.UTF_8)
    }
}

class ExternalChatDb(ctx:Context):SQLiteOpenHelper(ctx,"lemmiq_external_v17.db",null,1) {
    private val gson=Gson()
    override fun onCreate(db:SQLiteDatabase){
        db.execSQL("CREATE TABLE snippets(uid INTEGER NOT NULL, id TEXT NOT NULL, ts INTEGER NOT NULL, sealed TEXT NOT NULL, PRIMARY KEY(uid,id))")
        db.execSQL("CREATE INDEX idx_external_time ON snippets(uid,ts)")
    }
    override fun onUpgrade(db:SQLiteDatabase,oldVersion:Int,newVersion:Int){}
    fun save(uid:Int,notificationKey:String,item:ExternalSnippet){
        val text="${notificationKey}|${item.text}|${item.occurred_at/120000L}"
        val id=MessageDigest.getInstance("SHA-256").digest(text.toByteArray())
            .take(16).joinToString(""){"%02x".format(it)}
        val values=android.content.ContentValues().apply{
            put("uid",uid);put("id",id);put("ts",item.occurred_at)
            put("sealed",ExternalCipher.encrypt(gson.toJson(item)))
        }
        writableDatabase.insertWithOnConflict("snippets",null,values,SQLiteDatabase.CONFLICT_IGNORE)
    }
    fun list(uid:Int,days:Int):List<ExternalSnippet>{
        prune(uid,days)
        val output=mutableListOf<ExternalSnippet>()
        readableDatabase.query("snippets",arrayOf("sealed"),"uid=?",arrayOf(uid.toString()),null,null,"ts DESC","200").use{c->
            while(c.moveToNext()) runCatching{
                output.add(gson.fromJson(ExternalCipher.decrypt(c.getString(0)),ExternalSnippet::class.java))
            }
        }
        return output
    }
    fun prune(uid:Int,days:Int){
        val cutoff=System.currentTimeMillis()-days.coerceIn(1,30)*86_400_000L
        writableDatabase.delete("snippets","uid=? AND ts<?",arrayOf(uid.toString(),cutoff.toString()))
    }
    fun clear(uid:Int){writableDatabase.delete("snippets","uid=?",arrayOf(uid.toString()))}
}

object ExternalClassifier {
    private val blocked=Regex("(?i)(\\botp\\b|one.time.password|verification.code|security.code|\\b2fa\\b|reset.password|authenticat(?:ion|or)|passcode|\\bpin\\b|login.code|sign.in.code|\\bcvv\\b|your.code.is)")
    fun fromNotification(source:String,title:String,body:String,now:Long):ExternalSnippet? {
        val contact=title.trim().take(100)
        val text=body.trim().take(700)
        if(contact.isBlank() || text.isBlank() || blocked.containsMatchIn("$contact $text"))return null
        if(contact.equals("WhatsApp",true) || contact.equals("Messages",true) || contact.equals("New messages",true))return null
        // Group summary notifications and hidden previews are not conversation messages.
        if(text.equals("New message",true) || text.contains("new messages",true))return null
        return ExternalSnippet(source,contact,text,now)
    }
}
