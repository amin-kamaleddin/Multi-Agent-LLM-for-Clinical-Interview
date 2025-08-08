import streamlit as st
import subprocess
import threading
import queue
import sys
import os
from pathlib import Path

"""
This is a Streamlit app that allows you to run the MINI interview agent.

*** This is a work in progress and is a poor implementation of a Streamlit app. ***
*** There are lots of improvements that need to be made, but the goal was to have a simple UI working
for the demo on August 8th, 2025.***
"""

st.set_page_config(page_title="MINI Interview Agent", layout="centered")
st.title("MINI Interview Agent")
st.write(
    "I will guide you through a series of brief questions to assess your symptoms "
    "and help a clinician determine your next steps."
)


SCRIPT = str(Path(__file__).parent / "run_interview.py")


def ensure_session_state():
    if "proc" not in st.session_state:
        st.session_state.proc = None
    if "out_q" not in st.session_state:
        st.session_state.out_q = queue.Queue()
    if "out_lines" not in st.session_state:
        st.session_state.out_lines = []
    if "started" not in st.session_state:
        st.session_state.started = False


ensure_session_state()


def reader_thread(proc, out_q):
    for line in iter(proc.stdout.readline, ""):
        out_q.put(line)
    proc.stdout.close()


def pump_output():
    try:
        while True:
            line = st.session_state.out_q.get_nowait()
            st.session_state.out_lines.append(line)
    except queue.Empty:
        pass


def start_process():
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
        env=env,
        cwd=str(Path(__file__).parent),
    )
    st.session_state.proc = proc
    t = threading.Thread(target=reader_thread, args=(
        proc, st.session_state.out_q), daemon=True)
    t.start()
    st.session_state.started = True


col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Start / Restart interview", type="primary"):
        if st.session_state.proc and st.session_state.proc.poll() is None:
            st.session_state.proc.terminate()
        st.session_state.out_lines = []
        start_process()

with col2:
    if st.session_state.proc and st.session_state.proc.poll() is None and st.button("Stop"):
        st.session_state.proc.terminate()

if st.session_state.started:
    pump_output()

if st.session_state.out_lines:
    st.text("".join(st.session_state.out_lines))
else:
    st.info("Click **Start / Restart interview** to begin.")

if st.session_state.proc and st.session_state.proc.poll() is None:
    user_msg = st.chat_input("Type your response and press Enter")
    if user_msg is not None:
        try:
            st.session_state.proc.stdin.write(user_msg + "\n")
            st.session_state.proc.stdin.flush()
        except Exception as e:
            st.error(f"Failed to send input: {e}")

if st.session_state.proc and st.session_state.proc.poll() is not None:
    pump_output()
    code = st.session_state.proc.returncode
    if code != 0:
        st.warning(f"Interview completed (process exited with code {code}).")
