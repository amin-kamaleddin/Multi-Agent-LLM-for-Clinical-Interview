import argparse
import os
from pathlib import Path

import pandas as pd


DEFAULT_MODULES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "L", "M", "MB", "N", "P"]
DEFAULT_OUTPUT_CSV = "baselines/predictions_single_llm_combined_clean.csv"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a clean, deduplicated single-agent combined predictions CSV."
    )
    parser.add_argument(
        "--output-csv",
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT_CSV})",
    )
    parser.add_argument(
        "--modules",
        default=",".join(DEFAULT_MODULES),
        help="Comma-separated module letters to include (default: A,B,C,D,E,F,G,H,I,J,L,M,MB,N,P)",
    )
    return parser.parse_args()


def load_module_rows(module_letter: str) -> pd.DataFrame:
    baseline_csv = f"baselines/module_{module_letter}/predictions_single_llm_gpt-4o-mini.csv"
    patients_json = (
        f"backend/agent_core/interview_agent/prompts/"
        f"patients_with_system_prompts_module_{module_letter}.json"
    )

    if not os.path.exists(baseline_csv):
        raise FileNotFoundError(f"Missing baseline predictions for module {module_letter}: {baseline_csv}")
    if not os.path.exists(patients_json):
        raise FileNotFoundError(f"Missing patient metadata for module {module_letter}: {patients_json}")

    base_df = pd.read_csv(baseline_csv)
    required_pred_cols = {"id", "label", "prediction"}
    pred_missing = sorted(required_pred_cols - set(base_df.columns))
    if pred_missing:
        raise ValueError(
            f"Module {module_letter}: missing prediction columns: {', '.join(pred_missing)}"
        )

    base_df = base_df[["id", "label", "prediction"]].copy()
    base_df["id"] = base_df["id"].astype(int)
    if base_df["id"].duplicated().any():
        dup_ids = base_df.loc[base_df["id"].duplicated(), "id"].tolist()
        raise ValueError(f"Module {module_letter}: duplicate ids in baseline CSV: {dup_ids[:5]}")

    meta_df = pd.read_json(patients_json)
    required_meta_cols = {
        "id",
        "Module",
        "Tier of Symptom Disclosure",
        "Expected Symptom Direction",
        "Emotion/Tone Tier",
    }
    meta_missing = sorted(required_meta_cols - set(meta_df.columns))
    if meta_missing:
        raise ValueError(
            f"Module {module_letter}: missing metadata columns: {', '.join(meta_missing)}"
        )

    meta_df = meta_df[
        [
            "id",
            "Module",
            "Tier of Symptom Disclosure",
            "Expected Symptom Direction",
            "Emotion/Tone Tier",
        ]
    ].copy()
    meta_df["id"] = meta_df["id"].astype(int)
    if meta_df["id"].duplicated().any():
        dup_ids = meta_df.loc[meta_df["id"].duplicated(), "id"].tolist()
        raise ValueError(f"Module {module_letter}: duplicate ids in patient metadata: {dup_ids[:5]}")

    merged = base_df.merge(meta_df, on="id", how="left", indicator=True)
    missing_meta = merged.loc[merged["_merge"] != "both", "id"].tolist()
    if missing_meta:
        raise ValueError(
            f"Module {module_letter}: missing patient metadata for ids: {missing_meta[:10]}"
        )
    merged = merged.drop(columns=["_merge"])
    merged["module_letter"] = module_letter
    return merged


def main():
    args = parse_args()
    modules = [m.strip().upper() for m in args.modules.split(",") if m.strip()]
    module_order = {m: i for i, m in enumerate(modules)}

    frames = []
    for mod in modules:
        df = load_module_rows(mod)
        frames.append(df)
        print(f"[{mod}] rows: {len(df)}")

    combined = pd.concat(frames, ignore_index=True)
    dup = combined.duplicated(subset=["Module", "id"])
    if dup.any():
        dup_rows = combined.loc[dup, ["Module", "id"]].head(10).to_dict("records")
        raise ValueError(
            f"Duplicate (Module, id) rows in combined output. Sample duplicates: {dup_rows}"
        )

    combined["_module_order"] = combined["module_letter"].map(module_order)
    combined = combined.sort_values(by=["_module_order", "id"], kind="stable")
    combined = combined.drop(columns=["module_letter", "_module_order"])

    combined = combined[
        [
            "id",
            "label",
            "prediction",
            "Module",
            "Tier of Symptom Disclosure",
            "Expected Symptom Direction",
            "Emotion/Tone Tier",
        ]
    ]

    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)

    print(f"Saved clean combined CSV: {output_path}")
    print(f"Rows: {len(combined)} | Modules: {combined['Module'].nunique()}")


if __name__ == "__main__":
    main()
