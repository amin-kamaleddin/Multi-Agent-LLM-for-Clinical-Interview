
# 🧠 MINI Interview Agent

AI agent for conducting MINI (Mini International Neuropsychiatric Interview) assessments with dynamic conversation flow, clinical tone, and intelligent follow-ups powered by LLMs.

---

## ✨ Features

- 🧭 **LangGraph workflow:** Conditional branching that mirrors MINI logic
- 🧠 **LLM judgment:** Yes / No / Unclear classification 
- 🔍 **Smart clarifications:** Targeted follow-ups for ambiguous replies
- 🗂️ **JSON modules:** Questionnaire logic with explicit branching paths
- 🗣️ **Clinical tone:** Natural, professional conversation style
- 🧾 **Full logging:** Trace every prompt, response, and decision
- 🧪 **Patient Agent mode:** Simulate patient behavior for testing and demos

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Install dependencies:
  ```bash
  pip install -r requirements.txt


* Add your OpenAI key to a `.env` file:

  ```
  OPENAI_API_KEY=sk-proj-your-api-key-here
  ```

### Run an interview

```bash
python run_interview.py
```

* Choose a MINI module by entering a letter: `a, d, e, f, g, n, o, p`.
* The agent guides you through the module’s clinical questions.

### 🤖 Patient Agent mode

Simulate patient responses for automated testing or demos:

```bash
python run_interview.py --patient_agent true
```

---

## 🔄 Workflow

The system is a directed graph of coordinated nodes that share a single `InterviewState`.

### Graph

![Graph overview](./graph_visualization.png)

### Walkthrough

1. **Interviewer Node**

   * Presents the next MINI question with an LLM.
   * If the previous reply was ambiguous, generates a focused clarification prompt.
   * If the previous reply was request for more explanation, generates a detailed explanation for question and add 
     an example if applicable.

2. **Patient Node**

   * Receives the interviewer’s question.
   * Either simulates a patient reply via LLM (automated mode) or accepts user input (manual mode).

3. **Judge Node**

   * Reviews the patient’s response.
   * If the answer is clearly yes or no without extra context, classifies locally without an LLM call.
   * Otherwise calls an LLM to return one of: `yes`, `no`, `rephrase needed`, `explain request`.
   * Optional failsafe: after three consecutive ambiguities, classify as `yes` to break loops. This threshold is configurable.

4. **Clarification Handling**

   * If the judge requests clarification, route back to the interviewer to ask a clearer question.
   * Otherwise continue to selection.

5. **Selector Node**

   * Logs question, response, and classification.
   * Advances to the next question using module branching logic.
   * Flags completion or readiness for diagnosis.

6. **Diagnosis Node**

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
│   ├── nodes.py              # LangGraph nodes (interviewer, judge, etc.)
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


