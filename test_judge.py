import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from interview_agent.models import (
    ClassificationResult,
)
from typing import Any, Dict

from interview_agent.cli import _load_key

JUDGE_SYSTEM_PROMPT = """
You are a clinical psychological assessment agent. Analyze the patient's response and provide guidance to the interviewer.

CLASSIFICATION RULES:
- "yes" - Response indicates affirmation, agreement, or provides specific information that answers the question (interpret generously)
- "no" - Response indicates negation, disagreement, or clearly answers "no" to the question
- "rephrase needed" - Response is vague, unclear, or deflects, but shows engagement with the topic. Interviewer should rephrase the same question differently
- "explain request" - Patient asks for clarification about the question itself. Interviewer should explain the question

ANALYSIS PROCESS:
1. Try to interpret the response generously - can you reasonably infer a yes/no answer?
2. If unclear but relevant, request rephrasing rather than exact repetition
3. Only use "explain request" if patient explicitly asks what the question means

LIBERAL INTERPRETATION: Err on the side of extracting meaning. Vague responses like "kind of", "I guess", "sometimes" should often be classified as "yes" or "no" based on context.

EXAMPLES:
Question: "Do you often feel sad?"
- "Yes, sometimes" → yes
- "Kind of, I guess" → yes (generous interpretation)
- "Not really" → no
- "I don't know, maybe" → rephrase needed
- "What do you mean by sad?" → explain request

Question: "How many episodes have you had?"
- "12" → yes
- "A lot" → yes (provides meaningful info)
- "I'm not sure" → rephrase needed
- "What counts as an episode?" → explain request

When classification is "rephrase needed", the interviewer should ask the same question using different words or approach, not repeat exactly.

Question: {last_question}
Patient Response: {patient_last_answer}
"""

judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
structured_llm = judge_llm.with_structured_output(ClassificationResult)

def judge(question, answer):
    # assume the loop-driver put the user's message in state.messages[-1]
    print("enter judge")

    prompt = JUDGE_SYSTEM_PROMPT.format(last_question= question, patient_last_answer= answer)
    resp = structured_llm.invoke([HumanMessage(content=prompt)])

    # Access Pydantic model attributes directly
    print(f"reason behind the decision: {resp.reasoning}")
    print(f"decision: {resp.classification}")

    label = str(resp.classification)
    if label not in ["yes", "no", "need more clarification", "N/A", "explain request"]:
        label = "need more clarification"

    print("exit judge")
    # TODO search for best practices of adding pydantic class to 'Messages'
    return label

# Step 1: Read CSV
df = pd.read_csv("./interview_agent/prompts/judge_dataset_test.csv")

_load_key()

# Step 2: Apply judge to each row
df["prediction"] = df.apply(lambda row: judge(row["question"], row["answer"]), axis=1)

accuracy = (df["prediction"] == df["label"]).mean()

print(f"Accuracy: {accuracy:.4f}")

# Step 3: Save new dataframe with labels
df.to_csv("./interview_agent/prompts/judge_dataset_test_with_labels.csv", index=False)

print("Done! New file saved with labels.")