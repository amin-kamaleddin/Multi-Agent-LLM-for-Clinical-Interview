import pandas as pd

# Load your sentence-level file
df = pd.read_csv("clustered_conversations_with_depression.csv")

# Ensure correct dtypes
df['is_depression_related'] = df['is_depression_related'].astype(str).str.lower().isin(['true', '1', 'yes'])

# Group by conversation_id, join sentences
conv_df = (
    df[df['is_depression_related']]
    .groupby('conversation_id')
    .agg({
        'input': lambda x: " ".join(x.astype(str)),
        'is_depression_related': 'all'
    })
    .reset_index()
)

# Save to a new CSV
conv_df.to_csv("depression_conversations.csv", index=False)

print(f"Saved {len(conv_df)} depression-related conversations to depression_conversations.csv")
