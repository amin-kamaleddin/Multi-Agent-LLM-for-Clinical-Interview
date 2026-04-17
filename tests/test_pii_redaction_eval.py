import csv
import random
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Iterable, List

import pytest


@dataclass(frozen=True)
class PiiSpec:
    name: str
    token: str
    positives: Callable[[random.Random, int], List[str]]
    negatives: Callable[[random.Random, int], List[str]]


def _build_samples(
    rng: random.Random, templates: Iterable[str], values: Iterable[str], n: int
) -> List[str]:
    templates = list(templates)
    values = list(values)
    samples: List[str] = []
    noise_prefix = [
        "",
        "Um, ",
        "I guess ",
        "Honestly, ",
        "Well, ",
        "If you need it, ",
    ]
    noise_suffix = [
        "",
        " I think.",
        " That's all I remember.",
        " Not sure if that helps.",
        " That's what I have.",
        " Please don't share that.",
    ]
    question_stems = [
        "",
        "You asked for my contact info. ",
        "To answer your question: ",
        "Since you asked, ",
        "Regarding your question, ",
    ]
    symptom_context = [
        "",
        "I've been feeling anxious and tense lately. ",
        "I've been sleeping poorly and feeling on edge. ",
        "I've been stressed and my appetite is off. ",
        "I've had low mood and less energy recently. ",
        "I feel overwhelmed most days. ",
    ]
    for _ in range(n):
        template = rng.choice(templates)
        value = rng.choice(values) if values else ""
        prefix = rng.choice(noise_prefix)
        suffix = rng.choice(noise_suffix)
        question = rng.choice(question_stems)
        context = rng.choice(symptom_context)
        samples.append(f"{question}{context}{prefix}{template.format(value=value)}{suffix}")
    return samples


def _phone_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "415-555-2671",
        "(212) 555-0199",
        "1 604 555 1234",
        "+1 305-555-7788",
        "650.555.0101",
        "(646)5550199",
        "+44 20 7946 0958",  # intl (likely miss)
        "020 7946 0958",  # intl (likely miss)
    ]
    templates = [
        "My phone number is {value}.",
        "You can call me at {value}.",
        "It's {value}.",
        "The best number is {value}.",
        "Reach me at {value}.",
        "I can be reached at {value}.",
        "For follow-ups, it's {value}.",
    ]
    return _build_samples(rng, templates, values, n)


def _phone_neg(rng: random.Random, n: int) -> List[str]:
    templates = [
        "I will call you later.",
        "I don't have a phone right now.",
        "You can reach me through the clinic.",
        "I prefer not to share my number.",
        "The code is 1234.",
        "My extension is 77.",
        "The zip code is 94107.",
        "My order number is 4155552671.",
        "Please contact me via the portal.",
    ]
    return _build_samples(rng, templates, [""], n)


def _email_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "jane.doe@example.com",
        "a_b99@test.co",
        "first.last@domain.org",
        "user123@sample.net",
        "support+billing@company.io",
        "first.last@sub.domain.co.uk",
        "user@localhost",  # likely miss
    ]
    templates = [
        "My email is {value}.",
        "You can email me at {value}.",
        "Send it to {value}.",
        "It's {value}.",
        "Use {value} for follow-ups.",
        "If you need to reach me, use {value}.",
    ]
    return _build_samples(rng, templates, values, n)


def _email_neg(rng: random.Random, n: int) -> List[str]:
    templates = [
        "I don't really use email.",
        "You can send it through the portal.",
        "I check my inbox sometimes.",
        "Contact the office for details.",
        "I prefer phone calls.",
        "Reach out through the contact form.",
        "My handle is user at domain dot com.",
        "I can message you in the app.",
    ]
    return _build_samples(rng, templates, [""], n)


def _ssn_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "123-45-6789",
        "987 65 4321",
        "111-22-3333",
        "555223333",
        "000-12-3456",
        "123-456-789",  # invalid format (likely miss)
    ]
    templates = [
        "My SSN is {value}.",
        "It's {value}.",
        "The social security number is {value}.",
        "Use {value} for the SSN.",
        "I think it's {value}.",
        "You asked for my SSN, it's {value}.",
    ]
    return _build_samples(rng, templates, values, n)


def _ssn_neg(rng: random.Random, n: int) -> List[str]:
    templates = [
        "My employee id is AB-1234.",
        "The code is 12-345.",
        "I filled in the form yesterday.",
        "There are 3 items in the list.",
        "Reference number: 123-45-678.",
        "Case id 123-45-67890 is closed.",
        "I don't have that number on hand.",
    ]
    return _build_samples(rng, templates, [""], n)


def _date_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "01/02/1990",
        "12-31-2001",
        "7.4.1984",
        "10/9/76",
        "02/29/2000",
        "1990-01-02",  # ISO (likely miss)
        "1 Jan 1990",  # text month (likely miss)
    ]
    templates = [
        "My date of birth is {value}.",
        "I was born on {value}.",
        "The appointment is {value}.",
        "It's {value}.",
        "Use {value} for the date.",
        "You asked for my DOB, it's {value}.",
    ]
    return _build_samples(rng, templates, values, n)


def _date_neg(rng: random.Random, n: int) -> List[str]:
    templates = [
        "I was born in April 2020.",
        "The appointment is next Monday.",
        "It happened in 2020.",
        "Spring is my favorite season.",
        "Version 1/2 is deprecated.",
        "Room 10/9 is closed for repairs.",
        "I don't remember the exact date.",
    ]
    return _build_samples(rng, templates, [""], n)


def _address_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "123 Main St",
        "55 Broadway Avenue",
        "9 Pine Road",
        "742 Evergreen Drive",
        "1600 Pennsylvania Ave",
        "221B Baker Street",  # likely miss (Street vs St)
        "500 5th Ave.",  # punctuation variant
    ]
    templates = [
        "My address is {value}.",
        "I live at {value}.",
        "The address is {value}.",
        "It's {value}.",
        "Please update it to {value}.",
        "For mail, use {value}.",
    ]
    return _build_samples(rng, templates, values, n)


def _address_neg(rng: random.Random, n: int) -> List[str]:
    templates = [
        "I live downtown near the park.",
        "The office is on the second floor.",
        "We met on campus last year.",
        "The neighborhood is quiet.",
        "Meet me on Main Street near the cafe.",
        "The road is closed for construction.",
        "I'd rather not share my address.",
    ]
    return _build_samples(rng, templates, [""], n)


def _age_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "I am 90 years old.",
        "I'm 91.",
        "age 102",
        "I am 95 years old.",
        "age is 100",
        "I am 89 years old.",  # boundary (should be negative per rule)
    ]
    templates = [
        "{value}",
        "I said {value}",
        "It's {value}",
        "The answer is {value}",
        "You asked my age, {value}",
    ]
    return _build_samples(rng, templates, values, n)


def _age_neg(rng: random.Random, n: int) -> List[str]:
    values = [
        "I am 45 years old.",
        "I'm 29.",
        "age 67",
        "I am 18 years old.",
        "age 89",
    ]
    templates = [
        "{value}",
        "I said {value}",
        "It's {value}",
        "The answer is {value}",
        "You asked my age, {value}",
    ]
    return _build_samples(rng, templates, values, n)


def _mrn_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "MRN 123456",
        "medical record: A12B34C",
        "patient id# ZXCVBN12",
        "MRN: 99887766",
        "medical record 1A2B3C4D",
        "MRN 12345",  # too short (likely miss)
    ]
    templates = [
        "{value}",
        "It's {value}.",
        "I think it's {value}.",
        "The record says {value}.",
        "You asked for my patient ID, it's {value}.",
    ]
    return _build_samples(rng, templates, values, n)


def _mrn_neg(rng: random.Random, n: int) -> List[str]:
    templates = [
        "The chart is complete.",
        "The record was updated.",
        "The patient is waiting.",
        "The identifier is missing.",
        "The medical record is accurate.",
        "Patient id not provided.",
        "I don't know the ID number.",
    ]
    return _build_samples(rng, templates, [""], n)


def _med_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "taking Xanax",
        "prescribed Zoloft 50 mg",
        "medication Prozac",
        "pills Adderall",
        "taking Ibuprofen 200 mg",
        "prescribed Wellbutrin",
        "taking metformin",  # lowercase (likely miss)
        "prescribed Vitamin D",  # multi-word (likely miss)
        "taking Sertraline 10mg",  # no space (likely miss)
    ]
    templates = [
        "I am {value}.",
        "Currently {value}.",
        "I'm {value}.",
        "I was {value}.",
        "You asked about meds, I'm {value}.",
    ]
    return _build_samples(rng, templates, values, n)


def _med_neg(rng: random.Random, n: int) -> List[str]:
    templates = [
        "I use supplements daily.",
        "My regimen is stable.",
        "The dosage was adjusted.",
        "I follow the plan as discussed.",
        "I stopped drinking coffee.",
        "We discussed nutrition.",
        "I am taking Placebo.",
        "prescribed Rest and hydration.",
        "I don't take any meds.",
    ]
    return _build_samples(rng, templates, [""], n)


def _name_pos(rng: random.Random, n: int) -> List[str]:
    values = [
        "John Doe",
        "Mary Jane",
        "Alice Johnson",
        "Michael Smith",
        "Sarah Connor",
        "Dr. Emily Stone",
        "jean-luc picard",  # lowercase (likely miss)
        "José Alvarez",  # non-ascii (NER variance)
        "A. J. Brown",  # initials
    ]
    templates = [
        "My name is {value}.",
        "I'm {value}.",
        "This is {value}.",
        "{value} called earlier.",
        "They said {value} is my name.",
        "You asked my name, it's {value}.",
    ]
    return _build_samples(rng, templates, values, n)


def _name_neg(rng: random.Random, n: int) -> List[str]:
    templates = [
        "my name is unknown.",
        "a person called earlier.",
        "someone left a note.",
        "a visitor arrived today.",
        "the doctor called earlier.",
        "the patient asked a question.",
        "I'd rather not give my name.",
    ]
    return _build_samples(rng, templates, [""], n)


def _safe_import_sanitizer():
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from backend.agent_core.utils import redact_sensitive
    except Exception as exc:  # pragma: no cover - environment dependency
        pytest.skip(f"PII redaction module unavailable: {exc}")
    return redact_sensitive.sanitize_for_llm


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _evaluate_type(
    sanitize_for_llm, token: str, positives: List[str], negatives: List[str]
) -> dict:
    counts = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    for text in positives:
        redacted = token in sanitize_for_llm(text)
        if redacted:
            counts["TP"] += 1
        else:
            counts["FN"] += 1
    for text in negatives:
        redacted = token in sanitize_for_llm(text)
        if redacted:
            counts["FP"] += 1
        else:
            counts["TN"] += 1
    return counts


def _print_report(results: dict):
    print("\nPII Redaction Evaluation (Evaluator Logic Only)")
    print("Type | TP | FP | TN | FN | TPR | FPR")
    print("-" * 68)
    for name, counts in results.items():
        tp = counts["TP"]
        fp = counts["FP"]
        tn = counts["TN"]
        fn = counts["FN"]
        tpr = _rate(tp, tp + fn)
        fpr = _rate(fp, fp + tn)
        print(
            f"{name} | {tp} | {fp} | {tn} | {fn} | {_format_pct(tpr)} | {_format_pct(fpr)}"
        )


def _print_overall(overall: dict):
    tp = overall["TP"]
    fp = overall["FP"]
    tn = overall["TN"]
    fn = overall["FN"]
    tpr = _rate(tp, tp + fn)
    fpr = _rate(fp, fp + tn)
    print("-" * 68)
    print(
        f"OVERALL | {tp} | {fp} | {tn} | {fn} | {_format_pct(tpr)} | {_format_pct(fpr)}"
    )


def _write_csv(rows: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["type", "label", "passed", "redacted_text", "text"]
        )
        writer.writeheader()
        writer.writerows(rows)


def _specs() -> List[PiiSpec]:
    return [
        PiiSpec("phone", "[PHONE_REDACTED]", _phone_pos, _phone_neg),
        PiiSpec("email", "[EMAIL_REDACTED]", _email_pos, _email_neg),
        PiiSpec("ssn", "[SSN_REDACTED]", _ssn_pos, _ssn_neg),
        PiiSpec("date", "[DATE_REDACTED]", _date_pos, _date_neg),
        PiiSpec("address", "[ADDRESS_REDACTED]", _address_pos, _address_neg),
        PiiSpec("age_over_89", "[AGE>89_REDACTED]", _age_pos, _age_neg),
        PiiSpec("mrn", "[MRN_REDACTED]", _mrn_pos, _mrn_neg),
        PiiSpec("medication", "[MEDICATION_REDACTED]", _med_pos, _med_neg),
        PiiSpec("name", "[NAME_REDACTED]", _name_pos, _name_neg),
    ]


def test_pii_redaction_evaluation():
    sanitize_for_llm = _safe_import_sanitizer()
    rng = random.Random(1337)

    results = {}
    overall = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    csv_rows: List[dict] = []

    for spec in _specs():
        positives = spec.positives(rng, 200)
        negatives = spec.negatives(rng, 200)

        assert len(positives) == 200
        assert len(negatives) == 200

        counts = _evaluate_type(sanitize_for_llm, spec.token, positives, negatives)
        results[spec.name] = counts

        for text in positives:
            redacted_text = sanitize_for_llm(text)
            redacted = spec.token in redacted_text
            csv_rows.append(
                {
                    "type": spec.name,
                    "label": "positive",
                    "passed": str(redacted),
                    "redacted_text": redacted_text,
                    "text": text,
                }
            )
        for text in negatives:
            redacted_text = sanitize_for_llm(text)
            redacted = spec.token in redacted_text
            csv_rows.append(
                {
                    "type": spec.name,
                    "label": "negative",
                    "passed": str(not redacted),
                    "redacted_text": redacted_text,
                    "text": text,
                }
            )

        for key in overall:
            overall[key] += counts[key]

    csv_path = Path(__file__).resolve().parent / "pii_redaction_scenarios.csv"
    _write_csv(csv_rows, csv_path)

    _print_report(results)
    _print_overall(overall)
