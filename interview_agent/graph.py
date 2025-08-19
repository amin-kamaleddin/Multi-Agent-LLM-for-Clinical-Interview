from pathlib import Path
from langgraph.constants import START, END
from langgraph.graph import StateGraph

from .models import InterviewState, ModuleLoader
from .nodes import (
    questioner_node,
    evaluator_node,
    navigator_node,
    diagnoser_node,
    should_clarify,
    should_diagnose,
    patient_node,
)


def build_graph(loader: ModuleLoader, visualize: bool = True):
    sg = StateGraph(InterviewState)

    sg.add_node("questioner", questioner_node)
    sg.add_node("patient", patient_node)
    sg.add_node("evaluator", evaluator_node)
    sg.add_node("navigator", navigator_node)
    sg.add_node("diagnoser", diagnoser_node)

    sg.add_edge(START, "questioner")
    sg.add_edge("questioner", "patient")
    sg.add_edge("patient", "evaluator")

    sg.add_conditional_edges("evaluator", should_clarify,
                             {"clarify": "questioner", "continue": "navigator"})

    sg.add_conditional_edges("navigator", should_diagnose,
                             {"continue": "questioner", "diagnose": "diagnoser", "end": END})

    sg.add_edge("diagnoser", END)

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

