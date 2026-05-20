"""
plot_overall_metric_comparison.py

Produces a figure with 5 panels (one per metric: Accuracy, Specificity,
Sensitivity, F1, F2).  Each panel shows the grand-mean ± 95 % CI for the
three systems (Rule-Based, Single-Agent, Multi-Agent), computed from all
module × condition rows in the respective evaluation-results CSV.

Output: figures/overall_metric_comparison.svg / .jpg
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy.stats import t

# ── Paths ──────────────────────────────────────────────────────────────────────
MULTI_CSV  = "patient_agent_results/evaluation_results.csv"
SINGLE_CSV = "baselines/evaluation_results_single_agent.csv"
RULE_CSV   = "baselines/evaluation_results_rule_based.csv"
OUT_DIR    = "figures"

# ── Metrics & display labels ───────────────────────────────────────────────────
METRICS = ["accuracy", "sensitivity", "specificity", "f1", "f2"]
METRIC_LABELS = {
    "accuracy":    "Accuracy",
    "sensitivity": "Sensitivity",
    "specificity": "Specificity",
    "f1":          "F1",
    "f2":          "F2",
}

# ── Scenarios ──────────────────────────────────────────────────────────────────
SCENARIOS = [
    ("Rule-Based",    RULE_CSV,   "#2ca02c"),   # green
    ("Single-Agent",  SINGLE_CSV, "#ff7f0e"),   # orange
    ("Multi-Agent",   MULTI_CSV,  "#1f77b4"),   # blue
]


# ── Helper: compute grand mean ± 95 % CI ──────────────────────────────────────
def mean_ci(series: pd.Series):
    """Return (mean, ci_half_width) using the t-distribution."""
    vals = series.dropna().values
    n = len(vals)
    if n < 2:
        return float(vals[0]) if n == 1 else (np.nan, np.nan)
    mean   = vals.mean()
    se     = vals.std(ddof=1) / np.sqrt(n)
    ci     = t.ppf(0.975, df=n - 1) * se
    return mean, ci


# ── Load data ──────────────────────────────────────────────────────────────────
dfs = {}
for label, path, _ in SCENARIOS:
    dfs[label] = pd.read_csv(path)


# ── Build summary table ────────────────────────────────────────────────────────
records = []
for label, _, _ in SCENARIOS:
    df = dfs[label]
    for metric in METRICS:
        col = f"{metric}_mean"
        m, ci = mean_ci(df[col])
        records.append({"scenario": label, "metric": metric,
                        "mean": m, "ci": ci})

summary = pd.DataFrame(records)


# ── Plot ───────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 5, figsize=(13, 4.5), sharey=True)
fig.subplots_adjust(wspace=0.08)

x_positions = np.array([0, 1, 2])          # one tick per scenario
x_labels    = [s[0] for s in SCENARIOS]
colors      = [s[2] for s in SCENARIOS]

for ax, metric in zip(axes, METRICS):
    sub = summary[summary["metric"] == metric].reset_index(drop=True)

    for i, (label, _, color) in enumerate(SCENARIOS):
        row  = sub[sub["scenario"] == label].iloc[0]
        mean = row["mean"]
        ci   = row["ci"]

        ax.errorbar(
            x=i, y=mean,
            yerr=ci,
            fmt="o",
            color=color,
            markersize=7,
            capsize=6,
            capthick=1.8,
            linewidth=1.8,
            zorder=3,
        )

    ax.set_title(METRIC_LABELS[metric], fontsize=12, fontweight="bold", pad=6)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(["RB", "SA", "MA"], fontsize=9)
    ax.set_xlim(-0.6, 2.6)
    ax.set_ylim(0, 105)
    ax.tick_params(axis="y", labelsize=9)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)

# shared y-label only on the leftmost panel
axes[0].set_ylabel("Mean Score ± 95% CI (%)", fontsize=10)

# legend
legend_handles = [
    mpatches.Patch(color=color, label=label)
    for label, _, color in SCENARIOS
]
fig.legend(
    handles=legend_handles,
    loc="lower center",
    ncol=3,
    fontsize=10,
    frameon=False,
    bbox_to_anchor=(0.5, -0.04),
)

fig.suptitle(
    "Overall Mean Score ± 95% CI by Metric and System",
    fontsize=13,
    fontweight="bold",
    y=1.02,
)

# ── Save ───────────────────────────────────────────────────────────────────────
os.makedirs(OUT_DIR, exist_ok=True)

svg_path = os.path.join(OUT_DIR, "overall_metric_comparison.svg")
jpg_path = os.path.join(OUT_DIR, "overall_metric_comparison.jpg")

fig.savefig(svg_path, format="svg", bbox_inches="tight", pad_inches=0.1)
print(f"Saved: {svg_path}")

fig.savefig(jpg_path, format="jpg", dpi=300, bbox_inches="tight",
            pad_inches=0.1, facecolor="white")
print(f"Saved: {jpg_path}")

plt.show()
