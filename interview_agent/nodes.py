import json, uuid, csv, time, os
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

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

SYSTEM_MESSAGE_TEMPLATE = (
    "You are a clinician administering the MINI.\n\n"
    "Current question:\n{question}\n\n"
    "- Present only this question.\n"
    "- Ask the patient to answer yes or no. If uncertain, say 'feel free to explain'."
)

# -------------------------------- Nodes ------------------------------------ #
def interviewer_node(state: InterviewState) -> Dict[str, Any]:
    """Interviewer node that presents questions, then collects user reply."""
    print("enter interviewer")

    # 1. Build the system prompt + history
    q = state.module_loader.get_question(state.current_question_id)
    sys_msg = SystemMessage(content=SYSTEM_MESSAGE_TEMPLATE.format(question=q.prompt))
    msgs = [sys_msg] + state.messages

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
    prompt = f"""
You are a clinical psychological assessment agent. Analyze the patient's response to determine if it clearly answers the interviewer's question.

CLASSIFICATION RULES: 
- "need more clarification" - Response is ambiguous, uncertain, irrelevant, incomplete, or confidence is ≤70%

ANALYSIS PROCESS:
1. Does the response directly address the question asked?
2. Is the patient's intent clear and unambiguous?
3. Are you >70% confident in the positive/negative classification?

If any answer above is "no", classify as "need more clarification".

EXAMPLES:
Question: "Do you often feel sad?"
- "Yes, almost every day" → yes
- "No, I'm generally happy" → no
- "Sometimes, I guess" → need more clarification
- "What do you mean by sad?" → need more clarification

Question: {last_question.prompt}
Patient Response: {patient_last_answer.content}

"""
    resp = structured_llm.invoke([HumanMessage(content=prompt)])

    # Access Pydantic model attributes directly
    print(f"reason behind the decision: {resp.reasoning}")
    print(f"decision: {resp.classification}")

    label = str(resp.classification)
    if label not in ("yes", "no", "need more clarification"):
        label = "need more clarification"

    print("exit judge")
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
    prompt = (
        "Assess the following responses and produce a JSON answer.\n"
        f"{summary}"
    )
    resp = diagnosis_llm.invoke([HumanMessage(content=prompt)])
    return resp