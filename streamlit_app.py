import os
import uuid
from pathlib import Path
from io import StringIO

import streamlit as st
from dotenv import load_dotenv

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from interview_agent.models import ModuleLoader, InterviewState
from interview_agent.prompts import (
    INTERVIEWER_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    EXPLAIN_PROMPT,
)
from interview_agent.nodes import (
    llm,
    structured_llm,
    should_clarify,
    selector,
    should_diagnose,
    diagnosis,
    judge_node,
)

# This is a work in progress and is a poor implementation of a Streamlit app.
# There are lots of improvements that need to be made, but the goal was to have a simple UI working
# for the demo on August 8th, 2025.

# ----------------------------- Setup / Utilities ----------------------------- #
load_dotenv()

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)
MODULES_DIR = Path("modules")


def ensure_api_key():
    if "OPENAI_API_KEY" not in os.environ:
        st.error("OPENAI_API_KEY not set. Add it to your environment or .env file.")
        st.stop()


def list_available_modules():
    if not MODULES_DIR.exists():
        return []
    files = sorted(MODULES_DIR.glob("module_*.json"))
    items = []
    for f in files:
        letter = f.stem.split("_")[-1]
        items.append((letter, str(f)))
    return items


def make_thread_id() -> str:
    return f"session_{uuid.uuid4().hex[:8]}"


def create_initial_state(loader: ModuleLoader, start_qid: str) -> InterviewState:
    return InterviewState(
        module_loader=loader,
        current_question_id=start_qid,
        messages=[],
        question_path=[],
        judge_results=[],
        conversation_log=[],
        module_completed=False,
        ready_for_diagnosis=False,
        diagnosis_content={},
    )


def generate_interviewer_question(state: InterviewState) -> AIMessage:
    current_question = state.module_loader.get_question(state.current_question_id)
    sys_msg = SystemMessage(content=INTERVIEWER_SYSTEM_PROMPT.format(question=current_question.prompt))

    if len(state.judge_results) > 0 and state.judge_results[-1] == "explain request":
        patient_response = state.messages[-1].content if state.messages else ""
        sys_msg = SystemMessage(
            content=EXPLAIN_PROMPT.format(response=patient_response, current_question=current_question.prompt)
        )

    response = llm.invoke([sys_msg])
    if not isinstance(response, AIMessage):
        response = AIMessage(content=response.content)
    return response


def apply_selector_updates(state: InterviewState, updates: dict) -> InterviewState:
    if "conversation_log" in updates:
        state.conversation_log += updates["conversation_log"]
    if "module_completed" in updates:
        state.module_completed = updates["module_completed"]
    if "ready_for_diagnosis" in updates:
        state.ready_for_diagnosis = updates["ready_for_diagnosis"]
    if "current_question_id" in updates:
        state.current_question_id = updates["current_question_id"]
    return state


def save_conversation_log(conversation_log: list[dict], thread_id: str) -> Path:
    import csv

    path = REPORTS_DIR / f"{thread_id}.csv"
    if conversation_log:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=conversation_log[0].keys())
            writer.writeheader()
            writer.writerows(conversation_log)
    return path


def csv_string_from_log(conversation_log: list[dict]) -> str:
    if not conversation_log:
        return ""
    import csv

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=conversation_log[0].keys())
    writer.writeheader()
    writer.writerows(conversation_log)
    return buf.getvalue()


def _prettify_group_title(name: str) -> str:
    """Make raw group keys more readable for display."""
    if not isinstance(name, str):
        return str(name)
    pretty = name.replace("_", " ").replace("-", " ").strip()
    if not pretty:
        return name
    return pretty[:1].upper() + pretty[1:]


# --------------------------------- UI State ---------------------------------- #
if "thread_id" not in st.session_state:
    st.session_state.thread_id = make_thread_id()

if "loader" not in st.session_state:
    st.session_state.loader = None

if "state" not in st.session_state:
    st.session_state.state = None

if "awaiting_answer" not in st.session_state:
    st.session_state.awaiting_answer = False

if "last_question" not in st.session_state:
    st.session_state.last_question = ""

if "finished" not in st.session_state:
    st.session_state.finished = False

if "diagnosis_result" not in st.session_state:
    st.session_state.diagnosis_result = None

if "answer_input" not in st.session_state:
    st.session_state.answer_input = ""

if "clear_answer" not in st.session_state:
    st.session_state.clear_answer = False


# ----------------------------------- UI -------------------------------------- #
st.set_page_config(page_title="MINI Interview", page_icon="🗣️", layout="centered")
st.title("MINI Interview")

ensure_api_key()

modules = list_available_modules()
if not modules:
    st.error("No modules found in the `modules/` directory.")
    st.stop()

with st.sidebar:
    st.header("Setup")
    letters = [m[0] for m in modules]
    selected_letter = st.selectbox("Select module letter", letters, index=0)
    selected_path = dict(modules)[selected_letter]    

    if st.button("Start / Reset Interview", type="primary"):
        loader = ModuleLoader.from_file(selected_path)
        start_qid = loader.get_first_question_id()
        st.session_state.loader = loader
        st.session_state.state = create_initial_state(loader, start_qid)
        st.session_state.awaiting_answer = False
        st.session_state.last_question = ""
        st.session_state.finished = False
        st.session_state.diagnosis_result = None
        st.session_state.thread_id = make_thread_id()
        st.session_state["answer_input"] = ""
        st.session_state["clear_answer"] = True
        st.rerun()

if st.session_state.loader is None or st.session_state.state is None:
    st.info("Select a module in the sidebar and click 'Start / Reset Interview'.")
    st.stop()

state: InterviewState = st.session_state.state

if st.session_state.finished:
    st.success("Interview completed.")

    if st.session_state.diagnosis_result is not None:
        st.subheader("Diagnosis")
        diag_data = st.session_state.diagnosis_result.model_dump()
        total = len(diag_data)
        met = [k for k, v in diag_data.items() if v.get("diagnosis") is True]
        not_met = [k for k, v in diag_data.items() if v.get("diagnosis") is not True]

        if total > 0 and len(not_met) == 0:
            st.success("Meets all required criteria based on interview responses.")
        else:
            st.info("Does not meet all required criteria based on interview responses.")

        for group_name, group_result in diag_data.items():
            title = _prettify_group_title(group_name)
            st.markdown(f"### {title}")
            st.markdown(f"- **Result**: {'Met' if group_result.get('diagnosis') else 'Not met'}")
            timeframe = group_result.get("timeFrame") or "—"
            st.markdown(f"- **Time frame**: {timeframe}")
            st.markdown("- **Reasoning**:")
            st.write(group_result.get("reasoning", ""))
            st.markdown("---")

    csv_data = csv_string_from_log(state.conversation_log)
    st.download_button(
        "Download conversation log (CSV)",
        data=csv_data,
        file_name=f"{st.session_state.thread_id}.csv",
        mime="text/csv",
    )
    st.stop()

if not st.session_state.awaiting_answer:
    question_msg = generate_interviewer_question(state)
    state.messages = list(state.messages) + [question_msg]
    st.session_state.last_question = question_msg.content
    st.session_state.awaiting_answer = True

st.markdown("---")

# Progress tracking
if st.session_state.state:
    current_question_num = len(st.session_state.state.question_path) + 1
    current_qid = st.session_state.state.current_question_id
    total_questions = len(st.session_state.state.module_loader.questions)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"Question #{current_question_num}")
    with col2:        
        progress = min(current_question_num / total_questions, 1.0)
        st.metric("Progress", f"{progress:.0%}")
        
    st.progress(progress, text=f"Questions asked: {current_question_num} (approx. progress)")
        
    st.caption(f"Question ID: {current_qid} | Module: {st.session_state.state.module_loader.module.name}")
    
    st.write(st.session_state.last_question)
else:
    st.subheader("Question")
    st.write(st.session_state.last_question)

if st.session_state.get("clear_answer"):
    st.session_state.answer_input = ""
    st.session_state.clear_answer = False

# Quick response buttons
st.markdown("**Quick responses:**")
col1, col2 = st.columns([1, 1])

with col1:
    yes_clicked = st.button("Yes", use_container_width=True, type="secondary")
with col2:
    no_clicked = st.button("No", use_container_width=True, type="secondary")

user_input = st.text_area("Your answer", height=120, key="answer_input")

col3, col4 = st.columns([1, 1])

with col3:
    submit_clicked = st.button("Submit answer", use_container_width=True)
with col4:
    cancel_clicked = st.button("Cancel / Reset", use_container_width=True)

if cancel_clicked:
    st.session_state.awaiting_answer = False
    st.session_state["clear_answer"] = True
    st.rerun()

# Handle button clicks - Yes/No buttons or Submit button
answer = ""
if yes_clicked:
    answer = "Yes"
elif no_clicked:
    answer = "No"
elif submit_clicked:
    answer = st.session_state["answer_input"].strip()
    if not answer:
        st.warning("Please enter an answer before submitting.")
        st.stop()

if answer:
    human_msg = HumanMessage(content=answer)
    state.messages = list(state.messages) + [human_msg]

    judge_result = judge_node(state)
    
    state.messages = list(state.messages) + judge_result["messages"]
    state.judge_results = list(state.judge_results) + judge_result["judge_results"]

    if should_clarify(state) == "clarify":
        st.session_state.awaiting_answer = False
        st.session_state["clear_answer"] = True
        st.rerun()

    updates = selector(state)
    state = apply_selector_updates(state, updates)

    branch = should_diagnose(state)
    if branch == "diagnose":
        diag = diagnosis(state)
        state.diagnosis_content = diag.get("diagnosis_content")
        st.session_state.diagnosis_result = state.diagnosis_content
        save_conversation_log(state.conversation_log, st.session_state.thread_id)
        st.session_state.finished = True
        st.session_state["clear_answer"] = True
        st.rerun()

    elif branch == "end":
        save_conversation_log(state.conversation_log, st.session_state.thread_id)
        st.session_state.finished = True
        st.session_state["clear_answer"] = True
        st.rerun()

    else:
        st.session_state.awaiting_answer = False
        st.session_state["clear_answer"] = True
        st.rerun() 