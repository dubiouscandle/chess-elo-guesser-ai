import math
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score

filename = "stat_data_cleaned"

df = pd.read_csv(filename)

w_pred = df.iloc[:, 0].to_numpy(dtype=float)
w_true = df.iloc[:, 1].to_numpy(dtype=float)
b_pred = df.iloc[:, 2].to_numpy(dtype=float)
b_true = df.iloc[:, 3].to_numpy(dtype=float)

n = len(df)

all_true = np.concatenate([w_true, b_true])
all_pred = np.concatenate([w_pred, b_pred])

w_err = w_pred - w_true
b_err = b_pred - b_true
all_err = all_pred - all_true

w_sq_err = w_err ** 2
b_sq_err = b_err ** 2
all_sq_err = all_err ** 2


def evaluate_subset(y_true, y_pred, sq_err, trim_pct=0.0):
    if trim_pct == 0.0:
        mask = np.ones(len(sq_err), dtype=bool)
    else:
        cutoff = np.quantile(sq_err, 1.0 - trim_pct)
        mask = sq_err <= cutoff

    mae = np.mean(np.abs(y_true[mask] - y_pred[mask]))
    rmse = math.sqrt(np.mean(sq_err[mask]))
    r2 = r2_score(y_true[mask], y_pred[mask])
    return mae, rmse, r2


cutoffs = [
    ("Full (100%)", 0.00),
    ("Trimmed (99%)", 0.01),
    ("Trimmed (98%)", 0.02),
    ("Trimmed (95%)", 0.05),
]

print(f"Total Games Evaluated: {n}")
print(
    "Cutoff\t\tWhite MAE\tWhite RMSE\tBlack MAE\tBlack RMSE\tOverall MAE\tOverall RMSE\tWhite R2\tOverall R2"
)

for label, trim_pct in cutoffs:
    w_mae, w_rmse, w_r2 = evaluate_subset(w_true, w_pred, w_sq_err, trim_pct)
    b_mae, b_rmse, b_r2 = evaluate_subset(b_true, b_pred, b_sq_err, trim_pct)
    all_mae, all_rmse, all_r2 = evaluate_subset(
        all_true, all_pred, all_sq_err, trim_pct
    )

    print(
        f"{label}\t{w_mae:.2f}\t\t{w_rmse:.2f}\t\t{b_mae:.2f}\t\t{b_rmse:.2f}\t\t{all_mae:.2f}\t\t{all_rmse:.2f}\t\t{w_r2:.4f}\t\t{all_r2:.4f}"
    )
