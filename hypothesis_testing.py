"""
hypothesis_testing.py
---------------------
Compares Rule-Based, Single-Agent, and Multi-Agent systems across five
classification metrics (Accuracy, Sensitivity, Specificity, F1, F2) using
matched samples (same 150 module × group × condition test cases evaluated by
all three systems).

Tests used (mirrors the Psychotherapy-Agent approach):
  1. Friedman test — omnibus non-parametric test for 3 matched groups.
     Applied per metric; BH-FDR correction across the 5 metrics.
  2. Pairwise Wilcoxon signed-rank test — post-hoc for each of the 3 pairs
     (Rule vs Single, Rule vs Multi, Single vs Multi).
     Bonferroni correction for 3 comparisons; BH-FDR across 5 metrics within
     each pair.
  3. Effect size — rank-biserial correlation r = 1 - (2W)/(n*(n+1)) for each
     Wilcoxon test (analogous to the Cohen's d used in Psychotherapy-Agent).

Why these tests?
  - Data are bounded [0, 100] percentages, non-normal (many 0s / 100s from
    rare-condition rows), so parametric t-tests / ANOVA are inappropriate.
  - Samples ARE matched: every system was evaluated on the exact same 150
    module × group × condition combinations, making paired/matched tests valid.
  - Friedman generalises the paired Wilcoxon to k > 2 groups.

Outputs (saved to stats/):
  stats/friedman_results.csv
  stats/wilcoxon_rule_vs_single.csv
  stats/wilcoxon_rule_vs_multi.csv
  stats/wilcoxon_single_vs_multi.csv
  figures/hypothesis_test_summary.svg / .jpg
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy.stats import friedmanchisquare, wilcoxon
from statsmodels.stats.multitest import multipletests

# ── Paths ──────────────────────────────────────────────────────────────────────
MULTI_CSV  = "patient_agent_results/evaluation_results.csv"
SINGLE_CSV = "baselines/evaluation_results_single_agent.csv"
RULE_CSV   = "baselines/evaluation_results_rule_based.csv"
STATS_DIR  = "stats"
FIG_DIR    = "figures"

os.makedirs(STATS_DIR, exist_ok=True)
os.makedirs(FIG_DIR,   exist_ok=True)

# ── Metrics ────────────────────────────────────────────────────────────────────
METRICS = ["accuracy", "sensitivity", "specificity", "f1", "f2"]
METRIC_LABELS = {
    "accuracy":    "Accuracy",
    "sensitivity": "Sensitivity",
    "specificity": "Specificity",
    "f1":          "F1",
    "f2":          "F2",
}

KEY_COLS = ["module", "group", "condition"]

# ── Load & merge on matched keys ───────────────────────────────────────────────
def load_merged():
    multi  = pd.read_csv(MULTI_CSV)
    single = pd.read_csv(SINGLE_CSV)
    rule   = pd.read_csv(RULE_CSV)

    # Rename metric columns to avoid clashes
    def tag(df, tag):
        rename = {f"{m}_mean": f"{m}_{tag}" for m in METRICS}
        return df[KEY_COLS + list(rename.keys())].rename(columns=rename)

    merged = (tag(rule,   "rule")
              .merge(tag(single, "single"), on=KEY_COLS)
              .merge(tag(multi,  "multi"),  on=KEY_COLS))

    print(f"Matched rows: {len(merged)}")
    return merged


# ── Effect size: rank-biserial correlation ─────────────────────────────────────
def rank_biserial(w_stat, n):
    """r = 1 - 2W / (n*(n+1))  (ranges –1 to +1, like Pearson r)."""
    return 1 - (2 * w_stat) / (n * (n + 1))


# ── 1. Friedman test ───────────────────────────────────────────────────────────
def run_friedman(merged):
    records = []
    for metric in METRICS:
        r = merged[f"{metric}_rule"].values
        s = merged[f"{metric}_single"].values
        m = merged[f"{metric}_multi"].values

        stat, p = friedmanchisquare(r, s, m)
        n = len(r)

        records.append({
            "Metric":           METRIC_LABELS[metric],
            "N":                n,
            "Friedman_Chi2":    round(stat, 4),
            "p_value":          p,
            "Significant":      "Yes" if p < 0.05 else "No",
            "rule_mean":        round(r.mean(), 3),
            "single_mean":      round(s.mean(), 3),
            "multi_mean":       round(m.mean(), 3),
            "rule_std":         round(r.std(ddof=1), 3),
            "single_std":       round(s.std(ddof=1), 3),
            "multi_std":        round(m.std(ddof=1), 3),
        })

    df = pd.DataFrame(records)

    # BH-FDR across 5 metrics
    reject, p_bh, _, _ = multipletests(df["p_value"].values, alpha=0.05, method="fdr_bh")
    df["p_fdr_bh"]          = p_bh
    df["Significant_fdr_bh"] = ["Yes" if r else "No" for r in reject]

    path = os.path.join(STATS_DIR, "friedman_results.csv")
    df.to_csv(path, index=False)
    print(f"\n[Friedman] Saved → {path}")
    print(df[["Metric", "Friedman_Chi2", "p_value", "Significant", "p_fdr_bh", "Significant_fdr_bh"]].to_string(index=False))
    return df


# ── 2. Pairwise Wilcoxon ───────────────────────────────────────────────────────
def run_wilcoxon_pair(merged, tag1, tag2, label1, label2, filename):
    N_PAIRS = 3   # Bonferroni family: 3 pairwise comparisons
    records = []

    for metric in METRICS:
        x = merged[f"{metric}_{tag1}"].values
        y = merged[f"{metric}_{tag2}"].values
        n = len(x)

        stat, p = wilcoxon(x, y, alternative="two-sided")

        diff      = x - y
        mean_diff = diff.mean()
        direction = (f"{label1} > {label2}" if mean_diff > 0 else
                     f"{label2} > {label1}" if mean_diff < 0 else "Equal")

        records.append({
            "Metric":           METRIC_LABELS[metric],
            "N":                n,
            "W_statistic":      round(stat, 4),
            "p_value":          p,
            "Significant":      "Yes" if p < 0.05 else "No",
            f"{tag1}_mean":     round(x.mean(), 3),
            f"{tag2}_mean":     round(y.mean(), 3),
            f"{tag1}_std":      round(x.std(ddof=1), 3),
            f"{tag2}_std":      round(y.std(ddof=1), 3),
            "Mean_Difference":  round(mean_diff, 3),
            "Direction":        direction,
            "Effect_Size_r":    round(rank_biserial(stat, n), 4),
        })

    df = pd.DataFrame(records)
    p_vals = df["p_value"].values

    # Bonferroni (×3 pairs)
    df["p_bonferroni"]          = np.minimum(p_vals * N_PAIRS, 1.0)
    df["Significant_bonferroni"] = ["Yes" if p < 0.05 else "No"
                                    for p in df["p_bonferroni"]]

    # BH-FDR across 5 metrics within this pair
    reject, p_bh, _, _ = multipletests(p_vals, alpha=0.05, method="fdr_bh")
    df["p_fdr_bh"]          = p_bh
    df["Significant_fdr_bh"] = ["Yes" if r else "No" for r in reject]

    path = os.path.join(STATS_DIR, filename)
    df.to_csv(path, index=False)
    print(f"\n[Wilcoxon {label1} vs {label2}] Saved → {path}")
    print(df[["Metric", "W_statistic", "p_value", "Significant",
              "p_bonferroni", "Significant_bonferroni",
              "Mean_Difference", "Direction", "Effect_Size_r"]].to_string(index=False))
    return df


# ── 3. Summary visualisation ───────────────────────────────────────────────────
def plot_summary(friedman_df, wilcoxon_dfs):
    """
    Two-panel figure:
      Left:  Friedman chi² per metric (bar chart, colour by significance)
      Right: Effect-size heat-map from pairwise Wilcoxon (metrics × pairs)
    """
    metrics_order = [METRIC_LABELS[m] for m in METRICS]

    pair_labels  = ["Rule vs Single", "Rule vs Multi", "Single vs Multi"]
    pair_dfs     = wilcoxon_dfs   # same order

    # Build effect-size matrix (5 metrics × 3 pairs)
    es_matrix  = np.zeros((len(METRICS), len(pair_labels)))
    sig_matrix = np.full((len(METRICS), len(pair_labels)), "", dtype=object)

    for j, (pair_label, pdf) in enumerate(zip(pair_labels, pair_dfs)):
        for i, ml in enumerate(metrics_order):
            row = pdf[pdf["Metric"] == ml]
            if row.empty:
                continue
            es_matrix[i, j]  = row["Effect_Size_r"].values[0]
            sig = row["Significant_bonferroni"].values[0]
            sig_matrix[i, j] = "*" if sig == "Yes" else ""

    fig, (ax_bar, ax_heat) = plt.subplots(
        1, 2, figsize=(15, 5.5),
        gridspec_kw={"width_ratios": [1, 1.8]}
    )
    fig.subplots_adjust(wspace=0.55)

    # ── Left: Friedman chi² bars ───────────────────────────────────────────────
    chi2_vals = friedman_df.set_index("Metric").loc[metrics_order, "Friedman_Chi2"].values
    sig_fdr   = friedman_df.set_index("Metric").loc[metrics_order, "Significant_fdr_bh"].values
    bar_colors = ["#d62728" if s == "Yes" else "#aec7e8" for s in sig_fdr]

    y_pos = np.arange(len(metrics_order))
    bars  = ax_bar.barh(y_pos, chi2_vals, color=bar_colors, edgecolor="white", height=0.55)
    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(metrics_order, fontsize=11)
    ax_bar.set_xlabel("Friedman χ²", fontsize=10)
    ax_bar.set_title("Friedman Test\n(omnibus across 3 systems)", fontsize=11, fontweight="bold")
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.axvline(0, color="grey", lw=0.8)

    # Extend x-axis enough that outside labels never overflow
    ax_bar.set_xlim(0, chi2_vals.max() * 1.45)

    # Significance label: always placed just to the right of the bar end
    for bar, s in zip(bars, sig_fdr):
        label = "p<0.05 (FDR)" if s == "Yes" else "n.s."
        x = bar.get_width()
        ax_bar.text(
            x + chi2_vals.max() * 0.02,
            bar.get_y() + bar.get_height() / 2,
            label, va="center", ha="left",
            fontsize=8.5,
            color="#d62728" if s == "Yes" else "grey"
        )

    sig_patch = mpatches.Patch(color="#d62728", label="Significant (FDR-corrected)")
    ns_patch  = mpatches.Patch(color="#aec7e8", label="Not significant")
    ax_bar.legend(handles=[sig_patch, ns_patch], fontsize=8, frameon=False,
                  loc="upper right", bbox_to_anchor=(1.0, -0.12))

    # ── Right: Effect-size heatmap ─────────────────────────────────────────────
    abs_max = max(abs(es_matrix).max(), 0.01)
    im = ax_heat.imshow(es_matrix, aspect="auto", cmap="RdBu_r",
                         vmin=-abs_max, vmax=abs_max)

    ax_heat.set_xticks(range(len(pair_labels)))
    ax_heat.set_xticklabels(pair_labels, fontsize=9, rotation=15, ha="right")
    ax_heat.set_yticks(range(len(metrics_order)))
    ax_heat.set_yticklabels(metrics_order, fontsize=11)
    ax_heat.set_title("Pairwise Wilcoxon Effect Size (r)\n(* = Bonferroni-significant)",
                       fontsize=11, fontweight="bold")

    for i in range(len(metrics_order)):
        for j in range(len(pair_labels)):
            val  = es_matrix[i, j]
            star = sig_matrix[i, j]
            text = f"{val:.2f}{star}"
            color = "white" if abs(val) > abs_max * 0.55 else "black"
            ax_heat.text(j, i, text, ha="center", va="center",
                         fontsize=10, color=color, fontweight="bold")

    cbar = plt.colorbar(im, ax=ax_heat, fraction=0.046, pad=0.04)
    cbar.set_label("Rank-biserial r\n(positive = left system higher)", fontsize=8)

    fig.suptitle(
        "Statistical Comparison: Rule-Based vs Single-Agent vs Multi-Agent\n"
        "Friedman omnibus test + pairwise Wilcoxon signed-rank (matched samples, N=150)",
        fontsize=12, fontweight="bold", y=1.02
    )

    for ext in ("svg", "jpg"):
        path = os.path.join(FIG_DIR, f"hypothesis_test_summary.{ext}")
        kw = dict(bbox_inches="tight", pad_inches=0.15)
        if ext == "jpg":
            kw.update(dpi=300, facecolor="white")
        fig.savefig(path, format=ext, **kw)
        print(f"Saved: {path}")

    plt.show()


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    merged = load_merged()

    friedman_df = run_friedman(merged)

    wlx_rule_single = run_wilcoxon_pair(
        merged, "rule", "single", "Rule-Based", "Single-Agent",
        "wilcoxon_rule_vs_single.csv"
    )
    wlx_rule_multi = run_wilcoxon_pair(
        merged, "rule", "multi", "Rule-Based", "Multi-Agent",
        "wilcoxon_rule_vs_multi.csv"
    )
    wlx_single_multi = run_wilcoxon_pair(
        merged, "single", "multi", "Single-Agent", "Multi-Agent",
        "wilcoxon_single_vs_multi.csv"
    )

    plot_summary(friedman_df, [wlx_rule_single, wlx_rule_multi, wlx_single_multi])
