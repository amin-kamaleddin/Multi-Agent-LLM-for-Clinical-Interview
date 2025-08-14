import json, csv
from pathlib import Path
from langgraph.graph import StateGraph
from interview_agent.models import ModuleLoader, _add_log
from langchain_core.messages import SystemMessage, HumanMessage
from interview_agent.cli import _load_key
from typing import Any, Dict, List, Literal, Optional, Sequence, Union, Annotated
from langgraph.constants import START, END
import operator

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from interview_agent.nodes import (
    judge_node,
    interviewer_node,
    should_clarify,
    selector,
    should_diagnose,
    diagnosis,
)

from langchain_openai import ChatOpenAI

PATIENT_USER_PROMPT = """
The interviewer asks: {question}

Respond as the patient described in your system prompt. Answer each question clearly with either "yes" or "no." If necessary, add one short sentence of clarification at the end.
"""

patient_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.9)


class InterviewState(BaseModel):
    messages: Annotated[Sequence, add_messages] = Field(default_factory=list)
    conversation_log: Annotated[list[dict], _add_log] = Field(default_factory=list)
    module_loader: Any
    current_question_id: Optional[str] = None
    question_path: List[str] = Field(default_factory=list)
    judge_results: Annotated[List[Any], operator.add] = Field(default_factory=list)
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

def build_graph(loader: ModuleLoader, visualize: bool = True):
    sg = StateGraph(InterviewState)

    sg.add_node("interviewer", interviewer_node)
    sg.add_node("patient", patient_node)
    sg.add_node("judge", judge_node)
    sg.add_node("selector", selector)
    sg.add_node("diagnosis", diagnosis)

    sg.add_edge(START, "interviewer")
    sg.add_edge("interviewer", "patient")
    sg.add_edge("patient", "judge")

    sg.add_conditional_edges("judge", should_clarify,
                             {"clarify": "interviewer", "continue": "selector"})

    sg.add_conditional_edges("selector", should_diagnose,
                             {"continue": "interviewer", "diagnose": "diagnosis", "end": END})

    sg.add_edge("diagnosis", END)

    compiled_sg = sg.compile()

    return compiled_sg

def run():
    _load_key()

    # Load patient data from JSON
    with open("./interview_agent/prompts/patients_with_system_prompts.json", "r", encoding="utf-8") as f:
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
        diagnosis_dict = result["diagnosis_content"].root
        diagnosis_output = {k: v.model_dump() for k, v in diagnosis_dict.items()}
        _save_diagnosis(diagnosis_output, run_id)



def _save_log(log, run_id):
    Path("patient_agent_results").mkdir(exist_ok=True)
    path = Path("patient_agent_results") / f"{run_id}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log[0].keys())
        writer.writeheader()
        writer.writerows(log)
    print(f"Conversation log saved to {path}")


def _save_diagnosis(diagnosis_content, run_id):
    Path("patient_agent_results").mkdir(exist_ok=True)
    path = Path("patient_agent_results") / f"diagnosis_{run_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(diagnosis_content, f, indent=4)
    print(diagnosis_content)
    print(f"Diagnosis saved to {path}")


if __name__ == "__main__":
    run()
