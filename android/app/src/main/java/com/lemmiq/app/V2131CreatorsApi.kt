/* V21356_STUDIO_DELETE */
package com.lemmiq.app

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okio.BufferedSink
import okio.source
import java.io.IOException
import java.io.File
import java.net.URLEncoder
import java.util.UUID
import java.util.concurrent.TimeUnit

/** Native LEMMIQ V2.13.1 creator client. Reuses the existing signed-in SessionStore.
 * Never stores the bearer token in a creator profile, public URL or media URL.
 */
internal class CreatorApiV2131(private val context: Context, private val session: SessionStore) {
    private val base = BuildConfig.API_BASE_URL.trimEnd('/')
    private val gson = Gson()
    private val json = "application/json; charset=utf-8".toMediaType()
    private val http = OkHttpClient.Builder().connectTimeout(25, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS).callTimeout(180, TimeUnit.SECONDS).build()

    fun requestKey(): String = UUID.randomUUID().toString()

    private fun builder(path: String): Request.Builder {
        require(path.startsWith("/v213/") || path.startsWith("/v2131/")) { "Unexpected creator API path" }
        val token = session.token ?: error("Sign in to LEMMIQ again")
        return Request.Builder().url(base + path).header("Authorization", "Bearer $token")
            .header("Cache-Control", "no-store")
    }

    private suspend fun raw(request: Request): String = withContext(Dispatchers.IO) {
        http.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val detail = runCatching {
                    val e = JsonParser.parseString(text).asJsonObject.get("detail")
                    when {
                        e == null || e.isJsonNull -> null
                        e.isJsonPrimitive -> e.asString
                        else -> e.toString()
                    }
                }.getOrNull()
                throw IOException(detail ?: "LEMMIQ server HTTP ${response.code}")
            }
            text
        }
    }

    private suspend fun get(path: String): String = raw(builder(path).get().build())
    private suspend fun write(path: String, data: Any, method: String = "POST"): String {
        val payload = gson.toJson(data).toRequestBody(json)
        val b = builder(path)
        return raw((if (method == "PUT") b.put(payload) else b.post(payload)).build())
    }
    private inline fun <reified T> parse(source: String): T = gson.fromJson(source, object : TypeToken<T>() {}.type)

    suspend fun config(): CreatorConfigNative = parse(get("/v213/creators/config"))
    suspend fun discover(q: String = "", category: String = "", following: Boolean = false): List<CreatorProfileNative> =
        parse(get("/v213/creators/discover?qtext=${enc(q)}&category=${enc(category)}&following=$following&limit=75"))
    suspend fun mine(): CreatorMineNative = parse(get("/v213/creators/me"))
    suspend fun profile(id: Int): CreatorPageNative = parse(get("/v213/creators/profile/$id"))
    suspend fun follow(id: Int): Unit { write("/v213/creators/profile/$id/follow", emptyMap<String, String>()) }
    suspend fun unfollow(id: Int): Unit { raw(builder("/v213/creators/profile/$id/follow").delete().build()) }
    suspend fun saveProfile(profile: Map<String, Any>): CreatorProfileNative = parse(write("/v213/creators/me", profile, "PUT"))
    suspend fun subscribe(id: Int): JsonObject = parse(write("/v213/creators/profile/$id/subscribe", mapOf("request_key" to requestKey())))
    suspend fun unlockPost(id: Int): JsonObject = parse(write("/v213/creators/posts/$id/unlock", mapOf("request_key" to requestKey())))
    suspend fun tip(id: Int, q: Double): JsonObject = parse(write("/v213/creators/profile/$id/tip", mapOf("request_key" to requestKey(), "amount_q" to q)))
    suspend fun request(id: Int, kind: String, message: String, scheduledAt: String? = null): CreatorRequestNative {
        val body = mutableMapOf<String, Any>("request_key" to requestKey(), "kind" to kind, "message" to message)
        if (scheduledAt != null) body["scheduled_at"] = scheduledAt
        return parse(write("/v213/creators/profile/$id/request", body))
    }
    suspend fun requests(): List<CreatorRequestNative> = parse(get("/v213/creators/requests"))
    suspend fun requestAction(id: Int, action: String, reply: String = ""): CreatorRequestNative =
        parse(write("/v213/creators/requests/$id/action", mapOf("action" to action, "reply" to reply)))
    suspend fun earnings(): CreatorEarningsNative = parse(get("/v213/creators/earnings"))
    suspend fun transfer(q: Double): JsonObject = parse(write("/v213/creators/earnings/transfer", mapOf("amount_q" to q)))
    suspend fun createPost(title: String, teaser: String, body: String, visibility: String, priceQ: Double, level: String): CreatorPostNative =
        parse(write("/v213/creators/posts", mapOf("title" to title, "teaser" to teaser, "body" to body,
            "visibility" to visibility, "price_q" to priceQ, "level" to level)))

    suspend fun deleteLibraryAsset(id: Int): Unit { raw(builder("/v2131/exclusives/library/$id").delete().build()) }
    suspend fun deleteGalleryItem(id: Int): Unit { raw(builder("/v2131/exclusives/gallery/$id").delete().build()) }
    suspend fun library(): List<CreatorAssetNative> = parse(get("/v2131/exclusives/library"))
    suspend fun galleryMine(): List<CreatorGalleryNative> = parse(get("/v2131/exclusives/gallery/mine"))
    suspend fun gallery(id: Int): List<CreatorGalleryNative> = parse(get("/v2131/exclusives/profile/$id/gallery"))
    suspend fun galleryAssets(id: Int): List<CreatorGalleryAssetNative> = parse(get("/v2131/exclusives/gallery/$id/assets"))
    suspend fun createGallery(title: String, teaser: String, kind: String, visibility: String, price: Double, assetIds: List<Int>): CreatorGalleryNative =
        parse(write("/v2131/exclusives/gallery", mapOf("title" to title, "teaser" to teaser,
            "kind" to kind, "visibility" to visibility, "price_q" to price, "asset_ids" to assetIds)))
    suspend fun unlockGallery(id: Int): JsonObject = parse(write("/v2131/exclusives/gallery/$id/unlock", mapOf("request_key" to requestKey())))
    suspend fun chatOffer(id: Int, galleryId: Int, price: Double): CreatorOfferNative =
        parse(write("/v2131/exclusives/chats/$id/offers", mapOf("item_id" to galleryId, "price_q" to price, "client_key" to requestKey())))
    suspend fun offer(id: Int): CreatorOfferNative = parse(get("/v2131/exclusives/offers/$id"))
    suspend fun unlockOffer(id: Int): JsonObject = parse(write("/v2131/exclusives/offers/$id/unlock", mapOf("request_key" to requestKey())))
    suspend fun offers(): List<CreatorOfferNative> = parse(get("/v2131/exclusives/offers/inbox"))

    private fun enc(t: String) = URLEncoder.encode(t, "UTF-8")

    /** Upload uses a streaming RequestBody rather than loading 100 MB videos into RAM. */
    suspend fun uploadAsset(uri: Uri, title: String, level: String): CreatorAssetNative =
        parse(upload("/v2131/exclusives/library/upload", uri,
            mapOf("title" to title, "level" to level)))
    suspend fun uploadPostMedia(postId: Int, uri: Uri): JsonObject =
        parse(upload("/v213/creators/posts/$postId/media", uri, emptyMap()))

    private suspend fun upload(path: String, uri: Uri, fields: Map<String, String>): String = withContext(Dispatchers.IO) {
        val mime = context.contentResolver.getType(uri)?.lowercase()?.substringBefore(';')
            ?: throw IOException("Cannot determine photo/video type")
        // V21342_HEIC_TO_JPEG: many Android camera galleries return image/heic.
        // Decode through Android and encode as a bounded JPEG before uploading.
        if (mime in setOf("image/heic", "image/heif", "image/heic-sequence")) {
            if (android.os.Build.VERSION.SDK_INT < 28)
                throw IOException("HEIC conversion needs Android 9+. Export photo as JPEG.")
            val source = android.graphics.ImageDecoder.createSource(context.contentResolver, uri)
            val bmp = android.graphics.ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
                val width=info.size.width;val height=info.size.height
                val scale=maxOf(1.0, maxOf(width/2500.0,height/2500.0))
                decoder.setTargetSize(maxOf(1,(width/scale).toInt()),maxOf(1,(height/scale).toInt()))
            }
            val out = java.io.ByteArrayOutputStream()
            try { if(!bmp.compress(android.graphics.Bitmap.CompressFormat.JPEG,88,out))
                  throw IOException("Could not convert HEIC photo") }
            finally { bmp.recycle() }
            val jpg=out.toByteArray()
            if (jpg.size>20*1024*1024)throw IOException("Converted photo exceeds 20 MB")
            val form=MultipartBody.Builder().setType(MultipartBody.FORM)
            fields.forEach{(key,value)->form.addFormDataPart(key,value)}
            form.addFormDataPart("file", "creator_photo.jpg", jpg.toRequestBody("image/jpeg".toMediaType()))
            return@withContext raw(builder(path).post(form.build()).build())
        }
        if (mime !in setOf("image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm"))
            throw IOException("Choose JPG/PNG/WebP photos or MP4/WebM videos. Export MOV as MP4 before uploading.")
        val maxBytes = if (mime.startsWith("image/")) 20L * 1024 * 1024 else 100L * 1024 * 1024
        val length = runCatching {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { c ->
                if (c.moveToFirst()) c.getLong(0) else -1L
            } ?: -1L
        }.getOrDefault(-1L)
        if (length > maxBytes) throw IOException("Media exceeds LEMMIQ size limit")
        val streamingBody = object : RequestBody() {
            override fun contentType() = mime.toMediaType()
            override fun contentLength(): Long = if (length >= 0) length else -1L
            override fun writeTo(sink: BufferedSink) {
                context.contentResolver.openInputStream(uri)?.use { input ->
                    input.source().use { source ->
                        var total = 0L
                        val buffer = okio.Buffer()
                        while (true) {
                            val count = source.read(buffer, 65536)
                            if (count < 0) break
                            total += count
                            if (total > maxBytes) throw IOException("Media exceeds size limit")
                            sink.write(buffer, count)
                        }
                    }
                } ?: throw IOException("Cannot read selected media")
            }
        }
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
        fields.forEach { (key, value) -> form.addFormDataPart(key, value) }
        form.addFormDataPart("file", "creator_upload", streamingBody)
        raw(builder(path).post(form.build()).build())
    }

    /** Streams private videos into app-only cache, avoiding a 100 MB in-memory array. */
    suspend fun downloadVideo(path: String, cacheDir: File): Pair<File, String> = withContext(Dispatchers.IO) {
        val dir = File(cacheDir, "creator_private_view").apply { mkdirs() }
        dir.listFiles()?.filter { it.lastModified() < System.currentTimeMillis() - 3600000L }?.forEach { it.delete() }
        http.newCall(builder(path).get().build()).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Private video unavailable (${response.code})")
            val mime = response.header("Content-Type", "video/mp4")?.substringBefore(';') ?: "video/mp4"
            if (mime !in setOf("video/mp4", "video/webm", "video/quicktime")) throw IOException("Unexpected video media type")
            val ext = if (mime == "video/webm") ".webm" else if (mime == "video/quicktime") ".mov" else ".mp4"
            val output = File.createTempFile("creator_", ext, dir)
            try {
                val limit = 105L * 1024L * 1024L
                var total = 0L
                response.body?.byteStream()?.use { input ->
                    output.outputStream().use { dest ->
                        val buffer = ByteArray(65536)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            total += count
                            if (total > limit) throw IOException("Video exceeds size limit")
                            dest.write(buffer, 0, count)
                        }
                    }
                } ?: throw IOException("Missing video data")
                output to mime
            } catch (e: Exception) { output.delete(); throw e }
        }
    }

    /** Server authorises each media request. Locked files have no public URL. */
    suspend fun media(path: String, maxBytes: Long = 105L * 1024 * 1024): ByteArray = withContext(Dispatchers.IO) {
        http.newCall(builder(path).get().build()).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Media unavailable (${response.code}). Unlock or request access first.")
            val length = response.body?.contentLength() ?: -1L
            if (length > maxBytes) throw IOException("Media too large")
            val data = response.body?.bytes() ?: throw IOException("Empty media response")
            if (data.size > maxBytes) throw IOException("Media too large")
            data
        }
    }
}

internal data class CreatorConfigNative(val fee_percent: Double = 20.0, val payments_enabled: Boolean = false,
    val adult_content_enabled: Boolean = false)
internal data class CreatorProfileNative(val id: Int = 0, val username: String = "", val display_name: String = "",
    val avatar_url: String? = null, val bio: String = "", val category: String = "LIFESTYLE",
    val level: String = "MAINSTREAM", val adult_requested: Boolean = false, val status: String = "PENDING",
    val monthly_q: Double = 0.0, val chat_q: Double = 0.0, val voice_q: Double = 0.0,
    val video_q: Double = 0.0, val tips_enabled: Boolean = true, val followers: Int = 0,
    val subscribers: Int = 0, val following: Boolean = false, val subscribed: Boolean = false, val mine: Boolean = false)
internal data class CreatorEarningsSummaryNative(val available_q: Double = 0.0, val lifetime_q: Double = 0.0,
    val transferred_q: Double = 0.0)
internal data class CreatorMineNative(val profile: CreatorProfileNative? = null,
    val earnings: CreatorEarningsSummaryNative = CreatorEarningsSummaryNative())
internal data class CreatorPageNative(val profile: CreatorProfileNative = CreatorProfileNative(),
    val posts: List<CreatorPostNative> = emptyList())
internal data class CreatorPostNative(val id: Int = 0, val creator_id: Int = 0, val title: String = "",
    val teaser: String = "", val body: String? = null, val visibility: String = "PUBLIC",
    val price_q: Double = 0.0, val kind: String = "TEXT", val level: String = "MAINSTREAM",
    val review: String = "PENDING", val unlocked: Boolean = false, val media_url: String? = null)
internal data class CreatorAssetNative(val id: Int = 0, val title: String = "", val kind: String = "PHOTO",
    val level: String = "MAINSTREAM", val review: String = "PENDING", val size_bytes: Long = 0)
internal data class CreatorGalleryNative(val id: Int = 0, val creator_id: Int = 0, val title: String = "",
    val teaser: String = "", val kind: String = "PHOTO", val visibility: String = "PPV",
    val price_q: Double = 0.0, val review: String = "PENDING", val unlocked: Boolean = false, val media_count: Int = 1)
internal data class CreatorGalleryAssetNative(val id: Int = 0, val kind: String = "PHOTO")
internal data class CreatorOfferNative(val id: Int = 0, val creator_id: Int = 0, val fan_id: Int = 0,
    val chat_id: Int = 0, val item_id: Int = 0, val title: String = "", val kind: String = "MEDIA",
    val price_q: Double = 0.0, val unlocked: Boolean = false)
internal data class CreatorRequestNative(val id: Int = 0, val kind: String = "CHAT", val status: String = "REQUESTED",
    val role: String = "FAN", val message: String = "", val reply: String = "",
    val creator_id: Int = 0, val fan_id: Int = 0, val scheduled_at: String? = null)
internal data class CreatorPaymentNative(val id: Int = 0, val kind: String = "", val gross_q: Double = 0.0,
    val fee_q: Double = 0.0, val net_q: Double = 0.0, val status: String = "")
internal data class CreatorEarningsNative(val available_q: Double = 0.0, val lifetime_q: Double = 0.0,
    val transferred_q: Double = 0.0, val transactions: List<CreatorPaymentNative> = emptyList())
