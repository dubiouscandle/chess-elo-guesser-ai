# This file takes in games and prints out a CSV-formatted output.
import os
from pathlib import Path
from typing import List

import msgpack
import torch
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import ConcatDataset, DataLoader, Subset

from main.data import brackets, MPDataset, get_img_seq, EloFromDistribution
from main.net import Model


def collate_fn(games: List):
    images, moves, lengths = [], [], []
    model_target = []

    for sample in games:
        elos = sample[0]
        model_target.append([elos[0], elos[1]])

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


def get_data_set():
    datasets = []
    for bracket in brackets:
        here = Path(__file__).resolve().parent
        path = here / f"../DataParsing/data/{str(bracket).zfill(4)}_00.msgpack"
        if os.path.exists(path):
            print(path)
            with open(path, "rb") as f:
                games = msgpack.unpack(f, raw=False)
                print(len(games))
                dataset = MPDataset(games)
                datasets.append(Subset(dataset, [i for i in range(0, min(1000, len(dataset)))]))

    return ConcatDataset(datasets)


if __name__ == "__main__":
    device = torch.device("cpu")
    torch.set_num_threads(16)

    model = Model().to(device)
    state_dict = torch.load("chess_elo_model.pt", map_location=device)

    new_state_dict = {
        key.removeprefix("_orig_mod."): value
        for key, value in state_dict.items()
    }
    model.load_state_dict(new_state_dict)
    model.eval()

    dataset = get_data_set()

    data_loader = DataLoader(
        dataset,
        num_workers=8,
        prefetch_factor=4,
        collate_fn=collate_fn,
        batch_size=1,
        shuffle=True
    )

    print("--------------------")
    sb = []

    with torch.inference_mode():
        print(len(data_loader))

        for i, (images, moves, lengths, model_target) in enumerate(data_loader):
            out_w, out_b, _, _ = model(images, moves, lengths)

            w_pred = torch.exp(out_w[0, -1, :]).numpy()
            b_pred = torch.exp(out_b[0, -1, :]).numpy()

            sb.append(
                f"{EloFromDistribution(w_pred).get()}, "
                f"{model_target[0][0].item()}, "
                f"{EloFromDistribution(b_pred).get()}, "
                f"{model_target[0][1].item()}"
            )

            if len(sb) % 100 == 0:
                print(len(sb))

            if len(sb) >= 100000:
                break

    print(str.join('\n', sb))


    # note to self, run this in terminal: python testing.py  > stat_data
