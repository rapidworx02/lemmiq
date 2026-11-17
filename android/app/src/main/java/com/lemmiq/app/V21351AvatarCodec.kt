package com.lemmiq.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.IOException
import kotlin.math.max
import kotlin.math.roundToInt

/** Personal avatars only. Always encode a normalised JPEG; handles HEIC/HEIF on supported Android devices.
 * Normalisation also avoids confusing the backend with mislabeled document-provider MIME types.
 */
internal data class AvatarStatusV21351(
    val has_photo:Boolean=false,
    val stored_ok:Boolean=false,
    val reason:String="",
    val avatar_url:String?=null
)

internal object V21351AvatarCodec {
    private const val MAX_BYTES = 5 * 1024 * 1024
    private const val MAX_EDGE = 1600

    suspend fun encode(context: Context, uri: Uri): Triple<String, String, ByteArray> = withContext(Dispatchers.IO) {
        val cr=context.contentResolver
        val bitmap: Bitmap = try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                ImageDecoder.decodeBitmap(ImageDecoder.createSource(cr, uri)) { decoder, info, _ ->
                    decoder.allocator=ImageDecoder.ALLOCATOR_SOFTWARE
                    val width=info.size.width; val height=info.size.height
                    val longest=max(width,height)
                    if (longest>MAX_EDGE) {
                        val ratio=MAX_EDGE.toDouble()/longest
                        decoder.setTargetSize(max(1,(width*ratio).roundToInt()),max(1,(height*ratio).roundToInt()))
                    }
                }
            } else {
                // Legacy Android: use two streams for bounded-size decoding.
                val opts=BitmapFactory.Options().apply { inJustDecodeBounds=true }
                cr.openInputStream(uri)?.use { BitmapFactory.decodeStream(it,null,opts) }
                val sample=BitmapFactory.Options().apply {
                    inSampleSize=max(1,max(opts.outWidth,opts.outHeight)/MAX_EDGE)
                }
                cr.openInputStream(uri)?.use { BitmapFactory.decodeStream(it,null,sample) }
                    ?: throw IOException("Cannot decode selected photo")
            }
        } catch(e:Exception){ throw IOException("This photo could not be opened. Try another photo or save it as JPG.",e) }
        try {
            var scaled=bitmap
            var q=90
            var encoded:ByteArray
            do {
                val output=ByteArrayOutputStream()
                if (!scaled.compress(Bitmap.CompressFormat.JPEG,q,output))
                    throw IOException("Could not convert the photo to JPG")
                encoded=output.toByteArray()
                if(encoded.size<=MAX_BYTES)break
                if(q>64) q-=12
                else {
                    val w=max(1,(scaled.width*0.8).roundToInt())
                    val h=max(1,(scaled.height*0.8).roundToInt())
                    val smaller=Bitmap.createScaledBitmap(scaled,w,h,true)
                    if(scaled!==bitmap)scaled.recycle()
                    scaled=smaller
                }
            } while (true)
            if(scaled!==bitmap)scaled.recycle()
            Triple("profile.jpg","image/jpeg",encoded)
        } finally { bitmap.recycle() }
    }
}
