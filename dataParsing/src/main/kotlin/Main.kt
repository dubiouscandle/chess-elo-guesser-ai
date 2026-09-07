import com.github.bhlangonijr.chesslib.Piece
import com.github.bhlangonijr.chesslib.game.Game
import com.github.bhlangonijr.chesslib.pgn.PgnIterator
import com.github.bhlangonijr.chesslib.util.LargeFile
import com.github.luben.zstd.ZstdInputStream
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.joinAll
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.msgpack.jackson.dataformat.MessagePackMapper
import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.util.concurrent.ConcurrentLinkedDeque
import java.util.concurrent.atomic.AtomicBoolean

typealias CompressedGame = Array<IntArray>


fun main(args: Array<String>) {
    loadData(args[0], "data") { game ->
        // filters provisional ratings and high volatility ratings
        val whiteRatingDiff = game.property["WhiteRatingDiff"]
        val blackRatingDiff = game.property["BlackRatingDiff"]
        if (whiteRatingDiff == null || blackRatingDiff == null) return@loadData false
        if (whiteRatingDiff.toInt() > 10 || blackRatingDiff.toInt() > 10) return@loadData false
        //

        if (game.halfMoves.size <= 10) return@loadData false // filter against super short games
        if (!game.round.event.name.equals("Rated Blitz game")) return@loadData false // blitz only

        return@loadData true
    }

}


/**
 * parses the games into the specified directory as message pack files
 *
 * @param pgnFilePath the path to find the pgn file
 * @param outDirectoryPath the directory to store the files
 * @param gamesPerFile the number of games per file
 * @param gameLimit the max number of games that will be saved
 * @param filter the filter, return true if the game should be included and false if it should be excluded
 */
fun loadData(
    pgnFilePath: String,
    outDirectoryPath: String,
    gamesPerFile: Int = 100_000,
    maxPerBracket: Int = 2,
    gameLimit: Int = 1_000_000_000,
    numWorkers: Int = 2,
    printRate: Int = 10_000,
    filter: (Game) -> Boolean
) {
    clearDir(outDirectoryPath)

    val scope = CoroutineScope(Dispatchers.Default)
    val parsedStack = ConcurrentLinkedDeque<Game>()
    val savingStack = ConcurrentLinkedDeque<CompressedGame>()
    val mapper = MessagePackMapper()
    val workersRunning = AtomicBoolean(true)

    // launching game compressing workers
    val workers: List<Job> = List(numWorkers) { index ->
        scope.launch {
            while (workersRunning.get()) {
                val next = parsedStack.poll()
                if (next == null) {
                    delay(1)
                    continue
                }

                val data = getData(next)
                savingStack.add(data)
            }
        }

    }

    // launching saver thread
    val saverRunning = AtomicBoolean(true)
    val saverThread = scope.launch {
        val brackets = Array(40) { ArrayList<CompressedGame>(gamesPerFile) }
        val bracketCounts = IntArray(brackets.size) { 0 }
        while (saverRunning.get()) {
            val game = savingStack.poll()
            if (game == null) {
                delay(1)
                continue
            }
            val bracket = ((game[0][0] + game[0][1]) / 200).coerceAtMost(brackets.lastIndex)
            brackets[bracket].add(game)

            if (brackets[bracket].size >= gamesPerFile) {
                if (bracketCounts[bracket] < maxPerBracket) {
                    val formattedBracket = "%04d".format(bracket * 100)
                    val formattedCount = "%02d".format(bracketCounts[bracket])
                    val filePath = "$outDirectoryPath/${formattedBracket}_$formattedCount.msgpack"

                    mapper.writeValue(File(filePath), brackets[bracket])
                    println("Saved ${brackets[bracket].size} games to $filePath")

                }
                brackets[bracket].clear()
                bracketCounts[bracket]++
            }

        }

        for (bracket in brackets.indices) {
            if (brackets[bracket].isNotEmpty()) {
                val formattedBracket = "%04d".format(bracket * 100)
                val formattedCount = "%02d".format(bracketCounts[bracket])
                val filePath = "$outDirectoryPath/${formattedBracket}_$formattedCount.msgpack"

                mapper.writeValue(File(filePath), brackets[bracket])
                println("Saved ${brackets[bracket].size} leftover games to $filePath")

                brackets[bracket].clear()
            }
        }
    }

    val iterator = PgnIterator(LargeFile(ZstdInputStream(BufferedInputStream(FileInputStream(pgnFilePath))))).iterator()
    var gameCount = 0

    while (true) {
        if (!iterator.hasNext() || gameCount >= gameLimit) {
            break
        }
        val game = iterator.next()
        if (!filter(game)) {
            continue
        }
        gameCount++
        parsedStack.add(game)

        if (gameCount % printRate == 0) {
            println("Parsed $gameCount games.")
        }
    }

    workersRunning.set(false)
    runBlocking {
        workers.joinAll()
    }
    while (savingStack.isNotEmpty()) {
        Thread.sleep(10)
    }
    saverRunning.set(false)
    runBlocking {
        saverThread.join()
    }
}

fun getData(game: Game): CompressedGame {
    val data = arrayOf(
        intArrayOf(game.whitePlayer.elo, game.blackPlayer.elo),
        IntArray(game.halfMoves.size),
        IntArray(game.halfMoves.size),
        IntArray(game.halfMoves.size),
    )

    for (move in game.halfMoves.withIndex()) {
        data[1][move.index] = move.value.to.ordinal
        data[2][move.index] = move.value.from.ordinal
        val promo = move.value.promotion
        data[3][move.index] = when (promo) {
            Piece.NONE -> 0
            Piece.BLACK_KNIGHT, Piece.WHITE_KNIGHT -> 1
            Piece.BLACK_BISHOP, Piece.WHITE_BISHOP -> 2
            Piece.BLACK_ROOK, Piece.WHITE_ROOK -> 3
            Piece.BLACK_QUEEN, Piece.WHITE_QUEEN -> 4
            else -> throw IllegalStateException()
        }
    }

    return data
}

fun clearDir(dirPath: String) {
    val dir = File(dirPath)
    if (!dir.exists() || !dir.isDirectory) throw RuntimeException("if (!dir.exists() || !dir.isDirectory) throw RuntimeException()")

    dir.listFiles()?.forEach { file ->
        if (file.name != ".gitkeep") {
            file.delete()
        }
    }
}
