import json
import csv
import os
import re
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score, fbeta_score
import pandas as pd

# Paths
MODULE_FILE_NAME = "patients_with_system_prompts_module_L"
patients_file = "./interview_agent/prompts/" + MODULE_FILE_NAME + ".json"
results_dir = "./patient_agent_results/" + MODULE_FILE_NAME
output_csv = results_dir + "/predictions_gpt-4o-mini.csv"

# Load patients data
with open(patients_file, "r", encoding="utf-8") as f:
    patients_data = json.load(f)

# Map id → label ("true"/"false")
id_to_label = {
    int(item["id"]): "true" if item["Expected Symptom Direction"] == "Positive Symptom Presentation" else "false"
    for item in patients_data
}

# Check if CSV file already exists
if os.path.exists(output_csv):
    print(f"CSV file already exists at {output_csv}. Loading existing predictions...")
    # Read existing CSV file for metrics calculation
    df = pd.read_csv(output_csv)
    y_true = []
    y_pred = []
    wrong_ids = {}

    for _, row in df.iterrows():
        file_id = int(row['id'])
        label = row['label']  # Already boolean
        prediction = row['prediction']  # Already boolean

        # Convert boolean to our expected format for consistency
        if isinstance(label, bool) and isinstance(prediction, bool):
            y_true.append(label)
            y_pred.append(prediction)

            if label != prediction:
                # Find module for this file_id to categorize wrong predictions
                patient_entry = next((p for p in patients_data if int(p["id"]) == file_id), None)
                if patient_entry:
                    module_letter = patient_entry["Module"].split()[0]
                    wrong_ids.setdefault(module_letter, []).append(file_id)
                else:
                    # If we can't find the module, use a generic category
                    wrong_ids.setdefault("Unknown", []).append(file_id)

else:
    print(f"CSV file not found. Creating new predictions at {output_csv}...")

    # Regex pattern for valid files
    pattern = re.compile(r"^diagnosis_(\d+)\.json$")
    diagnosis_files = sorted(
        (f for f in os.listdir(results_dir) if pattern.match(f)),
        key=lambda x: int(pattern.match(x).group(1))
    )

    # Lists for evaluation
    y_true, y_pred = [], []
    wrong_ids = {}  # store wrong IDs by module

    # Write CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "label", "prediction"])

        for file_name in diagnosis_files:
            file_id = int(pattern.match(file_name).group(1))
            file_path = os.path.join(results_dir, file_name)

            # Find the patient entry for this file_id
            patient_entry = next((p for p in patients_data if int(p["id"]) == file_id), None)
            if not patient_entry:
                continue  # skip if not found

            # Determine key based on first letter of Module
            module_letter = patient_entry["Module"].split()[0]  # e.g., "A"
            if module_letter in ["A", "O", "B", "C", "H", "I", "J", "L", "G"]:
                key = "positive"
            elif module_letter in ["P", "D"]:
                key = "lifetime"
            else:
                key = "current"

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            prediction_bool = data.get(key, {}).get("diagnosis", None)
            prediction = "true" if prediction_bool is True else "false"
            label = id_to_label.get(file_id, "")

            writer.writerow([file_id, label, prediction])

            if label in ["true", "false"] and prediction in ["true", "false"]:
                truth = label == "true"
                pred = prediction == "true"
                y_true.append(truth)
                y_pred.append(pred)

                if truth != pred:
                    # Add wrong ID to the list for this module
                    wrong_ids.setdefault(module_letter, []).append(file_id)

    print(f"CSV file created at {output_csv}")

# Calculate metrics (common for both paths)
if y_true and y_pred:  # Only calculate if we have data
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred)
    rec = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    f2 = fbeta_score(y_true, y_pred, beta=2)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    # Output results
    print(f"Accuracy : {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall   : {rec:.4f}")
    print(f"F1-score : {f1:.4f}")
    print(f"F2-score : {f2:.4f}")
    print("Confusion Matrix (rows=true label, cols=predicted label):")
    print(f"            Predicted False   Predicted True")
    print(f"Actual False     {tn:5d}           {fp:5d}")
    print(f"Actual True      {fn:5d}           {tp:5d}")

    # Print results per module
    for module, ids in wrong_ids.items():
        print(f"Module {module} wrong IDs: {ids}")
else:
    print("No valid predictions found for metrics calculation.")