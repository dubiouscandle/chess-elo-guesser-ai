fun main(args: Array<String>) {
    loadData("src/main/kotlin/lichess_db_standard_rated_2026-08.pgn.zst", "data") { game ->
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
