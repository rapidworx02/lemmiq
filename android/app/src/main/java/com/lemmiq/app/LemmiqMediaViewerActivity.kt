package com.lemmiq.app

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.view.WindowCompat

/**
 * Lightweight full-screen image viewer for chat media.
 * Uses the platform WebView so HTTPS and content:// image URIs can be displayed without
 * adding a third-party photo-view dependency. Pinch zoom is enabled.
 */
class LemmiqMediaViewerActivity : ComponentActivity() {

    companion object {
        const val EXTRA_URI = "lemmiq_media_uri"
    }

    private var webView: WebView? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = Color.BLACK
        window.navigationBarColor = Color.BLACK

        val uri = intent.getStringExtra(EXTRA_URI)?.trim().orEmpty()
        if (uri.isEmpty()) {
            finish()
            return
        }

        val wv = WebView(this).apply {
            setBackgroundColor(Color.BLACK)
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            webViewClient = WebViewClient()
            settings.apply {
                builtInZoomControls = true
                displayZoomControls = false
                setSupportZoom(true)
                loadWithOverviewMode = true
                useWideViewPort = true
                allowContentAccess = true
                allowFileAccess = false
                javaScriptEnabled = false
                cacheMode = WebSettings.LOAD_DEFAULT
            }
        }
        webView = wv
        setContentView(wv)

        // Loading the image URL directly gives a native full-screen browser image surface
        // with platform pinch zoom. Works for HTTPS and FileProvider content:// URIs.
        wv.loadUrl(uri)

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = finish()
        })
    }

    override fun onDestroy() {
        webView?.apply {
            stopLoading()
            loadUrl("about:blank")
            destroy()
        }
        webView = null
        super.onDestroy()
    }
}
