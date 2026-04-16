# ── plot_bootstrap_figures.py ──────────────────────────────────────────────────
# Reads evaluation_results.csv (output of evaluate_bootstrap.py) and produces
# one heatmap figure per metric per group, in the same visual style as the
# original evaluation script.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
import os
import warnings
warnings.filterwarnings('ignore')

# ── Config ─────────────────────────────────────────────────────────────────────
RESULTS_PATH       = "evaluation_results.csv"
FIGURES_OUTPUT_DIR = "./figures"

os.makedirs(FIGURES_OUTPUT_DIR, exist_ok=True)

METRICS = ["accuracy", "sensitivity", "specificity", "f1", "f2"]

GROUPS = ["Symptom Direction", "Symptom Disclosure", "Emotional Tone"]

GROUP_TITLES = {
    "Symptom Direction":  "Performance by Module and Symptom Direction",
    "Symptom Disclosure": "Performance by Module and Symptom Disclosure Tier",
    "Emotional Tone":     "Performance by Module and Emotion/Tone Tier",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def save_figure(fig, filename_base, output_dir=FIGURES_OUTPUT_DIR):
    clean = "".join(
        c for c in filename_base if c.isalnum() or c in (' ', '-', '_')
    ).rstrip().replace(' ', '_')

    svg_path = os.path.join(output_dir, f"{clean}.svg")
    fig.savefig(svg_path, format='svg', bbox_inches='tight', pad_inches=0.1)
    print(f"  Saved SVG: {svg_path}")

    jpg_path = os.path.join(output_dir, f"{clean}.jpg")
    fig.savefig(jpg_path, format='jpg', dpi=600, bbox_inches='tight',
                pad_inches=0.1, facecolor='white', edgecolor='none')
    print(f"  Saved JPG: {jpg_path}")


def build_matrices(df, group, metric):
    """
    Pivot evaluation_results.csv into:
        mean_matrix  : DataFrame (modules x conditions), float  — already in %
        annot_matrix : DataFrame (modules x conditions), string "mean\n±ci"
    Appends a Mean row and Mean column.
    """
    subset = df[df["group"] == group].copy()

    mean_col = f"{metric}_mean"
    ci_low_col  = f"{metric}_ci_low"
    ci_high_col = f"{metric}_ci_high"

    # Pivot to matrix
    mean_pivot = subset.pivot(index="module", columns="condition", values=mean_col)
    ci_low_pivot  = subset.pivot(index="module", columns="condition", values=ci_low_col)
    ci_high_pivot = subset.pivot(index="module", columns="condition", values=ci_high_col)
    ci_pivot = (ci_high_pivot - ci_low_pivot) / 2

    # Add Mean column
    mean_pivot["Mean"] = mean_pivot.mean(axis=1, skipna=True)
    ci_pivot["Mean"]   = ci_pivot.mean(axis=1, skipna=True)

    # Add Mean row
    mean_row      = mean_pivot.mean(axis=0, skipna=True)
    mean_row.name = "Mean"
    ci_row        = ci_pivot.mean(axis=0, skipna=True)
    ci_row.name   = "Mean"

    mean_pivot = pd.concat([mean_pivot, mean_row.to_frame().T])
    ci_pivot   = pd.concat([ci_pivot,   ci_row.to_frame().T])

    # Build annotation strings  "66.7\n±5.8"
    annot = mean_pivot.copy().astype(object)
    for r in mean_pivot.index:
        for c in mean_pivot.columns:
            mv = mean_pivot.loc[r, c]
            cv = ci_pivot.loc[r, c]
            if pd.isna(mv):
                annot.loc[r, c] = "N/A"
            else:
                annot.loc[r, c] = f"{mv:.1f}\n±{cv:.1f}"

    return mean_pivot, annot


def plot_heatmap(mean_matrix, annot_matrix, metric, group, title_suffix):
    """Create heatmap with same style as original script, annotated with mean±CI."""
    n_cols = len(mean_matrix.columns)
    n_rows = len(mean_matrix.index)
    fig_width  = max(8, n_cols * 1.1)
    fig_height = max(5, n_rows * 0.65)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    plt.rcParams['font.family'] = 'Helvetica'
    plt.rcParams['font.size']   = 10

    blues_custom = plt.cm.Blues(np.linspace(0.3, 0.9, 256))
    custom_cmap  = LinearSegmentedColormap.from_list('custom_blues', blues_custom)

    sns.heatmap(
        mean_matrix,
        annot=annot_matrix,
        fmt='',                      # fmt must be '' when annot is strings
        cmap=custom_cmap,
        vmin=50.0,
        vmax=100.0,
        cbar_kws={
            'label': f'{metric.upper()} Score (%)',
            'shrink': 0.8,
        },
        linewidths=0.2,
        linecolor='white',
        square=True,
        ax=ax,
        annot_kws={
            'fontsize': 8,
            'fontfamily': 'Helvetica',
            'fontweight': 'bold',
        }
    )

    metric_name = metric.upper()
    ax.set_title(
        f'{metric_name} Score: {title_suffix}',
        fontsize=10, fontweight='bold', pad=10, fontfamily='Helvetica'
    )
    ax.set_xlabel(group,    fontsize=10, fontweight='bold', fontfamily='Helvetica')
    ax.set_ylabel('Module', fontsize=10, fontweight='bold', fontfamily='Helvetica')

    ax.set_xticklabels(ax.get_xticklabels(),
                       rotation=45, ha='right', fontsize=9, fontfamily='Helvetica')
    ax.set_yticklabels(ax.get_yticklabels(),
                       rotation=0, fontsize=9, fontfamily='Helvetica')

    cbar = ax.collections[0].colorbar
    cbar.ax.tick_params(labelsize=9)
    for label in cbar.ax.get_yticklabels():
        label.set_fontfamily('Helvetica')
    cbar.ax.yaxis.label.set_fontfamily('Helvetica')
    cbar.ax.yaxis.label.set_fontsize(10)

    plt.tight_layout(pad=0.5)
    plt.subplots_adjust(left=0.15, right=0.95, top=0.92, bottom=0.2)

    return fig


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"Reading: {RESULTS_PATH}")
    df = pd.read_csv(RESULTS_PATH)

    print(f"Figures will be saved to: {os.path.abspath(FIGURES_OUTPUT_DIR)}\n")
    print("=" * 60)

    for group in GROUPS:
        title = GROUP_TITLES[group]
        group_df = df[df["group"] == group]

        if group_df.empty:
            print(f"No data for group '{group}', skipping.")
            continue

        print(f"\nGroup: {group}")

        for metric in METRICS:
            print(f"  Metric: {metric.upper()}")

            mean_matrix, annot_matrix = build_matrices(df, group, metric)
            fig = plot_heatmap(mean_matrix, annot_matrix, metric, group, title)

            filename = f"{metric}_{group}_heatmap"
            save_figure(fig, filename)
            plt.close(fig)

    print("\n" + "=" * 60)
    print("DONE")
    print(f"All figures saved to: {os.path.abspath(FIGURES_OUTPUT_DIR)}")
    print("=" * 60)


if __name__ == "__main__":
    main()