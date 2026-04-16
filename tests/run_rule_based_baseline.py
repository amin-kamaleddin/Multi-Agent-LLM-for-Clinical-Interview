"""
Rule-based baseline: post-hoc diagnosis from raw interview transcripts.

Run from repo root:
    python tests/run_rule_based_baseline.py --module A

Outputs:
    baselines_rule_based/module_{LETTER}/diagnosis_{id}.json
    baselines_rule_based/module_{LETTER}/predictions_rule_based.csv
"""

import argparse
import csv
import json
import os
import re
from pathlib import Path

from rule_based_engine import run_rule_diagnosis, prediction_from_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run rule-based baseline for a given module.")
    parser.add_argument("--module", default="A", help="Module letter (default: A)")
    parser.add_argument("--force", action="store_true", help="Re-run even if predictions CSV already exists")
    args = parser.parse_args()

    letter = args.module.upper()

    module_json_path = f"./modules/module_{letter.lower()}.json"
    patients_json_path = f"./backend/agent_core/interview_agent/prompts/patients_with_system_prompts_module_{letter}.json"
    transcripts_dir = f"./patient_agent_results/patients_with_system_prompts_module_{letter}"
    rules_dir = "./baselines/rules"
    output_dir = f"./baselines_rule_based/module_{letter}"
    output_csv_path = f"{output_dir}/predictions_rule_based.csv"

    for p, label in [
        (module_json_path, "module JSON"),
        (patients_json_path, "patients JSON"),
        (transcripts_dir, "transcripts dir"),
        (f"{rules_dir}/module_{letter}.json", "module rule config"),
    ]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Cannot find {label}: {p}")

    if os.path.exists(output_csv_path) and not args.force:
        print(f"Predictions already exist at {output_csv_path}. Use --force to re-run.")
        return

    with open(patients_json_path, "r", encoding="utf-8") as f:
        patients_data = json.load(f)
    id_to_label = {
        int(p["id"]): "true" if p["Expected Symptom Direction"] == "Positive Symptom Presentation" else "false"
        for p in patients_data
    }

    csv_pattern = re.compile(r"^(\d+)\.csv$")
    patient_ids = sorted(
        int(csv_pattern.match(name).group(1))
        for name in os.listdir(transcripts_dir)
        if csv_pattern.match(name)
    )

    print(f"Module {letter} — {len(patient_ids)} patients found")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    rows = []
    for pid in patient_ids:
        csv_path = os.path.join(transcripts_dir, f"{pid}.csv")
        label = id_to_label.get(pid, "")
        if not label:
            print(f"  [{pid}] WARNING: no ground truth label found, skipping")
            continue

        print(f"  [{pid}/{patient_ids[-1]}] Running...", end=" ", flush=True)
        try:
            result = run_rule_diagnosis(letter, csv_path, rules_dir=rules_dir)
            diag_json_path = os.path.join(output_dir, f"diagnosis_{pid}.json")
            with open(diag_json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4)

            prediction = prediction_from_result(letter, result)
            print(f"label={label}, pred={prediction}")
        except Exception as exc:
            print(f"ERROR: {exc}")
            prediction = "false"

        rows.append({"id": pid, "label": label, "prediction": prediction})

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "label", "prediction"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Predictions saved to {output_csv_path}")


if __name__ == "__main__":
    main()
