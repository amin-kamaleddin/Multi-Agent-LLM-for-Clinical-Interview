import os
import uuid
from pathlib import Path
from io import StringIO

import streamlit as st
from dotenv import load_dotenv
from utils.red_flag import detect_red_flag

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from interview_agent.models import ModuleLoader, InterviewState
from interview_agent.prompts import (
    QUESTIONER_SYSTEM_PROMPT,    
    EXPLAIN_PROMPT,
    CLARIFICATION_PROMPT,
)
from interview_agent.nodes import (
    get_llm,  # Using lazy loading instead of direct llm import
    should_clarify,
    navigator_node,
    should_diagnose,
    diagnoser_node,
    evaluator_node,
)
from utils.styling import apply_custom_styling

# ----------------------------- Setup / Utilities ----------------------------- #
load_dotenv()

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)
MODULES_DIR = Path("modules")


def ensure_api_key():
    if "OPENAI_API_KEY" not in os.environ:
        st.warning("⚠️ OPENAI_API_KEY not found in environment variables.")
        st.info("For Hugging Face Spaces: Add your OpenAI API key in the Spaces settings under 'Repository secrets'.")
        st.info("For local development: Add your API key to a .env file or export it as an environment variable.")
        
        # Allow users to input API key directly in the interface
        api_key = st.text_input("Enter your OpenAI API key:", type="password", help="Your API key will be used for this session only")
        
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            st.success("✅ API key set successfully!")
            st.rerun()
        else:
            st.stop()


def list_available_modules():
    import json
    if not MODULES_DIR.exists():
        return []
    files = sorted(MODULES_DIR.glob("module_*.json"))
    items = []
        
    excluded_files = ["module_o.json"]
    
    for f in files:
        if f.name in excluded_files:
            continue
            
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                module_id = data.get("module", {}).get("id", "")
                module_name = data.get("module", {}).get("name", "")
                
                if module_id and module_name:
                    display_text = f"{module_id} - {module_name}"
                    items.append((display_text, str(f)))
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            letter = f.stem.split("_")[-1]
            items.append((letter.upper(), str(f)))
    
    return items


def make_thread_id() -> str:
    return f"session_{uuid.uuid4().hex[:8]}"


def create_initial_state(loader: ModuleLoader, start_qid: str) -> InterviewState:
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


def generate_questioner_question(state: InterviewState) -> AIMessage:
    current_question = state.module_loader.get_question(state.current_question_id)
    sys_msg = SystemMessage(content=QUESTIONER_SYSTEM_PROMPT.format(question=current_question.prompt))

    if len(state.evaluator_results) > 0:
        if state.evaluator_results[-1] == "explain request":
            patient_response = state.messages[-1].content if state.messages else ""
            sys_msg = SystemMessage(
                content=EXPLAIN_PROMPT.format(response=patient_response, current_question=current_question.prompt)
            )
        elif state.evaluator_results[-1] == "rephrase needed":
            patient_response = state.messages[-1].content if state.messages else ""
            evaluator_reasoning = state.messages[-2].content if len(state.messages) >= 2 else "Response was unclear"
            sys_msg = SystemMessage(
                content=CLARIFICATION_PROMPT.format(
                    question=current_question.prompt,
                    response=patient_response,
                    reasoning=evaluator_reasoning
                )
            )

    response = get_llm().invoke([sys_msg])  # Updated to use lazy loading
    if not isinstance(response, AIMessage):
        response = AIMessage(content=response.content)
    return response




def apply_navigator_updates(state: InterviewState, updates: dict) -> InterviewState:
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


def display_evaluator_feedback(evaluator_result: dict, user_answer: str):
    if not evaluator_result:
        return
    
    # Extract the classification and reasoning
    classification = evaluator_result.get("evaluator_results", [""])[0] if evaluator_result.get("evaluator_results") else ""
    reasoning_msg = evaluator_result.get("messages", [None])[0]
    if classification == "red_flag":
        reasoning = st.session_state.red_flag_message
    else:
        reasoning = reasoning_msg.content if reasoning_msg else "No reasoning provided"
    
    if classification == "yes":
        st.success("✅ **Evaluator Decision: YES** - Answer accepted")
    elif classification == "no":
        st.success("❌ **Evaluator Decision: NO** - Answer accepted")
    elif classification == "explain request":
        st.info("❓ **Evaluator Decision: EXPLAIN REQUEST** - Patient needs explanation")
    elif classification == "rephrase needed":
        st.warning("🤔 **Evaluator Decision: NEEDS CLARIFICATION** - Response unclear")
    else:
        st.info(f"ℹ️ **Evaluator Decision: {classification.upper()}**")
    
    # Show user's answer and evaluator reasoning
    with st.expander("📝 See evaluator analysis", expanded=False):
        st.write(f"**Your answer:** \"{user_answer}\"")
        st.write(f"**evaluator reasoning:** {reasoning}")
        
    st.markdown("---")


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

if "red_flag_detected" not in st.session_state:
    st.session_state.red_flag_detected = False

# App state: "asking_question" or "showing_feedback"
if "app_state" not in st.session_state:
    st.session_state.app_state = "asking_question"


# ----------------------------------- UI -------------------------------------- #
st.set_page_config(page_title="MINI Interview", page_icon="🗣️", layout="centered")

apply_custom_styling()

st.title("MINI Interview")

# Show subtitle only when interview hasn't started
if st.session_state.loader is None or st.session_state.state is None:
    st.markdown("The MINI (Mini International Neuropsychiatric Interview) is a structured diagnostic interview traditionally administered by clinicians. With this platform, we are automating the MINI using an agentic AI system. The goal is to make the assessment process faster, more scalable, and easier to use, while maintaining clinical rigor and reliability.")
    st.markdown("⚠️ This is currently a proof of concept and should not be considered a replacement for diagnosis or evaluation by a qualified human clinician.")
    st.markdown("We strongly encourage users not to share personal or sensitive information on this platform.")

ensure_api_key()

modules = list_available_modules()
if not modules:
    st.error("❌ No modules found in the `modules/` directory.")
    st.info("Expected module files like `module_a.json`, `module_d.json`, etc.")
    st.info("Please check that the modules directory exists and contains valid module files.")
    
    # Show what files we did find in the modules directory
    if MODULES_DIR.exists():
        files_found = list(MODULES_DIR.glob("*"))
        if files_found:
            st.write("Files found in modules directory:")
            for f in files_found[:10]:  # Show first 10 files
                st.write(f"- {f.name}")
    else:
        st.write(f"Modules directory does not exist: {MODULES_DIR}")
    
    st.stop()

with st.sidebar:
    st.header("Setup")
    module_options = [m[0] for m in modules]
    selected_module = st.selectbox("Select module", module_options, index=0)
    selected_path = dict(modules)[selected_module]    

    if st.button("Start / Reset Interview", type="primary"):
        loader = ModuleLoader.from_file(selected_path)
        start_qid = loader.get_first_question_id()
        st.session_state.loader = loader
        st.session_state.state = create_initial_state(loader, start_qid)
        st.session_state.awaiting_answer = False
        st.session_state.last_question = ""
        st.session_state.finished = False
        st.session_state.diagnosis_result = None
        st.session_state.latest_evaluator_result = None  # Clear evaluator results
        st.session_state.red_flag_detected = False  # Reset red flag state
        st.session_state.red_flag_message = ""
        st.session_state.thread_id = make_thread_id()
        st.session_state["answer_input"] = ""
        st.session_state["clear_answer"] = True
        st.rerun()
    
    # Add spacer to push content to bottom
    st.markdown("<br>" * 20, unsafe_allow_html=True)
    
    # Add content at the bottom of the sidebar
    st.markdown("---")
    st.markdown(
        "Give feedback: [Feedback Form](https://docs.google.com/forms/d/1kwnEcoh_XnVidUVthPu66d3Wr2w8beN3ywQ8NvkLmMQ/edit)"
    )

if st.session_state.loader is None or st.session_state.state is None:
    st.info("Select a module in the sidebar and click 'Start / Reset Interview'.")
    st.stop()

state: InterviewState = st.session_state.state

if st.session_state.finished:
    if st.session_state.red_flag_detected:
        st.error("🚨 **CRISIS ALERT** 🚨")
        st.markdown("It looks like you may be going through a very difficult time.")
        st.markdown("If you feel you are in immediate danger, please call 911 or your local emergency services:")
        st.markdown("- **Emergency Services**: 911")
        st.markdown("- **National Suicide Prevention Lifeline**: 988")        
        st.markdown("---")
        st.info("The interview has been stopped for your safety. Please seek immediate professional help.")
        
        # Add feedback section even for red flag cases
        st.markdown("---")
        st.markdown("### Help Us Improve")
        st.markdown("Your feedback helps us make this tool better for everyone.")
        if st.button("📝 Share Your Feedback", type="secondary", use_container_width=True, key="red_flag_feedback"):
            st.markdown("Please visit: [https://forms.google.com/feedback](https://forms.google.com/feedback)")
    else:
        st.success("Interview completed.")

    if st.session_state.diagnosis_result is not None and not st.session_state.red_flag_detected:
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
            
            # Show timeFrame if present
            timeframe = group_result.get("timeFrame")
            if timeframe:
                st.markdown(f"- **Time frame**: {timeframe}")
            
            # Show Module F specific field: fearRestricted
            fear_restricted = group_result.get("fearRestricted")
            if fear_restricted is not None:
                restriction_text = "Yes - Limited to speaking/performing in public" if fear_restricted else "No - Broader social situations"
                st.markdown(f"- **Fear restriction**: {restriction_text}")
            
            # Show Module G specific fields: insight and ticRelated
            insight = group_result.get("insight")
            if insight:
                st.markdown(f"- **Insight level**: {insight}")
            
            tic_related = group_result.get("ticRelated")
            if tic_related is not None:
                tic_text = "Yes" if tic_related else "No"
                st.markdown(f"- **Tic-related**: {tic_text}")
            
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
    
    # Additional feedback section on completion page
    st.markdown("---")
    st.markdown("### Help Us Improve")
    st.markdown("Your feedback helps us make this tool better for everyone.")
    if st.button("📝 Share Your Feedback", type="secondary", use_container_width=True):
        st.markdown("Please visit: [https://forms.google.com/feedback](https://forms.google.com/feedback)")
    
    st.stop()

if not st.session_state.awaiting_answer:
    question_msg = generate_questioner_question(state)
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

# Display evaluator results from the previous answer
if st.session_state.get("latest_evaluator_result"):
    display_evaluator_feedback(
        st.session_state.latest_evaluator_result["evaluator_data"], 
        st.session_state.latest_evaluator_result["user_answer"]
    )
    
    # Show Next Question button
    if st.button("Next Question", use_container_width=True, type="primary"):
        # Clear feedback and continue (navigator logic already ran after evaluator)
        st.session_state.latest_evaluator_result = None
        st.session_state.awaiting_answer = False
        st.session_state.clear_answer = True
        st.rerun()
    
    # Hide the input buttons when showing feedback
    st.stop()

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

    evaluator_result = evaluator_node(state)
    
    # Store evaluator results for display
    st.session_state.latest_evaluator_result = {
        "evaluator_data": evaluator_result,
        "user_answer": answer
    }
    
    state.messages = list(state.messages) + evaluator_result["messages"]
    state.evaluator_results = list(state.evaluator_results) + evaluator_result["evaluator_results"]

    # Check if the latest evaluator result is a red flag
    if evaluator_result["evaluator_results"] and evaluator_result["evaluator_results"][0].lower() == "red_flag":
        st.session_state.red_flag_detected = True
        st.session_state.red_flag_message = detect_red_flag(answer)[1]

    # Run navigator to determine next step (this sets ready_for_diagnosis if needed)
    if should_clarify(state) == "continue":
        updates = navigator_node(state)
        state = apply_navigator_updates(state, updates)
    
    # Update session state with the modified state
    st.session_state.state = state

    # Always rerun to show the feedback
    # st.rerun()

    branch = should_diagnose(state)
    if branch == "diagnose":
        diag = diagnoser_node(state)
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