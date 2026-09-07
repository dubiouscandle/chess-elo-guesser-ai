import torch
from torch import nn, GradScaler, autocast
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import Subset, DataLoader

from Python.main.data import get_data_sets, collate_fn
from Python.main.net import Model

if __name__ == "__main__":
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    torch.set_printoptions(profile="full")
    torch.set_float32_matmul_precision('high')
    torch.cuda.manual_seed_all(42)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    train_dataset, test_dataset = get_data_sets(0.01)

    print("Train samples:", len(train_dataset))
    print("Test samples:", len(test_dataset))

    batch_size = 64
    train_dataloader = DataLoader(train_dataset, shuffle=True, batch_size=batch_size, num_workers=16,
                                  collate_fn=collate_fn, pin_memory=True)
    test_dataloader = DataLoader(test_dataset, shuffle=True, batch_size=batch_size, num_workers=28,
                                 collate_fn=collate_fn, pin_memory=True, prefetch_factor=10)

    max_epochs = 10

    model = Model().to(device)
    model = torch.compile(model)
    model.train()

    optimizer = AdamW(model.parameters(), lr=0.001)
    scheduler = ReduceLROnPlateau(optimizer, "min", 0.5, 5)
    loss_fn = nn.KLDivLoss(reduction='none')
    scaler = GradScaler()

    for epoch in range(max_epochs):
        print("EPOCH:", epoch)
        for i, (images, moves, lengths, model_target) in enumerate(train_dataloader):
            images = images.to(device, non_blocking=True)
            moves = moves.to(device, non_blocking=True)
            model_target = model_target.to(device, non_blocking=True)

            optimizer.zero_grad()
            with autocast(device_type='cuda'):
                prediction_w, prediction_b, lengths_w, lengths_b = model(images, moves, lengths)
                model_target = model_target.unbind(dim=1)
                model_target_w = model_target[0]
                model_target_b = model_target[1]

                model_target_w = model_target_w.unsqueeze(1).expand(prediction_w.shape)
                model_target_b = model_target_b.unsqueeze(1).expand(prediction_b.shape)

                loss_w = loss_fn(prediction_w, model_target_w)
                loss_b = loss_fn(prediction_b, model_target_b)

                lengths_w = lengths_w.to(device)
                lengths_b = lengths_b.to(device)

                mask_w = (torch.arange(loss_w.size(1), device=device)[None, :] < lengths_w[:, None]).unsqueeze(-1)
                mask_b = (torch.arange(loss_b.size(1), device=device)[None, :] < lengths_b[:, None]).unsqueeze(-1)
                loss_w = loss_w * mask_w
                loss_b = loss_b * mask_b
                loss = (loss_w.sum(dim=(1, 2)) / lengths_w).mean() + (loss_b.sum(dim=(1, 2)) / lengths_b).mean()

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            if i % 1000 == 0:
                print("Validating...")
                model.eval()
                accumulated_loss = 0.0
                with torch.no_grad():
                    for i, (images, moves, lengths, model_target) in enumerate(test_dataloader):
                        images = images.to(device, non_blocking=True)
                        moves = moves.to(device, non_blocking=True)
                        model_target = model_target.to(device, non_blocking=True)

                        prediction_w, prediction_b, lengths_w, lengths_b = model(images, moves, lengths)
                        model_target = model_target.unbind(dim=1)
                        model_target_w = model_target[0]
                        model_target_b = model_target[1]

                        model_target_w = model_target_w.unsqueeze(1).expand(prediction_w.shape)
                        model_target_b = model_target_b.unsqueeze(1).expand(prediction_b.shape)

                        loss_w = loss_fn(prediction_w, model_target_w)
                        loss_b = loss_fn(prediction_b, model_target_b)

                        lengths_w = lengths_w.to(device)
                        lengths_b = lengths_b.to(device)

                        mask_w = (torch.arange(loss_w.size(1), device=device)[None, :] < lengths_w[:, None]).unsqueeze(-1)
                        mask_b = (torch.arange(loss_b.size(1), device=device)[None, :] < lengths_b[:, None]).unsqueeze(-1)
                        loss_w = loss_w * mask_w
                        loss_b = loss_b * mask_b
                        loss = (loss_w.sum(dim=(1, 2)) / lengths_w).mean() + (loss_b.sum(dim=(1, 2)) / lengths_b).mean()

                        accumulated_loss += loss.item()

                model.train()
                scheduler.step(accumulated_loss)
                torch.save(model.state_dict(), f"../chess_elo_model.pt")
                print("LOSS:", accumulated_loss / len(test_dataloader))
