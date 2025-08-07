import json, uuid, csv, time, os
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

# Load environment variables from .env file
load_dotenv()
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .models import (
    InterviewState,
    ModuleLoader,
    ClassificationResult,
    DiagnosisResult,
    DiagnosisEvaluationOutput,
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
    """analyses the conversation log and gives a diagnosis based on the criteria"""
    print("enter diagnose node")
    criteria = state.module_loader.diagnostic_criteria

    module_name = state.module_loader.module.name


    patient_responses = {}
    for entry in state.conversation_log:
        qid = entry.get("question_id")
        classification = entry.get("classification")
        if qid and classification:
            patient_responses[qid] = classification.strip().upper()

    module_key = module_name.strip().replace(" ", "")
    module_key = module_key[0].lower() + module_key[1:]
    if module_key not in criteria:
        raise ValueError(f"No criteria found for module '{module_name}'.")

    criteria_groups = criteria[module_key]
    if not isinstance(criteria_groups, dict) or not criteria_groups:
        raise ValueError(f"No valid criteria groups found for module '{module_name}'.")

    summary = "\n".join(f"{qid}: {ans}" for qid, ans in sorted(patient_responses.items()))

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.1)
    result = {}

    for group_name, rule_list in criteria_groups.items():
        if isinstance(rule_list, list):
            if not rule_list:
                result[group_name] = {"diagnosis": False, "timeFrame": "unknown", "reasoning": "No criteria provided."}
                continue
            criteria_formatted = "\n".join(f"{i+1}. {crit}" for i, crit in enumerate(rule_list))
        elif isinstance(rule_list, str):
            criteria_formatted = rule_list.strip()
        else:
            result[group_name] = {"diagnosis": False, "timeFrame": "unknown", "reasoning": "Invalid criteria format."}
            continue

        prompt = (
            "You are a psychiatric diagnostic evaluator.\n\n"

            "=== Patient Summary ===\n"
            "The patient's answers to yes/no questions are listed below:\n"
            f"{summary}\n\n"

            f"=== Diagnostic Group: {group_name} ===\n"
            "Criteria to evaluate:\n"
            f"{criteria_formatted}\n\n"

            "=== Instructions ===\n"
            "You must assess whether each diagnostic criterion is met, based solely on the patient's answers.\n\n"

            "1. General Rules:\n"
            "   - Analyze each criterion independently.\n"
            "   - Provide a concise explanation for whether each is met.\n\n"

            "2. Symptom Group Criteria (e.g., 'at least 5 symptom groups'):\n"
            "   - Treat all questions that belong to the same symptom group as one unit.\n"
            "   - If **any** question in a group is marked 'YES' (whether past or current), consider that symptom group as positive.\n"
            "   - To satisfy the criterion, the required number of positive symptom groups must all come from **only one** time frame — either 'current' or 'past', not a mix.\n"
            "   - List which symptom groups are positive and under which time frame(s).\n\n"

            "3. Non-Time-Frame-Specific Items (e.g., A1a, A1b, A2):\n"
            "   - For items that do **not** include a time frame suffix (like _past or _current), evaluate them as TRUE or FALSE regardless of time frame.\n"
            "   - These items are valid if marked 'YES' in any context.\n\n"

            "4. Organic Cause / Rule-Out Criteria:\n"
            "   - For now, infer that organic causes are ruled out.\n\n"

            "5. Diagnosis Summary:\n"
            "   - After assessing all criteria, provide a final diagnosis summary.\n"
            "   - If **all** criteria are met, the diagnosis is 'Yes'. Otherwise, it is 'No'.\n"
            "   - For a positive diagnosis, also determine the **time frame**:\n"
            "     - Choose from: **past**, **current**, or **both**.\n"
            "     - This refers to the time frame in which the symptom group criteria were satisfied.\n"
            "     - Do not use 'both' unless both past and current **independently** meet the symptom threshold.\n\n"

            "=== Output Format ===\n"
            "Return ONLY a JSON object with these fields:\n"
            "{\n"
            '  "diagnosis": true/false,\n'
            '  "timeFrame": "past" | "current" | "both" | null,\n'
            '  "reasoning": "<a concise explanation for the assessment>"\n'
            "}\n"
            "DO NOT include any other text outside this JSON.\n"
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        print(f"LLM JSON output for group '{group_name}':\n{content}\n{'-'*40}")

        try:
            data = json.loads(content)
            group_result = CriteriaGroupResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Failed to parse LLM JSON output for group '{group_name}': {e}\nRaw output:\n{content}")

        result[group_name] = group_result.model_dump()

    return DiagnosisEvaluationOutput.model_validate(result)