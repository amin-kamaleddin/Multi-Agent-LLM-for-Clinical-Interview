import json, uuid, csv, time, os
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

# Load environment variables from .env file
load_dotenv()
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from .prompts import INTERVIEWER_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT, DIAGNOSIS_SYSTEM_PROMPT, EXPLAIN_PROMPT, \
    PATIENT_SYSTEM_PROMPT, PATIENT_USER_PROMPT
from .prompts import INTERVIEWER_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT, DIAGNOSIS_SYSTEM_PROMPT, EXPLAIN_PROMPT, CLARIFICATION_PROMPT

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
patient_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.9)

# ------------------------------ Global Vars ------------------------------ #
AUTO_SET_YES_AFTER = 3  # after 3 consecutive clarifies, the 4th auto-yes


# -------------------------------- Nodes ------------------------------------ #
def interviewer_node(state: InterviewState) -> Dict[str, Any]:
    """Interviewer node that presents questions, then collects user reply."""
    print("enter interviewer")

    # 1. Build the system prompt + history
    current_question = state.module_loader.get_question(state.current_question_id)
    sys_msg = SystemMessage(content=INTERVIEWER_SYSTEM_PROMPT.format(question=current_question.prompt))

    if len(state.judge_results) > 0:
        if state.judge_results[-1] == "explain request":
            patient_response = state.messages[-1].content
            sys_msg = SystemMessage(EXPLAIN_PROMPT.format(response=patient_response, current_question=current_question.prompt))
        elif state.judge_results[-1] == "rephrase needed":
            # Generate specific clarification using LLM based on patient's unclear response
            patient_response = state.messages[-1].content
            judge_reasoning = state.messages[-2].content if len(state.messages) >= 2 else "Response was unclear"

            clarification_prompt = CLARIFICATION_PROMPT.format(
                question=current_question.prompt,
                response=patient_response,
                reasoning=judge_reasoning
            )
            sys_msg = SystemMessage(content=clarification_prompt)

    msgs = [sys_msg]

    # 2. Invoke LLM to get the next question
    response = llm.invoke(msgs)
    print('\n\n' + 15* '--' + f" Start of question {state.current_question_id}" + 15* '--')
    print(response.content)  # show question to user

    # 3. Immediately read the user's answer

    print("exit interviewer")
    # 4. Return both the LLM question and the new HumanMessage
    return {"messages": [response]}


def patient_node(state: InterviewState):
    print("enter patient node")
    if not state.patient_agent:
        result = input("You: ").strip()
    else:
        sys_msg = SystemMessage(content=PATIENT_SYSTEM_PROMPT)
        patient_prompt = HumanMessage(content=PATIENT_USER_PROMPT.format(question=state.messages[-1].content))
        result = patient_llm.invoke([sys_msg, patient_prompt])
        print(f"agent response: {result.content}")

    print(15 * '--' + f" End of question {state.current_question_id}" + 15 * '--' + '\n\n')
    return {'messages': [result]}


def _clarify_streak(judge_results: list[Any], last_result) -> bool:
    clarify_label = "rephrase needed"
    results = judge_results
    results.append(last_result)
    if len(judge_results) >= AUTO_SET_YES_AFTER and all(r == clarify_label for r in results[-AUTO_SET_YES_AFTER:]):
        return True
    else:
        return False


def judge_node(state: InterviewState) -> Dict[str, Any]:
    # assume the loop-driver put the user's message in state.messages[-1]
    print("enter judge")
    last_question = state.module_loader.get_question(state.current_question_id)
    patient_last_answer = state.messages[-1]

    response_text = patient_last_answer.content.strip().lower()
    if response_text == "yes":
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
        resp = structured_llm.invoke([HumanMessage(content=prompt)])

        # Access Pydantic model attributes directly
        print(f"reason behind the decision: {resp.reasoning}")
        print(f"decision: {resp.classification}")

        label = str(resp.classification)
        reasoning = str(resp.reasoning)

        if label not in ["yes", "no", "rephrase needed", "N/A", "explain request"]:
            label = "rephrase needed"

    if _clarify_streak(judge_results=state.judge_results, last_result=label):
        print("Direct classification after 3 round of clarification: YES")
        label = "yes"
        reasoning = f"Patient prompted a vague answer after three rounds of clarification :" \
                    f" '{patient_last_answer.content}'"
    print("exit judge")
    # TODO search for best practices of adding pydantic class to 'Messages'
    return {"messages": [AIMessage(content=reasoning)], "judge_results": [label]}


def should_clarify(state: InterviewState) -> str:
    return "clarify" if state.judge_results[-1] in ["rephrase needed", "explain request"] else "continue"


def _log_entry(state: InterviewState) -> Dict[str, Any]:
    # Determine if this is a clarification based on previous judge results
    exchange_type = "clarification" if len(state.judge_results) > 1 and state.judge_results[-2] in ["rephrase needed", "explain request"] else "initial"

    return {
        "question_id": state.current_question_id,
        "ai_question": state.messages[-3].content if len(state.messages) >= 3 else "",  # The AI question
        "patient_response": state.messages[-2].content,
        "classification": state.judge_results[-1],
        "reasoning": state.messages[-1].content,
        "timestamp": datetime.now().isoformat(),
        "exchange_type": exchange_type,
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
                result[group_name] = {"diagnosis": False, "timeFrame": None, "reasoning": "No criteria provided."}
                continue
            criteria_formatted = "\n".join(f"{i+1}. {crit}" for i, crit in enumerate(rule_list))
        elif isinstance(rule_list, str):
            criteria_formatted = rule_list.strip()
        else:
            result[group_name] = {"diagnosis": False, "timeFrame": None, "reasoning": "Invalid criteria format."}
            continue
        prompt = DIAGNOSIS_SYSTEM_PROMPT.format(summary=summary, group_name=group_name, criteria_formatted=criteria_formatted)

        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # remove markdown code block formatting
        if content.startswith("```json"):
            content = content.removeprefix("```json").removesuffix("```").strip()

        print(f"LLM JSON output for group '{group_name}':\n{content}\n{'-'*40}")

        try:
            data = json.loads(content)
            group_result = CriteriaGroupResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            # Ensure the errors directory exists
            os.makedirs("errors", exist_ok=True)
            
            # Save the raw LLM output
            error_path = f"errors/group_{group_name}_raw.txt"
            with open(error_path, "w", encoding="utf-8") as f:
                f.write(content)
            raise ValueError(f"Failed to parse LLM JSON output for group '{group_name}': {e}\nRaw output:\n{content}")

        result[group_name] = group_result.model_dump()

    return {'diagnosis_content': DiagnosisEvaluationOutput.model_validate(result)}