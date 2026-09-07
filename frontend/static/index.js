import {Chessground} from 'https://unpkg.com/chessground@8.4.0/chessground.js';

Chart.defaults.font.size = 16;

const status = document.getElementById('status');
setStatus("")

let data = {
    fens: [],
    w: null,
    b: null,
    pe_w: null,
    pe_b: null,
}

const board = Chessground(document.getElementById('board'), {
    orientation: 'white',
    coordinates: false,
    movable: false,
    selectable: false,
});
const collapseInstance = new bootstrap.Collapse(document.getElementById('collapse-container'), {toggle: false});

const labels = [400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000];

const options = {
    categoryPercentage: 1,
    barPercentage: 0.9,
    offset: false,
    scales: {
        x: {
            ticks: {
               align: 'center',
            },
        },

        y: {
            min: 0,
            suggestedMax: 0.2,
            beginAtZero: true,
     }
    },
    plugins: {
        title: {
            display: true,
            text: 'Main Title',
            font: {
                size: 20,
                weight: 'bold'
            },
            padding: {
                top: 5
            }
        },
        subtitle: {
            display: true,
            text: 'Subtitle',
            font: {
                size: 16,
                style: 'italic'
            },
            padding: {
                bottom: 10
            }
        },
        legend: {
            display: false
        }
    }
};
const whiteChart = new Chart(document.getElementById('white-chart'), {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [{
            data: new Array(27).fill(0),
            borderWidth: 1,
        },],
    },
    options: structuredClone(options),
});

const blackChart = new Chart(document.getElementById('black-chart'), {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [{
            data: new Array(27).fill(0),
            borderWidth: 1,
            backgroundColor: 'rgba(220, 57, 18, 0.5)',
            borderColor: '#DC3912',
        },],
    },
    options: structuredClone(options),
});

let currentMove = 0;
updateComponents()

document.getElementById('flip-btn').addEventListener('click', (e) => {
    const currentOrientation = board.state.orientation;
    const newOrientation = currentOrientation === 'white' ? 'black' : 'white';

    board.set({orientation: newOrientation});
})

document.getElementById('start-btn').addEventListener('click', (e) => {
    currentMove = 0;
    updateComponents();
})
document.getElementById('end-btn').addEventListener('click', (e) => {
    currentMove = data.fens.length - 1;
    updateComponents();
})
document.getElementById('next-btn').addEventListener('click', (e) => {
    currentMove = Math.min(currentMove + 1, data.fens.length - 1);
    updateComponents();
})
document.getElementById('prev-btn').addEventListener('click', (e) => {
    currentMove = Math.max(currentMove - 1, 0);
    updateComponents();
})
document.getElementById("board").addEventListener('click', () => {
    document.getElementById("board").focus();
});

const list = [...document.getElementsByClassName('board-btn')];
list.push(document.getElementById("board"));
for (let element of list) {
    element.addEventListener('keydown', (event) => {
        switch (event.key) {
            case 'ArrowRight':
                currentMove = Math.min(currentMove + 1, data.fens.length - 1);
                updateComponents();
                break;
            case 'ArrowLeft':
                currentMove = Math.max(currentMove - 1, 0);
                updateComponents();
                break;
            case 'ArrowDown':
                currentMove = 0;
                updateComponents();
                break;
            case 'ArrowUp':
                currentMove = data.fens.length - 1;
                updateComponents();
                break;
            case 'f':
                const currentOrientation = board.state.orientation;
                const newOrientation = currentOrientation === 'white' ? 'black' : 'white';

                board.set({orientation: newOrientation});
                break;
        }
    });
}

function updateComponents() {
    board.set({fen: data.fens[currentMove]});

    if (data.w != null && data.b != null) {
        if (currentMove === 0) {
            whiteChart.data.datasets[0].data = new Array(27).fill(0);
            whiteChart.options.plugins.subtitle.text = "Point Estimate: ?";
        } else {
            const idx = Math.floor((currentMove - 1) / 2)
            whiteChart.data.datasets[0].data = data.w[idx];
            whiteChart.options.plugins.subtitle.text = "Point Estimate: " + Math.round(data.pe_w[idx]);
        }
        if (currentMove <= 1) {
            blackChart.data.datasets[0].data = new Array(27).fill(0);
            blackChart.options.plugins.subtitle.text = "Point Estimate: ?";
        } else {
            const idx = Math.floor((currentMove - 2) / 2)
            blackChart.data.datasets[0].data = data.b[idx];
            blackChart.options.plugins.subtitle.text = "Point Estimate: " + Math.round(data.pe_b[idx]);
        }

        document.getElementById("move-counter").innerHTML = "Move: " + currentMove + "/" + (data.w.length + data.b.length)
    }

    whiteChart.update()
    blackChart.update()

    whiteChart.options.plugins.title.text = "White Prediction";
    blackChart.options.plugins.title.text = "Black Prediction";
}

document.getElementById('pgn-button').addEventListener('click', (e) => {
    fetchPGN(document.getElementById('pgn').value, true)
})
document.getElementById('link-button').addEventListener('click', (e) => {
    try {
        const link = document.getElementById('link').value
        const gameID = new URL(link).pathname.split('/')[1]
        const url = `https://lichess.org/game/export/${gameID}?json=true`;

        fetch(url, {
            headers: {
                'Accept': 'application/json'
            }
        }).then(response => {
            if (!response.ok) {
                throw new Error('');
            }
            return response.text();
        })
            .then(jsonString => {
                const json = JSON.parse(jsonString);
                const chess = new Chess();
                const moves = json.moves.split(' ');
                for (const move of moves) {
                    chess.move(move);
                }
                fetchPGN(chess.pgn(), json.variant === "standard" && json.speed === "blitz")
            })
            .catch(err => setStatus("Something went wrong", "danger"));
    } catch (err) {
        setStatus("Invalid URL", "danger");
    }
})

function setStatus(state, color) {
    if (state === "") {
        status.style.display = 'none';
    } else {
        status.style.opacity = '0';

        setTimeout(() => {
            status.style.opacity = '1';
            status.style.display = 'block';
            status.innerHTML = state
            status.classList.forEach(cls => {
                if (cls.startsWith('alert-') && cls !== 'alert') {
                    status.classList.remove(cls);
                }
            });
            status.classList.add(`alert-${color}`);
        }, 10)

    }
}

function fetchPGN(pgn, isStandardGame) {
    const chess = new Chess();
    if (!chess.load_pgn(pgn)) {
        setStatus("Invalid PGN", "danger");
        return
    }

    const collapseElement = document.getElementById('collapse-container');
    collapseElement.style.transition = 'none';
    collapseElement.classList.remove('show');
    collapseElement.style.transition = '';

    setStatus(`
  <div class="d-flex flex-column justify-content-center align-items-center" style="height: 100%;">
    <div class="spinner-border mb-3" role="status"></div>
    <p>Please wait. This can take up to 30 seconds.</p>
  </div>
`, "");
    
    data.fens = []
    const history = chess.history()
    chess.reset()
    data.fens.push(chess.fen())
    for (const move of history) {
        chess.move(move);
        data.fens.push(chess.fen())
    }

    currentMove = 0;

    fetch('/infer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ pgn })
    })        .then(response => {
            if (!response.ok) {
                console.log(response.status)
                if (response.status === 429) {
                    setStatus("Too many requests.", "danger");
                    return undefined;
                } else {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
            }
            return response.json();
        })
        .then(json => {
            if (!json) return;
            data.w = json.white;
            data.b = json.black;
            data.pe_w = json.pe_white;
            data.pe_b = json.pe_black;
            const exp = structuredClone(data)
            delete exp.fens

            const blob = new Blob([JSON.stringify(exp)], {type: "application/json"});
            document.getElementById("export").href = URL.createObjectURL(new Blob([blob]));

            if (!isStandardGame) {
                setStatus("Non-Blitz game detected: results may vary", "warning");
            } else {
                setStatus("");
            }
            updateComponents();
            collapseInstance.show();
        })
        .catch(error => {
            setStatus("Something went wrong", "danger");
        });
}