from langgraph.constants import START, END
from langgraph.graph import StateGraph

from .models import InterviewState, ModuleLoader
from .nodes import (
    interviewer_node,
    judge_node,
    selector,
    diagnosis,
    should_clarify,
    should_diagnose,
)


def build_graph(loader: ModuleLoader):
    sg = StateGraph(InterviewState)

    sg.add_node("interviewer", interviewer_node)
    sg.add_node("judge", judge_node)
    sg.add_node("selector", selector)
    sg.add_node("diagnosis", diagnosis)

    sg.add_edge(START, "interviewer")
    sg.add_edge("interviewer", "judge")

    sg.add_conditional_edges("judge", should_clarify,
                             {"clarify": "interviewer", "continue": "selector"})

    sg.add_conditional_edges("selector", should_diagnose,
                             {"continue": "interviewer", "diagnose": "diagnosis", "end": END})

    sg.add_edge("diagnosis", END)
    return sg.compile()