"""
plot_overall_metric_comparison.py

Produces a figure with 5 panels (one per metric: Accuracy, Specificity,
Sensitivity, F1, F2). Each panel shows the mean ± 95 % CI for the three
systems (Rule-Based, Single-Agent, Multi-Agent), computed over the matched
module × group × condition rows in the evaluation-results CSVs.

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

KEY_COLS = ["module", "group", "condition"]

# ── Scenarios ──────────────────────────────────────────────────────────────────
SCENARIOS = [
    ("Rule-Based",    RULE_CSV,   "#2ca02c"),   # green
    ("Single-Agent",  SINGLE_CSV, "#ff7f0e"),   # orange
    ("Multi-Agent",   MULTI_CSV,  "#1f77b4"),   # blue
]


# ── Load & merge on matched keys ──────────────────────────────────────────────
def load_merged():
    multi = pd.read_csv(MULTI_CSV)
    single = pd.read_csv(SINGLE_CSV)
    rule = pd.read_csv(RULE_CSV)

    def tag(df: pd.DataFrame, tag: str):
        rename = {f"{metric}_mean": f"{metric}_{tag}" for metric in METRICS}
        return df[KEY_COLS + list(rename.keys())].rename(columns=rename)

    merged = (tag(rule, "rule")
              .merge(tag(single, "single"), on=KEY_COLS)
              .merge(tag(multi, "multi"), on=KEY_COLS))

    return merged


# ── Helper: compute matched-row mean ± 95% CI ────────────────────────────────
def row_mean_and_ci(values: pd.Series):
    """
    Compute mean ± 95% CI over the same matched row values used in
    hypothesis_testing: one observation per module × group × condition row.
    """
    values = values.dropna().to_numpy(dtype=float)

    n = len(values)
    if n == 0:
        return np.nan, np.nan
    if n == 1:
        return values[0], 0.0

    mean = values.mean()
    std = values.std(ddof=1)
    se = std / np.sqrt(n)
    ci = t.ppf(0.975, df=n - 1) * se

    return mean, ci


# ── Load matched data ─────────────────────────────────────────────────────────
merged = load_merged()


# ── Build summary table ────────────────────────────────────────────────────────
records = []
scenario_tags = {
    "Rule-Based": "rule",
    "Single-Agent": "single",
    "Multi-Agent": "multi",
}

for label, _, _ in SCENARIOS:
    tag = scenario_tags[label]
    for metric in METRICS:
        m, ci = row_mean_and_ci(merged[f"{metric}_{tag}"])
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
