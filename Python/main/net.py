import torch
from torch import nn, Tensor, log_softmax
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

from Python.main import data


class Model(nn.Module):
    def __init__(self):
        super().__init__()

        embedding_dim = 512
        first_conv_embed_dim = 32
        hidden_size = 512
        self.lstm_w = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            dropout=0.1,
        )
        self.lstm_b = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            dropout=0.1,
        )
        self.conv = nn.Sequential(
            nn.Conv2d(first_conv_embed_dim, 64, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(64, 128, 3, padding=1),
            nn.ReLU(),

            nn.MaxPool2d(2),
            nn.Conv2d(128, 256, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(256, 512, 3, padding=1),
            nn.ReLU(),

            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(512, embedding_dim)
        )
        self.square_embed = nn.Embedding(64, embedding_dim=first_conv_embed_dim)
        self.piece_embed = nn.Embedding(14, embedding_dim=first_conv_embed_dim)

        self.from_embed = nn.Embedding(64, embedding_dim=first_conv_embed_dim)
        self.to_embed = nn.Embedding(64, embedding_dim=first_conv_embed_dim)
        self.promo_embed = nn.Embedding(5, embedding_dim=first_conv_embed_dim)

        self.dnn_w = nn.Sequential(
            nn.Linear(hidden_size, data.brackets.__len__()),
        )
        self.dnn_b = nn.Sequential(
            nn.Linear(hidden_size, data.brackets.__len__()),
        )

    # images = [batchsize][seq_len][8][8]
    # moves = [batchsize][seq_len][3]
    # lengths = [batchsize]
    def forward(self, images: Tensor, moves: Tensor, lengths: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        batch_size, seq_len, _, _ = images.shape
        device = images.device

        square_ids = torch.arange(64, device=device).reshape(1, 1, 8, 8).expand(batch_size, seq_len, -1, -1)
        square_embed = self.square_embed(square_ids)
        piece_embed = self.piece_embed(images)
        x = piece_embed + square_embed

        from_sq, to_sq, promo = moves.unbind(dim=-1)
        file_to, rank_to = to_sq % 8, to_sq // 8
        file_from, rank_from = from_sq % 8, from_sq // 8

        to_emb = self.to_embed(to_sq)  # [B,S - 1,D]
        from_emb = self.from_embed(from_sq)  # [B,S - 1,D]
        promo_emb = self.promo_embed(promo)  # [B,S - 1,D]

        batch_idx = torch.arange(batch_size, device=device).unsqueeze(1).expand(batch_size, seq_len)
        seq_idx = torch.arange(seq_len, device=device).unsqueeze(0).expand(batch_size, seq_len)

        x[batch_idx, seq_idx, rank_to, file_to] += (to_emb + promo_emb)
        x[batch_idx, seq_idx, rank_from, file_from] += from_emb

        # cnn trickery
        _, _, _, _, first_conv_embed_dim = x.shape
        x = x.view(batch_size * seq_len, 8, 8, first_conv_embed_dim).permute(0, 3, 1, 2)
        x = self.conv(x)
        x = x.view(batch_size, seq_len, -1)
        #

        lstm_in_w = x[:, ::2, :]
        lstm_in_b = x[:, 1::2, :]

        lstm_in_w = pack_padded_sequence(lstm_in_w, (lengths + 1) // 2, enforce_sorted=False, batch_first=True)
        lstm_in_b = pack_padded_sequence(lstm_in_b, lengths // 2, enforce_sorted=False, batch_first=True)

        lstm_out_w, (_, _) = self.lstm_w(lstm_in_w)  # [batch_size][seq_len][hidden_size]
        lstm_out_b, (_, _) = self.lstm_b(lstm_in_b)  # [batch_size][seq_len][hidden_size]
        lstm_out_w, lengths_w = pad_packed_sequence(lstm_out_w, batch_first=True)
        lstm_out_b, lengths_b = pad_packed_sequence(lstm_out_b, batch_first=True)

        dnn_w = self.dnn_w(lstm_out_w)
        dnn_b = self.dnn_b(lstm_out_b)

        return log_softmax(dnn_w, dim=-1), log_softmax(dnn_b, dim=-1), lengths_w, lengths_b
