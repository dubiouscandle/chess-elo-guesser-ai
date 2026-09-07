package com.honeybuggy.cegm

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.graphics.toColorInt
import com.honeybuggy.cegm.ui.theme.CEGMTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.statusBarColor = "#121212".toColorInt()
        window.decorView.setBackgroundColor("#121212".toColorInt())
        window.navigationBarColor = "#121212".toColorInt()
        setContent {
            CEGMTheme {
                WebViewScreen()
            }
        }
    }
}

@Composable
private fun WebViewScreen() {
    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { context ->
            WebView(context).apply {
                settings.javaScriptEnabled = true
                addJavascriptInterface(Bridge(context), "Android")
                webViewClient = WebViewClient()

                loadUrl("file:///android_asset/index.html")
            }
        },
        update = { webView -> }
    )
}

class Bridge(val context: Context) {
    @JavascriptInterface
    fun analyzePgn(pgn: String) {
        val intent = Intent(context, AnalysisActivity::class.java)

        intent.putExtra("PGN_DATA", pgn)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }
}
