import json, uuid, csv, time, os
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .prompts import INTERVIEWER_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT, DIAGNOSIS_SYSTEM_PROMPT

# Load environment variables from .env file
load_dotenv()
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .models import (
    InterviewState,
    ModuleLoader,
    ClassificationResult,
    DiagnosisResult,
    CriteriaGroupResult,
)

# ------------------------------ LLM instances ------------------------------ #
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
structured_llm = judge_llm.with_structured_output(ClassificationResult)
diagnosis_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1).with_structured_output(
    DiagnosisResult
)


# -------------------------------- Nodes ------------------------------------ #
def interviewer_node(state: InterviewState) -> Dict[str, Any]:
    """Interviewer node that presents questions, then collects user reply."""

    # TODO when requesting explanation, interviewer does not understand.

    print("enter interviewer")

    # 1. Build the system prompt + history
    q = state.module_loader.get_question(state.current_question_id)
    sys_msg = SystemMessage(content=INTERVIEWER_SYSTEM_PROMPT.format(question=q.prompt))
    msgs = state.messages + [sys_msg]

    # 2. Invoke LLM to get the next question
    response = llm.invoke(msgs)
    print('\n\n' + 15* '--' + f" Start of question {state.current_question_id}" + 15* '--')
    print(response.content)  # show question to user

    # 3. Immediately read the user's answer
    user_input = input("You: ").strip()
    human_msg = HumanMessage(content=user_input)
    print(15* '--' + f" End of question {state.current_question_id}" + 15* '--' + '\n\n')
    print("exit interviewer")
    # 4. Return both the LLM question and the new HumanMessage
    return {"messages": [response, human_msg]}


def judge_node(state: InterviewState) -> Dict[str, Any]:
    # assume the loop-driver put the user's message in state.messages[-1]
    print("enter judge")
    last_question = state.module_loader.get_question(state.current_question_id)
    patient_last_answer = state.messages[-1]

    prompt = JUDGE_SYSTEM_PROMPT.format(last_question= last_question.prompt, patient_last_answer= patient_last_answer.content)
    resp = structured_llm.invoke([HumanMessage(content=prompt)])

    # Access Pydantic model attributes directly
    print(f"reason behind the decision: {resp.reasoning}")
    print(f"decision: {resp.classification}")

    label = str(resp.classification)
    if label not in ("yes", "no", "need more clarification"):
        label = "need more clarification"

    print("exit judge")
    # TODO search for best practices of adding pydantic class to 'Messages'
    return {"messages": [AIMessage(content=str(resp.reasoning))], "judge_results": [str(resp.classification)]}


def should_clarify(state: InterviewState) -> str:
    return "clarify" if state.judge_results[-1] == "need more clarification" else "continue"


def _log_entry(state: InterviewState) -> Dict[str, Any]:
    return {
        "question_id": state.current_question_id,
        "patient_response": state.messages[-2].content,
        "classification": state.judge_results[-1],
        "reasoning": state.messages[-1].content,
    }


def selector(state: InterviewState) -> Dict[str, Any]:
    updates: Dict[str, Any] = {"conversation_log": [_log_entry(state)]}

    qid = state.current_question_id
    branches = state.module_loader.get_question(qid).next
    label = state.judge_results[-1].lower()
    next_qid = branches.get(label, branches.get("default"))

    if next_qid == "END_MODULE":
        updates["module_completed"] = True
    elif next_qid == "DIAGNOSTIC":
        updates["ready_for_diagnosis"] = True
    else:
        updates["current_question_id"] = next_qid
        state.question_path.append(next_qid)

    return updates


def should_diagnose(state: InterviewState) -> str:
    if state.ready_for_diagnosis:
        return "diagnose"
    if state.module_completed:
        return "end"
    return "continue"


def diagnosis(state: InterviewState):
    criteria = state.module_loader.diagnostic_criteria
    module_name = state.module_loader.module.name
    patient_responses = {
        entry["question_id"]: entry["classification"].upper()
        for entry in state.conversation_log
    }

    # Very slim logic here; adapt as needed
    summary = json.dumps(patient_responses, indent=2)
    prompt = DIAGNOSIS_SYSTEM_PROMPT.format(summary= summary, group_name= module_name, criteria_formatted= criteria)
    resp = diagnosis_llm.invoke([HumanMessage(content=prompt)])
    print('\n\n' + 15 * '--' + f" Start of Diagnosis {state.current_question_id}" + 15 * '--')
    print(resp)
    print('\n\n' + 15 * '--' + f" End of Diagnosis {state.current_question_id}" + 15 * '--')
    return {"diagnosis_result": resp}
