# 🧠 MINI Interview Agent

An AI-powered agent system for conducting MINI (Mini International Neuropsychiatric Interview) assessments with intelligent response analysis and dynamic conversation flow.

## Features

- **🔄 LangGraph-powered workflow** with conditional branching logic
- **🤖 LLM-based response analysis** (yes/no/unclear classification) 
- **🎯 Intelligent clarification** when patient responses are ambiguous
- **📋 JSON-based modules** with branching questionnaire logic
- **💬 Natural conversation flow** with professional clinical tone
- **📊 Comprehensive logging** of all interactions and classifications

## Quick Start

### Prerequisites

```bash
pip install -r requirements.txt
```

Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=sk-proj-your-api-key-here
```

### Simple Usage

**Option 1: Default module (Module A - Major Depression)**
```bash
python3 run_interview.py
```

**Option 2: Specify module by letter**
```bash
python3 run_interview.py a    # Module A (Major Depression)
python3 run_interview.py e    # Module E (Agoraphobia)
```

**Option 3: Advanced usage with CLI**
```bash
python3 -c "from interview_agent.cli import run; run()" modules/working/module_a.json
```

## 📁 Project Structure

```
mini-agenti-ai/
├── interview_agent/          # Core Python package
│   ├── models.py             # Data models and state management
│   ├── nodes.py              # LangGraph nodes (interviewer, judge, etc.)
│   ├── graph.py              # Graph construction and workflow
│   └── cli.py                # Command-line interface
├── modules/working/          # MINI questionnaire modules
│   ├── module_a.json         # Major Depressive Episode
│   └── module_e.json         # Agoraphobia
├── notebooks/                # Jupyter notebooks for development
├── run_interview.py          # Simple script to run interviews
└── requirements.txt          # Python dependencies
```

## 🔄 How It Works

### 1. **Interviewer Node**
- Presents MINI questions using natural language
- Collects patient responses through console input
- Maintains conversation history and context

### 2. **Judge Node** 
- Analyzes patient responses using GPT-4o-mini
- Classifies responses as: `yes`, `no`, or `need more clarification`
- Uses confidence thresholds (>70%) for reliable classification

### 3. **Conditional Flow**
- **Clear responses** → Move to next question based on JSON branching logic
- **Unclear responses** → Return to interviewer for clarification
- **Module completion** → Generate diagnostic summary

### 4. **Response Analysis**
```python
# Example LLM prompt for response analysis
"""
Question: "Do you feel sad most days?"
Patient Response: "Sometimes, I guess"
Classification: need more clarification
Reasoning: Response is ambiguous with uncertainty markers
"""
```

## Example Session

```
Starting interview with modules/working/module_a.json
==================================================

------------------------------ Start of question A1a------------------------------
Were you ever depressed or down, or felt sad, empty or hopeless most of the day, 
nearly every day, for two weeks? Please answer yes or no. If you're uncertain, 
feel free to explain.
You: I don't know, maybe sometimes

enter judge
reason behind the decision: Response is ambiguous with uncertainty markers
decision: need more clarification
exit judge

enter interviewer
------------------------------ Start of question A1a------------------------------
Could you help me understand better - have you experienced periods where you felt 
sad or hopeless most of the day, nearly every day, for at least two weeks? 
Please answer yes or no.
You: yes

enter judge  
reason behind the decision: Clear affirmative response
decision: yes
exit judge

Moving to next question based on 'yes' response...
```

## 🛠️ Configuration

### Environment Variables
- `OPENAI_API_KEY`: Your OpenAI API key (required)

### Module Structure
Each JSON module contains:
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
