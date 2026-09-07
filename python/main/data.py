import bisect
import random
from pathlib import Path
from typing import List

import chess
import msgpack
import numpy as np
import torch
from scipy.optimize import minimize_scalar
from scipy.stats import norm
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset, ConcatDataset, Subset

brackets = [
    400, 500, 600, 700, 800, 900, 1000, 1100, 1200,
    1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100,
    2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000,
]

def get_data_sets(reserve_test=0.1):
    train_datasets = []
    test_datasets = []
    rng = random.Random(2)

    for bracket in brackets:
        here = Path(__file__).resolve().parent
        with open(here / f"../../DataParsing/data/{str(bracket).zfill(4)}_00.msgpack", "rb") as f:
            print(f)
            games = msgpack.unpack(f, raw=False)
            dataset = MPDataset(games)
            num_games = dataset.__len__()

            n = int(reserve_test * num_games)
            all_indices = list(range(num_games))
            test_indices = rng.sample(all_indices, n)
            train_indices = [i for i in all_indices if i not in test_indices]

            test_datasets.append(Subset(dataset, test_indices))
            train_datasets.append(Subset(dataset, train_indices))

    return ConcatDataset(train_datasets), ConcatDataset(test_datasets)


class MPDataset(Dataset):
    def __init__(self, games):
        self.games = games

    def __len__(self):
        return len(self.games)

    def __getitem__(self, index):
        return self.games[index]


promo_map = {
    0: None,
    1: chess.KNIGHT,
    2: chess.BISHOP,
    3: chess.ROOK,
    4: chess.QUEEN,
}


def get_bracket(elo):
    bracket = bisect.bisect_right(brackets, elo) - 1

    if bracket < 0:
        bracket = 0
    elif bracket >= len(brackets):
        bracket = len(brackets) - 1

    return bracket


def board_to_tensor(board: chess.Board) -> torch.Tensor:
    image = torch.zeros((8, 8), dtype=torch.int64)
    for square in board.piece_map():
        piece = board.piece_at(square)
        row = chess.square_rank(square)
        col = chess.square_file(square)
        image[row, col] = piece.piece_type + (0 if piece.color == chess.WHITE else 6)
    return image


def get_img_seq(to_sq_seq, from_sq_seq, promo_seq):
    board = chess.Board()
    img_seq = []
    for from_sq, to_sq, promo in zip(from_sq_seq, to_sq_seq, promo_seq):
        img_seq.append(board_to_tensor(board))
        move = chess.Move(from_sq, to_sq, promo_map[promo])
        board.push(move)

    return torch.stack(img_seq)


def get_distribution(elo: float):
    total = norm.cdf(brackets[-1], loc=elo, scale=200) - norm.cdf(brackets[0], loc=elo, scale=200)
    return [(norm.cdf(bracket + 100, loc=elo, scale=200) - norm.cdf(bracket, loc=elo, scale=200)) / total for bracket in
            brackets]

class EloFromDistribution:
    def __init__(self, histogram):
        self.histogram = histogram

    def get(self):
        return minimize_scalar(self.objective, bounds=(0, 3000), method='bounded').x

    def objective(self, elo):
        p = np.array(get_distribution(elo))
        return np.sum((p - self.histogram) ** 2)

def collate_fn(games: List):
    images, moves, lengths = [], [], []
    model_target = []

    for sample in games:
        elos = sample[0]
        model_target.append([
            get_distribution(elos[0]),
            get_distribution(elos[1])
        ])

        to_sq_seq = sample[1]
        from_sq_seq = sample[2]
        promo_seq = sample[3]
        move_seq = list(zip(from_sq_seq, to_sq_seq, promo_seq))

        img_seq = get_img_seq(to_sq_seq, from_sq_seq, promo_seq)

        images.append(img_seq)
        moves.append(torch.tensor(move_seq))
        lengths.append(len(move_seq))

    images = pad_sequence(images, batch_first=True)
    moves = pad_sequence(moves, batch_first=True)
    lengths = torch.tensor(lengths)
    model_target = torch.tensor(model_target, dtype=torch.float32)

    return images, moves, lengths, model_target

