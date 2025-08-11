from pathlib import Path
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


def build_graph(loader: ModuleLoader, visualize: bool = True):
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
                             {"continue": "interviewer", "diagnose": "diagnosis"})

    sg.add_edge("diagnosis", END)

    compiled_sg = sg.compile()

    # Generate visualization if requested
    if visualize:
        try:
            _create_graph_visualization(compiled_sg)
        except Exception as e:
            print(f"Warning: Could not create graph visualization: {e}")
            print("Continuing without visualization...")

    return compiled_sg


def _create_graph_visualization(compiled_graph):
    """
    Simple graph visualization that saves PNG file.
    """
    try:
        png_data = compiled_graph.get_graph(xray=True).draw_mermaid_png()

        with open("graph_visualization.png", "wb") as f:
            f.write(png_data)

        print("📊 Graph visualization saved: graph_visualization.png")

    except Exception as e:
        raise Exception(f"Graph visualization failed: {e}")

