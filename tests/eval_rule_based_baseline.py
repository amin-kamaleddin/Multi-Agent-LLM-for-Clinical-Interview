"""
Compare rule-based baseline predictions against the multi-agent system for a module.

Run from repo root:
    python tests/eval_rule_based_baseline.py --module A
"""

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from eval_single_llm_baseline import (
    compute_metrics,
    mcnemar_test,
    load_predictions,
    print_stratified_f2,
)

COMBINED_CSV = "./baselines/predictions_rule_based_combined.csv"


def print_metrics_table_rule(multi: dict, rule: dict) -> None:
    metrics = ["Accuracy", "Precision", "Recall", "Specificity", "F1", "F2"]
    print(f"\n{'Metric':<14} {'Multi-agent':>12} {'Rule-based':>12} {'d':>10}")
    print("-" * 52)
    for m in metrics:
        mv, rv = multi[m], rule[m]
        delta = mv - rv
        print(f"{m:<14} {mv:>12.4f} {rv:>12.4f} {delta:>+10.4f}")
    print("-" * 52)
    print(f"{'TP/TN/FP/FN':<14} "
          f"{multi['TP']}/{multi['TN']}/{multi['FP']}/{multi['FN']:>3}  "
          f"{rule['TP']}/{rule['TN']}/{rule['FP']}/{rule['FN']:>3}")


def append_to_combined(merged: pd.DataFrame, module_name: str) -> None:
    out = pd.DataFrame({
        "id": merged["id"],
        "label": merged["label"].map({True: "TRUE", False: "FALSE"}),
        "prediction": merged["pred_rule"].map({True: "TRUE", False: "FALSE"}),
        "Module": module_name,
        "Tier of Symptom Disclosure": merged.get("Tier of Symptom Disclosure", pd.Series([""] * len(merged))),
        "Expected Symptom Direction": merged.get("Expected Symptom Direction", pd.Series([""] * len(merged))),
        "Emotion/Tone Tier": merged.get("Emotion/Tone Tier", pd.Series([""] * len(merged))),
    })

    write_header = not Path(COMBINED_CSV).exists()
    out.to_csv(COMBINED_CSV, mode="a", index=False, header=write_header)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare rule-based baseline vs. multi-agent system.")
    parser.add_argument("--module", default="A", help="Module letter (default: A)")
    parser.add_argument("--reset-combined", action="store_true", help="Delete combined CSV before append")
    args = parser.parse_args()

    letter = args.module.upper()

    if args.reset_combined and Path(COMBINED_CSV).exists():
        Path(COMBINED_CSV).unlink()
        print(f"Deleted existing combined CSV: {COMBINED_CSV}")

    baseline_csv = f"./baselines_rule_based/module_{letter}/predictions_rule_based.csv"
    multiagent_csv = f"./patient_agent_results/patients_with_system_prompts_module_{letter}/predictions_gpt-4o-mini.csv"
    patients_json = f"./backend/agent_core/interview_agent/prompts/patients_with_system_prompts_module_{letter}.json"
    module_json = f"./modules/module_{letter.lower()}.json"

    for p, label in [
        (baseline_csv, "rule-based predictions"),
        (multiagent_csv, "multi-agent predictions"),
        (patients_json, "patient metadata"),
        (module_json, "module JSON"),
    ]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Cannot find {label}: {p}")

    with open(module_json, "r", encoding="utf-8") as f:
        module_def = json.load(f)
    module_name = f"{letter} - {module_def['module']['name']}"

    df_base = load_predictions(baseline_csv).rename(columns={"prediction": "pred_rule"})
    df_multi = load_predictions(multiagent_csv).rename(columns={"prediction": "pred_multi", "label": "label_multi"})
    merged = df_base.merge(df_multi[["id", "pred_multi"]], on="id", how="inner")

    with open(patients_json, "r", encoding="utf-8") as f:
        patients_data = json.load(f)
    meta = pd.DataFrame(patients_data)
    meta["id"] = meta["id"].astype(int)
    merged = merged.merge(
        meta[["id", "Tier of Symptom Disclosure", "Expected Symptom Direction", "Emotion/Tone Tier"]],
        on="id",
        how="left",
    )

    y_true = merged["label"].tolist()
    y_pred_multi = merged["pred_multi"].tolist()
    y_pred_rule = merged["pred_rule"].tolist()

    print(f"\n=== Module {letter} — Rule-based Baseline vs. Multi-Agent System ===")
    print(f"Patients evaluated: {len(merged)}")

    print("\n--- Overall Metrics ---")
    m_multi = compute_metrics(y_true, y_pred_multi)
    m_rule = compute_metrics(y_true, y_pred_rule)
    print_metrics_table_rule(m_multi, m_rule)

    p_val = mcnemar_test(y_true, y_pred_multi, y_pred_rule)
    print("\n--- McNemar's Test (multi-agent vs. rule-based) ---")
    print(f"  p-value: {p_val:.4f}  {'** statistically significant (p < 0.05)' if p_val < 0.05 else 'not significant'}")

    print("\n--- Stratified F2 Breakdown ---")
    for col in ["Tier of Symptom Disclosure", "Expected Symptom Direction", "Emotion/Tone Tier"]:
        if col in merged.columns:
            print_stratified_f2(merged.rename(columns={"pred_rule": "pred_baseline"}), col)

    disagree = merged[merged["pred_multi"] != merged["pred_rule"]]
    print(f"\n--- Disagreements (n={len(disagree)}) ---")
    if disagree.empty:
        print("  No disagreements — systems produced identical predictions.")
    else:
        print(f"  {'ID':>4}  {'True':>6}  {'Multi':>6}  {'Rule':>6}  {'Tier'}")
        print("  " + "-" * 62)
        for _, row in disagree.iterrows():
            tier = str(row.get("Tier of Symptom Disclosure", "")).replace("Tier ", "T")[:30]
            print(f"  {int(row['id']):>4}  {str(row['label']):>6}  {str(row['pred_multi']):>6}  {str(row['pred_rule']):>6}  {tier}")

    f2_gap = m_multi["F2"] - m_rule["F2"]
    print("\n--- Summary ---")
    print(f"  Multi-agent F2:  {m_multi['F2']:.4f}")
    print(f"  Rule-based F2:   {m_rule['F2']:.4f}")
    if f2_gap > 0:
        print(f"  Multi-agent outperforms rule-based by dF2 = {f2_gap:+.4f}")
    elif f2_gap < 0:
        print(f"  Rule-based outperforms multi-agent by dF2 = {-f2_gap:+.4f}")
    else:
        print("  Systems are tied on F2.")

    append_to_combined(merged, module_name)
    print(f"\n  Combined CSV updated: {COMBINED_CSV}")


if __name__ == "__main__":
    main()
