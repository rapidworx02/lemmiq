package com.lemmiq.app

import android.app.Notification
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.os.Build
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import androidx.core.app.NotificationManagerCompat
import java.security.MessageDigest
import java.util.Date
import java.util.Locale
import java.text.SimpleDateFormat

/** Nothing is collected without explicit user opt-in and per-app allowlisting. */
object NotificationControl {
    private const val PREF = "lemmiq_notification_controls"
    val categories = listOf("MONEY", "BILL", "DELIVERY", "WORK", "TRAVEL", "TRUST")
    fun prefs(ctx:Context) = ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE)
    fun enabled(ctx:Context)=prefs(ctx).getBoolean("capture",false)
    fun sync(ctx:Context)=prefs(ctx).getBoolean("sync",false)
    fun keepDays(ctx:Context)=prefs(ctx).getInt("retention_days",7)
    fun allowedApps(ctx:Context)=prefs(ctx).getStringSet("apps",emptySet())?.toSet()?:emptySet()
    fun allowedCategories(ctx:Context)=prefs(ctx).getStringSet("categories",emptySet())?.toSet()?:emptySet()
    fun setCapture(ctx:Context,v:Boolean)=prefs(ctx).edit().putBoolean("capture",v).apply()
    fun setSync(ctx:Context,v:Boolean)=prefs(ctx).edit().putBoolean("sync",v).apply()
    fun setDays(ctx:Context,v:Int)=prefs(ctx).edit().putInt("retention_days",v.coerceIn(1,30)).apply()
    fun setApp(ctx:Context,pkg:String,on:Boolean){
        val values=allowedApps(ctx).toMutableSet();if(on)values.add(pkg) else values.remove(pkg)
        prefs(ctx).edit().putStringSet("apps",values).apply()
    }
    fun setCategory(ctx:Context,cat:String,on:Boolean){
        val values=allowedCategories(ctx).toMutableSet();if(on)values.add(cat) else values.remove(cat)
        prefs(ctx).edit().putStringSet("categories",values).apply()
    }
    fun hasSystemAccess(ctx:Context)=NotificationManagerCompat.getEnabledListenerPackages(ctx).contains(ctx.packageName)
    fun appChoices(ctx:Context):List<AppChoice>{
        val pm=ctx.packageManager
        val intent=Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        @Suppress("DEPRECATION")
        val results=pm.queryIntentActivities(intent, PackageManager.MATCH_ALL)
        return results.mapNotNull { r->
            val pkg=r.activityInfo?.packageName?:return@mapNotNull null
            if(pkg==ctx.packageName)return@mapNotNull null
            AppChoice(pkg,r.loadLabel(pm).toString())
        }.distinctBy { it.pkg }.sortedBy { it.name.lowercase() }
    }
}

data class AppChoice(val pkg:String,val name:String)
data class PhoneEvent(
    val client_event_id:String, val category:String,val source:String,val title:String,
    val detail:String, val amount_cents:Long?,val direction:String,val occurred_at:String,
    val synced:Boolean=false
)

/** Conservative local heuristics, NEVER a verified bank transaction feed. */
object LocalClassifier {
    private val money = Regex("(?:A\\$|AUD\\s*|\\$\\s*)([0-9]{1,9}(?:,[0-9]{3})*(?:\\.[0-9]{2})?)",RegexOption.IGNORE_CASE)
    private val extraAmount=Regex("([0-9]{1,9}(?:\\.[0-9]{2})?)\\s*AUD",RegexOption.IGNORE_CASE)
    private val blocked=Regex("(?i)(\\botp\\b|one.time.password|verification.code|security.code|\\b2fa\\b|reset.password|authenticat(?:ion|or)|passcode|\\bpin\\b|login.code|sign.in.code|\\bCVV\\b|your.code.is)")
    private val redactEmail=Regex("[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}")
    private val redactUrl=Regex("https?://\\S+",RegexOption.IGNORE_CASE)
    private val redactNumber=Regex("\\b[0-9]{7,}\\b")
    fun classify(title:String,body:String,app:String,whenMs:Long,key:String,selected:Set<String>):PhoneEvent? {
        val text="$title $body".trim()
        if(text.isBlank() || blocked.containsMatchIn(text)) return null
        val lower=text.lowercase(Locale.ROOT)
        // Prevent non-payment alerts (balances, due bills) being counted as spending.
        val bill=listOf("due date","payment due","bill due","renewal","expires tomorrow","due tomorrow","invoice due").any{it in lower}
        val delivery=listOf("out for delivery","delivered","parcel","tracking update","order shipped","dispatch","shipment").any{it in lower}
        val travel=listOf("flight","boarding","gate change","hotel booking","train delayed").any{it in lower}
        val work=listOf("meeting","calendar invite","appointment","rescheduled","schedule changed").any{it in lower}
        val trust=listOf("account suspended","click immediately","prize winner","urgent payment","unpaid toll").any{it in lower}
        val financial=listOf("paid ","purchase","transaction","spent ","debited","credited","card ending","payment of","payment at","received ","transfer of","refund").any{it in lower}
        val value=money.find(text)?.groupValues?.getOrNull(1) ?: extraAmount.find(text)?.groupValues?.getOrNull(1)
        val cents=value?.replace(",","")?.toBigDecimalOrNull()?.multiply(java.math.BigDecimal(100))?.toLong()
        val cat=when {
            bill->"BILL"
            financial && cents!=null->"MONEY"
            delivery->"DELIVERY"
            travel->"TRAVEL"
            work->"WORK"
            trust->"TRUST"
            else->return null // No broad notification harvesting.
        }
        if(cat !in selected)return null
        val direction=if(cat=="MONEY") {
            if(listOf("credited","received ","refund","deposit").any{it in lower}) "IN" else "OUT"
        } else "UNKNOWN"
        val merchant=if(cat=="MONEY"){
            Regex("""(?i)\b(?:at|to|from)\s+([A-Za-z][A-Za-z0-9 &'\-]{1,35})""")
                .find(text)?.groupValues?.getOrNull(1)?.trim()?.take(36)
        }else null
        val label=when(cat) {
            "MONEY"->(if(direction=="IN")"Detected incoming payment" else "Detected spending") +
                (if(merchant.isNullOrEmpty())"" else " · $merchant")
            "BILL"->"Bill or renewal alert"
            "DELIVERY"->"Delivery update"
            "TRAVEL"->"Travel update"
            "WORK"->"Schedule update"
            else->"Potential scam signal"
        }
        val detail=if(cat=="MONEY") "Review this alert in $app" else body
            .replace(redactUrl,"[link hidden]").replace(redactEmail,"[email hidden]")
            .replace(redactNumber,"[number hidden]").take(180)
        val timeBucket=whenMs/120_000L
        val digest=MessageDigest.getInstance("SHA-256")
            .digest("$key|$cat|$value|$title|$body|$timeBucket".toByteArray())
            .take(20).joinToString(""){"%02x".format(it)}
        val iso=SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'",Locale.US).apply{
            timeZone=java.util.TimeZone.getTimeZone("UTC")}.format(Date(whenMs))
        return PhoneEvent(digest,cat,app.take(80),label,detail,cents,direction,iso)
    }
}

/** This small SQLite DB stores only selected, structured alerts; per account, not full notification history. */
class PhoneEventDb(ctx:Context):SQLiteOpenHelper(ctx,"lemmiq_phone_insights.db",null,1){
    override fun onCreate(db:SQLiteDatabase){
        db.execSQL("""CREATE TABLE events (
          id TEXT NOT NULL, uid INTEGER NOT NULL, category TEXT NOT NULL, source TEXT NOT NULL,
          title TEXT NOT NULL, detail TEXT NOT NULL, amount INTEGER, direction TEXT NOT NULL,
          occurred TEXT NOT NULL, saved_ms INTEGER NOT NULL, synced INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(id,uid))""")
        db.execSQL("CREATE INDEX idx_event_user_time ON events(uid,saved_ms)")
    }
    override fun onUpgrade(db:SQLiteDatabase,oldVersion:Int,newVersion:Int) {}
    fun insert(uid:Int,e:PhoneEvent) {
        val values=android.content.ContentValues().apply{
            put("id",e.client_event_id);put("uid",uid);put("category",e.category)
            put("source",e.source);put("title",e.title);put("detail",e.detail)
            if(e.amount_cents!=null)put("amount",e.amount_cents) else putNull("amount")
            put("direction",e.direction);put("occurred",e.occurred_at);put("saved_ms",System.currentTimeMillis())
        }
        writableDatabase.insertWithOnConflict("events",null,values,SQLiteDatabase.CONFLICT_IGNORE)
    }
    fun list(uid:Int,days:Int=30,pendingOnly:Boolean=false):List<PhoneEvent>{
        val out=mutableListOf<PhoneEvent>()
        val cutoff=(System.currentTimeMillis()-days.coerceIn(1,30)*86_400_000L).toString()
        val where="uid=? AND saved_ms>=?"+(if(pendingOnly)" AND synced=0" else "")
        readableDatabase.query("events",null,where,arrayOf(uid.toString(),cutoff),null,null,"saved_ms DESC","250").use {c->
            val get={col:String->c.getColumnIndexOrThrow(col)}
            while(c.moveToNext())out+=PhoneEvent(
                c.getString(get("id")),c.getString(get("category")),c.getString(get("source")),
                c.getString(get("title")),c.getString(get("detail")),
                if(c.isNull(get("amount")))null else c.getLong(get("amount")),
                c.getString(get("direction")),c.getString(get("occurred")),c.getInt(get("synced"))==1)
        }
        return out
    }
    fun markSynced(uid:Int,id:String){
        val v=android.content.ContentValues().apply{put("synced",1)}
        writableDatabase.update("events",v,"uid=? AND id=?",arrayOf(uid.toString(),id))
    }
    fun prune(days:Int){
        val before=(System.currentTimeMillis()-days.coerceIn(1,30)*86_400_000L).toString()
        writableDatabase.delete("events","saved_ms<?",arrayOf(before))
    }
    fun clear(uid:Int){writableDatabase.delete("events","uid=?",arrayOf(uid.toString()))}
}

class LemmiqNotificationListener:NotificationListenerService(){
    override fun onNotificationPosted(sbn:StatusBarNotification){
        try {
            if(!NotificationControl.enabled(this) || !NotificationControl.hasSystemAccess(this)) return
            val session=SessionStore(this)
            if(session.token.isNullOrEmpty()||session.userId<1)return
            if(sbn.packageName !in NotificationControl.allowedApps(this))return
            if(sbn.packageName==packageName)return
            if(sbn.notification.flags and Notification.FLAG_GROUP_SUMMARY!=0)return
            val extras=sbn.notification.extras
            val title=extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
            val body=(extras.getCharSequence(Notification.EXTRA_BIG_TEXT)
              ?:extras.getCharSequence(Notification.EXTRA_TEXT))?.toString().orEmpty()
            @Suppress("DEPRECATION") val label=runCatching{packageManager.getApplicationLabel(
               packageManager.getApplicationInfo(sbn.packageName,0)).toString()}.getOrDefault(sbn.packageName)
            val e=LocalClassifier.classify(title,body,label,sbn.postTime,sbn.key,
                NotificationControl.allowedCategories(this))?:return
            PhoneEventDb(this).use{db->db.prune(NotificationControl.keepDays(this));db.insert(session.userId,e)}
        } catch(_:Exception){ /* Never crash the system notification listener. */ }
    }
}
