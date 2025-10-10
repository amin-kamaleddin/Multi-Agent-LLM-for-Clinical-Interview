# %%
import os
import glob
import pandas as pd

# Order matters for global id offsets (90 each)
MODULES = ['A','B','C','D','E','F','G','H','I','J','L','M','MB','N','P']

# Zero-based mapping for block offsets
BLOCK_INDEX = {m: i for i, m in enumerate(MODULES)}

# Paths
JSON_TMPL = './interview_agent/prompts/patients_with_system_prompts_module_{mod}.json'
PRED_DIR_TMPL = './patient_agent_results/patients_with_system_prompts_module_{mod}/'
PRED_FILE_EXACT = None  # set to 'predictions_gpt-4o-mini.csv' to force a specific file

OUTPUT_PATH = '../patient_agent_results/prediction_combined_all_modules.csv'

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
    base_offset = BLOCK_INDEX[mod] * 90  # A->0, B->90, ...

    # Load meta JSON
    json_path = JSON_TMPL.format(mod=mod)
    if not os.path.exists(json_path):
        print(f'[WARN] JSON not found for module {mod}: {json_path}')
        continue

    meta_df = pd.read_json(json_path)
    meta_df = meta_df[META_COLS].copy()

    # Create a stable local position 1..len(meta) based on JSON order
    # If you prefer by numeric sort of id within the JSON, use: meta_df.sort_values('id', kind="stable")
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

    # Merge on original id, then compute global id using the local position
    merged = pd.merge(pred_df, meta_df, on='id', how='inner')

    if merged.empty:
        print(f'[WARN] No matching IDs for module {mod}. Skipping.')
        continue

    # Debug ranges
    print(f"[{mod}] original id range: {merged['id'].min()}..{merged['id'].max()}")
    print(f"[{mod}] local positions present: {merged['_local_pos'].min()}..{merged['_local_pos'].max()}")

    # Global id = base_offset + local position
    merged['id'] = merged['_local_pos'].astype(int) + base_offset

    # Drop helper column
    merged = merged.drop(columns=['_local_pos'])

    # Keep requested columns
    merged = merged[['id', 'label', 'prediction',
                     'Module', 'Tier of Symptom Disclosure',
                     'Expected Symptom Direction', 'Emotion/Tone Tier']]

    combined_parts.append(merged)

# Combine all modules
if combined_parts:
    combined_df = pd.concat(combined_parts, ignore_index=True).sort_values('id').reset_index(drop=True)
    combined_df = combined_df[['id', 'label', 'prediction',
                               'Module', 'Tier of Symptom Disclosure',
                               'Expected Symptom Direction', 'Emotion/Tone Tier']]
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    combined_df.to_csv(OUTPUT_PATH, index=False)
    print(f'[OK] Combined CSV saved to: {OUTPUT_PATH}')
    print(f'[INFO] Rows: {len(combined_df)}, ID range: {combined_df.id.min()}..{combined_df.id.max()}')
else:
    print('[WARN] Nothing combined. No data generated.')
