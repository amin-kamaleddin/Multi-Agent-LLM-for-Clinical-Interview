import json
import csv
import os
import re
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score

# Paths
MODULE_FILE_NAME = "patients_with_system_prompts_e"
patients_file = "./interview_agent/prompts/" + MODULE_FILE_NAME + ".json"
results_dir = "./patient_agent_results/" + MODULE_FILE_NAME
output_csv = results_dir + "/predictions.csv"

# Load patients data
with open(patients_file, "r", encoding="utf-8") as f:
    patients_data = json.load(f)

# Map id → label ("true"/"false")
id_to_label = {
    int(item["id"]): "true" if item["Expected Symptom Direction"] == "Positive Symptom Presentation" else "false"
    for item in patients_data
}

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
        if module_letter in ["A", "O"]:
            key = "mustHave"
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

# Metrics
acc = accuracy_score(y_true, y_pred)
prec = precision_score(y_true, y_pred)
rec = recall_score(y_true, y_pred)
f1 = f1_score(y_true, y_pred)
tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

# Output results
print(f"CSV file created at {output_csv}")
print(f"Accuracy : {acc:.4f}")
print(f"Precision: {prec:.4f}")
print(f"Recall   : {rec:.4f}")
print(f"F1-score : {f1:.4f}")
print("Confusion Matrix (rows=true label, cols=predicted label):")
print(f"            Predicted False   Predicted True")
print(f"Actual False     {tn:5d}           {fp:5d}")
print(f"Actual True      {fn:5d}           {tp:5d}")

# Print results per module
for module, ids in wrong_ids.items():
    print(f"Module {module} wrong IDs: {ids}")