def extract_question_answer_pair(log: list[dict], max_pairs=5):
    results = []
    last_logs = None
    if len(log) > 5:
        last_logs = log[-5:]
    else:
        last_logs = log

    for pair in last_logs:
        results.append({
            'question': pair["ai_question"],
            'patient_answer': pair["patient_response"]
        })

    return results
