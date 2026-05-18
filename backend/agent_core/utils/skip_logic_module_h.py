from backend.agent_core.interview_agent.models import InterviewState
from backend.agent_core.utils.extract_question_answer_pair import extract_question_classification_pairs


def module_h_ready_to_diagnose(state: InterviewState) -> bool:
    # module H has skip logic almost after every question. this function checks if the module is ready for diagnosis.
    # returns a boolean for ready_for_diagnosis
    question_checkpoints = {"H4a", "H5a", "H6"}
    if state.current_question_id not in question_checkpoints:
        return False
    pairs = extract_question_classification_pairs(state.conversation_log)
    if state.current_question_id == "H4a":
        if pairs["H3a"] == "no" and pairs["H3b"] == "no":
            return True  # Ready for diagnosis

    elif state.current_question_id == "H5a":
        h4_keys = ["H4a", "H4b", "H4c", "H4d", "H4e", "H4f", "H4g"]

        # Count how many of them are coded "yes"
        yes_count = sum(1 for key in h4_keys if pairs.get(key) == "yes")

        # Return True if two or more are "yes"
        if yes_count >= 2:
            return False  # Not ready for diagnosis

    elif state.current_question_id == "H6":
        h5_keys = ["H5a", "H5b", "H5c", "H5d", "H5e", "H5f"]

        # Count how many of them are coded "yes"
        yes_count = sum(1 for key in h5_keys if pairs.get(key) == "yes")

        # Return True if two or more are "yes"
        if yes_count >= 2:
            return False  # Not ready for diagnosis

    return False  # Not ready for diagnosis
