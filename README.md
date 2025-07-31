# 🧠 MINI Agentic Interview System

An agentic AI system for conducting MINI 7.0.2 psychiatric assessments using autonomous agents to simulate clinician-patient interaction, analyze responses, and follow diagnostic logic.

---

## 🚀 Project Overview

This system features a modular and extensible architecture:

### 🧑‍⚕️ Patient Agent
- Simulates patient responses, which can be scripted or generated dynamically.
- Supports real-time or offline interaction modes.

### 💬 Interview Agent
- Administers MINI modules (e.g., depression, anxiety, phobia).
- Handles question sequencing based on branching logic.
- Follows MINI phrasing and time-frame instructions.
- Handles transitions between modules and concludes the interview.

### ⚖️ Judge Agent
- Monitors both patient responses and LLM analysis.
- Validates consistency with MINI logic.
- Flags **mismatches or inconsistencies** between the response and logic.
- Passes flagged items to the **Client Observer**.

### 👁️ Client Observer
- Receives flagged responses from the Judge Agent.
- Allows a human reviewer (e.g., a clinician or researcher) to **inspect, override, or intervene** in real-time or post-interview.
- Provides transparency and safety before any clinical or research action is taken.

---

### 🔧 Core Methods

- `get_next_question()`:  
  Returns the next relevant question based on MINI branching logic and past answers.

- `ask_patient()`:  
  Delivers the question to the patient agent and receives the answer.

- `ask_clarification()`:  
  Re-engages the patient if the answer is vague or uncertain.

- `analyze_response()`:  
  Applies LLM analysis to map free-text answers to standardized MINI responses.

---

## 🧪 Example: Agoraphobia Module (Module E)

```text
[Question E1]
Clinician: Do you feel anxious or uneasy in places or situations where help might not be available or escape difficult if you had a panic-like or embarrassing symptom, such as being in a crowd or queue, in an open space or crossing a bridge, in an enclosed space, when alone away from home, when alone at home, or traveling in a bus, train, car, or using public transportation?
Patient answered: yes
LLM Analysis: yes
Based on 'yes' response, next: E2

[Question E2]
Clinician: Do these situations almost always bring on fear or anxiety?
Patient answered: no
LLM Analysis: no
Based on 'no' response, next: END_MODULE

======================================================================
INTERVIEW COMPLETE
======================================================================