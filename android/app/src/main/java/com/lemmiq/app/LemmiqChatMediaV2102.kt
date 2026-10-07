package com.lemmiq.app

import android.graphics.Bitmap
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties

/**
 * LEMMIQ V2.10.2 chat photo helpers.
 *
 * Image detection intentionally checks kind + MIME + filename because older uploads can arrive
 * as FILE attachments even when their content is JPG/PNG/WEBP.
 */
fun isLemmiqImageAttachmentV2102(a: AttachmentDto?): Boolean {
    if (a == null) return false
    val kind = a.kind.uppercase()
    val mime = a.mime_type.orEmpty().lowercase()
    val name = a.name.orEmpty().lowercase()
    if (kind == "PHOTO" || kind == "IMAGE") return true
    if (mime.startsWith("image/")) return true
    return name.endsWith(".jpg") || name.endsWith(".jpeg") ||
        name.endsWith(".png") || name.endsWith(".webp") || name.endsWith(".gif")
}

/** Full-screen WhatsApp-style image surface: pinch zoom, pan, double-tap zoom and Back/Close. */
@Composable
fun LemmiqFullScreenPhotoV2102(
    bitmap: Bitmap,
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
                bitmap = bitmap.asImageBitmap(),
                contentDescription = "Full screen chat photo",
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
                            val next = (scale * zoom).coerceIn(1f, 5f)
                            scale = next
                            if (next <= 1.01f) {
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
                            onTap = { controlsVisible = !controlsVisible },
                            onDoubleTap = {
                                if (scale > 1.05f) {
                                    scale = 1f
                                    offsetX = 0f
                                    offsetY = 0f
                                } else {
                                    scale = 2.5f
                                }
                            }
                        )
                    }
            )

            if (controlsVisible) {
                Surface(
                    color = Color.Black.copy(alpha = .48f),
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
