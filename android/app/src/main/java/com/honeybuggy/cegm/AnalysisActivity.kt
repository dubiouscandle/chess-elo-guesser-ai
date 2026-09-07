package com.honeybuggy.cegm

import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.util.Base64
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.graphics.toColorInt
import com.github.bhlangonijr.chesslib.Board
import com.github.bhlangonijr.chesslib.Piece
import com.github.bhlangonijr.chesslib.PieceType
import com.github.bhlangonijr.chesslib.Side
import com.github.bhlangonijr.chesslib.Square
import com.github.bhlangonijr.chesslib.pgn.PgnHolder
import com.github.bhlangonijr.chesslib.util.LargeFile
import com.honeybuggy.cegm.ui.theme.CEGMTheme
import org.json.JSONArray
import org.json.JSONObject
import org.pytorch.IValue
import org.pytorch.Module
import org.pytorch.Tensor
import java.io.File
import java.io.FileOutputStream
import kotlin.math.exp

class AnalysisActivity : ComponentActivity() {

    private var analysisWebView: WebView? = null
    private var torchModule: Module? = null

    private val MODEL_FILE_NAME = "model.ptl"
    private val NUM_CLASSES = 40

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.statusBarColor = "#121212".toColorInt()
        window.decorView.setBackgroundColor("#121212".toColorInt())
        window.navigationBarColor = "#121212".toColorInt()

        val pgnData = intent.getStringExtra("PGN_DATA") ?: ""

        setContent {
            CEGMTheme {
                WebViewScreen { webView ->
                    analysisWebView = webView

                    Thread {
                        performAnalysis(pgnData)
                    }.start()
                }
            }
        }
    }

    override fun onDestroy() {
        torchModule?.destroy()
        super.onDestroy()
    }
    private fun callJsWhenReady(payload: JSONObject) {
        Thread {
            // wait until JS is ready
            var ready = false
            while (!ready) {
                val check = BooleanArray(1)
                val latch = java.util.concurrent.CountDownLatch(1)
                runOnUiThread {
                    analysisWebView?.evaluateJavascript(
                        "(window.isAnalysisReady === true).toString()"
                    ) { result ->
                        check[0] = result == "true"
                        latch.countDown()
                    }
                }
                latch.await()
                ready = check[0]
                if (!ready) Thread.sleep(50)
            }

            // call the function
            runOnUiThread {
                analysisWebView?.evaluateJavascript(
                    "window.loadAnalysisData($payload)",
                    null
                )
            }
        }.start()
    }
    private fun updateStatus(message: String) {
        runOnUiThread {
            analysisWebView?.evaluateJavascript("window.updateAnalysisStatus('$message')", null)
        }
    }

    private fun performAnalysis(pgn: String) {
        Log.d("AnalysisActivity", "Starting Analysis...")
        updateStatus("Initializing AI Model...")

        try {
            if (torchModule == null) {
                val modelPath = assetFilePath(this, MODEL_FILE_NAME)
                torchModule = Module.load(modelPath)
            }
        } catch (e: Exception) {
            Log.e("AnalysisActivity", "Error loading model", e)
            sendErrorToWebView(e.toString())
            return
        }

        try {
            updateStatus("Parsing Game Moves...")
            val pgnHolder = PgnHolder(null)
            pgnHolder.loadPgn(LargeFile(pgn.byteInputStream()))

            val games = pgnHolder.games
            if (games.isEmpty()) {
                sendErrorToWebView("Could not parse games from PGN.")
                return
            }

            val game = games[0]
            game.loadMoveText()
            val moves = game.halfMoves

            if (moves.isEmpty()) {
                sendErrorToWebView("No moves found in this game.")
                return
            }

            updateStatus("Preparing Game Data...")
            val board = Board()
            val boardStates = mutableListOf<LongArray>()
            val moveData = mutableListOf<LongArray>()

            for (move in moves) {
                val currentBoardState = LongArray(64)
                for (sq in 0 until 64) {
                    val piece = board.getPiece(Square.squareAt(sq))
                    currentBoardState[sq] = mapPieceToModelId(piece)
                }
                boardStates.add(currentBoardState)

                val fromSq = Square.valueOf(move.from.name).ordinal.toLong()
                val toSq = Square.valueOf(move.to.name).ordinal.toLong()
                var promo = 0L
                if (move.promotion != Piece.NONE) {
                    promo = mapPromoToModelId(move.promotion)
                }
                moveData.add(longArrayOf(fromSq, toSq, promo))

                board.doMove(move)
            }

            val seqLen = boardStates.size
            Log.d("AnalysisActivity", "Sequence Length: $seqLen")

            val inputImagesData = LongArray(seqLen * 64)
            for (i in 0 until seqLen) {
                System.arraycopy(boardStates[i], 0, inputImagesData, i * 64, 64)
            }

            val inputMovesData = LongArray(seqLen * 3)
            for (i in 0 until seqLen) {
                System.arraycopy(moveData[i], 0, inputMovesData, i * 3, 3)
            }

            val inputImagesTensor = Tensor.fromBlob(
                inputImagesData, longArrayOf(1, seqLen.toLong(), 8, 8)
            )

            val inputMovesTensor = Tensor.fromBlob(
                inputMovesData, longArrayOf(1, seqLen.toLong(), 3)
            )

            val inputLengthsTensor = Tensor.fromBlob(
                longArrayOf(seqLen.toLong()), longArrayOf(1)
            )

            updateStatus("Running Neural Network...")
            var result: IValue?
            try {
                result = torchModule!!.forward(
                    IValue.from(inputImagesTensor),
                    IValue.from(inputMovesTensor),
                    IValue.from(inputLengthsTensor)
                )
            } catch (e: Throwable) {
                Log.e("AnalysisActivity", "Fatal Inference Error", e)
                sendErrorToWebView("Crash: ${e.message}")
                return
            }

            updateStatus("Calculating Probabilities...")
            val outputTuple = result!!.toTuple()

            val logSoftmaxWhite = outputTuple[0].toTensor()
            val logSoftmaxBlack = outputTuple[1].toTensor()

            val whiteData = logSoftmaxWhite.dataAsFloatArray
            val blackData = logSoftmaxBlack.dataAsFloatArray

            val whiteResults = processOutput(whiteData, NUM_CLASSES)
            val blackResults = processOutput(blackData, NUM_CLASSES)

            updateStatus("Finalizing...")
            val payload = JSONObject().apply {
                put("pgn", pgn)
                put("white", JSONArray(whiteResults.first))
                put("black", JSONArray(blackResults.first))
                put("pe_white", JSONArray(whiteResults.second))
                put("pe_black", JSONArray(blackResults.second))
            }

            runOnUiThread {
                analysisWebView?.evaluateJavascript(
                    "window.loadAnalysisData(${payload.toString()})",
                    null
                )
            }
        } catch (e: Exception) {
            Log.e("AnalysisActivity", "Analysis Error", e)
            sendErrorToWebView("Analysis Failed: ${e.message}")
        }
    }

    private fun processOutput(
        flatLogits: FloatArray, numClasses: Int
    ): Pair<List<List<Float>>, List<Float>> {
        val numSteps = flatLogits.size / numClasses
        val allProbs = mutableListOf<List<Float>>()
        val pointEstimates = mutableListOf<Float>()

        for (i in 0 until numSteps) {
            val offset = i * numClasses
            val probs = mutableListOf<Float>()
            var weightedSum = 0.0f

            for (c in 0 until numClasses) {
                val logVal = flatLogits[offset + c]
                val p = exp(logVal)
                probs.add(p)
                weightedSum += p * c
            }

            val eloEstimate = weightedSum * 100f

            allProbs.add(probs)
            pointEstimates.add(eloEstimate)
        }
        return Pair(allProbs, pointEstimates)
    }

    private fun mapPieceToModelId(piece: Piece): Long {
        if (piece == Piece.NONE) return 0

        val typeId = when (piece.pieceType) {
            PieceType.PAWN -> 1
            PieceType.KNIGHT -> 2
            PieceType.BISHOP -> 3
            PieceType.ROOK -> 4
            PieceType.QUEEN -> 5
            PieceType.KING -> 6
            else -> 0
        }

        if (typeId == 0) return 0

        // White=0 offset, Black=6 offset
        val offset = if (piece.pieceSide == Side.WHITE) 0 else 6
        return (typeId + offset).toLong()
    }

    private fun mapPromoToModelId(piece: Piece): Long {
        return when (piece.pieceType) {
            PieceType.KNIGHT -> 2
            PieceType.BISHOP -> 3
            PieceType.ROOK -> 4
            PieceType.QUEEN -> 5
            else -> 0
        }
    }

    private fun sendErrorToWebView(error: String) {
        runOnUiThread {
            analysisWebView?.evaluateJavascript(
                "document.getElementById('loading-text').innerText = 'Error: $error'; " + "document.getElementById('loading-text').style.color = '#ff5555';",
                null
            )
        }
    }

    // Helper to copy asset to internal storage for PyTorch C++ loader
    private fun assetFilePath(context: Context, assetName: String): String {
        val file = File(context.filesDir, assetName)
        if (file.exists() && file.length() > 0) {
            return file.absolutePath
        }
        context.assets.open(assetName).use { inputStream ->
            FileOutputStream(file).use { outputStream ->
                val buffer = ByteArray(4 * 1024)
                var read: Int
                while (inputStream.read(buffer).also { read = it } != -1) {
                    outputStream.write(buffer, 0, read)
                }
                outputStream.flush()
            }
        }
        return file.absolutePath
    }
}

class AnalysisBridge(val activity: Activity) {
    @JavascriptInterface
    fun closeActivity() {
        activity.finish()
    }
}

@Composable
private fun WebViewScreen(
    onWebViewCreated: (WebView) -> Unit
) {
    val context = LocalContext.current
    val activity = context as? Activity

    AndroidView(
        modifier = Modifier.fillMaxSize(), factory = { ctx ->
            WebView(ctx).apply {
                setBackgroundColor(Color.parseColor("#121212"))
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.allowFileAccess = true

                if (activity != null) {
                    addJavascriptInterface(AnalysisBridge(activity), "AndroidAnalysis")
                }

                webViewClient = WebViewClient()
                loadUrl("file:///android_asset/analysis.html")
                onWebViewCreated(this)
            }
        })
}

