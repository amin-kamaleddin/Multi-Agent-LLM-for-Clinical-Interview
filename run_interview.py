import argparse
import os
import sys
from pathlib import Path


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="MINI interview agent for symptom assessment"
    )
    parser.add_argument(
        "--patient_agent",
        type=str,
        choices=["True", "False", "true", "false"],
        default="false",
        help="Enable patient agent mode (default: false)"
    )

    # Parse command line arguments
    args = parser.parse_args()

    # Convert string to boolean
    PATIENT_AGENT = args.patient_agent.lower() == "true"

    module_file = None
    available_modules = ["a", "d", "e", "f", "g", "h", "n", "o", "p", "b", "c", "x"]

    print(
        "\nWelcome to the MINI interview agent. I will guide you through a series of brief questions to assess your "
        "symptoms and help a clinician determine your next steps.\n")
    print(
        "Patient Agent mode is activated and will simulate the end user behaviour\n" if PATIENT_AGENT else "end user mode is activated\n")
    print("Please enter the letter corresponding to the module you want to start with: (a, b, c, d, e, f, g, h, n, o, "
          "p)")
    module_file = input()

    while True:
        if len(module_file) == 1 and module_file.isalpha() and module_file.lower() in available_modules:
            module_file = f"modules/module_{module_file.lower()}.json"
            break
        else:
            print("Invalid module letter. Please enter a valid letter: (a, b, c, d, e, f, g, h, n, o, p)")
            module_file = input().strip()

    # Check if file exists
    if not os.path.exists(module_file):
        print(f"Error: Module file '{module_file}' not found")
        print("Available modules:")
        modules_dir = Path("modules/")
        if modules_dir.exists():
            for file in sorted(modules_dir.glob("module_*.json")):
                module_letter = file.stem.split("_")[-1]
                print(f"  {module_letter} -> {file}")
        sys.exit(1)

    print(f"Starting interview with {module_file}")
    print(f"Patient Agent Mode: {PATIENT_AGENT}")
    print("=" * 50)

    try:
        from interview_agent.cli import run
        sys.argv = ["run_interview.py", module_file]
        run(patient_agent=PATIENT_AGENT)
    except KeyboardInterrupt:
        print("\n\nInterview interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
