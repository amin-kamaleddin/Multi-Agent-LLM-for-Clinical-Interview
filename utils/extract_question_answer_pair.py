def extract_question_answer_pair(log: list[dict], max_pairs=5) -> list[dict]:
    results = []
    last_logs = log[-max_pairs:] if len(log) > max_pairs else log

    for pair in last_logs:
        results.append({
            'question': pair.get("ai_question", None),
            'patient_answer': pair.get("patient_response", None)
        })

    return results


def extract_question_classification_pairs(log: list[dict]) -> dict:
    yes_no = {"yes", "no"}
    results = {}
    for pair in log:
        cls = pair.get("classification")
        if cls in yes_no:
            results[f"{pair['question_id']}"] = cls
    return results
