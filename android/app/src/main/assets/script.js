document.addEventListener('DOMContentLoaded', () => {
    const importAlerts = document.getElementById("import-alerts");
    const pgnAlerts = document.getElementById("pgn-alerts");
    const lichessButton = document.querySelector('.btn-primary');
    const lichessInput = document.getElementById('lichess-id');
    const pgnButton = document.querySelector('.btn-secondary');
    const pgnInput = document.getElementById('pgn-input');

    let notificationTimeout;

    function handlePgnAnalysis(pgnData = null) {

        if (pgnData === null || typeof pgnData !== 'string') {
            pgnData = pgnInput.value;
        }

        if (pgnData.trim() === "") {
            return;
        }
        pgnAlerts.innerHTML = "";

        if (typeof Chess === 'undefined') {
            pgnAlerts.innerHTML = "System Error: Chess library not loaded.";
            return;
        }

        const chess = new Chess();

        if (!chess.load_pgn(pgnData)) {
            pgnAlerts.innerHTML = "Invalid PGN.";
            return;
        }

        const headers = chess.header();
        const variant = headers['Variant'];

        if (variant && variant.trim().toLowerCase() !== 'standard') {
            pgnAlerts.innerHTML = `Error: Unsupported variant "${variant}". Only Standard chess is supported.`;
            return;
        }

        try {
            window.Android.analyzePgn(pgnData);
        } catch (error) {
            pgnAlerts.innerHTML = error.message;
        }
    }

    function handleLichessImport() {
        importAlerts.innerHTML = "";
        pgnInput.value = "";
        const gameId = lichessInput.value.trim();

        if (gameId === "") {
            importAlerts.innerHTML = "Please enter a Game ID.";
            return;
        }

        const url = `https://lichess.org/game/export/${gameId}`;

        fetch(url, {
            method: 'GET',
            headers: { 'Accept': 'application/x-chess-pgn' }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Lichess API Error: ${response.status}`);
            }
            return response.text();
        })
        .then(pgnData => {
            pgnInput.value = pgnData;

            const chess = new Chess();
            if(chess.load_pgn(pgnData)) {
                const headers = chess.header();

                const event = headers['Event'] || "";
                if(!event.toLowerCase().includes("blitz")) {
                    importAlerts.innerHTML = "Non-blitz game detected: Accuracy may vary.";
                }
            }
        })
        .catch(error => {
            console.error(error);
            importAlerts.innerHTML = error.message;
        });
    }

    lichessButton.addEventListener('click', handleLichessImport);

    pgnButton.addEventListener('click', () => {
        handlePgnAnalysis();
    });
});