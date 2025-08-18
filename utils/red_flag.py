import os
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

# from interview_agent.cli import _load_key # uncomment if needed

# Load your model (make sure OPENAI_API_KEY is set in env)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ---- Red flag detector using ChatOpenAI ----
def detect_red_flag(user_input: str) -> bool:
    system_prompt = """You are a classifier that determines if a message 
    contains a mental health crisis red flag.
    Red flags include: self-harm, suicidal thoughts, wanting to die, or severe hopelessness.
    Respond ONLY with "YES" or "NO"."""  

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ])

    answer = response.content.strip().upper()
    return answer == "YES"


# ---------------- RUNNER USING CSV ----------------

def run_tests_with_csv(csv_path: str, save_path: str = None):
    """
    Runs test cases from a CSV file with columns: data, label
    Adds a 'prediction' column and optionally saves the updated CSV.
    """
    # _load_key()  # if you're using your own key loader
    df = pd.read_csv(csv_path)

    predictions = []
    for text in df["data"]:
        result = detect_red_flag(text)
        predictions.append(int(result))  # 1 for YES, 0 for NO

    # Add predictions to dataframe
    df["prediction"] = predictions

    # Calculate accuracy
    correct = (df["label"] == df["prediction"]).sum()
    total = len(df)
    accuracy = correct / total * 100
    print(f"Final Accuracy: {accuracy:.2f}% ({correct}/{total})")

    # Save updated dataset with predictions if requested
    if save_path:
        df.to_csv(save_path, index=False)
        print(f"Results saved to {save_path}")

    return df


if __name__ == "__main__":
    dataset_path = "./utils/redflag_dataset.csv"   # path to your dataset
    output_path = "./utils/redflag_dataset_with_predictions.csv"
    df_with_preds = run_tests_with_csv(dataset_path, output_path)
    print(df_with_preds.head())
