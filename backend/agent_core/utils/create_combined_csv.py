# %%
import os
import glob
import pandas as pd

# Order matters for global id offsets (90 each)
MODULES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'L', 'M', 'MB', 'N', 'P']

# Zero-based mapping for block offsets
BLOCK_INDEX = {m: i for i, m in enumerate(MODULES)}

# Paths
JSON_TMPL = './interview_agent/prompts/patients_with_system_prompts_module_{mod}.json'
PRED_DIR_TMPL = './patient_agent_results/patients_with_system_prompts_module_{mod}/'
PRED_FILE_EXACT = "predictions_gpt-4o-mini.csv"  # set to 'predictions_gpt-4o-mini.csv' to force a specific file

OUTPUT_PATH = './patient_agent_results/prediction_combined_all_modules.csv'
# OUTPUT_PATH = './prediction_combined_all_modules.csv'

# Columns to carry from JSON
META_COLS = [
    'id',
    'Module',
    'Tier of Symptom Disclosure',
    'Expected Symptom Direction',
    'Emotion/Tone Tier'
]

combined_parts = []

for mod in MODULES:
    base_offset = BLOCK_INDEX[mod] * 90  # A->0 (starts at ID 1), B->90 (starts at ID 91), ...

    # Load meta JSON
    json_path = JSON_TMPL.format(mod=mod)
    if not os.path.exists(json_path):
        print(f'[WARN] JSON not found for module {mod}: {json_path}')
        continue

    meta_df = pd.read_json(json_path)
    meta_df = meta_df[META_COLS].copy()

    # Create a stable local position 1..len(meta) based on JSON order
    # _json_order is 0-based; _local_pos is 1-based.
    meta_df = meta_df.reset_index(drop=False).rename(columns={'index': '_json_order'})
    meta_df['_local_pos'] = meta_df['_json_order'] + 1
    meta_df = meta_df.drop(columns=['_json_order'])

    # Load predictions file
    pred_dir = PRED_DIR_TMPL.format(mod=mod)
    if PRED_FILE_EXACT:
        pred_path = os.path.join(pred_dir, PRED_FILE_EXACT)
        pred_files = [pred_path] if os.path.exists(pred_path) else []
    else:
        pred_files = sorted(glob.glob(os.path.join(pred_dir, 'predictions_*.csv')),
                            key=os.path.getmtime)

    if not pred_files:
        print(f'[WARN] No predictions file found for module {mod} in {pred_dir}. Skipping.')
        continue

    pred_path = pred_files[-1]
    pred_df = pd.read_csv(pred_path)  # expects: id,label,prediction

    # Keep last prediction per id if duplicates exist
    pred_df = pred_df.drop_duplicates(subset=['id'], keep='last')

    # Merge on original id
    merged = pd.merge(pred_df, meta_df, on='id', how='inner')

    if merged.empty:
        print(f'[WARN] No matching IDs for module {mod}. Skipping.')
        continue

    # FIX 1: Rename the original ID before overwriting it with the global ID
    merged = merged.rename(columns={'id': 'original_file_id'})

    # Debug ranges
    print(f"[{mod}] original id range: {merged['original_file_id'].min()}..{merged['original_file_id'].max()}")
    print(f"[{mod}] local positions present: {merged['_local_pos'].min()}..{merged['_local_pos'].max()}")

    # Global id = base_offset + local position (Correctly starts at 1 for the first element)
    # e.g., for Module A: 0 + 1 = 1
    merged['id'] = merged['_local_pos'].astype(int) + base_offset

    # Drop helper column
    merged = merged.drop(columns=['_local_pos'])

    # Keep requested columns
    merged = merged[['id', 'label', 'prediction',
                     'Module', 'Tier of Symptom Disclosure',
                     'Expected Symptom Direction', 'Emotion/Tone Tier']]

    combined_parts.append(merged)

# ---
# Combine all modules and save
# ---
if combined_parts:
    combined_df = pd.concat(combined_parts, ignore_index=True).sort_values('id').reset_index(drop=True)
    combined_df = combined_df[['id', 'label', 'prediction',
                               'Module', 'Tier of Symptom Disclosure',
                               'Expected Symptom Direction', 'Emotion/Tone Tier']]

    # FIX 2: Resolve the output path to an absolute path for robust saving
    absolute_output_path = os.path.abspath(OUTPUT_PATH)
    output_dir = os.path.dirname(absolute_output_path)

    os.makedirs(output_dir, exist_ok=True)
    combined_df.to_csv(absolute_output_path, index=False)

    print(f'[OK] Combined CSV saved to: {absolute_output_path}')
    print(f'[INFO] Rows: {len(combined_df)}, ID range: {combined_df.id.min()}..{combined_df.id.max()}')
else:
    print('[WARN] Nothing combined. No data generated.')