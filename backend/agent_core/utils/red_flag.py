import os
import pandas as pd
import json
from pydantic import BaseModel, Field, ValidationError
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from sklearn.metrics import precision_score, recall_score, f1_score, fbeta_score, confusion_matrix
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

    system_prompt = """You are a clinical mental health safety classifier. Your task is to determine whether a message contains a RED FLAG — any expression of suicidal ideation, self-harm urge, wish to die or not exist, or dangerous proximity to means of self-harm.

RED FLAGS include BOTH explicit AND implicit expressions:

EXPLICIT red flags (direct language):
- Statements naming suicide, self-harm, wanting to die, ending one's life, or harming oneself.
  Examples: "I want to kill myself", "I've been cutting", "I plan to overdose"
- Coded method references — messages that reference a specific lethal method or means even without naming suicide:
  * Enclosed space + vehicle/hose: "the hose in the garage is ready", "the car and garage will do the trick"
  * Tying knots or rope in a personal context: "I've been practicing tying knots for what I need to do"
  * Train, bridge, or tall structure at a specific time: "I'm checking train schedules for tonight", "the train schedule is memorized for Saturday night"
  * Sealed goodbye letters: "each letter I wrote is stamped and sealed"
  * Acquired means for an unstated purpose: "I've rented a car with a particular purpose in mind", "I finalized my plan for Saturday night"
  When content implies a specific lethal means at a specific time, flag it even if suicide is never named.

IMPLICIT red flags — passive ideation (emotional/metaphorical):
- Passive death wish: longing for non-existence, welcoming silence/darkness/ending, wishing not to wake up, attraction to "eternal rest" or "final peace"
  Examples: "Silence seems more welcoming than the chaos inside me", "The world spins fine without my presence"
- Wanting mental or emotional cessation: desiring thoughts, pain, or noise to permanently stop — distinct from wanting a break
  Examples: "I just want the noise in my head to stop", "I wish my mind would go quiet forever", "I want to stop feeling anything"
- Ghost/fading/shadow imagery expressing feeling already non-existent or invisible:
  Examples: "I feel like a ghost wandering through life", "I feel like I'm already fading away", "I'm stuck in the shadows"
- Burden/invisibility: expressing that one's absence or disappearance would be unnoticed or beneficial
  Examples: "I feel like I'm just an afterthought in everyone's story", "I'm stuck in a life that doesn't want me", "nobody would notice if I were gone"
- Exhaustion from existing: profound tiredness of being alive, of fighting to exist, of trying to matter
  Examples: "I'm tired of the fight that never ends", "exhausted from trying to matter", "I can't keep fighting just to be here"
- Feeling trapped with no future: "how do you keep going when you're this lost?", "I see no way out", "I don't see myself in any future"

IMPLICIT red flags — active ideation (behavioral/planning signals):
- Behavioral proximity to means: repeated visits to high-risk locations, calculating height/depth, lingering near means
  Examples: "I walk by the lake each day calculating its depth", "every visit to the garage feels more significant now", "whenever I drive past the river, I stop to think"
- Cryptic planning language: marking a private date, referencing a plan only the speaker understands, feeling peace as planning progresses
  Examples: "the calendar on my wall highlights a day only I understand", "the more I plan, the more at peace I feel", "I finalized something for Saturday no one knows about"
- Writing unsent farewell communications:
  Examples: "I'm writing letters I never intend to send", "I recorded a message for when I'm no longer here"
- Vague research into methods framed as seeking peace/rest:
  Examples: "I've been researching ways to ensure a lasting peace", "I've been looking into what brings permanent calm"
- Giving away possessions or settling affairs without explanation

DO NOT flag:
- Ordinary sadness, stress, or frustration without any death/self-harm/disappearance theme
- Feeling stuck in a situation (job, relationship) with no proximity to death or non-existence
- Answering a clinical question with a simple yes/no without crisis content
- Figurative idioms where the death/harm word is clearly non-literal and the emotional context is neutral or positive:
  Examples: "that hike murdered my knees", "I could kill for a coffee", "I died laughing", "to die for", "killing it at the gym"
- Professional clinical or forensic documentation — speaker is clearly a clinician/researcher describing a patient or case, not themselves:
  Examples: "my patient had been researching methods", "the coroner's report confirmed the method", "in EM training, high-lethality plans are escalation triggers"
- Academic or literary analysis — speaker is analytically discussing a text or character's death wish, not expressing their own:
  Examples: "Hamlet's soliloquy expresses passive ideation", "Victorian poets romanticised death as a trope"
- Creative/professional writing context where the speaker describes a fictional character's actions with clear authorial distance and positive/neutral tone:
  Examples: "plotting the villain's escape route — love this part", "my mystery novel research has me visiting archives"

When in doubt about implicit signals with NO clear contextual carve-out above, err on the side of flagging (favour recall over precision for safety).

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

def _compute_metrics(y_true, y_pred, label: str = "Overall") -> dict:
    """Compute and print Accuracy, Precision, Recall, Specificity, F1, F2 for a subset."""
    accuracy = (y_true == y_pred).mean() * 100
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    f2 = fbeta_score(y_true, y_pred, beta=2, zero_division=0)

    # Specificity = TN / (TN + FP) — only meaningful if negatives present
    has_negatives = (y_true == 0).any()
    if has_negatives:
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        specificity = tn / (tn + fp) if (tn + fp) > 0 else float("nan")
        fp_count = int(fp)
        fn_count = int(fn)
    else:
        specificity = float("nan")
        fp_count = 0
        fn_count = int((y_true != y_pred).sum())

    print(f"\n-- {label} (n={len(y_true)}) --")
    print(f"  Accuracy    : {accuracy:.2f}%")
    print(f"  Precision   : {precision:.4f}")
    print(f"  Recall      : {recall:.4f}")
    print(f"  Specificity : {specificity:.4f}" if not __import__('math').isnan(specificity) else "  Specificity : N/A (no negatives)")
    print(f"  F1 Score    : {f1:.4f}")
    print(f"  F2 Score    : {f2:.4f}")
    print(f"  FP={fp_count}  FN={fn_count}")

    return {
        "subset": label,
        "n": len(y_true),
        "n_pos": int((y_true == 1).sum()),
        "n_neg": int((y_true == 0).sum()),
        "accuracy": round(accuracy, 2),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4) if not __import__('math').isnan(specificity) else None,
        "f1": round(f1, 4),
        "f2": round(f2, 4),
        "fp": fp_count,
        "fn": fn_count,
    }


def run_tests_with_csv(csv_path: str, save_path: str = None):
    """
    Runs test cases from a CSV file.

    Required columns : data, label
    Optional columns : expression_type (explicit/implicit),
                       ideation_type   (active/passive)

    Adds 'prediction' and 'explanation' columns.
    When the optional stratification columns are present, reports metrics
    broken down by expression_type and ideation_type in addition to overall.
    """
    df = pd.read_csv(csv_path)

    predictions = []
    explanations = []

    for text in df["data"]:
        result, reason = detect_red_flag(text, numbering=True)
        predictions.append(int(result))  # 1 for YES, 0 for NO
        explanations.append(reason)

    df["prediction"] = predictions
    df["explanation"] = explanations

    y_true = df["label"]
    y_pred = df["prediction"]

    # ── Save predictions first (before any print that could crash) ────────────
    if save_path:
        df.to_csv(save_path, index=False, encoding="utf-8")
        print(f"Results saved to {save_path}")

    # -- Overall metrics --
    summary_rows = []
    summary_rows.append(_compute_metrics(y_true, y_pred, label="Overall"))

    # -- Stratified metrics (if columns present) --
    if "expression_type" in df.columns:
        for val in sorted(df["expression_type"].dropna().unique()):
            mask = df["expression_type"] == val
            summary_rows.append(
                _compute_metrics(y_true[mask], y_pred[mask], label=f"expression_type={val}")
            )

    if "ideation_type" in df.columns:
        for val in sorted(df["ideation_type"].dropna().unique()):
            mask = df["ideation_type"] == val
            summary_rows.append(
                _compute_metrics(y_true[mask], y_pred[mask], label=f"ideation_type={val}")
            )

    if "negative_category" in df.columns:
        for val in sorted(df["negative_category"].dropna().unique()):
            mask = df["negative_category"] == val
            summary_rows.append(
                _compute_metrics(y_true[mask], y_pred[mask], label=f"negative_category={val}")
            )

    # -- Save summary metrics --
    if save_path:
        summary_path = save_path.replace(".csv", "_summary_metrics.csv")
        pd.DataFrame(summary_rows).to_csv(summary_path, index=False, encoding="utf-8")
        print(f"Summary metrics saved to {summary_path}")

    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run red-flag detection on a dataset CSV.")
    parser.add_argument(
        "--input",
        default="./utils/redflag_dataset.csv",
        help="Path to input CSV (columns: data, label [, expression_type, ideation_type])",
    )
    parser.add_argument(
        "--output",
        default="./utils/redflag_dataset_with_predictions.csv",
        help="Path to save output CSV with predictions appended",
    )
    args = parser.parse_args()

    df_with_preds = run_tests_with_csv(args.input, args.output)
    print(df_with_preds.head())

    # Examples:
    #   python utils/red_flag.py
    #   python utils/red_flag.py --input utils/redflag_dataset.csv \
    #                            --output utils/redflag_dataset_with_predictions.csv
