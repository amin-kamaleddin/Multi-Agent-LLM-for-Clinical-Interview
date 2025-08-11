from datetime import datetime
import json
import argparse, uuid, os
from pathlib import Path
from dotenv import load_dotenv

from .models import InterviewState, ModuleLoader
from .graph import build_graph


def _load_key():
    load_dotenv()
    if "OPENAI_API_KEY" not in os.environ:
        raise RuntimeError("OPENAI_API_KEY not set (use .env or export)")


def run():
    parser = argparse.ArgumentParser(description="Run MINI interviewer")
    parser.add_argument("module_path", help="Path to MINI JSON file")
    parser.add_argument(
        "--start_qid",
        help="First question ID",
        default=None
    )
    args = parser.parse_args()

    _load_key()
    loader = ModuleLoader.from_file(args.module_path)
    app = build_graph(loader)

    # Use provided start_qid or automatically get the first question
    start_qid = args.start_qid if args.start_qid else loader.get_first_question_id()

    state = InterviewState(
        module_loader=loader,
        current_question_id=start_qid,
        messages=[],
    )

    thread_id = f"session_{uuid.uuid4().hex[:8]}"
    result = app.invoke(state, config={"recursion_limit": 100})
    _save_log(result, thread_id, loader)


def _save_log(result, thread_id, module_loader):
    export_data = {
        "session_metadata": {
            "session_id": thread_id,
            "module_id": module_loader.module.id,
            "module_name": module_loader.module.name,
            "timestamp": datetime.now().isoformat(),
        },
        
        "conversation_log": [
            {
                "question_id": entry["question_id"],
                "original_question_text": module_loader.get_question(entry["question_id"]).prompt,
                "ai_question": entry.get("ai_question", ""),
                "follow_up": getattr(module_loader.get_question(entry["question_id"]), 'followUp', None),
                "patient_response": entry["patient_response"],
                "ai_classification": entry["classification"],
                "ai_reasoning": entry["reasoning"],
                "timestamp": entry.get("timestamp", ""),
                "exchange_type": entry.get("exchange_type", "initial"),
            }
            for entry in result["conversation_log"]
        ],
        
        "diagnostic_results": result.get("diagnosis_content", {}).model_dump() if hasattr(result.get("diagnosis_content", {}), 'model_dump') else result.get("diagnosis_content", {}),
    }
    
    Path("reports").mkdir(exist_ok=True)
    path = Path("reports") / f"{thread_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"Conversation export saved to {path}")


if __name__ == "__main__":
    run()