import operator
from typing import Any, Dict, List, Literal, Optional, Sequence, Union, Annotated

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, RootModel


# ---------------------------- JSON module models ---------------------------- #
class Question(BaseModel):
    id: str
    prompt: str
    next: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class ModuleInfo(BaseModel):
    id: str
    name: str

    class Config:
        extra = "allow"


class ModuleLoader(BaseModel):
    questions: List[Question]
    module: ModuleInfo
    diagnostic_criteria: Optional[Dict[str, Any]] = Field(alias="diagnosticCriteria")

    _questions_dict: Dict[str, Question] = {}

    class Config:
        extra = "allow"
        validate_by_name = True

    def __init__(self, **data):
        super().__init__(**data)
        self._questions_dict = {q.id: q for q in self.questions}

    @classmethod
    def from_file(cls, path: str) -> "ModuleLoader":
        import json, pathlib
        with open(pathlib.Path(path), "r", encoding="utf-8") as f:
            return cls(**json.load(f))

    def get_question(self, qid: str) -> Question:
        return self._questions_dict[qid]
    
    def get_first_question_id(self) -> str:
        """Get the ID of the first question in the module."""
        if not self.questions:
            raise ValueError("No questions found in module")
        return self.questions[0].id

# ------------------------------ Graph state --------------------------------- #
def _add_log(left: list[dict], right: list[dict]) -> list[dict]:
    return left + right


class InterviewState(BaseModel):
    messages: Annotated[Sequence, add_messages] = Field(default_factory=list)
    conversation_log: Annotated[list[dict], _add_log] = Field(default_factory=list)
    module_loader: Any
    current_question_id: Optional[str] = None
    question_path: List[str] = Field(default_factory=list)
    evaluator_results: Annotated[List[Any], operator.add] = Field(default_factory=list)
    patient_agent: bool = False
    red_flag: bool = True
    module_completed: bool = False
    ready_for_diagnosis: bool = False
    diagnosis_content: Optional[Any] = Field(default_factory=dict)


# ---------------------------- LLM output schemas ---------------------------- #
class ClassificationResult(BaseModel):
    reasoning: str
    classification: Union[
        Literal["yes", "no", "explain request", "need more clarification"],  # for yes_no
        Literal["valid_quantity", "explain request", "need more clarification"],  # for quantity
        Literal["valid_response", "explain request", "need more clarification"]  # for descriptive answers
    ]
    extracted_quantity: Optional[str] = None  # Store the actual quantity/frequency mentioned


class DiagnosisResult(BaseModel):
    reasoning: str
    classification: Literal["Yes", "No"]
    red_flags: str


class CriteriaGroupResult(BaseModel):
    diagnosis: bool
    timeFrame: Optional[Literal['past', 'recent', 'both']] = None
    reasoning: str
    insight: Optional[Literal['goodOrFair', 'poor', 'absent', 'delusional']] = None
    ticRelated: Optional[bool] = None
    fearRestricted: Optional[bool] = None


class DiagnosisEvaluationOutput(RootModel[Dict[str, CriteriaGroupResult]]):
    pass