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

# If we haven't started yet
if st.session_state.loader is None or st.session_state.state is None:
    st.info("Select a module in the sidebar and click 'Start / Reset Interview'.")
    st.stop()

state: InterviewState = st.session_state.state

# If finished, show outputs and CSV download
if st.session_state.finished:
    st.success("Interview completed.")

    # TODO: Add diagnosis output
    # st.subheader("Diagnosis")
    # diag_data = st.session_state.diagnosis_result.model_dump()
    # for group_name, group_result in diag_data.items():
    #     title_suffix = "Yes" if group_result.get("diagnosis") else "No"
    #     with st.expander(f"{group_name} — {title_suffix}", expanded=True):
    #         st.markdown(f"- **diagnosis**: {group_result.get('diagnosis')}")
    #         st.markdown(f"- **timeFrame**: {group_result.get('timeFrame')}")
    #         st.markdown("- **reasoning**:")
    #         st.write(group_result.get("reasoning", ""))

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
st.subheader("Question")
st.write(st.session_state.last_question)

if st.session_state.get("clear_answer"):
    st.session_state.answer_input = ""
    st.session_state.clear_answer = False

user_input = st.text_area("Your answer", height=120, key="answer_input")
col1, col2 = st.columns([1, 1])

with col1:
    submit_clicked = st.button("Submit answer", use_container_width=True)
with col2:
    cancel_clicked = st.button("Cancel / Reset", use_container_width=True)

if cancel_clicked:
    st.session_state.awaiting_answer = False
    st.session_state["clear_answer"] = True
    st.rerun()

if submit_clicked:
    answer = st.session_state["answer_input"].strip()
    if not answer:
        st.warning("Please enter an answer before submitting.")
        st.stop()

    human_msg = HumanMessage(content=answer)
    state.messages = list(state.messages) + [human_msg]

    last_question = state.module_loader.get_question(state.current_question_id)
    prompt = JUDGE_SYSTEM_PROMPT.format(
        last_question=last_question.prompt,
        patient_last_answer=answer,
    )
    resp = structured_llm.invoke([HumanMessage(content=prompt)])

    label = str(resp.classification)
    if label not in ["yes", "no", "need more clarification", "N/A", "explain request"]:
        label = "need more clarification"

    reasoning_msg = AIMessage(content=str(resp.reasoning))
    state.messages = list(state.messages) + [reasoning_msg]
    state.judge_results = list(state.judge_results) + [label]

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