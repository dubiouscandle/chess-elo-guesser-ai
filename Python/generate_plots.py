import pandas as pd
import plotly.graph_objects as go

# Load data
df = pd.read_csv("stat_data_cleaned")

# Combine White and Black data into a single unified series
pred_combined = pd.concat([df["w_pred"], df["b_pred"]], ignore_index=True)
true_combined = pd.concat([df["w_true"], df["b_true"]], ignore_index=True)

# Calculate global extents for axes and identity line
min_val = min(pred_combined.min(), true_combined.min())
max_val = max(pred_combined.max(), true_combined.max())

fig = go.Figure()

# Single combined scatter trace
fig.add_trace(
    go.Scattergl(
        x=pred_combined,
        y=true_combined,
        mode="markers",
        name="Predictions vs Truth",
        marker=dict(
            color="#00d4ff",
            size=2,
            opacity=0.08,
            line=dict(width=0),
        ),
    )
)

# Reference identity line (y = x)
fig.add_shape(
    type="line",
    x0=min_val,
    y0=min_val,
    x1=max_val,
    y1=max_val,
    line=dict(color="#ff4d4d", width=1.5, dash="dash"),
)

# Text annotation for the reference line
fig.add_annotation(
    x=max_val,
    y=max_val,
    text="Ideal (y = x)",
    showarrow=False,
    xanchor="right",
    yanchor="bottom",
    font=dict(color="#ff4d4d", size=11),
)

fig.update_layout(
    title=f"Model Predictions vs. Truth ({len(pred_combined):,} Points)",
    xaxis_title="Predicted Value",
    yaxis_title="True Value",
    plot_bgcolor="#1e1e24",
    paper_bgcolor="#2b2d30",
    font=dict(color="#f0f0f0"),
    yaxis=dict(scaleanchor="x", scaleratio=1),
    width=900,
    height=750,
    showlegend=False,
)

# Display interactive plot
fig.show()

# Export static high-res image
fig.write_image("predictions_vs_truth.png", width=900, height=750, scale=2)