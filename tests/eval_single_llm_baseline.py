"""
Compare single-LLM baseline predictions against the multi-agent system
for a given module.

Run from repo root:
    python tests/eval_single_llm_baseline.py --module A

Outputs:
  - Overall side-by-side metrics table (Accuracy, Precision, Recall,
    Specificity, F1, F2, Confusion Matrix)
  - Stratified F2 breakdown by Tier, Symptom Direction, Emotion/Tone
  - McNemar's test p-value
  - List of patient IDs where the two systems disagree
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
)

# ---------------------------------------------------------------------------
# Diagnosis key per module (matches eval_patient_agent.py)
# ---------------------------------------------------------------------------
DIAGNOSIS_KEY = {
    **{m: "positive" for m in ["A", "O", "B", "C", "H", "I", "J", "L", "G"]},
    **{m: "lifetime" for m in ["P", "D"]},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_metrics(y_true: list[bool], y_pred: list[bool]) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[False, True]).ravel()
    spec = tn / (tn + fp) if (tn + fp) > 0 else float("nan")
    return {
        "Accuracy":    accuracy_score(y_true, y_pred),
        "Precision":   precision_score(y_true, y_pred, zero_division=0),
        "Recall":      recall_score(y_true, y_pred, zero_division=0),
        "Specificity": spec,
        "F1":          f1_score(y_true, y_pred, zero_division=0),
        "F2":          fbeta_score(y_true, y_pred, beta=2, zero_division=0),
        "TP": tp, "TN": tn, "FP": fp, "FN": fn,
    }


def mcnemar_test(y_true: list[bool], y_pred_a: list[bool], y_pred_b: list[bool]) -> float:
    """
    McNemar's test comparing two classifiers on the same samples.
    Returns p-value. b = A correct & B wrong, c = B correct & A wrong.
    """
    b = sum(1 for t, a, b_ in zip(y_true, y_pred_a, y_pred_b) if a == t and b_ != t)
    c = sum(1 for t, a, b_ in zip(y_true, y_pred_a, y_pred_b) if a != t and b_ == t)
    if (b + c) == 0:
        return 1.0  # no disagreements → no difference
    stat = (abs(b - c) - 1) ** 2 / (b + c)  # with continuity correction
    p = 1 - chi2.cdf(stat, df=1)
    return float(p)


def load_predictions(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Normalise label/prediction columns to bool
    for col in ["label", "prediction"]:
        if df[col].dtype == object:
            df[col] = df[col].str.strip().str.lower().map(
                {"true": True, "false": False, "1": True, "0": False}
            )
        else:
            df[col] = df[col].astype(bool)
    return df


def print_metrics_table(multi: dict, baseline: dict):
    metrics = ["Accuracy", "Precision", "Recall", "Specificity", "F1", "F2"]
    print(f"\n{'Metric':<14} {'Multi-agent':>12} {'Single-LLM':>12} {'d':>10}")
    print("-" * 52)
    for m in metrics:
        mv, bv = multi[m], baseline[m]
        delta = mv - bv
        print(f"{m:<14} {mv:>12.4f} {bv:>12.4f} {delta:>+10.4f}")
    print("-" * 52)
    print(f"{'TP/TN/FP/FN':<14} "
          f"{multi['TP']}/{multi['TN']}/{multi['FP']}/{multi['FN']:>3}  "
          f"{baseline['TP']}/{baseline['TN']}/{baseline['FP']}/{baseline['FN']:>3}")


def print_stratified_f2(merged: pd.DataFrame, col: str):
    """Print stratified breakdown.
    For strata where all labels are the same class (e.g. Expected Symptom
    Direction), F2 is undefined.  Fall back to Recall for all-positive strata
    (measures sensitivity) and Specificity for all-negative strata (measures
    selectivity), labelling the metric column accordingly.
    """
    rows = []
    use_f2 = True  # will be set False if any stratum is single-class
    for stratum, grp in merged.groupby(col):
        yt  = grp["label"].tolist()
        ym  = grp["pred_multi"].tolist()
        yb  = grp["pred_baseline"].tolist()
        if len(set(yt)) < 2:
            use_f2 = False
            all_pos = yt[0]  # True → recall, False → specificity
            if all_pos:
                vm = recall_score(yt, ym, zero_division=0)
                vb = recall_score(yt, yb, zero_division=0)
                metric = "Recall"
            else:
                tn_m, _, _, _ = confusion_matrix([not v for v in yt], [not v for v in ym], labels=[False, True]).ravel() if len(set(ym)) > 1 else (sum(1 for a, b in zip(yt, ym) if not a and not b), 0, 0, 0)
                vm = sum(1 for a, b in zip(yt, ym) if not a and not b) / sum(1 for a in yt if not a)
                vb = sum(1 for a, b in zip(yt, yb) if not a and not b) / sum(1 for a in yt if not a)
                metric = "Specificity"
        else:
            vm = fbeta_score(yt, ym, beta=2, zero_division=0)
            vb = fbeta_score(yt, yb, beta=2, zero_division=0)
            metric = "F2"
        rows.append((stratum, vm, vb, metric))

    metric_col = "Metric" if not use_f2 else "F2"
    hdr_multi   = f"Multi-agent {metric_col}"
    hdr_base    = f"Single-LLM {metric_col}"
    print(f"\n  Stratified {metric_col} by '{col}':")
    print(f"  {'Stratum':<40} {hdr_multi:>18} {hdr_base:>16} {'d':>8}")
    print("  " + "-" * 88)
    for stratum, vm, vb, metric in rows:
        label = f"{stratum} [{metric}]" if not use_f2 else str(stratum)
        print(f"  {label:<50} {vm:>14.4f} {vb:>14.4f} {vm - vb:>+8.4f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMBINED_CSV = "./baselines/predictions_single_llm_combined.csv"


def append_to_combined(merged: pd.DataFrame, module_name: str) -> None:
    """Append this module's baseline predictions to the combined CSV.

    Matches the schema of patient_agent_results/prediction_combined.csv:
        id, label, prediction, Module, Tier of Symptom Disclosure,
        Expected Symptom Direction, Emotion/Tone Tier
    """
    out = pd.DataFrame({
        "id":                        merged["id"],
        "label":                     merged["label"].map({True: "TRUE", False: "FALSE"}),
        "prediction":                merged["pred_baseline"].map({True: "TRUE", False: "FALSE"}),
        "Module":                    module_name,
        "Tier of Symptom Disclosure":   merged.get("Tier of Symptom Disclosure", pd.Series([""] * len(merged))),
        "Expected Symptom Direction":   merged.get("Expected Symptom Direction", pd.Series([""] * len(merged))),
        "Emotion/Tone Tier":            merged.get("Emotion/Tone Tier", pd.Series([""] * len(merged))),
    })

    write_header = not Path(COMBINED_CSV).exists()
    out.to_csv(COMBINED_CSV, mode="a", index=False, header=write_header)


def main():
    parser = argparse.ArgumentParser(description="Compare single-LLM baseline vs. multi-agent system.")
    parser.add_argument("--module", default="A", help="Module letter (default: A)")
    parser.add_argument("--reset-combined", action="store_true",
                        help="Delete the combined CSV before appending (use before first module in a batch)")
    args = parser.parse_args()
    letter = args.module.upper()

    if args.reset_combined and Path(COMBINED_CSV).exists():
        Path(COMBINED_CSV).unlink()
        print(f"Deleted existing combined CSV: {COMBINED_CSV}")

    # Paths
    baseline_csv  = f"./baselines/module_{letter}/predictions_single_llm_gpt-4o-mini.csv"
    multiagent_csv = f"./patient_agent_results/patients_with_system_prompts_module_{letter}/predictions_gpt-4o-mini.csv"
    patients_json  = f"./backend/agent_core/interview_agent/prompts/patients_with_system_prompts_module_{letter}.json"
    module_json    = f"./modules/module_{letter.lower()}.json"

    for p, label in [(baseline_csv, "baseline predictions"), (multiagent_csv, "multi-agent predictions"), (patients_json, "patient metadata"), (module_json, "module JSON")]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Cannot find {label}: {p}")

    # Load module name for combined CSV
    with open(module_json, "r", encoding="utf-8") as f:
        module_def = json.load(f)
    module_name = f"{letter} - {module_def['module']['name']}"

    # Load data
    df_base  = load_predictions(baseline_csv).rename(columns={"prediction": "pred_baseline"})
    df_multi = load_predictions(multiagent_csv).rename(columns={"prediction": "pred_multi", "label": "label_multi"})

    # Merge on id
    merged = df_base.merge(df_multi[["id", "pred_multi"]], on="id", how="inner")

    # Load patient metadata for stratification
    with open(patients_json, "r", encoding="utf-8") as f:
        patients_data = json.load(f)
    meta = pd.DataFrame(patients_data)
    meta["id"] = meta["id"].astype(int)
    merged = merged.merge(
        meta[["id", "Tier of Symptom Disclosure", "Expected Symptom Direction", "Emotion/Tone Tier"]],
        on="id", how="left"
    )

    y_true        = merged["label"].tolist()
    y_pred_multi  = merged["pred_multi"].tolist()
    y_pred_base   = merged["pred_baseline"].tolist()

    n = len(merged)
    print(f"\n=== Module {letter} — Single-LLM Baseline vs. Multi-Agent System ===")
    print(f"Patients evaluated: {n}")

    # -----------------------------------------------------------------------
    # 1. Overall metrics
    # -----------------------------------------------------------------------
    print("\n--- Overall Metrics ---")
    m_multi   = compute_metrics(y_true, y_pred_multi)
    m_base    = compute_metrics(y_true, y_pred_base)
    print_metrics_table(m_multi, m_base)

    # -----------------------------------------------------------------------
    # 2. McNemar's test
    # -----------------------------------------------------------------------
    p_val = mcnemar_test(y_true, y_pred_multi, y_pred_base)
    print(f"\n--- McNemar's Test (multi-agent vs. single-LLM) ---")
    print(f"  p-value: {p_val:.4f}  {'** statistically significant (p < 0.05)' if p_val < 0.05 else 'not significant'}")

    # -----------------------------------------------------------------------
    # 3. Stratified F2
    # -----------------------------------------------------------------------
    print("\n--- Stratified F2 Breakdown ---")
    for col in ["Tier of Symptom Disclosure", "Expected Symptom Direction", "Emotion/Tone Tier"]:
        if col in merged.columns:
            print_stratified_f2(merged, col)

    # -----------------------------------------------------------------------
    # 4. Disagreement list
    # -----------------------------------------------------------------------
    disagree = merged[merged["pred_multi"] != merged["pred_baseline"]]
    print(f"\n--- Disagreements (n={len(disagree)}) ---")
    if disagree.empty:
        print("  No disagreements — systems produced identical predictions.")
    else:
        print(f"  {'ID':>4}  {'True':>6}  {'Multi':>6}  {'Baseline':>9}  {'Tier'}")
        print("  " + "-" * 65)
        for _, row in disagree.iterrows():
            tier = str(row.get("Tier of Symptom Disclosure", "")).replace("Tier ", "T")[:30]
            print(f"  {int(row['id']):>4}  {str(row['label']):>6}  {str(row['pred_multi']):>6}  {str(row['pred_baseline']):>9}  {tier}")

    # -----------------------------------------------------------------------
    # 5. Summary verdict
    # -----------------------------------------------------------------------
    f2_gap = m_multi["F2"] - m_base["F2"]
    print(f"\n--- Summary ---")
    print(f"  Multi-agent F2:  {m_multi['F2']:.4f}")
    print(f"  Single-LLM F2:   {m_base['F2']:.4f}")
    if f2_gap > 0:
        print(f"  Multi-agent outperforms single-LLM by dF2 = {f2_gap:+.4f}")
    elif f2_gap < 0:
        print(f"  Single-LLM outperforms multi-agent by dF2 = {-f2_gap:+.4f}")
    else:
        print("  Systems are tied on F2.")
    print(f"  Statistical significance: {'YES (p={:.4f})'.format(p_val) if p_val < 0.05 else 'NO (p={:.4f})'.format(p_val)}")

    # -----------------------------------------------------------------------
    # 6. Append to combined baseline CSV
    # -----------------------------------------------------------------------
    append_to_combined(merged, module_name)
    print(f"\n  Combined CSV updated: {COMBINED_CSV}")


if __name__ == "__main__":
    main()
