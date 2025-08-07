#!/usr/bin/env python3
"""Simple script to run MINI interview agent."""

import sys
import os
from pathlib import Path


def main():
    module_file = None
    question_id = None

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--start_qid':
            if i + 1 < len(sys.argv):
                question_id = sys.argv[i + 1]
                i += 2
            else:
                print("Error: --question_id requires a value")
                sys.exit(1)
        else:
            # This is the module argument
            if module_file is None:
                module_file = arg
            i += 1

    # Default to module_a if no module specified
    if module_file is None:
        module_file = "modules/working/module_a.json"
        print(f"No module specified, using default: {module_file}")
    else:
        # Allow just the module letter (a, b, e)
        if len(module_file) == 1 and module_file.isalpha():
            module_file = f"modules/working/module_{module_file.lower()}.json"
    
    # Check if file exists
    if not os.path.exists(module_file):
        print(f"Error: Module file '{module_file}' not found")
        print("Available modules:")
        modules_dir = Path("modules/working")
        if modules_dir.exists():
            for file in sorted(modules_dir.glob("module_*.json")):
                module_letter = file.stem.split("_")[-1]
                print(f"  {module_letter} -> {file}")
        sys.exit(1)
    
    print(f"Starting interview with {module_file}")
    print("=" * 50)
    
    try:
        from interview_agent.cli import run
        sys.argv = ["run_interview.py", module_file]
        if question_id:
            sys.argv.extend(["--start_qid", question_id])
        run()
    except KeyboardInterrupt:
        print("\n\nInterview interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()