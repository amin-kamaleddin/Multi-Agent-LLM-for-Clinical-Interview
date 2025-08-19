import json, csv
from pathlib import Path
from langgraph.graph import StateGraph
from interview_agent.models import ModuleLoader, _add_log
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from interview_agent.cli import _load_key
from typing import Any, Dict, List, Literal, Optional, Sequence, Union, Annotated
from langgraph.constants import START, END
import operator
import pandas as pd

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from interview_agent.nodes import (
    questioner_node,
    should_clarify,
    get_structured_llm,
    navigator_node,
    should_diagnose,
    diagnoser_node,
    _clarify_streak
)
from utils.red_flag import detect_red_flag

from langchain_openai import ChatOpenAI

PATIENT_USER_PROMPT = """
The interviewer asks: {question}

Respond as the patient described in your system prompt. sometimes implicitly answer (dont use 'yes' or 'no') and  sometimes explicitly use 'yes' or 'no', with a brief clarification if helpful.
"""

JUDGE_SYSTEM_PROMPT = """
You are a clinical psychological assessment agent. Analyze the patient's response and provide guidance to the interviewer.

CLASSIFICATION RULES:
- "yes" - Response indicates affirmation, agreement, or provides specific information that answers the question (interpret generously)
- "no" - Response indicates negation, disagreement, or clearly answers "no" to the question
- "rephrase needed" - Response is vague, unclear, or deflects, but shows engagement with the topic. Interviewer should rephrase the same question differently
- "explain request" - Patient asks for clarification about the question itself. Interviewer should explain the question

ANALYSIS PROCESS:
1. Try to interpret the response generously - can you reasonably infer a yes/no answer?
2. If unclear but relevant, request rephrasing rather than exact repetition
3. Only use "explain request" if patient explicitly asks what the question means

LIBERAL INTERPRETATION: Err on the side of extracting meaning. Vague responses like "kind of", "I guess", "sometimes" should often be classified as "yes" or "no" based on context.

EXAMPLES:
Question: "Do you often feel sad?"
- "Yes, sometimes" → yes
- "Kind of, I guess" → yes (generous interpretation)
- "Not really" → no
- "I don't know, maybe" → rephrase needed
- "What do you mean by sad?" → explain request

Question: "How many episodes have you had?"
- "12" → yes
- "A lot" → yes (provides meaningful info)
- "I'm not sure" → rephrase needed
- "What counts as an episode?" → explain request

When classification is "rephrase needed", the interviewer should ask the same question using different words or approach, not repeat exactly.

Question: {last_question}
Patient Response: {patient_last_answer}
"""

patient_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.9)
FILE_NAME = "red_flag_prompts"

class InterviewState(BaseModel):
    messages: Annotated[Sequence, add_messages] = Field(default_factory=list)
    conversation_log: Annotated[list[dict], _add_log] = Field(default_factory=list)
    module_loader: Any
    current_question_id: Optional[str] = None
    question_path: List[str] = Field(default_factory=list)
    evaluator_results: Annotated[List[Any], operator.add] = Field(default_factory=list)
    patient_agent: bool = False
    module_completed: bool = False
    ready_for_diagnosis: bool = False
    diagnosis_content: Optional[Any] = Field(default_factory=dict)

    # NEW: store the system prompt for this conversation
    patient_system_prompt: Optional[str] = None

def patient_node(state: InterviewState):
    print("enter patient node")
    patient_system_prompt = state.patient_system_prompt  # now comes from state

    if not state.patient_agent:
        result = input("You: ").strip()
    else:
        sys_msg = SystemMessage(content=patient_system_prompt)
        patient_prompt = HumanMessage(
            content=PATIENT_USER_PROMPT.format(question=state.messages[-1].content)
        )
        result = patient_llm.invoke([sys_msg, patient_prompt])
        print(f"agent response: {result.content}")

    print(15 * '--' + f" End of question {state.current_question_id}" + 15 * '--' + '\n\n')
    return {'messages': [result]}


def evaluator_node(state: InterviewState) -> Dict[str, Any]:
    # assume the loop-driver put the user's message in state.messages[-1]
    print("enter judge")
    updates: Dict[str, Any] = {}
    last_question = state.module_loader.get_question(state.current_question_id)
    patient_last_answer = state.messages[-1]

    response_text = patient_last_answer.content.strip().lower()
    if detect_red_flag(response_text):
        print("Direct classification: RED FLAG")
        label = "red_flag"
        reasoning = f"Red flag detected: '{patient_last_answer.content}'"
    elif response_text == "yes":
        print("Direct classification: YES (no LLM call needed)")
        label = "yes"
        reasoning = f"Patient gave a clear affirmative response: '{patient_last_answer.content}'"
    elif response_text == "no":
        print("Direct classification: NO (no LLM call needed)")
        label = "no"
        reasoning = f"Patient gave a clear negative response: '{patient_last_answer.content}'"
    else:
        print("MAKING AN LLM CALL TO JUDGE THE ANSWER")
        prompt = JUDGE_SYSTEM_PROMPT.format(last_question= last_question.prompt, patient_last_answer= patient_last_answer.content)
        resp = get_structured_llm().invoke([HumanMessage(content=prompt)])

        # Access Pydantic model attributes directly
        print(f"reason behind the decision: {resp.reasoning}")
        print(f"decision: {resp.classification}")

        label = str(resp.classification)
        reasoning = str(resp.reasoning)

        if label not in ["yes", "no", "rephrase needed", "N/A", "explain request"]:
            label = "rephrase needed"

    if _clarify_streak(evaluator_results=state.evaluator_results, last_result=label):
        print("Direct classification after 3 round of clarification: YES")
        label = "yes"
        reasoning = f"Patient prompted a vague answer after three rounds of clarification :" \
                    f" '{patient_last_answer.content}'"
    print("exit judge")

    updates['messages'] = [AIMessage(content=reasoning)]
    updates["evaluator_results"] = [label]

    return updates


def build_graph(loader: ModuleLoader, visualize: bool = True):
    sg = StateGraph(InterviewState)

    sg.add_node("questioner", questioner_node)
    sg.add_node("patient", patient_node)
    sg.add_node("evaluator", evaluator_node)
    sg.add_node("navigator", navigator_node)
    sg.add_node("diagnoser", diagnoser_node)

    sg.add_edge(START, "questioner")
    sg.add_edge("questioner", "patient")
    sg.add_edge("patient", "evaluator")

    sg.add_conditional_edges("evaluator", should_clarify,
                             {"clarify": "questioner", "continue": "navigator"})

    sg.add_conditional_edges("navigator", should_diagnose,
                             {"continue": "questioner", "diagnose": "diagnoser", "end": END})

    sg.add_edge("diagnoser", END)

    compiled_sg = sg.compile()

    return compiled_sg

def run():
    _load_key()

    # Load patient data from JSON
    with open("./interview_agent/prompts/" + FILE_NAME + ".json", "r", encoding="utf-8") as f:
        patients_data = json.load(f)

    for entry in patients_data:
        if "System Prompt" not in entry or "id" not in entry or "Module" not in entry:
            continue  # skip if missing data

        # Convert module name into a file-friendly format
        module_name = entry["Module"].split(" - ")[0].lower()  # e.g., "F" from "F - Social Anxiety Disorder"
        module_filename = f"./modules/module_{module_name}.json"

        # Load module dynamically
        loader = ModuleLoader.from_file(module_filename)
        app = build_graph(loader)

        prompt = entry["System Prompt"]
        run_id = entry["id"]

        print(f"\n--- Starting conversation for ID {run_id} | Module: {entry['Module']} ---\n")

        start_qid = loader.get_first_question_id()

        state = InterviewState(
            module_loader=loader,
            current_question_id=start_qid,
            messages=[],
            patient_agent=True,
            patient_system_prompt=prompt
        )

        result = app.invoke(state, config={"recursion_limit": 500})

        # Save conversation log
        _save_log(result["conversation_log"], run_id)

        # Extract and save diagnosis content
        if result['diagnosis_content']:
            diagnosis_dict = result["diagnosis_content"].root
            diagnosis_output = {k: v.model_dump() for k, v in diagnosis_dict.items()}
            _save_diagnosis(diagnosis_output, run_id)


def _save_log(log, run_id):
    # Create main directory
    base_dir = Path("patient_agent_results")
    base_dir.mkdir(exist_ok=True)

    # Create subdirectory
    sub_dir = base_dir / FILE_NAME
    sub_dir.mkdir(exist_ok=True)

    # Save file in subdirectory
    path = sub_dir / f"{run_id}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log[0].keys())
        writer.writeheader()
        writer.writerows(log)

    print(f"Conversation log saved to {path}")


def _save_diagnosis(diagnosis_content, run_id):
    # Create main directory
    base_dir = Path("patient_agent_results")
    base_dir.mkdir(exist_ok=True)

    # Create subdirectory
    sub_dir = base_dir / FILE_NAME
    sub_dir.mkdir(exist_ok=True)

    # Save file in subdirectory
    path = sub_dir / f"diagnosis_{run_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(diagnosis_content, f, indent=4)

    print(diagnosis_content)
    print(f"Diagnosis saved to {path}")


def calculate_red_flag_accuracy():
    base_dir = Path("patient_agent_results") / FILE_NAME
    csv_files = list(base_dir.glob("*.csv"))

    results = []
    total_files = len(csv_files)
    red_flag_files = 0

    for file in csv_files:
        prediction = 0
        try:
            df = pd.read_csv(file)
            if "classification" in df.columns:
                if (df["classification"].astype(str).str.strip().str.lower() == "red_flag").any():
                    prediction = 1
                    red_flag_files += 1
        except Exception as e:
            print(f"Error reading {file}: {e}")

        # remove ".csv" from file name
        results.append({"file_name": file.stem, "prediction": prediction})

    if total_files == 0:
        print("No CSV files found.")
        return

    percentage = (red_flag_files / total_files) * 100
    print(f"Total files: {total_files}")
    print(f"Files with at least one 'red_flag': {red_flag_files}")
    print(f"Percentage: {percentage:.2f}%")

    # Save results CSV (file_name + prediction only)
    pred_df = pd.DataFrame(results)
    out_path = base_dir / "red_flag_predictions.csv"
    pred_df.to_csv(out_path, index=False)
    print(f"Predictions saved to {out_path}")

    # === JOIN WITH PROMPTS JSON ===
    with open(f"./interview_agent/prompts/{FILE_NAME}.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)
    prompts_df = pd.DataFrame(prompts)

    # Align column for merge (id vs file_name)
    pred_df["id"] = pred_df["file_name"].astype(str)
    prompts_df["id"] = prompts_df["id"].astype(str)   # <-- FIX

    merged = prompts_df.merge(pred_df[["id", "prediction"]], on="id", how="left")
    # Fill missing predictions with 0
    merged["prediction"] = merged["prediction"].fillna(0).astype(int)

    # Save merged dataset
    merged_out = base_dir / "red_flag_prompts_with_predictions.csv"
    merged.to_csv(merged_out, index=False)
    print(f"Merged dataset saved to {merged_out}")

    return merged


if __name__ == "__main__":
    run()
    calculate_red_flag_accuracy()
