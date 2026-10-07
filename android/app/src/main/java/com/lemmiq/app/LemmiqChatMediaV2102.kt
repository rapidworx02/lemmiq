package com.lemmiq.app

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.roundToInt

/**
 * V2.10.2 chat photo UX.
 *
 * The loader uses the same authenticated LEMMIQ media routes as the current backend:
 *  direct chat: /media/{messageId}
 *  group chat : /v24/group-media/{messageId}
 *
 * No FileProvider/raw-private-path handoff is needed for the full-screen viewer because the
 * already-downloaded image bytes stay inside Compose.
 */
object LemmiqMediaLoaderV2102 {
    suspend fun directMessage(
        serverBaseUrl: String,
        authToken: String,
        messageId: Long
    ): ByteArray = fetch(
        "${serverBaseUrl.trimEnd('/')}/media/$messageId",
        authToken
    )

    suspend fun groupMessage(
        serverBaseUrl: String,
        authToken: String,
        messageId: Long
    ): ByteArray = fetch(
        "${serverBaseUrl.trimEnd('/')}/v24/group-media/$messageId",
        authToken
    )

    private suspend fun fetch(url: String, authToken: String): ByteArray =
        withContext(Dispatchers.IO) {
            val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 15_000
                readTimeout = 30_000
                setRequestProperty("Authorization", "Bearer $authToken")
                setRequestProperty("Accept", "image/*")
            }
            try {
                val code = connection.responseCode
                if (code !in 200..299) error("Image download failed ($code)")
                connection.inputStream.use { it.readBytes() }
            } finally {
                connection.disconnect()
            }
        }
}

fun isLemmiqImageAttachmentV2102(
    kind: String?,
    mimeType: String?,
    fileName: String?
): Boolean {
    val k = kind.orEmpty().uppercase()
    val mime = mimeType.orEmpty().lowercase()
    val name = fileName.orEmpty().lowercase()

    if (k == "IMAGE" || k == "PHOTO") return true
    if (mime.startsWith("image/")) return true
    return name.endsWith(".jpg") ||
        name.endsWith(".jpeg") ||
        name.endsWith(".png") ||
        name.endsWith(".webp") ||
        name.endsWith(".gif")
}

@Composable
fun LemmiqChatPhotoV2102(
    imageLoader: suspend () -> ByteArray,
    mine: Boolean,
    timestamp: String,
    modifier: Modifier = Modifier,
    caption: String? = null,
    onAskQVision: (() -> Unit)? = null
) {
    var bytes by remember { mutableStateOf<ByteArray?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var fullScreen by remember { mutableStateOf(false) }

    LaunchedEffect(imageLoader) {
        try {
            bytes = imageLoader()
            error = null
        } catch (t: Throwable) {
            error = t.message ?: "Could not load photo"
        }
    }

    val bitmap = remember(bytes) {
        bytes?.let { data ->
            BitmapFactory.decodeByteArray(data, 0, data.size)?.asImageBitmap()
        }
    }

    Surface(
        modifier = modifier.widthIn(max = 330.dp),
        shape = RoundedCornerShape(18.dp),
        color = if (mine) {
            MaterialTheme.colorScheme.primary.copy(alpha = 0.88f)
        } else {
            MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.84f)
        },
        tonalElevation = 0.dp,
        shadowElevation = 0.dp
    ) {
        Column(
            modifier = Modifier.padding(4.dp) // intentionally small: removes the oversized blue/purple frame
        ) {
            when {
                bitmap != null -> {
                    Image(
                        bitmap = bitmap,
                        contentDescription = "Chat photo",
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 150.dp, max = 360.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .pointerInput(bitmap) {
                                detectTapGestures(onTap = { fullScreen = true })
                            }
                    )
                }

                error != null -> {
                    Surface(
                        color = Color.Black.copy(alpha = 0.10f),
                        shape = RoundedCornerShape(14.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            error!!,
                            modifier = Modifier.padding(18.dp),
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }

                else -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(190.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator()
                    }
                }
            }

            if (!caption.isNullOrBlank()) {
                Text(
                    caption,
                    modifier = Modifier.padding(horizontal = 7.dp, vertical = 6.dp),
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            if (onAskQVision != null) {
                TextButton(
                    onClick = onAskQVision,
                    contentPadding = PaddingValues(horizontal = 7.dp, vertical = 2.dp)
                ) {
                    Text("📷 Ask Q Vision")
                }
            }

            Text(
                text = timestamp,
                modifier = Modifier
                    .align(Alignment.End)
                    .padding(horizontal = 7.dp, vertical = 3.dp),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.65f)
            )
        }
    }

    if (fullScreen && bitmap != null) {
        LemmiqFullScreenPhotoV2102(
            bitmap = bitmap,
            onDismiss = { fullScreen = false }
        )
    }
}

@Composable
private fun LemmiqFullScreenPhotoV2102(
    bitmap: androidx.compose.ui.graphics.ImageBitmap,
    onDismiss: () -> Unit
) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offsetX by remember { mutableFloatStateOf(0f) }
    var offsetY by remember { mutableFloatStateOf(0f) }
    var controlsVisible by remember { mutableStateOf(true) }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            usePlatformDefaultWidth = false,
            dismissOnBackPress = true,
            dismissOnClickOutside = false
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            Image(
                bitmap = bitmap,
                contentDescription = "Full screen photo",
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .fillMaxSize()
                    .graphicsLayer {
                        scaleX = scale
                        scaleY = scale
                        translationX = offsetX
                        translationY = offsetY
                    }
                    .pointerInput(Unit) {
                        detectTransformGestures { _, pan, zoom, _ ->
                            val newScale = (scale * zoom).coerceIn(1f, 5f)
                            scale = newScale
                            if (newScale <= 1.01f) {
                                offsetX = 0f
                                offsetY = 0f
                            } else {
                                offsetX += pan.x
                                offsetY += pan.y
                            }
                        }
                    }
                    .pointerInput(Unit) {
                        detectTapGestures(
                            onDoubleTap = {
                                if (scale > 1.05f) {
                                    scale = 1f
                                    offsetX = 0f
                                    offsetY = 0f
                                } else {
                                    scale = 2.5f
                                }
                            },
                            onTap = { controlsVisible = !controlsVisible }
                        )
                    }
            )

            if (controlsVisible) {
                Surface(
                    color = Color.Black.copy(alpha = 0.48f),
                    shape = RoundedCornerShape(22.dp),
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .statusBarsPadding()
                        .padding(14.dp)
                ) {
                    TextButton(onClick = onDismiss) {
                        Text("Close", color = Color.White, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
    }
}
