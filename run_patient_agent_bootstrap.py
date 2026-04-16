import pandas as pd
import numpy as np
import logging
import warnings
warnings.filterwarnings("ignore")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
CSV_PATH    = "patient_agent_results/prediction_combined_all_modules.csv"
N_BOOTSTRAP = 10_000
RANDOM_SEED = 42

# ── Helpers ───────────────────────────────────────────────────────────────────

def compute_metrics(y_true, y_pred):
    y_true = np.array(y_true, dtype=int)
    y_pred = np.array(y_pred, dtype=int)

    TP = np.sum((y_true == 1) & (y_pred == 1))
    TN = np.sum((y_true == 0) & (y_pred == 0))
    FP = np.sum((y_true == 0) & (y_pred == 1))
    FN = np.sum((y_true == 1) & (y_pred == 0))

    accuracy    = (TP + TN) / (TP + TN + FP + FN) if (TP + TN + FP + FN) > 0 else 0.0
    sensitivity = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    specificity = TN / (TN + FP) if (TN + FP) > 0 else 0.0
    precision   = TP / (TP + FP) if (TP + FP) > 0 else 0.0

    f1 = (2 * precision * sensitivity / (precision + sensitivity)
          if (precision + sensitivity) > 0 else 0.0)
    f2 = (5 * precision * sensitivity / (4 * precision + sensitivity)
          if (4 * precision + sensitivity) > 0 else 0.0)

    return {"accuracy": accuracy, "sensitivity": sensitivity,
            "specificity": specificity, "f1": f1, "f2": f2}


def bootstrap_cell(subset, n_bootstrap, seed):
    rng = np.random.default_rng(seed)
    n = len(subset)
    y_true = subset["label"].values
    y_pred = subset["prediction"].values

    results = {m: np.empty(n_bootstrap) for m in
               ("accuracy", "sensitivity", "specificity", "f1", "f2")}

    for i in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        m = compute_metrics(y_true[idx], y_pred[idx])
        for key in results:
            results[key][i] = m[key]

    out = {}
    for key, vals in results.items():
        vals_pct = vals * 100
        out[key] = (
            round(float(np.mean(vals_pct)), 2),
            round(float(np.percentile(vals_pct, 2.5)),  2),
            round(float(np.percentile(vals_pct, 97.5)), 2),
        )
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info(f"Loading data from: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    log.info(f"Loaded {len(df)} rows")

    for col in ("label", "prediction"):
        df[col] = df[col].astype(str).str.strip().str.lower().map(
            {"true": 1, "false": 0, "1": 1, "0": 0, "yes": 1, "no": 0})

    groups = {
        "Symptom Direction": (
            "Expected Symptom Direction",
            ["Negative Symptom Presentation", "Positive Symptom Presentation"]
        ),
        "Symptom Disclosure": (
            "Tier of Symptom Disclosure",
            ["Tier 1: Superficial/Vague",
             "Tier 2: Basic with Minimal Detail",
             "Tier 3: Moderate Detail",
             "Tier 4: Detailed/Coherent",
             "Tier 5: Rich/Nuanced + Background"]
        ),
        "Emotional Tone": (
            "Emotion/Tone Tier",
            ["Emotional/Expressive", "Flat/Detached", "Neutral/Cooperative"]
        ),
    }

    metrics   = ["accuracy", "sensitivity", "specificity", "f1", "f2"]
    modules   = df["Module"].dropna().unique()
    n_modules = len(modules)
    total_cells = n_modules * sum(len(c) for _, c in groups.values())

    log.info(f"Modules: {n_modules} | Groups: {len(groups)} | "
             f"Total cells: {total_cells} | Bootstrap iterations: {N_BOOTSTRAP:,}")

    rows = []
    seed_counter = 0
    cell_counter = 0

    for mod_idx, mod_full in enumerate(modules, 1):
        mod_short = mod_full.split(" - ", 1)[-1]
        df_mod = df[df["Module"] == mod_full]
        log.info(f"[{mod_idx}/{n_modules}] Module: {mod_short} ({len(df_mod)} rows)")

        for group_label, (col, conditions) in groups.items():
            for condition in conditions:
                subset = df_mod[df_mod[col] == condition]
                n_total = len(subset)
                cell_counter += 1

                row = {
                    "module":    mod_short,
                    "group":     group_label,
                    "condition": condition,
                    "n_total":   n_total,
                }

                if n_total == 0:
                    log.warning(f"  [{cell_counter}/{total_cells}] "
                                f"{group_label} | {condition} — no data, skipping")
                    for m in metrics:
                        row[f"{m}_mean"]    = None
                        row[f"{m}_ci"]      = None
                        row[f"{m}_ci_low"]  = None
                        row[f"{m}_ci_high"] = None
                else:
                    log.info(f"  [{cell_counter}/{total_cells}] "
                             f"{group_label} | {condition} (n={n_total})")
                    cell = bootstrap_cell(subset, N_BOOTSTRAP,
                                          RANDOM_SEED + seed_counter)
                    seed_counter += 1
                    for m in metrics:
                        row[f"{m}_mean"]    = cell[m][0]
                        row[f"{m}_ci"]      = round((cell[m][2] - cell[m][1]) / 2, 2)
                        row[f"{m}_ci_low"]  = cell[m][1]
                        row[f"{m}_ci_high"] = cell[m][2]
                    log.info(f"    accuracy: {row['accuracy_mean']} "
                             f"+-{row['accuracy_ci']} "
                             f"[{row['accuracy_ci_low']}, {row['accuracy_ci_high']}]")

                rows.append(row)

    result_df = pd.DataFrame(rows)
    out_path = "patient_agent_results/evaluation_results.csv"
    result_df.to_csv(out_path, index=False)
    log.info(f"Saved: {out_path} ({len(result_df)} rows)")


if __name__ == "__main__":
    main()