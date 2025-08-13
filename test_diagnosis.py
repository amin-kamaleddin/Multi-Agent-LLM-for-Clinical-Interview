import json, os
from typing import Dict, Literal, Optional
from pydantic import BaseModel, ValidationError, RootModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from interview_agent.cli import _load_key

DIAGNOSIS_SYSTEM_PROMPT="""
You are a psychiatric diagnostic evaluator.
=== Patient Summary ===
The patient's answers to yes/no questions are listed below:
{summary}

=== Diagnostic Group: {group_name} ===
Criteria to evaluate:
{criteria_formatted}

=== Instructions ===
You must assess whether each diagnostic criterion is met, based solely on the patient's answers.
1. General Rules:
    - Analyze each criterion independently.
    - Provide a concise explanation for whether each is met.
2. Symptom Group Criteria (e.g., 'at least 5 symptom groups'):
   - Treat all questions that belong to the same symptom group as one unit.
   - If **any** question in a group is marked 'YES' (whether past or recent), consider that symptom group as positive.
   - To satisfy the criterion, the required number of positive symptom groups must all come from **only one** time frame — either 'recent' or 'past', not a mix.
   - List which symptom groups are positive and under which time frame(s).
3. Non-Time-Frame-Specific Items (e.g., A1a, A1b, A2):
   - For items that do **not** include a time frame suffix (like _past or _recent), evaluate them as TRUE or FALSE regardless of time frame.
   - These items are valid if marked 'YES' in any context.
4. Organic Cause / Rule-Out Criteria:
   - For now, infer that organic causes are ruled out.
5. Diagnosis Summary:
   - After assessing all criteria, provide a final diagnosis summary.
   - If **all** criteria are met, the diagnosis is 'True'. Otherwise, it is 'False'.
   - For a positive diagnosis, also determine the **time frame**:
        - Choose from: **past**, **recent**, or **both**.
        - This refers to the time frame in which the symptom group criteria were satisfied.
        - Do not use 'both' unless both past and recent **independently** meet the symptom threshold.
        
=== Output Format ===
            Return ONLY a JSON object with these fields:
            
            "reasoning": "<a concise explanation for the assessment>",
            "timeFrame": "past" | "recent" | "both" | null,
            "diagnosis": true/false
            
            DO NOT include any other text outside this JSON. Your diagnosis must match with your reasoning.
"""

CRITERIA = {
    "majorDepressiveEpisode": {
        "mustHave": [
            "At least 5 symptom groups (A3a–A3g) coded YES",
            "Core symptom: A1b=YES or A2b=YES",
            "Functional impairment: A4_recent=YES or A4_past=YES",
            "Organic cause ruled out"
        ],
        "recurrent": "A5 = YES"
    }
}
MODULE_NAME = "majorDepressiveEpisode"

from pydantic import BaseModel, ValidationError, RootModel

class CriteriaGroupResult(BaseModel):
    diagnosis: bool
    timeFrame: Optional[Literal['past', 'recent', 'both']] = None
    reasoning: str

class DiagnosisEvaluationOutput(RootModel[Dict[str, CriteriaGroupResult]]):
    pass

def lowercase_first_letter(s: str) -> str:
    s = s.strip().replace(" ", "")
    return s[0].lower() + s[1:] if s else s

def evaluate_diagnosis_from_log(conversation_log, criteria_rules, module_name, verbose=True) -> DiagnosisEvaluationOutput:
    patient_responses = {}
    for entry in conversation_log:
        qid = entry.get("question_id")
        classification = entry.get("classification")
        if qid and classification:
            patient_responses[qid] = classification.strip().upper()

    module_key = lowercase_first_letter(module_name)
    if module_key not in criteria_rules:
        raise ValueError(f"No criteria found for module '{module_name}'.")

    criteria_groups = criteria_rules[module_key]
    if not isinstance(criteria_groups, dict) or not criteria_groups:
        raise ValueError(f"No valid criteria groups found for module '{module_name}'.")

    summary = "\n".join(f"{qid}: {ans}" for qid, ans in sorted(patient_responses.items()))

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.1)
    result = {}

    for group_name, rule_list in criteria_groups.items():
        if isinstance(rule_list, list):
            if not rule_list:
                result[group_name] = {"diagnosis": False, "timeFrame": None, "reasoning": "No criteria provided."}
                continue
            criteria_formatted = "\n".join(f"{i+1}. {crit}" for i, crit in enumerate(rule_list))
        elif isinstance(rule_list, str):
            criteria_formatted = rule_list.strip()
        else:
            result[group_name] = {"diagnosis": False, "timeFrame": None, "reasoning": "Invalid criteria format."}
            continue
        prompt = DIAGNOSIS_SYSTEM_PROMPT.format(summary=summary, group_name=group_name, criteria_formatted=criteria_formatted)

        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # remove markdown code block formatting
        if content.startswith("```json"):
            content = content.removeprefix("```json").removesuffix("```").strip()

        print(f"LLM JSON output for group '{group_name}':\n{content}\n{'-'*40}")

        try:
            data = json.loads(content)
            group_result = CriteriaGroupResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            # Ensure the errors directory exists
            os.makedirs("errors", exist_ok=True)
            
            # Save the raw LLM output
            error_path = f"errors/group_{group_name}_raw.txt"
            with open(error_path, "w", encoding="utf-8") as f:
                f.write(content)
            raise ValueError(f"Failed to parse LLM JSON output for group '{group_name}': {e}\nRaw output:\n{content}")

        result[group_name] = group_result.model_dump()

    return DiagnosisEvaluationOutput.model_validate(result)


def run_test_case(name, conversation_log, expected_diagnosis, expected_time_frame=None):
    print("=" * 50)
    print(f"Running Test Case: {name}")
    print("-" * 50)
    
    result = evaluate_diagnosis_from_log(conversation_log, CRITERIA, MODULE_NAME)
    print(f"Result: {result}")
    
    actual_diagnosis = result.root['mustHave'].diagnosis
    actual_time_frame = result.root['mustHave'].timeFrame

    print(f"\nFinal Diagnosis Result: {actual_diagnosis}")
    print(f"Expected Diagnosis: {expected_diagnosis}")
    assert actual_diagnosis == expected_diagnosis, f"Test failed: Expected diagnosis {expected_diagnosis}, got {actual_diagnosis}"

    if expected_time_frame is not None:
        print(f"Time Frame Reported: {actual_time_frame}")
        print(f"Expected Time Frame: {expected_time_frame}")
        assert actual_time_frame == expected_time_frame, f"Test failed: Expected time frame '{expected_time_frame}', got '{actual_time_frame}'"
    
    print("Test Passed!")
    print("=" * 50 + "\n")

def run_all_test():
    _load_key()

    # Test Case 1: Mixed time frame → FAIL
    run_test_case(
        "Invalid: Mixed Time Frame Symptoms",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A2b", "classification": "NO"},
            {"question_id": "A3a_recent", "classification": "YES"},
            {"question_id": "A3b_past", "classification": "YES"},
            {"question_id": "A3c_recent", "classification": "YES"},
            {"question_id": "A3d_recent", "classification": "YES"},
            {"question_id": "A3e_past", "classification": "YES"},
            {"question_id": "A4_recent", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
        ],
        expected_diagnosis=False
    )

    # Test Case 2: Valid current-only symptoms → PASS
    run_test_case(
        "Positive: All Symptom Groups from Current",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A2b", "classification": "NO"},
            {"question_id": "A3a_recent", "classification": "YES"},
            {"question_id": "A3b_recent", "classification": "YES"},
            {"question_id": "A3c_recent", "classification": "YES"},
            {"question_id": "A3d_recent", "classification": "YES"},
            {"question_id": "A3e_recent", "classification": "YES"},
            {"question_id": "A4_recent", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
        ],
        expected_diagnosis=True,
        expected_time_frame="recent"
    )

    # Test Case 3: Valid past-only symptoms → PASS
    run_test_case(
        "Positive: All Symptom Groups from Past",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A2b", "classification": "NO"},
            {"question_id": "A3a_past", "classification": "YES"},
            {"question_id": "A3b_past", "classification": "YES"},
            {"question_id": "A3c_past", "classification": "YES"},
            {"question_id": "A3d_past", "classification": "YES"},
            {"question_id": "A3e_past", "classification": "YES"},
            {"question_id": "A4_past", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
        ],
        expected_diagnosis=True,
        expected_time_frame="past"
    )

    # Test Case 4: Fewer than 5 symptom groups → FAIL
    run_test_case(
        "Negative: Fails 'At least 5 symptom groups'",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A2b", "classification": "NO"},
            {"question_id": "A3a_recent", "classification": "YES"},
            {"question_id": "A3b_past", "classification": "YES"},
            {"question_id": "A3c_recent", "classification": "YES"},
            {"question_id": "A3d_recent", "classification": "YES"},
            {"question_id": "A3e_recent", "classification": "NO"},
            {"question_id": "A3e_past", "classification": "NO"},
            {"question_id": "A3f_recent", "classification": "NO"},
            {"question_id": "A3g_recent", "classification": "NO"},
            {"question_id": "A4_recent", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
        ],
        expected_diagnosis=False
    )

    # Test Case 5: Missing core symptom → FAIL
    run_test_case(
        "Negative: Fails 'Core symptom'",
        [
            {"question_id": "A1b", "classification": "NO"},
            {"question_id": "A2b", "classification": "NO"},
            {"question_id": "A3a_recent", "classification": "YES"},
            {"question_id": "A3b_recent", "classification": "YES"},
            {"question_id": "A3c_recent", "classification": "YES"},
            {"question_id": "A3d_recent", "classification": "YES"},
            {"question_id": "A3e_recent", "classification": "YES"},
            {"question_id": "A4_recent", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
        ],
        expected_diagnosis=False
    )

    # Test Case 6: Missing functional impairment → FAIL
    run_test_case(
        "Negative: Fails 'Functional impairment'",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A2b", "classification": "NO"},
            {"question_id": "A3a_recent", "classification": "YES"},
            {"question_id": "A3b_recent", "classification": "YES"},
            {"question_id": "A3c_recent", "classification": "YES"},
            {"question_id": "A3d_recent", "classification": "YES"},
            {"question_id": "A3e_recent", "classification": "YES"},
            {"question_id": "A4_recent", "classification": "NO"},
            {"question_id": "A4_past", "classification": "NO"},
            {"question_id": "O1", "classification": "NO"},
        ],
        expected_diagnosis=False
    )

    run_test_case(
        "Positive: Current + Recurrent",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A3a_recent", "classification": "YES"},
            {"question_id": "A3b_recent", "classification": "YES"},
            {"question_id": "A3c_recent", "classification": "YES"},
            {"question_id": "A3d_recent", "classification": "YES"},
            {"question_id": "A3e_recent", "classification": "YES"},
            {"question_id": "A4_recent", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
            {"question_id": "A5", "classification": "YES"},  # Recurrent
        ],
        expected_diagnosis=True,
        expected_time_frame="recent"
    )

    run_test_case(
        "Positive: Past + Not Recurrent",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A3a_past", "classification": "YES"},
            {"question_id": "A3b_past", "classification": "YES"},
            {"question_id": "A3c_past", "classification": "YES"},
            {"question_id": "A3d_past", "classification": "YES"},
            {"question_id": "A3e_past", "classification": "YES"},
            {"question_id": "A4_past", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
            {"question_id": "A5", "classification": "NO"},  # Not recurrent
        ],
        expected_diagnosis=True,
        expected_time_frame="past"
    )

    run_test_case(
        "Positive: Past, Recurrent Not Specified",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A3a_past", "classification": "YES"},
            {"question_id": "A3b_past", "classification": "YES"},
            {"question_id": "A3c_past", "classification": "YES"},
            {"question_id": "A3d_past", "classification": "YES"},
            {"question_id": "A3e_past", "classification": "YES"},
            {"question_id": "A4_past", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
        ],
        expected_diagnosis=True,
        expected_time_frame="past"
    )

    run_test_case(
        "Positive: Current only meets threshold in Mixed Set",
        [
            {"question_id": "A1b", "classification": "YES"},
            {"question_id": "A3a_recent", "classification": "YES"},
            {"question_id": "A3b_recent", "classification": "YES"},
            {"question_id": "A3c_recent", "classification": "YES"},
            {"question_id": "A3d_recent", "classification": "YES"},
            {"question_id": "A3e_recent", "classification": "YES"},
            {"question_id": "A3f_past", "classification": "YES"},  # Should be ignored
            {"question_id": "A4_recent", "classification": "YES"},
            {"question_id": "O1", "classification": "NO"},
            {"question_id": "A5", "classification": "YES"},
        ],
        expected_diagnosis=True,
        expected_time_frame="recent"
    )

    run_test_case(
        "Negative: Only A5 YES, No Criteria Met",
        [
            {"question_id": "A1b", "classification": "NO"},
            {"question_id": "A2b", "classification": "NO"},
            {"question_id": "A3a_recent", "classification": "NO"},
            {"question_id": "A3b_recent", "classification": "NO"},
            {"question_id": "A3c_recent", "classification": "NO"},
            {"question_id": "A3d_recent", "classification": "NO"},
            {"question_id": "A4_recent", "classification": "NO"},
            {"question_id": "O1", "classification": "NO"},
            {"question_id": "A5", "classification": "YES"},
        ],
        expected_diagnosis=False
    )

    run_test_case(
        "Positive: Both Past and Current, Not Recurrent",
        [
            {"question_id": "A1b", "classification": "YES"},

            # Past symptom groups (5)
            {"question_id": "A3a_past", "classification": "YES"},
            {"question_id": "A3b_past", "classification": "YES"},
            {"question_id": "A3c_past", "classification": "YES"},
            {"question_id": "A3d_past", "classification": "YES"},
            {"question_id": "A3e_past", "classification": "YES"},

            # Current symptom groups (5)
            {"question_id": "A3a_recent", "classification": "YES"},
            {"question_id": "A3b_recent", "classification": "YES"},
            {"question_id": "A3c_recent", "classification": "YES"},
            {"question_id": "A3d_recent", "classification": "YES"},
            {"question_id": "A3e_recent", "classification": "YES"},

            # Functional impairment (both available)
            {"question_id": "A4_recent", "classification": "YES"},
            {"question_id": "A4_past", "classification": "YES"},

            # Organic cause ruled out
            {"question_id": "O1", "classification": "NO"},

            # No recurrence indicated
            {"question_id": "A5", "classification": "NO"},
        ],
        expected_diagnosis=True,
        expected_time_frame="both"
    )


if __name__ == "__main__":
    # Diagnostic criteria JSON
    run_all_test()