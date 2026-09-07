import io
import os

import chess
import flask
import torch
from chess import pgn
from flask import Flask, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from Python.main import data
from Python.main.data import EloFromDistribution
from Python.main.net import Model

# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
device = torch.device("cpu")
model = Model().to(device)
model = torch.compile(model)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "chess_elo_model.pt")
model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
model.eval()

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(
    __name__,
    static_folder=os.path.join(basedir, '../Frontend/static'),
    static_url_path=''
)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1 per second"]
)
CORS(app)


@app.route("/")
def home():
    return app.send_static_file("index.html")


promo_map = {
    None: 0,
    chess.KNIGHT: 1,
    chess.BISHOP: 2,
    chess.ROOK: 3,
    chess.QUEEN: 4,
}


@app.route("/infer", methods=["GET", "POST"])
def infer():
    try:
        # 1) grab pgn_value depending on method
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
            pgn_value = body.get("pgn", "")
        else:
            pgn_value = request.args.get("pgn", "")

        # 2) validate
        if not pgn_value:
            return flask.jsonify({"error": "No PGN provided."}), 400

        # 3) parse
        game = pgn.read_game(io.StringIO(pgn_value))
        if game is None:
            return flask.jsonify({"error": "Could not parse PGN."}), 400

        formatted = [[0, 0], [], [], []]

        for move in game.mainline_moves():
            formatted[1].append(move.to_square)
            formatted[2].append(move.from_square)
            formatted[3].append(promo_map[move.promotion])

        images, moves, lengths, _ = data.collate_fn([formatted])
        images, moves = images.to(device), moves.to(device)

        out_w, out_b, _, _ = model(images, moves, lengths)

        out_w = torch.exp(out_w[0])
        out_b = torch.exp(out_b[0])

        w = [EloFromDistribution(x.detach().cpu().numpy()).get() for x in out_w]
        b = [EloFromDistribution(x.detach().cpu().numpy()).get() for x in out_b]

        w_mat = out_w.tolist()
        b_mat = out_b.tolist()

        return flask.jsonify({
            "white": w_mat,
            "black": b_mat,
            "pe_white": w,
            "pe_black": b,
        })
    except Exception as e:
        print(e)
        return flask.jsonify({'error': 'Something went wrong.'}), 400


if __name__ == '__main__':
    app.run()
