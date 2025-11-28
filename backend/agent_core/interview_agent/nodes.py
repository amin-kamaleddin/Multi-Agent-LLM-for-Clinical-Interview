from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
import contextvars
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from backend.agent_core.utils.bmi import is_bmi_below_normal
from backend.agent_core.utils.extract_question_answer_pair import extract_question_answer_pair
from backend.agent_core.utils.redact_sensitive import sanitize_for_llm
from backend.agent_core.utils.skip_logic_module_h import module_h_ready_to_diagnose
from backend.agent_core.utils.transcribe_audio import transcribe_audio_file

# Load environment variables from .env file
load_dotenv()
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from .prompts import QUESTIONER_SYSTEM_PROMPT, EVALUATOR_SYSTEM_PROMPT, DIAGNOSER_SYSTEM_PROMPT, EXPLAIN_PROMPT, \
    CLARIFICATION_PROMPT, PATIENT_SYSTEM_PROMPT, PATIENT_USER_PROMPT
from .prompts.diagnoser import MODULE_G_DIAGNOSER_PROMPT, MODULE_F_DIAGNOSER_PROMPT

from .models import (
    InterviewState,
    ClassificationResult,
    DiagnosisResult,
    DiagnosisEvaluationOutput,
    CriteriaGroupResult,
)

from backend.agent_core.utils.red_flag import detect_red_flag

# ------------------------------ LLM instances (lazy loading) ------------------------------ #
_llm_cache = {}
_evaluator_llm_cache = {}
_structured_llm_cache = {}
_diagnosis_llm_cache = {}
_patient_llm_cache = {}

# Context variable to enable per-session API keys
session_openai_api_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "session_openai_api_key", default=None
)


def get_llm():
    api_key = session_openai_api_key.get()
    key = api_key or "__default__"
    if key not in _llm_cache:
        _llm_cache[key] = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=api_key)
    return _llm_cache[key]


def get_evaluator_llm():
    api_key = session_openai_api_key.get()
    key = api_key or "__default__"
    if key not in _evaluator_llm_cache:
        _evaluator_llm_cache[key] = ChatOpenAI(model="gpt-5-mini", reasoning_effort="low", api_key=api_key)
    return _evaluator_llm_cache[key]


def get_structured_llm():
    api_key = session_openai_api_key.get()
    key = api_key or "__default__"
    if key not in _structured_llm_cache:
        _structured_llm_cache[key] = get_evaluator_llm().with_structured_output(ClassificationResult)
    return _structured_llm_cache[key]


def get_diagnosis_llm():
    api_key = session_openai_api_key.get()
    key = api_key or "__default__"
    if key not in _diagnosis_llm_cache:
        _diagnosis_llm_cache[key] = ChatOpenAI(
            model="gpt-5-mini", reasoning_effort="medium", api_key=api_key
        ).with_structured_output(DiagnosisResult)
    return _diagnosis_llm_cache[key]


def get_patient_llm():
    api_key = session_openai_api_key.get()
    key = api_key or "__default__"
    if key not in _patient_llm_cache:
        _patient_llm_cache[key] = ChatOpenAI(model="gpt-4o-mini", temperature=0.9, api_key=api_key)
    return _patient_llm_cache[key]


# Module-level lazy loading - these will call the getter functions
def _get_module_llm():
    return get_llm()


def _get_module_evaluator_llm():
    return get_evaluator_llm()


def _get_module_structured_llm():
    return get_structured_llm()


def _get_module_diagnosis_llm():
    return get_diagnosis_llm()


def _get_module_patient_llm():
    return get_patient_llm()


# ------------------------------ Global Vars ------------------------------ #
AUTO_SET_YES_AFTER = 3  # after 3 consecutive clarifies, the 4th auto-yes
VALID_LABELS = ["yes", "no", "rephrase needed", "explain request", "valid_quantity",
                "valid_response"]  # valid labels from evaluator


# -------------------------------- Nodes ------------------------------------ #
def questioner_node(state: InterviewState) -> Dict[str, Any]:
    """questioner node that presents questions, then collects user reply."""
    print("enter questioner")
    updates: Dict[str, Any] = {}
    q_a_pairs = extract_question_answer_pair(state.conversation_log, max_pairs=2)
    # 1. Build the system prompt + history
    current_question = state.module_loader.get_question(state.current_question_id)
    # Special handling for "info"-type questions (e.g. definitions or intros)
    if getattr(current_question, "responseType", "").lower() == "info":
        # show text in the console
        print("\n" + "-" * 30)
        print(current_question.prompt)
        print("-" * 30 + "\n")

        # put an AI message in history so logging/diagnosis stay consistent
        updates["messages"] = [AIMessage(content=current_question.prompt)]

        # seed a label so navigator can take branches.get("default")
        updates["evaluator_results"] = ["default"]

        return updates


    # Otherwise proceed as usual
    sys_msg = SystemMessage(content=QUESTIONER_SYSTEM_PROMPT.format(q_a_pairs=q_a_pairs ,question=current_question.prompt))

    if len(state.evaluator_results) > 0:
        if state.evaluator_results[-1] == "explain request":
            updates["conversation_log"] = [_log_entry(state)]
            patient_response = sanitize_for_llm(state.messages[-1].content)
            sys_msg = SystemMessage(
                EXPLAIN_PROMPT.format(response=patient_response, current_question=current_question.prompt))
        elif state.evaluator_results[-1] == "rephrase needed":
            updates["conversation_log"] = [_log_entry(state)]
            # Generate specific clarification using LLM based on patient's unclear response
            patient_response = sanitize_for_llm(state.messages[-1].content)
            evaluator_reasoning = sanitize_for_llm(state.messages[-2].content) if len(
                state.messages) >= 2 else "Response was unclear"

            clarification_prompt = CLARIFICATION_PROMPT.format(
                question=current_question.prompt,
                response=patient_response,
                reasoning=evaluator_reasoning
            )
            sys_msg = SystemMessage(content=clarification_prompt)

    msgs = [sys_msg]

    # 2. Invoke LLM to get the next question
    response = get_llm().invoke(msgs)
    print('\n\n' + 15 * '--' + f" Start of question {state.current_question_id}" + 15 * '--')
    print(response.content)  # show question to user

    # 3. Immediately read the user's answer
    updates['messages'] = [response]
    print("exit questioner")
    # 4. Return both the LLM question and the new HumanMessage
    return updates


def patient_node(state: InterviewState):
    """
    Enhanced patient node that supports both text and audio input
    Automatically detects if input is a file path and transcribes accordingly
    """
    print("enter patient node")

    if not state.patient_agent:
        print("Respond by typing or providing audio file path:")
        user_input = input("You (or path to audio): ").strip()

        # Check if input looks like a file path
        if (user_input.startswith(('/', './', '../', '~')) or
                ('/' in user_input and Path(user_input).exists()) or
                Path(user_input).suffix.lower() in {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg', '.mpga', '.webm', '.ogg',
                                                    '.flac'}):

            if os.path.exists(user_input):
                print("Transcribing audio...")
                transcribed_text = transcribe_audio_file(user_input)
                if transcribed_text:
                    print(f"Transcribed: {transcribed_text}")
                    result = HumanMessage(content=transcribed_text)
                else:
                    fallback_text = input("Transcription failed. Please type your response: ").strip()
                    result = HumanMessage(content=fallback_text)
            else:
                print("File not found. Assuming your input is not a path!")
                result = HumanMessage(content=user_input)
        else:
            result = HumanMessage(content=user_input)
    else:
        sys_msg = SystemMessage(content=PATIENT_SYSTEM_PROMPT)
        patient_prompt = HumanMessage(
            content=PATIENT_USER_PROMPT.format(question=state.messages[-1].content)
        )

        result = get_patient_llm().invoke([sys_msg, patient_prompt])
        print(f"agent response: {result.content}")
        result = HumanMessage(content=result.content)
    print(15 * '--' + f" End of question {state.current_question_id}" + 15 * '--' + '\n\n')
    return {'messages': [result]}


def _clarify_streak(evaluator_results: list[Any], last_result) -> bool:
    clarify_label = "rephrase needed"
    results = evaluator_results
    results.append(last_result)
    if len(evaluator_results) >= AUTO_SET_YES_AFTER and all(r == clarify_label for r in results[-AUTO_SET_YES_AFTER:]):
        return True
    else:
        return False

def should_collect_input(state: InterviewState) -> str:
    q = state.module_loader.get_question(state.current_question_id)
    return "patient" if getattr(q, "responseType", "").lower() != "info" else "navigator"

def evaluator_node(state: InterviewState) -> Dict[str, Any]:
    # assume the loop-driver put the user's message in state.messages[-1]
    print("enter evaluator")
    updates: Dict[str, Any] = {}
    last_question = state.module_loader.get_question(state.current_question_id)
    patient_last_answer = state.messages[-1]

    response_text = patient_last_answer.content.strip().lower()
    response_type = state.module_loader.get_question(state.current_question_id).responseType
    # Create sanitized version for LLM and output, but keep original for logic
    sanitized_response = sanitize_for_llm(patient_last_answer.content)

    print(f"original response: {response_text}")
    print(f"sanitized response: {sanitized_response}")

    if not state.patient_agent and (state.red_flag and detect_red_flag(response_text)[0]):
        print("Direct classification: RED FLAG")
        label = "red_flag"
        reasoning = f"Red flag detected: '{sanitized_response}'"
    elif response_text == "yes" and response_type == "yes_no":
        print("Direct classification: YES (no LLM call needed)")
        label = "yes"
        reasoning = f"Patient gave a clear affirmative response: '{sanitized_response}'"
    elif response_text == "no" and response_type == "yes_no":
        print("Direct classification: NO (no LLM call needed)")
        label = "no"
        reasoning = f"Patient gave a clear negative response: '{sanitized_response}'"
    else:
        print("MAKING AN LLM CALL TO EVALUATE THE ANSWER")
        context_history = extract_question_answer_pair(log=state.conversation_log, max_pairs=5)
        prompt = EVALUATOR_SYSTEM_PROMPT.format(previous_qa_pairs=context_history, response_type=response_type
                                                , last_question=last_question.prompt,
                                                patient_last_answer=sanitized_response)
        resp = get_structured_llm().invoke([SystemMessage(content=prompt)])

        # Access Pydantic model attributes directly
        print(f"reason behind the decision: {resp.reasoning}")
        print(f"decision: {resp.classification}")

        label = str(resp.classification)
        reasoning = str(resp.reasoning)

        if label not in VALID_LABELS:
            label = "rephrase needed"

    if _clarify_streak(evaluator_results=state.evaluator_results, last_result=label):
        print("Direct classification after 3 round of clarification: YES")
        label = "yes"
        reasoning = f"Patient prompted a vague answer after three rounds of clarification :" \
                    f" '{sanitized_response}'"
    print("exit evaluator")

    updates['messages'] = [AIMessage(content=reasoning)]
    updates["evaluator_results"] = [label]

    return updates


def should_clarify(state: InterviewState) -> str:
    return "clarify" if state.evaluator_results[-1] in ["rephrase needed", "explain request"] else "continue"


def _log_entry(state: InterviewState) -> Dict[str, Any]:
    # Determine if this is a clarification based on previous evaluator results
    exchange_type = "clarification" if len(state.evaluator_results) > 1 and state.evaluator_results[-2] in [
        "rephrase needed", "explain request"] else "initial"

    return {
        "question_id": state.current_question_id,
        "ai_question": state.messages[-3].content if len(state.messages) >= 3 else "",  # The AI question
        "patient_response": state.messages[-2].content,
        "classification": state.evaluator_results[-1],
        "reasoning": state.messages[-1].content,
        "timestamp": datetime.now().isoformat(),
        "exchange_type": exchange_type,
    }


def navigator_node(state: InterviewState) -> Dict[str, Any]:
    updates: Dict[str, Any] = {"conversation_log": [_log_entry(state)]}

    qid = state.current_question_id
    branches = state.module_loader.get_question(qid).next
    label = state.evaluator_results[-1].lower()
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
    if state.current_question_id == "L2":
        return "continue" if is_bmi_below_normal(state) else "diagnose"
    if state.current_question_id.startswith('H'):
        return "diagnose" if module_h_ready_to_diagnose(state) else "continue"
    if state.ready_for_diagnosis:
        return "diagnose"
    else:
        return "continue"


def diagnoser_node(state: InterviewState):
    """analyses the conversation log and gives a diagnosis based on the criteria"""
    print("enter diagnose node")
    criteria = state.module_loader.diagnostic_criteria

    module_name = state.module_loader.module.name
    module_id = state.module_loader.module.id

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

    api_key = session_openai_api_key.get()
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.1, api_key=api_key)
    result = {}

    for group_name, rule_list in criteria_groups.items():
        if isinstance(rule_list, list):
            if not rule_list:
                result[group_name] = {"diagnosis": False, "timeFrame": None, "reasoning": "No criteria provided."}
                continue
            criteria_formatted = "\n".join(f"{i + 1}. {crit}" for i, crit in enumerate(rule_list))
        elif isinstance(rule_list, str):
            criteria_formatted = rule_list.strip()
        else:
            result[group_name] = {"diagnosis": False, "timeFrame": None, "reasoning": "Invalid criteria format."}
            continue

        # Use special prompts for specific modules
        if module_id == "G":
            prompt = MODULE_G_DIAGNOSER_PROMPT.format(
                summary=summary,
                group_name=group_name,
                criteria_formatted=criteria_formatted
            )
        elif module_id == "F":
            prompt = MODULE_F_DIAGNOSER_PROMPT.format(
                summary=summary,
                group_name=group_name,
                criteria_formatted=criteria_formatted
            )
        else:
            prompt = DIAGNOSER_SYSTEM_PROMPT.format(
                summary=summary,
                group_name=group_name,
                criteria_formatted=criteria_formatted,
                module_id=module_id
            )

        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # remove Markdown code block formatting
        if content.startswith("```json"):
            content = content.removeprefix("```json").removesuffix("```").strip()

        print(f"LLM JSON output for group '{group_name}':\n{content}\n{'-' * 40}")

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
