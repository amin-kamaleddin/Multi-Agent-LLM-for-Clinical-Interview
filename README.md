---
title: Structured Clinical Interview Agent
emoji: 🧠
colorFrom: blue
colorTo: green
sdk: streamlit
app_file: streamlit_app.py
pinned: false
license: mit
startup_duration_timeout: 1h
python_version: 3.11
---

# 🧠 Structured Clinical Interview Agent

AI agent for conducting structured neuropyschiatric assessments with dynamic conversation flow, clinical tone, and intelligent follow-ups powered by LLMs.

---

## ✨ Features

- 🧭 **LangGraph workflow:** Conditional branching logic to guide patients through required questions
- 🧠 **LLM judgment:** Yes / No / Unclear classification 
- 🔍 **Smart clarifications:** Targeted follow-ups for ambiguous replies
- 🗂️ **JSON modules:** Questionnaire logic with explicit branching paths
- 🗣️ **Clinical tone:** Natural, professional conversation style
- 🧾 **Full logging:** Trace every prompt, response, and decision
- 🧪 **Patient Agent mode:** Simulate patient behavior for testing and demos
- 🚨 **Red flag detection**: Identify potential self-harm risk based on responses

---

## 🚀 Quick Start

### 🌐 Use Online (Hugging Face Spaces)

Visit the [live demo](https://huggingface.co/spaces/areezvisram/MINI-Interview-Agent) - no setup required!

### 💻 Local Development

**Prerequisites:**
- Python 3.8+
- OpenAI API key

**Setup:**
```bash
# Clone the repository
git clone https://github.com/yourusername/mini-agent.git
cd mini-agent

# Install dependencies
pip install -r requirements.txt

# Add your OpenAI key to a .env file
echo "OPENAI_API_KEY=sk-proj-your-api-key-here" > .env
```

**Run Options:**

**Streamlit Web App:**
```bash
streamlit run streamlit_app.py
```

**Command Line Interface:**
```bash
python run_interview.py
```

**Patient Agent Mode (for testing):**
```bash
python run_interview.py --patient_agent true
```

---

## 🔄 Workflow

The system is a directed graph of coordinated nodes that share a single `InterviewState`.

### Graph

![Graph overview](./graph_visualization.png)

### Walkthrough

1. **Questioner Node**

   * Presents the next neuropyschiatric interview question with an LLM.
   * If the previous reply was ambiguous, generates a focused clarification prompt.
   * If the previous reply was request for more explanation, generates a detailed explanation for question and add 
     an example if applicable.

2. **Patient Node**

   * Receives the questioner’s question.
   * Either simulates a patient reply via LLM (automated mode) or accepts user input (manual mode).

3. **Evaluator Node**

   * Reviews the patient’s response.
   * Anonymize PII/PHI to protect privacy.
   * Raise a red flag for potential self-harm risk.
   * If the answer is clearly yes or no without extra context, classifies locally without an LLM call.
   * Otherwise calls an LLM to return one of: `yes`, `no`, `rephrase needed`, `explain request`, `red flag`.
   * Optional failsafe: after three consecutive ambiguities, classify as `yes` to break loops. This threshold is configurable.

4. **Clarification Handling**

   * If the evaluator requests clarification, route back to the questioner to ask a clearer question.
   * Otherwise continue to selection.

5. **Navigator Node**

   * Logs question, response, and classification.
   * Advances to the next question using module branching logic.
   * Flags completion or readiness for diagnosis.

6. **Diagnoser Node**

   * Compiles all responses and criteria.
   * Uses an LLM to produce a structured diagnostic summary.

7. **End**

   * Saves diagnostic results and the full conversation log for review.

**Input modes**

* 🧪 **Patient Agent:** Automated simulation via LLM and a system prompt.
* ⌨️ **Manual:** Interactive CLI input from the user.

---

## 📦 Project Structure

```
mini-agent/
├── interview_agent/          # Core package
│   ├── models.py             # Data models and InterviewState
│   ├── nodes.py              # LangGraph nodes (questioner, evaluator, etc.)
│   ├── graph.py              # Workflow construction
│   └── cli.py                # Command-line interface
├── modules/                  # MINI questionnaire modules
│   ├── module_a.json         # Major Depressive Episode
│   ├── module_d.json         # ... other modules
├── run_interview.py          # Entry script
└── requirements.txt          # Dependencies
```

### 🧩 Module JSON schema (example)

```json
{
  "module": {
    "id": "A",
    "name": "Major Depressive Episode"
  },
  "questions": [
    {
      "id": "A1a",
      "prompt": "Question text...",
      "next": {
        "yes": "A1b",
        "no": "A2a"
      }
    }
  ]
}
```

---

## ⚙️ Configuration

Environment variables:

* `OPENAI_API_KEY` (required): OpenAI API key

---


