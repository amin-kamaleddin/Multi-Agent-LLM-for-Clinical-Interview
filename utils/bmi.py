from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from interview_agent.models import InterviewState
from utils.extract_question_answer_pair import extract_question_answer_pair_with_classification


class BmiResult(BaseModel):
    below_normal: bool
    reasoning: str


def is_bmi_below_normal(state: InterviewState) -> bool:
    _diagnosis_llm = ChatOpenAI(model="gpt-5-mini").with_structured_output(BmiResult)
    pairs = extract_question_answer_pair_with_classification(state.conversation_log, max_pairs=2)
    prompt = f"""
    calculate the BMI based on the following question and answer pairs, and determine if the BMI is below normal:
    {pairs}.
    Answer with a JSON object with a boolean field "below_normal" and reasoning.
    """
    result = _diagnosis_llm.invoke(prompt)
    print(result)
    return result.below_normal
