import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark_modules import MODULES


def _run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)


def _require_prediction_files(base_pattern: str, modules: list[str]) -> None:
    missing = []
    for mod in modules:
        path = Path(base_pattern.format(module=mod))
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise FileNotFoundError("Missing required prediction files:\n" + "\n".join(missing))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the three-system benchmark pipeline (multi-agent, single-agent, rule-based)."
    )
    parser.add_argument(
        "--modules",
        default=",".join(MODULES),
        help="Comma-separated module letters (default: A,B,C,D,E,F,G,H,I,J,L,M,MB,N,P)",
    )
    parser.add_argument(
        "--python-bin",
        default="env311/bin/python",
        help="Python executable used for pipeline commands (default: env311/bin/python)",
    )
    parser.add_argument(
        "--skip-multi-sim",
        action="store_true",
        help="Skip multi-agent simulation rerun and reuse existing predictions files.",
    )
    parser.add_argument(
        "--skip-single-sim",
        action="store_true",
        help="Skip single-agent simulation rerun and reuse existing predictions files.",
    )
    parser.add_argument(
        "--skip-rule-sim",
        action="store_true",
        help="Skip rule-based simulation rerun and reuse existing predictions files.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    modules = [m.strip().upper() for m in args.modules.split(",") if m.strip()]
    py = args.python_bin

    # 1) Multi-agent simulation/eval pipeline
    if not args.skip_multi_sim:
        # Multi-agent "simulation rerun" is delegated to existing module prediction CSVs per module.
        # This script refreshes the canonical combined file from per-module predictions.
        _run([py, "backend/agent_core/utils/create_combined_csv.py"])
    _require_prediction_files(
        "patient_agent_results/patients_with_system_prompts_module_{module}/predictions_gpt-4o-mini.csv",
        modules,
    )
    _run(
        [
            py,
            "run_patient_agent_bootstrap.py",
            "--input-csv",
            "patient_agent_results/prediction_combined_all_modules.csv",
            "--output-csv",
            "patient_agent_results/evaluation_results.csv",
            "--n-bootstrap",
            "10000",
            "--seed",
            "42",
        ]
    )

    # 2) Single-agent baseline pipeline
    if not args.skip_single_sim:
        for mod in modules:
            _run([py, "tests/run_single_llm_baseline.py", "--module", mod, "--force"])
    _require_prediction_files("baselines/module_{module}/predictions_single_llm_gpt-4o-mini.csv", modules)
    _run([py, "baselines/build_single_agent_combined_csv.py", "--modules", ",".join(modules)])
    _run(
        [
            py,
            "run_patient_agent_bootstrap.py",
            "--input-csv",
            "baselines/predictions_single_llm_combined_clean.csv",
            "--output-csv",
            "baselines/evaluation_results_single_agent.csv",
            "--n-bootstrap",
            "10000",
            "--seed",
            "42",
        ]
    )

    # 3) Rule-based baseline pipeline
    if not args.skip_rule_sim:
        for mod in modules:
            _run([py, "tests/run_rule_based_baseline.py", "--module", mod, "--force"])
    _require_prediction_files("baselines_rule_based/module_{module}/predictions_rule_based.csv", modules)
    _run([py, "baselines/build_rule_based_combined_csv.py", "--modules", ",".join(modules)])
    _run(
        [
            py,
            "run_patient_agent_bootstrap.py",
            "--input-csv",
            "baselines/predictions_rule_based_combined_clean.csv",
            "--output-csv",
            "baselines/evaluation_results_rule_based.csv",
            "--n-bootstrap",
            "10000",
            "--seed",
            "42",
        ]
    )

    # 4) Figure generation for each system
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    env["MPLCONFIGDIR"] = "/tmp/mpl"

    _run(
        [
            py,
            "plot_bootstrap_evaluation_table.py",
            "--results-csv",
            "patient_agent_results/evaluation_results.csv",
            "--figures-dir",
            "figures/multi-agent",
        ],
        env=env,
    )
    _run(
        [
            py,
            "plot_bootstrap_evaluation_table.py",
            "--results-csv",
            "baselines/evaluation_results_single_agent.csv",
            "--figures-dir",
            "figures/single-agent",
        ],
        env=env,
    )
    _run(
        [
            py,
            "plot_bootstrap_evaluation_table.py",
            "--results-csv",
            "baselines/evaluation_results_rule_based.csv",
            "--figures-dir",
            "figures/rule-based",
        ],
        env=env,
    )

    # 5) 3-way summary artifact
    _run([py, "tests/eval_three_systems.py"])
    print("\nThree-system benchmark completed.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"\nPipeline failed (exit code {exc.returncode}).", file=sys.stderr)
        raise
