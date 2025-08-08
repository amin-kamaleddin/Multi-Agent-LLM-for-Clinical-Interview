import argparse, uuid, csv, os
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
        patient_agent=True
    )

    thread_id = f"session_{uuid.uuid4().hex[:8]}"
    result = app.invoke(state, config={"recursion_limit": 500})
    _save_log(result["conversation_log"], thread_id)


def _save_log(log, thread_id):
    Path("reports").mkdir(exist_ok=True)
    path = Path("reports") / f"{thread_id}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log[0].keys())
        writer.writeheader()
        writer.writerows(log)
    print(f"Conversation log saved to {path}")


if __name__ == "__main__":
    run()