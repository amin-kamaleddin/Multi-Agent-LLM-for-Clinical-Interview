import os
import pandas as pd
import json
from pydantic import BaseModel, Field, ValidationError
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from sklearn.metrics import precision_score, recall_score, f1_score, fbeta_score
from dotenv import load_dotenv

load_dotenv()

# from backend.agent_core.interview_agent.cli import _load_key # uncomment if needed

# Load your model (make sure OPENAI_API_KEY is set in env)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ---- Red flag detector using ChatOpenAI ----

# Define schema for LLM output
class RedFlagResponse(BaseModel):
    answer: str = Field(..., description="Either YES or NO")
    explanation: str = Field(..., description="One short sentence justification (no private chain-of-thought)")

# Global counter for row numbers
row_counter = 0

def detect_red_flag(user_input: str, numbering: bool = False) -> tuple[bool, str]:
    global row_counter
    row_counter += 1  # increment row number for each call

    system_prompt = """You are a classifier that determines if a message 
contains a mental health crisis red flag.
Red flags include: self-harm, suicidal thoughts, wanting to die, or severe hopelessness.
If the patient is only answering an interview question (e.g., 'Do you feel hopeless?'), 
do NOT classify it as a red flag unless they describe severe crisis symptoms or explicit intent to harm themselves in their own words.
Responses describing mild or temporary feelings, even if persistent, are NOT red flags.
Respond in STRICT JSON only with exactly these keys:
{"answer":"YES or NO","explanation":"one short sentence justification (max 20 words)"}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ])

    raw = getattr(response, "content", str(response))

    try:
        data = json.loads(raw)
        parsed = RedFlagResponse(**data)
    except (json.JSONDecodeError, ValidationError):
        parsed = RedFlagResponse(answer="NO", explanation="Invalid output from model, defaulting to NO.")

    if numbering == True:
        print(f"[row {row_counter}] [red-flag] {parsed.explanation}")

    is_red_flag = parsed.answer.strip().upper() == "YES"
    return is_red_flag, parsed.explanation


# ---------------- RUNNER USING CSV ----------------

def run_tests_with_csv(csv_path: str, save_path: str = None):
    """
    Runs test cases from a CSV file with columns: data, label
    Adds a 'prediction' column and optionally saves the updated CSV.
    Also computes Accuracy, Precision, Recall, F1, and F2 scores.
    """
    df = pd.read_csv(csv_path)

    predictions = []
    explanations = []

    for text in df["data"]:
        result, reason = detect_red_flag(text, numbering=True)
        predictions.append(int(result))  # 1 for YES, 0 for NO
        explanations.append(reason)

    df["prediction"] = predictions
    df["explanation"] = explanations  # Optional but useful for audit/debugging

    # Extract ground truth and predictions
    y_true = df["label"]
    y_pred = df["prediction"]

    # Calculate metrics
    accuracy = (y_true == y_pred).mean() * 100
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    f2 = fbeta_score(y_true, y_pred, beta=2, zero_division=0)  # F-beta with β=2

    # Print results
    print(f"Final Accuracy : {accuracy:.2f}%")
    print(f"Precision      : {precision:.4f}")
    print(f"Recall         : {recall:.4f}")
    print(f"F1 Score       : {f1:.4f}")
    print(f"F2 Score       : {f2:.4f}")

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

    # print(detect_red_flag('Yes, I feel that way for about 2 weeks'))
