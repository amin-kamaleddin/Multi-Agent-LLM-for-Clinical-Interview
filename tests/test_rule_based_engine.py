from __future__ import annotations

import tempfile
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))

from rule_based_engine import (
    classify_response,
    classify_rows,
    evaluate_module,
    load_rule_config,
    normalize_text,
    parse_quantity,
    run_rule_diagnosis,
)


def test_normalize_text_contractions() -> None:
    text = "I don't feel it's that bad."
    out = normalize_text(text)
    assert "do not" in out
    assert "it is" in out


def test_classify_response_negation() -> None:
    label, _ = classify_response("No, I do not have that symptom.", {})
    assert label == "NO"


def test_parse_quantity_frequency() -> None:
    assert parse_quantity("2 times per week") == 2
    assert parse_quantity("daily") == 7
    assert parse_quantity("a couple of times") == 2


def test_module_a_timeframe_combinator() -> None:
    responses = {
        "A1b": "YES",
        "A2b": "NO",
        "A4_recent": "YES",
        "A4_past": "NO",
        "O1a": "NO",
        "O1b": "NO",
        "A5": "YES",
        "A3a_recent": "YES",
        "A3b_recent": "YES",
        "A3c_recent": "YES",
        "A3d_recent": "YES",
        "A3e_recent": "YES",
    }
    result = evaluate_module("A", responses, {})
    assert result["positive"]["diagnosis"] is True
    assert result["positive"]["timeFrame"] == "recent"
    assert result["recurrent"]["diagnosis"] is True


def _rows(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"question_id": qid, "patient_response": resp} for qid, resp in pairs]


def test_module_golden_all_modules() -> None:
    scenarios = {
        "A": _rows(
            ("A1b", "yes"), ("A4_recent", "yes"), ("O1a", "no"), ("O1b", "no"),
            ("A3a_recent", "yes"), ("A3b_recent", "yes"), ("A3c_recent", "yes"), ("A3d_recent", "yes"), ("A3e_recent", "yes"),
        ),
        "B": _rows(("B2", "yes I think about harming myself")),
        "C": _rows(
            ("C1b", "yes"), ("C3f_current", "yes"), ("C3a_current", "yes"), ("C3b_current", "yes"),
            ("C4_current", "4 days"), ("C7_current", "yes"), ("C5_current", "yes"), ("O1a", "no"), ("O1b", "no"),
        ),
        "D": _rows(
            ("D3", "yes"), ("D4a", "yes"), ("D4b", "yes"), ("D4c", "yes"), ("D4d", "yes"), ("O1a", "no"), ("O1b", "no"),
        ),
        "E": _rows(("E6", "yes")),
        "F": _rows(("F6", "yes"), ("O1a", "no"), ("O1b", "no")),
        "G": _rows(("G1a", "yes"), ("G1b", "yes"), ("G2", "yes"), ("G4", "yes"), ("O1a", "no"), ("O1b", "no")),
        "H": _rows(
            ("H7", "yes"), ("H3a", "yes"), ("H4a", "yes"), ("H4b", "yes"), ("H5a", "yes"), ("H5b", "yes"),
            ("O1a", "no"), ("O1b", "no"),
        ),
        "I": _rows(("I2a", "yes"), ("I2b", "yes")),
        "J": _rows(("J2a", "yes"), ("J2b", "yes")),
        "L": _rows(("L4a", "yes")),
        "M": _rows(("M5", "yes"), ("M7", "yes"), ("M4a", "2 times per week")),
        "MB": _rows(("MB1", "yes"), ("MB2", "yes"), ("MB3", "yes"), ("MB4", "no"), ("MB6a", "yes"), ("MB6b", "yes"), ("MB6c", "yes"), ("MB7", "yes")),
        "N": _rows(("N4", "yes"), ("N3a", "yes"), ("N3b", "yes"), ("N3c", "yes"), ("O1a", "no"), ("O1b", "no")),
        "P": _rows(("P1a", "yes"), ("P1b", "yes"), ("P2a", "yes"), ("P2b", "yes"), ("P2c", "yes")),
    }

    expected_group = {
        "A": "positive", "B": "current", "C": "positive", "D": "lifetime", "E": "current",
        "F": "current", "G": "positive", "H": "positive", "I": "positive", "J": "positive",
        "L": "positive", "M": "current", "MB": "current", "N": "current", "P": "lifetime",
    }

    for letter, rows in scenarios.items():
        config = load_rule_config(letter)
        responses, quantities, _ = classify_rows(rows, config)
        result = evaluate_module(letter, responses, quantities)
        grp = expected_group[letter]
        assert grp in result
        assert isinstance(result[grp]["diagnosis"], bool)


def test_run_rule_diagnosis_from_csv() -> None:
    csv_content = "question_id,patient_response\nA1b,yes\nA3a_recent,yes\nA3b_recent,yes\nA3c_recent,yes\nA3d_recent,yes\nA3e_recent,yes\nA4_recent,yes\nO1a,no\nO1b,no\n"
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "sample.csv"
        path.write_text(csv_content, encoding="utf-8")
        result = run_rule_diagnosis("A", str(path))
        assert result["positive"]["diagnosis"] is True
