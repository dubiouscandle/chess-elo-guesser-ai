import { Chessground } from 'https://unpkg.com/chessground@8.4.0/chessground.js';

if (typeof Chart !== 'undefined') {
    Chart.defaults.font.size = 14;
    Chart.defaults.color = '#aaaaaa';
    Chart.defaults.font.family = "'Inter', sans-serif";
} else {
    console.error("Chart.js not loaded!");
    throw new Error("Chart.js failed to load. Check internet.");
}

let currentMove = 0;
let data = {
    fens: [],
    w: [],
    b: [],
    pe_w: [],
    pe_b: []
};
let whiteChart = null;
let blackChart = null;

const boardContainer = document.getElementById('board');
let board = null;

try {
    board = Chessground(boardContainer, {
        orientation: 'white',
        coordinates: false,
        movable: { free: false },
        selectable: { enabled: false },
        disableContextMenu: true
    });
} catch (e) {
}

function cloneOptions(options) {
    return JSON.parse(JSON.stringify(options));
}

const labels = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000];
const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    categoryPercentage: 1.0,
    barPercentage: 0.9,
    scales: {
        x: { display: false, grid: { display: false } },
        y: { min: 0, suggestedMax: 0.2, beginAtZero: true, display: false, grid: { display: false } }
    },
    plugins: {
        legend: { display: false },
        title: {
            display: true, text: 'Waiting...', color: '#fff',
            font: { size: 14, weight: '600' }, padding: { top: 5, bottom: 2 }
        },
        subtitle: {
            display: true, text: '-', color: '#888',
            font: { size: 11, style: 'italic' }, padding: { bottom: 5 }
        },
        tooltip: { enabled: true, intersect: false, mode: 'index' }
    }
};

try {
    whiteChart = new Chart(document.getElementById('white-chart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{ data: new Array(27).fill(0), backgroundColor: '#e0e0e0', borderWidth: 0, borderRadius: 2 }]
        },
        options: cloneOptions(chartOptions)
    });

    blackChart = new Chart(document.getElementById('black-chart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{ data: new Array(27).fill(0), backgroundColor: '#4CAF50', borderWidth: 0, borderRadius: 2 }]
        },
        options: cloneOptions(chartOptions)
    });
} catch (e) {
    console.error("Chart init failed:", e);
}

window.loadAnalysisData = function(payload) {
    const { pgn, white, black, pe_white, pe_black } = payload

    try {
        if (typeof Chess === 'undefined') throw new Error("Chess.js not loaded.");

        const chess = new Chess();

        if (!chess.load_pgn(pgn)) {
            throw new Error("Invalid PGN Data");
        }
        data.fens = [chess.fen()];

        const moves = chess.history();
        chess.reset();
        data.fens[0] = chess.fen();
        for (const move of moves) {
            chess.move(move);
            data.fens.push(chess.fen());
        }

        data.w = white || [];
        data.b = black || [];
        data.pe_w = pe_white || [];
        data.pe_b = pe_black || [];

        currentMove = 0;
        updateComponents();

        setTimeout(() => {
            if(whiteChart) whiteChart.resize();
            if(blackChart) blackChart.resize();
        }, 100);

    } catch (e) {
        console.error("JS Error: " + e.message);
        const ld = document.getElementById('loading-text');
        if(ld) {
            ld.innerText = "Error: " + e.message;
            ld.style.color = "#ff5555";
        }
    }
};

function updateComponents() {
    if (!data.fens || !board) return;

    if (data.fens[currentMove]) {
        board.set({ fen: data.fens[currentMove] });
    }

    const totalMoves = data.fens.length > 0 ? data.fens.length - 1 : 0;
    const moveNum = Math.ceil(currentMove / 2);
    const totalNum = Math.ceil(totalMoves / 2);
    document.getElementById("move-counter").innerText = `${moveNum}/${totalNum}`;

    if (whiteChart) {
        if (currentMove === 0) resetChart(whiteChart, "White Prediction");
        else {
            const idx = Math.floor((currentMove - 1) / 2);
            if (data.w[idx]) updateChartData(whiteChart, data.w[idx], "White", data.pe_w[idx]);
        }
    }

    if (blackChart) {
        if (currentMove <= 1) resetChart(blackChart, "Black Prediction");
        else {
            const idx = Math.floor((currentMove - 2) / 2);
            if (data.b[idx]) updateChartData(blackChart, data.b[idx], "Black", data.pe_b[idx]);
        }
    }
}

function updateChartData(chart, dataArray, label, pointEstimate) {
    chart.data.datasets[0].data = dataArray;
    chart.options.plugins.title.text = `${label}: ~${Math.round(pointEstimate)}`;
    chart.options.plugins.subtitle.text = "";
    chart.update();
}

function resetChart(chart, defaultTitle) {
    chart.data.datasets[0].data = new Array(27).fill(0);
    chart.options.plugins.title.text = defaultTitle;
    chart.options.plugins.subtitle.text = "Waiting for moves...";
    chart.update();
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('flip-btn').addEventListener('click', () => {
        if(board) {
            const newOri = board.state.orientation === 'white' ? 'black' : 'white';
            board.set({ orientation: newOri });
        }
    });

    const safeUpdate = (newMove) => {
        if (!data.fens || data.fens.length === 0) return;
        currentMove = Math.max(0, Math.min(newMove, data.fens.length - 1));
        updateComponents();
    };

    document.getElementById('start-btn').addEventListener('click', () => safeUpdate(0));
    document.getElementById('end-btn').addEventListener('click', () => safeUpdate(data.fens.length - 1));
    document.getElementById('prev-btn').addEventListener('click', () => safeUpdate(currentMove - 1));
    document.getElementById('next-btn').addEventListener('click', () => safeUpdate(currentMove + 1));
});
