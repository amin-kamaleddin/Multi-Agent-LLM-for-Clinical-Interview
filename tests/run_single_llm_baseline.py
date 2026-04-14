"""
Single-LLM Baseline: post-hoc diagnosis from raw interview transcripts.

For each patient conversation, the LLM receives only the raw Q&A transcript
(no Evaluator labels) and must apply the module's diagnostic criteria in a
single pass to produce a final diagnosis.

Run from repo root:
    python tests/run_single_llm_baseline.py --module A

Outputs:
    baselines/module_{LETTER}/diagnosis_{id}.json   (per-patient, for auditing)
    baselines/module_{LETTER}/predictions_single_llm_gpt-4o-mini.csv
"""

import argparse
import csv
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.1
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries on failure

# Diagnosis key per module letter (matches eval_patient_agent.py)
DIAGNOSIS_KEY = {
    **{m: "positive" for m in ["A", "O", "B", "C", "H", "I", "J", "L", "G"]},
    **{m: "lifetime" for m in ["P", "D"]},
}

MODULE_EXTRA_INSTRUCTIONS: dict = {}

# ---------------------------------------------------------------------------
# Pydantic output models
# ---------------------------------------------------------------------------

class DiagnosisGroup(BaseModel):
    diagnosis: bool
    reasoning: str
    timeFrame: Optional[str] = None       # Module A positive only
    insight: Optional[str] = None         # Module G positive only
    ticRelated: Optional[bool] = None     # Module G positive only
    fearRestricted: Optional[bool] = None # Module F positive only

class DiagnosisOutput(BaseModel):
    positive: Optional[DiagnosisGroup] = None
    recurrent: Optional[DiagnosisGroup] = None
    lifetime: Optional[DiagnosisGroup] = None
    current: Optional[DiagnosisGroup] = None

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """You are an expert psychiatric diagnostic evaluator trained to administer and score structured clinical interviews following SCID-5 (Structured Clinical Interview for DSM-5) conventions. Your task is to read a verbatim patient interview transcript and apply the module's diagnostic criteria to produce a precise, evidence-based diagnosis.

You have doctoral-level training in clinical psychopathology. You are familiar with DSM-5 diagnostic thresholds, symptom counting rules, temporal requirements (e.g., "most of the day, nearly every day for at least 2 weeks"), and the distinction between primary psychiatric disorders and symptoms better explained by substances, medical conditions, or other mental disorders.

{extra_instructions}
--- ROLE AND METHODOLOGY ---

You must reason like an experienced clinician completing a structured diagnostic evaluation. Your job is not to summarize the interview — it is to apply a formal diagnostic algorithm to the evidence in the transcript.

Core principles:
- Evidence-based: Every criterion determination must be grounded in explicit patient statements. Do not diagnose based on clinical intuition alone.
- Conservative where ambiguous: If a patient's response is vague, hedging, or contradictory, do not assume the criterion is met unless the preponderance of evidence supports it.
- Threshold-strict: Partial endorsement of a criterion does not count. Duration, frequency, severity, and functional impact thresholds must be specifically satisfied.
- Non-inferential: Do not assume symptoms exist because they were not explicitly denied. Absence of endorsement is not the same as endorsement.
- Hierarchy-aware: Consider whether symptoms could be wholly attributable to a substance, medication, or general medical condition — if so, they may not meet the diagnostic threshold.

Step-by-step reasoning process for each diagnostic group:
1. READ the transcript fully before scoring any criterion.
2. For each criterion in the module, locate the specific patient response(s) that are relevant.
3. Determine whether the criterion is MET, NOT MET, or UNCLEAR based solely on those responses.
4. For UNCLEAR criteria, note why (e.g., patient was evasive, question was not asked, response contradicted itself).
5. Apply the module's counting rule (e.g., "at least 5 of 9 symptoms") and any required sub-criteria (e.g., depressed mood OR anhedonia must be among the 5).
6. Check exclusion criteria: substance-induced, medical etiology, better explained by another disorder.
7. Determine whether functional impairment is explicitly described as clinically significant.
8. Reach a final determination for each diagnostic group and write a structured rationale.

--- DIAGNOSTIC CRITERIA ({module_name}) ---
{criteria_text}

--- DETAILED EVALUATION GUIDELINES ---

Symptom counting and thresholds:
- Count only symptoms that are clearly endorsed AND meet the stated severity or frequency requirements.
- A symptom mentioned only in passing or with significant minimization (e.g., "maybe a little, not really") should be coded as unclear/not met.
- If a module requires symptoms to be present "for most of the day, nearly every day," a patient reporting symptoms only occasionally or intermittently does not meet that criterion.
- When a symptom requires a minimum duration (e.g., 2 weeks, 6 months, 1 year), the patient's account must explicitly support that timeframe.

Temporal classification:
- "Current" or "positive" group: symptoms are active within the required recent timeframe (typically past 2 weeks to 1 month, depending on module).
- "Lifetime" group: the full diagnostic syndrome was met at some point in the past, regardless of current status.
- "Recurrent" group: a second or more distinct episode meeting full criteria has occurred, separated by a period of remission.
- Do not conflate lifetime history of isolated symptoms with a full syndromal episode.

Handling ambiguous or incomplete responses:
- If the patient uses hedging language ("sort of," "I guess," "maybe"), treat the criterion as unclear unless surrounding context makes endorsement clear.
- If a question was skipped or the patient refused to answer, note that the criterion could not be assessed.
- If the patient's responses are internally inconsistent (e.g., denies depressed mood in one answer but describes crying daily in another), note the inconsistency and weigh the stronger evidence.

Functional impairment:
- Functional impairment must be clinically significant: it causes marked distress OR meaningfully interferes with social, occupational, or other important areas of functioning.
- Statements like "it bothers me sometimes" are insufficient. Look for evidence of work/school difficulties, relationship problems, social withdrawal, or significant distress explicitly linked to the symptoms.

Exclusion criteria:
- If the patient describes symptoms that emerged exclusively during substance use or withdrawal, or during an acute medical illness, apply appropriate exclusion criteria.
- Do not assume exclusion unless the patient's account clearly supports it.

--- OUTPUT FORMAT ---
Return a single, raw JSON object with no markdown fences and no trailing text. Precision in the schema is required — do not add, omit, or rename fields.

For modules with a "positive" group:
{{
  "positive": {{
    "reasoning": "<structured clinical rationale — see requirements below>",
    "diagnosis": true or false{timeframe_field}{insight_field}{ticrelated_field}{fearrestricted_field}
  }},
  "recurrent": {{
    "reasoning": "<structured clinical rationale — see requirements below>",
    "diagnosis": true or false
  }}
}}

For modules with a "lifetime" group, replace "positive" with "lifetime".
For modules with a "current" group, replace "positive" with "current" and omit "recurrent".

Requirements for the "reasoning" field:
1. Criterion-by-criterion walkthrough: For each diagnostic criterion, state whether it is MET, NOT MET, or UNCLEAR, and quote or closely paraphrase the patient's relevant response.
2. Symptom count summary: State the required count and the actual count (e.g., "Requires ≥5 of 9 symptoms; found 6 clearly met, 1 unclear, 2 not met").
3. Threshold and exclusion check: Explicitly state whether duration, severity, functional impairment, and exclusion criteria are satisfied.
4. Final determination: Conclude with a one-sentence explanation of why the diagnosis is true or false, referencing the key deciding factor(s).

Example reasoning structure:
"Criterion A1 (depressed mood): MET — patient stated 'I feel sad and empty almost every day.' Criterion A2 (anhedonia): MET — 'I stopped enjoying things I used to love.' Criterion A3 (weight/appetite): NOT MET — patient denied changes. Criterion A4 (sleep): MET — 'I sleep maybe 3-4 hours a night.' [...] Total: 6 of 9 criteria met (threshold ≥5). Duration: met (patient reports symptoms for 3 weeks). Functional impairment: met ('I had to leave my job because of this'). Exclusions: not triggered. Diagnosis: TRUE — full threshold met with impairment confirmed."
"""

def _format_criteria_value(rules: object, indent: str = "  ") -> list:
    """Recursively format a criteria value into readable lines."""
    lines = []
    if isinstance(rules, list):
        for i, rule in enumerate(rules, 1):
            lines.append(f"{indent}{i}. {rule}")
    elif isinstance(rules, dict):
        for k, v in rules.items():
            lines.append(f"{indent}[{k}]")
            lines.extend(_format_criteria_value(v, indent + "  "))
    elif isinstance(rules, str):
        lines.append(f"{indent}{rules}")
    return lines


def build_system_prompt(module_letter: str, module_name: str, criteria: dict,
                        questions: list | None = None) -> str:
    extra = MODULE_EXTRA_INSTRUCTIONS.get(module_letter.upper(), "")

    # Format criteria groups (handles nested dicts correctly)
    criteria_lines = []
    for group, rules in criteria.items():
        criteria_lines.append(f"\n[{group}]")
        criteria_lines.extend(_format_criteria_value(rules))
    criteria_text = "\n".join(criteria_lines)

    # Build a question-code reference table so the LLM can resolve codes like
    # C3f, D4a, H5b that appear in the diagnostic criteria rules.
    # Optional JSON fields per module
    timeframe_field = ',\n    "timeFrame": "past" | "recent" | "both" | null' if module_letter.upper() == "A" else ""
    insight_field = ',\n    "insight": "goodOrFair" | "poor" | "absent" | "delusional" | null' if module_letter.upper() == "G" else ""
    ticrelated_field = ',\n    "ticRelated": true | false | null' if module_letter.upper() == "G" else ""
    fearrestricted_field = ',\n    "fearRestricted": true | false | null' if module_letter.upper() == "F" else ""

    return SYSTEM_PROMPT_TEMPLATE.format(
        extra_instructions=extra,
        module_name=module_name,
        criteria_text=criteria_text,
        timeframe_field=timeframe_field,
        insight_field=insight_field,
        ticrelated_field=ticrelated_field,
        fearrestricted_field=fearrestricted_field,
    )

# ---------------------------------------------------------------------------
# Output normalizer — ensures baseline JSON matches multi-agent format exactly
# ---------------------------------------------------------------------------

def normalize_group(group: dict) -> dict:
    """Return a group dict with fields in the canonical multi-agent field order.
    Optional fields (timeFrame, insight, ticRelated, fearRestricted) are only
    included when non-null — keeping output lean per module."""
    out: dict = {
        "diagnosis": group.get("diagnosis", False),
        "reasoning":  group.get("reasoning", ""),
    }
    for opt in ("timeFrame", "insight", "ticRelated", "fearRestricted"):
        val = group.get(opt)
        if val is not None:
            out[opt] = val
    return out


def normalize_diagnosis(result: dict) -> dict:
    """Normalize all top-level diagnosis groups in the LLM response."""
    return {key: normalize_group(val) for key, val in result.items() if isinstance(val, dict)}


# ---------------------------------------------------------------------------
# Transcript formatter
# ---------------------------------------------------------------------------

def format_transcript(csv_path: str, include_qids: bool = False) -> str:
    """Read a conversation CSV and return a Q&A transcript.
    
    include_qids=True (Module C only): prefix each question with [question_id]
    so the scoring guide can reference specific codes like [C3f_current].
    For all other modules the raw question text is sufficient and including
    IDs would let the LLM trivially map opaque criterion codes.
    """
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row.get("question_id", "").strip()
            question = row.get("ai_question", "").strip()
            response = row.get("patient_response", "").strip()
            if question and response:
                prefix = f"[{qid}] " if (qid and include_qids) else ""
                rows.append(f"Q: {prefix}{question}\nA: {response}")
    return "\n\n".join(rows)

# ---------------------------------------------------------------------------
# LLM caller
# ---------------------------------------------------------------------------

def call_llm(llm: ChatOpenAI, system_prompt: str, transcript: str) -> dict:
    """Call the LLM and return parsed JSON dict. Retries on failure."""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"--- INTERVIEW TRANSCRIPT ---\n\n{transcript}"),
    ]
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = llm.invoke(messages)
            text = response.content.strip()
            # Strip markdown code fences if present
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except (json.JSONDecodeError, Exception) as e:
            if attempt < MAX_RETRIES:
                print(f"    [retry {attempt}/{MAX_RETRIES}] Error: {e}")
                time.sleep(RETRY_DELAY)
            else:
                raise RuntimeError(f"LLM call failed after {MAX_RETRIES} attempts: {e}") from e

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run single-LLM baseline for a given module.")
    parser.add_argument("--module", default="A", help="Module letter (default: A)")
    parser.add_argument("--force", action="store_true", help="Re-run even if predictions CSV already exists")
    args = parser.parse_args()

    letter = args.module.upper()

    # Paths
    module_json_path = f"./modules/module_{letter.lower()}.json"
    patients_json_path = f"./backend/agent_core/interview_agent/prompts/patients_with_system_prompts_module_{letter}.json"
    transcripts_dir = f"./patient_agent_results/patients_with_system_prompts_module_{letter}"
    output_dir = f"./baselines/module_{letter}"
    output_csv_path = f"{output_dir}/predictions_single_llm_gpt-4o-mini.csv"

    # Validate paths
    for p, label in [(module_json_path, "module JSON"), (patients_json_path, "patients JSON"), (transcripts_dir, "transcripts dir")]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Cannot find {label}: {p}")

    # Short-circuit if already done
    if os.path.exists(output_csv_path) and not args.force:
        print(f"Predictions already exist at {output_csv_path}. Use --force to re-run.")
        return

    # Load module definition
    with open(module_json_path, "r", encoding="utf-8") as f:
        module_def = json.load(f)
    module_name = module_def["module"]["name"]
    criteria = module_def["diagnosticCriteria"]
    questions = module_def.get("questions", [])

    # Load patient metadata (ground truth)
    with open(patients_json_path, "r", encoding="utf-8") as f:
        patients_data = json.load(f)
    id_to_label = {
        int(p["id"]): "true" if p["Expected Symptom Direction"] == "Positive Symptom Presentation" else "false"
        for p in patients_data
    }

    # Collect transcript CSVs
    csv_pattern = re.compile(r"^(\d+)\.csv$")
    patient_ids = sorted(
        int(csv_pattern.match(f).group(1))
        for f in os.listdir(transcripts_dir)
        if csv_pattern.match(f)
    )
    print(f"Module {letter} — {len(patient_ids)} patients found")

    # Determine diagnosis key
    diag_key = DIAGNOSIS_KEY.get(letter, "current")

    # Build system prompt (shared across all patients for this module)
    system_prompt = build_system_prompt(letter, module_name, criteria, questions)

    # Load API key from .env
    load_dotenv()
    if "OPENAI_API_KEY" not in os.environ:
        raise RuntimeError("OPENAI_API_KEY not set — add it to .env or export it")

    # Set up LLM
    llm = ChatOpenAI(model=MODEL, temperature=TEMPERATURE)

    # Output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Run
    rows = []
    for pid in patient_ids:
        csv_path = os.path.join(transcripts_dir, f"{pid}.csv")
        label = id_to_label.get(pid, "")
        if not label:
            print(f"  [{pid}] WARNING: no ground truth label found, skipping")
            continue

        print(f"  [{pid}/{patient_ids[-1]}] Running...", end=" ", flush=True)
        try:
            transcript = format_transcript(csv_path)
            result = normalize_diagnosis(call_llm(llm, system_prompt, transcript))

            # Save per-patient JSON for auditing
            diag_json_path = os.path.join(output_dir, f"diagnosis_{pid}.json")
            with open(diag_json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4)

            # Extract prediction
            group = result.get(diag_key, {})
            # Fallback: C outputs 'current', D/P sometimes output 'positive'
            if not group:
                for alt in ("current", "positive", "lifetime"):
                    if alt != diag_key and result.get(alt):
                        group = result[alt]
                        break
            prediction_bool = group.get("diagnosis", None)
            prediction = "true" if prediction_bool is True else "false"
            print(f"label={label}, pred={prediction}")
        except Exception as e:
            print(f"ERROR: {e}")
            prediction = "false"  # conservative fallback on error

        rows.append({"id": pid, "label": label, "prediction": prediction})

    # Write predictions CSV
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "label", "prediction"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Predictions saved to {output_csv_path}")

if __name__ == "__main__":
    main()
