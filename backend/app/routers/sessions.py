from __future__ import annotations

import csv
from io import StringIO
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agent_core.interview_agent.models import ModuleLoader, InterviewState
from backend.agent_core.interview_agent.nodes import (
    get_llm,
    should_clarify,
    navigator_node,
    should_diagnose,
    diagnoser_node,
    evaluator_node,
    AIMessage,
)
from backend.agent_core.interview_agent.nodes import session_openai_api_key
from backend.agent_core.interview_agent.models import Question
from backend.agent_core.interview_agent.prompts import (
    QUESTIONER_SYSTEM_PROMPT,
    EXPLAIN_PROMPT,
    CLARIFICATION_PROMPT,
)
from backend.agent_core.utils.extract_question_answer_pair import extract_question_answer_pair
from langchain_core.messages import SystemMessage

from backend.app.session_store import SESSION_STORE
from backend.agent_core.utils.redact_sensitive import sanitize_for_llm

router = APIRouter()


class CreateSessionRequest(BaseModel):
    modulePath: str
    apiKey: Optional[str] = None


class CreateSessionResponse(BaseModel):
    threadId: str
    question: str
    responseType: str
    progress: float
    questionId: str
    moduleName: str


class AnswerRequest(BaseModel):
    answer: str


class AnswerResponse(BaseModel):
    classification: str
    reasoning: str
    redFlag: bool
    redFlagMessage: Optional[str] = None
    # Redaction metadata for UI
    redacted: bool = False
    originalResponse: Optional[str] = None
    redactedResponse: Optional[str] = None


class NextResponse(BaseModel):
    finished: bool = False
    question: Optional[str] = None
    responseType: Optional[str] = None
    progress: Optional[float] = None
    questionId: Optional[str] = None
    moduleName: Optional[str] = None
    diagnosis: Optional[Any] = None


def _create_initial_state(loader: ModuleLoader, start_qid: str) -> InterviewState:
    return InterviewState(
        module_loader=loader,
        current_question_id=start_qid,
        messages=[],
        question_path=[],
        evaluator_results=[],
        conversation_log=[],
        module_completed=False,
        ready_for_diagnosis=False,
        diagnosis_content={},
    )


def _progress(state: InterviewState) -> float:
    current_question_num = len(state.question_path) + 1
    total_questions = len(state.module_loader.questions)
    if total_questions <= 0:
        return 0.0
    return min(current_question_num / total_questions, 1.0)


def _generate_question_for_state(state: InterviewState) -> tuple[str, str]:
    q: Question = state.module_loader.get_question(state.current_question_id)
    rtype = (getattr(q, "responseType", "") or "").lower()

    # Extract previous Q&A pairs
    q_a_pairs = extract_question_answer_pair(state.conversation_log, max_pairs=2)

    if rtype == "info":
        info_msg = AIMessage(content=q.prompt)
        state.messages = list(state.messages) + [info_msg]
        state.evaluator_results = list(state.evaluator_results) + ["default"]
        return q.prompt, rtype

    sys_msg = SystemMessage(content=QUESTIONER_SYSTEM_PROMPT.format(
        question=q.prompt,
        q_a_pairs=q_a_pairs
    ))

    if len(state.evaluator_results) > 0:
        last_label = state.evaluator_results[-1]
        if last_label == "explain request":
            patient_response = state.messages[-1].content if state.messages else ""
            sys_msg = SystemMessage(content=EXPLAIN_PROMPT.format(
                response=patient_response,
                current_question=q.prompt
            ))
        elif last_label == "rephrase needed":
            patient_response = state.messages[-1].content if state.messages else ""
            evaluator_reasoning = state.messages[-2].content if len(state.messages) >= 2 else "Response was unclear"
            sys_msg = SystemMessage(content=CLARIFICATION_PROMPT.format(
                question=q.prompt,
                response=patient_response,
                reasoning=evaluator_reasoning
            ))

    response = get_llm().invoke([sys_msg])
    if not isinstance(response, AIMessage):
        response = AIMessage(content=getattr(response, "content", str(response)))

    state.messages = list(state.messages) + [response]
    return response.content, rtype

@router.post("")
def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    try:
        loader = ModuleLoader.from_file(req.modulePath)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid module path: {e}")

    start_qid = loader.get_first_question_id()
    state = _create_initial_state(loader, start_qid)

    thread_id = SESSION_STORE.create(loader, state, loader_path=req.modulePath)
    if req.apiKey:
        SESSION_STORE.set_api_key(thread_id, req.apiKey)

    # Set context API key for LLMs during this call
    token = session_openai_api_key.set(req.apiKey)
    try:
        # Generate initial question (handles info-only flow on client via flag)
        question_content, rtype = _generate_question_for_state(state)

        return CreateSessionResponse(
            threadId=thread_id,
            question=question_content,
            responseType=rtype,
            progress=_progress(state),
            questionId=state.current_question_id,
            moduleName=state.module_loader.module.name,
        )
    finally:
        session_openai_api_key.reset(token)


@router.post("/{thread_id}/answer")
def submit_answer(thread_id: str, req: AnswerRequest) -> AnswerResponse:
    session = SESSION_STORE.get(thread_id)
    state = session.state

    # Apply per-session API key
    token = session_openai_api_key.set(session.api_key)
    try:
        from langchain_core.messages import HumanMessage
        human_msg = HumanMessage(content=req.answer)
        state.messages = list(state.messages) + [human_msg]

        evaluator_result = evaluator_node(state)

        # Store evaluator results for later navigation
        state.messages = list(state.messages) + evaluator_result["messages"]
        state.evaluator_results = list(state.evaluator_results) + evaluator_result["evaluator_results"]
        SESSION_STORE.save_state(thread_id, state)

        # Persist after mutation
        SESSION_STORE.save_state(thread_id, state)

        # Check red flag classification
        red_flag = False
        red_flag_msg: Optional[str] = None
        if evaluator_result["evaluator_results"] and evaluator_result["evaluator_results"][0].lower() == "red_flag":
            red_flag = True
            from backend.agent_core.utils.red_flag import detect_red_flag
            red_flag_msg = detect_red_flag(req.answer)[1]
            SESSION_STORE.set_red_flag(thread_id, True, red_flag_msg)

        # Compute redaction info for UI (compare sanitized vs original)
        sanitized = sanitize_for_llm(req.answer)
        was_redacted = sanitized != (req.answer or "")

        return AnswerResponse(
            classification=evaluator_result["evaluator_results"][0] if evaluator_result["evaluator_results"] else "",
            reasoning=evaluator_result["messages"][0].content if evaluator_result.get("messages") else "",
            redFlag=red_flag,
            redFlagMessage=red_flag_msg,
            redacted=was_redacted,
            originalResponse=req.answer,
            redactedResponse=sanitized if was_redacted else None,
        )
    finally:
        session_openai_api_key.reset(token)


@router.post("/{thread_id}/next")
def go_next(thread_id: str) -> NextResponse:
    session = SESSION_STORE.get(thread_id)
    state = session.state

    token = session_openai_api_key.set(session.api_key)
    try:
        # If red flag was detected, mark finished similar to Streamlit path
        if session.red_flag_detected:
            return NextResponse(finished=True)

        # Run navigator to determine next step
        if should_clarify(state) == "continue":
            updates = navigator_node(state)
            if "conversation_log" in updates:
                state.conversation_log += updates["conversation_log"]
            if updates.get("module_completed"):
                state.module_completed = True
            if updates.get("ready_for_diagnosis"):
                state.ready_for_diagnosis = True
            if "current_question_id" in updates:
                state.current_question_id = updates["current_question_id"]
                state.question_path = list(state.question_path) + [state.current_question_id]
            SESSION_STORE.save_state(thread_id, state)

        branch = should_diagnose(state)
        if branch == "diagnose":
            diag = diagnoser_node(state)
            state.diagnosis_content = diag.get("diagnosis_content")
            SESSION_STORE.set_diagnosis(thread_id, state.diagnosis_content)
            return NextResponse(
                finished=True,
                diagnosis=state.diagnosis_content,
            )
        elif branch == "end":
            return NextResponse(finished=True)
        else:
            question_content, rtype = _generate_question_for_state(state)
            SESSION_STORE.save_state(thread_id, state)
            return NextResponse(
                finished=False,
                question=question_content,
                responseType=rtype,
                progress=_progress(state),
                questionId=state.current_question_id,
                moduleName=state.module_loader.module.name,
            )
    finally:
        session_openai_api_key.reset(token)


@router.post("/{thread_id}/finish-crisis")
def finish_crisis(thread_id: str) -> dict:
    session = SESSION_STORE.get(thread_id)
    session.red_flag_detected = True
    return {"ok": True}


@router.get("/{thread_id}")
def get_session(thread_id: str) -> dict:
    s = SESSION_STORE.get(thread_id)
    return {
        "threadId": thread_id,
        "redFlag": s.red_flag_detected,
        "moduleName": s.state.module_loader.module.name,
        "questionId": s.state.current_question_id,
        "progress": _progress(s.state),
    }


def csv_string_from_log(conversation_log: list[dict]) -> str:
    if not conversation_log:
        return ""
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=conversation_log[0].keys())
    writer.writeheader()
    writer.writerows(conversation_log)
    return buf.getvalue()


