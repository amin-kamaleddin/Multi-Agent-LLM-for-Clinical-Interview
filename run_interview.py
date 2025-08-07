#!/usr/bin/env python3
"""Simple script to run MINI interview agent."""

import sys
import os
from pathlib import Path

def main():
    # Default to module_a if no argument provided
    if len(sys.argv) < 2:
        module_file = "modules/working/module_a.json"
        print(f"No module specified, using default: {module_file}")
    else:
        # Allow just the module letter (a, b, e)
        module_arg = sys.argv[1].lower()
        if len(module_arg) == 1 and module_arg.isalpha():
            module_file = f"modules/working/module_{module_arg}.json"
        else:
            module_file = sys.argv[1]
    
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
        run()
    except KeyboardInterrupt:
        print("\n\nInterview interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()