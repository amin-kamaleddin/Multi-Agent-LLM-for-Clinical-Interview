from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

MODULES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "L", "M", "MB", "N", "P"]

DEFAULT_POSITIVE_PATTERNS = [
    r"\byes\b",
    r"\byeah\b",
    r"\byep\b",
    r"\btrue\b",
    r"\bdefinitely\b",
    r"\boften\b",
    r"\bfrequently\b",
    r"\bregularly\b",
    r"\bnearly every day\b",
    r"\balmost every day\b",
    r"\bevery day\b",
    r"\bpresent\b",
]

DEFAULT_NEGATIVE_PATTERNS = [
    r"\bno\b",
    r"\bnot really\b",
    r"\bnone\b",
    r"\bnever\b",
    r"\bden(?:y|ies|ied)\b",
    r"\bwithout\b",
    r"\bnot at all\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bdoesn't\b",
    r"\bhaven't\b",
    r"\bhasn't\b",
]

DEFAULT_EXCLUSION_PATTERNS = [
    r"because of (?:my|the) (?:partner|wife|husband|job|work|school|exam|breakup|divorce|bereavement|grief)",
    r"since (?:my|the) (?:partner|wife|husband) (?:passed|died)",
    r"situational",
    r"just stress",
    r"normal reaction",
]

CONTRACTIONS = {
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "cannot",
    "couldn't": "could not",
    "won't": "will not",
    "haven't": "have not",
    "hasn't": "has not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "i'm": "i am",
    "it's": "it is",
    "that's": "that is",
    "there's": "there is",
}

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "once": 1,
    "two": 2,
    "twice": 2,
    "couple": 2,
    "few": 3,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "several": 4,
}


DIAGNOSIS_KEY = {
    **{m: "positive" for m in ["A", "O", "B", "C", "H", "I", "J", "L", "G"]},
    **{m: "lifetime" for m in ["P", "D"]},
}


def normalize_text(text: str) -> str:
    out = (text or "").strip().lower()
    for src, dst in CONTRACTIONS.items():
        out = out.replace(src, dst)
    out = re.sub(r"[^a-z0-9\s\-\.%]", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _compile_patterns(patterns: List[str]) -> List[re.Pattern[str]]:
    compiled: List[re.Pattern[str]] = []
    for raw in patterns:
        # JSON "\b" can be decoded as a backspace char; convert it back to
        # a regex word-boundary token so configs remain robust.
        pattern = (raw or "").replace("\x08", r"\b")
        compiled.append(re.compile(pattern, re.IGNORECASE))
    return compiled


def _any_match(text: str, patterns: List[str]) -> Tuple[bool, str | None]:
    for pat in _compile_patterns(patterns):
        m = pat.search(text)
        if m:
            return True, pat.pattern
    return False, None


def parse_quantity(text: str) -> float | None:
    norm = normalize_text(text)

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-to]+\s*(\d+(?:\.\d+)?)", norm)
    if range_match:
        lo = float(range_match.group(1))
        hi = float(range_match.group(2))
        return (lo + hi) / 2

    unit_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:times?)?\s*(?:per|a)?\s*(day|week|month)", norm)
    if unit_match:
        value = float(unit_match.group(1))
        unit = unit_match.group(2)
        if unit == "day":
            return value * 7
        if unit == "week":
            return value
        if unit == "month":
            return value / 4

    if re.search(r"\bevery day\b|\bdaily\b", norm):
        return 7
    if re.search(r"\bweekly\b|\bonce a week\b", norm):
        return 1
    if re.search(r"\btwice a week\b", norm):
        return 2

    for word, num in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", norm):
            return float(num)

    num_match = re.search(r"\b(\d+(?:\.\d+)?)\b", norm)
    if num_match:
        return float(num_match.group(1))

    return None


def classify_response(text: str, rule: Dict[str, Any]) -> Tuple[str, str]:
    norm = normalize_text(text)
    order = rule.get("evaluation_order", ["positive", "negative", "exclusion"])
    positive = rule.get("positive_patterns", DEFAULT_POSITIVE_PATTERNS)
    negative = rule.get("negative_patterns", DEFAULT_NEGATIVE_PATTERNS)
    exclusion = rule.get("exclusion_patterns", DEFAULT_EXCLUSION_PATTERNS)

    buckets = {
        "positive": positive,
        "negative": negative,
        "exclusion": exclusion,
    }

    for name in order:
        pats = buckets.get(name, [])
        matched, pat = _any_match(norm, pats)
        if not matched:
            continue
        if name == "positive":
            return "YES", f"matched {name}:{pat}"
        return "NO", f"matched {name}:{pat}"

    return "NO", "unresolved->NO"


def _q(responses: Dict[str, str], qid: str) -> bool:
    return responses.get(qid, "NO") == "YES"


def _count_yes(responses: Dict[str, str], qids: List[str]) -> int:
    return sum(1 for qid in qids if _q(responses, qid))


def _organic_ruled_out(responses: Dict[str, str]) -> bool:
    if "O1a" in responses or "O1b" in responses:
        return responses.get("O1a", "NO") == "NO" and responses.get("O1b", "NO") == "NO"
    return True


def _reasoning(checks: List[Tuple[str, bool]]) -> str:
    parts = [f"{name}: {'MET' if met else 'NOT MET'}" for name, met in checks]
    return "; ".join(parts)


def evaluate_module(letter: str, responses: Dict[str, str], quantities: Dict[str, float | None]) -> Dict[str, Dict[str, Any]]:
    letter = letter.upper()
    organic_ok = _organic_ruled_out(responses)

    if letter == "A":
        groups = ["A3a", "A3b", "A3c", "A3d", "A3e", "A3f", "A3g"]
        recent = sum(1 for g in groups if _q(responses, f"{g}_recent") or _q(responses, f"{g}_delusional_recent"))
        past = sum(1 for g in groups if _q(responses, f"{g}_past") or _q(responses, f"{g}_delusional_past"))
        core = any(_q(responses, q) for q in ["A1a", "A1b", "A2a_1", "A2a_2", "A2b"])
        impairment = _q(responses, "A4_recent") or _q(responses, "A4_past")
        positive = (recent >= 5 or past >= 5) and core and impairment and organic_ok
        timeframe = None
        if positive:
            timeframe = "both" if recent >= 5 and past >= 5 else ("recent" if recent >= 5 else "past")
        recurrent = _q(responses, "A5") and organic_ok

        return {
            "positive": {
                "diagnosis": positive,
                "reasoning": _reasoning([
                    ("recent symptom groups>=5", recent >= 5),
                    ("past symptom groups>=5", past >= 5),
                    ("core symptom", core),
                    ("functional impairment", impairment),
                    ("organic rule-out", organic_ok),
                ]),
                "timeFrame": timeframe,
            },
            "recurrent": {
                "diagnosis": recurrent,
                "reasoning": _reasoning([
                    ("A5 coded YES", _q(responses, "A5")),
                    ("organic rule-out", organic_ok),
                ]),
            },
        }

    if letter == "B":
        suicide_qs = [q for q in responses if re.match(r"^B(?!1$)\d", q)]
        positive_any = _count_yes(responses, suicide_qs) >= 1
        return {
            "current": {
                "diagnosis": positive_any,
                "reasoning": _reasoning([
                    ("at least one suicidality indicator", positive_any),
                    ("organic rule-out", organic_ok),
                ]),
            }
        }

    if letter == "C":
        c3_current = _count_yes(responses, [f"C3{c}_current" for c in "abcdefg"])
        c3_past = _count_yes(responses, [f"C3{c}_past" for c in "abcdefg"])
        c1b_yes = _q(responses, "C1b")
        threshold = 3 if c1b_yes else 4
        c3f_present = _q(responses, "C3f_current") or _q(responses, "C3f_past")
        c4_valid = any(q in responses for q in ["C4_current", "C4_past"])
        impairment = _q(responses, "C7_current") or _q(responses, "C7_past")
        duration_or_extra = _q(responses, "C4C") or _q(responses, "C5_current") or _q(responses, "C5_past") or _q(responses, "C6_current") or _q(responses, "C6_past")
        symptom_ok = max(c3_current, c3_past) >= threshold and c3f_present
        positive = symptom_ok and c4_valid and impairment and duration_or_extra and organic_ok
        recurrent = c3_past >= threshold and c3f_present
        return {
            "positive": {
                "diagnosis": positive,
                "reasoning": _reasoning([
                    (f"C3 count>={threshold}", max(c3_current, c3_past) >= threshold),
                    ("C3f present", c3f_present),
                    ("C4 valid quantity present", c4_valid),
                    ("C7 impairment", impairment),
                    ("duration/extra criterion", duration_or_extra),
                    ("organic rule-out", organic_ok),
                ]),
            },
            "recurrent": {
                "diagnosis": recurrent,
                "reasoning": _reasoning([
                    (f"past C3 count>={threshold}", c3_past >= threshold),
                    ("past C3f present", _q(responses, "C3f_past")),
                ]),
            },
        }

    if letter == "D":
        d4_count = _count_yes(responses, [f"D4{c}" for c in "abcdefghijklm"])
        lifetime = _q(responses, "D3") and d4_count >= 4 and organic_ok
        return {
            "lifetime": {
                "diagnosis": lifetime,
                "reasoning": _reasoning([
                    ("D3 coded YES", _q(responses, "D3")),
                    ("D4 symptoms >= 4", d4_count >= 4),
                    ("organic rule-out", organic_ok),
                ]),
            }
        }

    if letter == "E":
        current = _q(responses, "E6")
        return {"current": {"diagnosis": current, "reasoning": _reasoning([("E6 coded YES", current)])}}

    if letter == "F":
        current = _q(responses, "F6") and organic_ok
        fear_restricted = None
        if current:
            broad_social = any(_q(responses, q) for q in ["F1", "F2", "F3", "F4", "F5"])
            fear_restricted = not broad_social
        payload = {"diagnosis": current, "reasoning": _reasoning([("F6 coded YES", _q(responses, "F6")), ("organic rule-out", organic_ok)])}
        if fear_restricted is not None:
            payload["fearRestricted"] = fear_restricted
        return {"current": payload}

    if letter == "G":
        obsessions = _q(responses, "G1a") and _q(responses, "G1b") and _q(responses, "G2")
        compulsions = _q(responses, "G3a") and _q(responses, "G3b")
        current = _q(responses, "G4") and (obsessions or compulsions) and organic_ok
        positive_payload = {
            "diagnosis": current,
            "reasoning": _reasoning([
                ("G4 coded YES", _q(responses, "G4")),
                ("obsession/compulsion pattern", obsessions or compulsions),
                ("organic rule-out", organic_ok),
            ]),
        }
        if current:
            positive_payload["insight"] = None
            positive_payload["ticRelated"] = None
        return {"positive": positive_payload, "recurrent": {"diagnosis": False, "reasoning": "recurrent criterion not configured in module rules"}}

    if letter == "H":
        h3 = _count_yes(responses, ["H3a", "H3b"])
        h4 = _count_yes(responses, [f"H4{c}" for c in "abcdefg"])
        h5 = _count_yes(responses, [f"H5{c}" for c in "abcdef"])
        positive = _q(responses, "H7") and h3 >= 1 and h4 >= 2 and h5 >= 2 and organic_ok
        return {
            "positive": {
                "diagnosis": positive,
                "reasoning": _reasoning([
                    ("H7 coded YES", _q(responses, "H7")),
                    ("H3 cluster >=1", h3 >= 1),
                    ("H4 cluster >=2", h4 >= 2),
                    ("H5 cluster >=2", h5 >= 2),
                    ("organic rule-out", organic_ok),
                ]),
            },
            "recurrent": {"diagnosis": False, "reasoning": "recurrent criterion not configured in module rules"},
        }

    if letter == "I":
        i_count = _count_yes(responses, [f"I2{c}" for c in "abcdefghij"] + ["I2k1", "I2k2"])
        positive = i_count >= 2
        return {"positive": {"diagnosis": positive, "reasoning": _reasoning([("I2 symptoms >=2", positive), ("I2 yes count", i_count >= 2)])}}

    if letter == "J":
        j_count = _count_yes(responses, [f"J2{c}" for c in "abcdefghij"] + ["J2k1", "J2k2"])
        positive = j_count >= 2
        return {
            "positive": {"diagnosis": positive, "reasoning": _reasoning([("J2 symptoms >=2", positive)])},
            "recurrent": {"diagnosis": positive, "reasoning": "proxy recurrent flag from persistent symptom burden"},
        }

    if letter == "L":
        l4 = _count_yes(responses, ["L4a", "L4b", "L4c"])
        positive = l4 >= 1
        return {"positive": {"diagnosis": positive, "reasoning": _reasoning([("any L4 coded YES", positive)])}}

    if letter == "M":
        current = _q(responses, "M5") and _q(responses, "M7")
        recurrent = current and (_q(responses, "M4") or (_q(responses, "M4a") if "M4a" in responses else False))
        return {
            "current": {"diagnosis": current, "reasoning": _reasoning([("M5 coded YES", _q(responses, "M5")), ("M7 coded YES", _q(responses, "M7"))])},
            "recurrent": {"diagnosis": recurrent, "reasoning": _reasoning([("current diagnosis true", current), ("binge frequency marker present", recurrent)])},
        }

    if letter == "MB":
        mb6 = _count_yes(responses, [f"MB6{c}" for c in "abcde"])
        current = all(_q(responses, q) for q in ["MB1", "MB2", "MB3", "MB7"]) and not _q(responses, "MB4") and mb6 >= 3
        return {
            "current": {
                "diagnosis": current,
                "reasoning": _reasoning([
                    ("MB1 yes", _q(responses, "MB1")),
                    ("MB2 yes", _q(responses, "MB2")),
                    ("MB3 yes", _q(responses, "MB3")),
                    ("MB4 no", not _q(responses, "MB4")),
                    ("MB6 cluster >=3", mb6 >= 3),
                    ("MB7 yes", _q(responses, "MB7")),
                ]),
            }
        }

    if letter == "N":
        n3 = _count_yes(responses, [f"N3{c}" for c in "abcdef"])
        current = _q(responses, "N4") and n3 >= 3 and organic_ok
        return {
            "current": {
                "diagnosis": current,
                "reasoning": _reasoning([
                    ("N4 yes", _q(responses, "N4")),
                    ("N3 symptom groups>=3", n3 >= 3),
                    ("organic rule-out", organic_ok),
                ]),
            }
        }

    if letter == "P":
        p1 = _count_yes(responses, [f"P1{c}" for c in "abcdef"])
        p2 = _count_yes(responses, [f"P2{c}" for c in "abcdefg"])
        lifetime = p1 >= 2 and p2 >= 3
        return {
            "lifetime": {
                "diagnosis": lifetime,
                "reasoning": _reasoning([
                    ("P1 cluster >=2", p1 >= 2),
                    ("P2 cluster >=3", p2 >= 3),
                ]),
            }
        }

    raise ValueError(f"Unsupported module: {letter}")


def load_rule_config(letter: str, base_dir: str = "./baselines/rules") -> Dict[str, Any]:
    path = Path(base_dir) / f"module_{letter.upper()}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_rows(rows: List[Dict[str, str]], config: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, float | None], Dict[str, str]]:
    question_rules = config.get("question_rules", {})
    module_defaults = {
        "evaluation_order": config.get("evaluation_order", ["positive", "negative", "exclusion"]),
        "positive_patterns": config.get("positive_patterns", DEFAULT_POSITIVE_PATTERNS),
        "negative_patterns": config.get("negative_patterns", DEFAULT_NEGATIVE_PATTERNS),
        "exclusion_patterns": config.get("exclusion_patterns", DEFAULT_EXCLUSION_PATTERNS),
    }
    responses: Dict[str, str] = {}
    quantities: Dict[str, float | None] = {}
    reasons: Dict[str, str] = {}

    for row in rows:
        qid = (row.get("question_id") or "").strip()
        text = row.get("patient_response", "")
        if not qid or not text:
            continue

        q_rule = {**module_defaults, **question_rules.get(qid, {})}
        label, reason = classify_response(text, q_rule)
        responses[qid] = label
        reasons[qid] = reason

        qty = parse_quantity(text)
        quantities[qid] = qty

        min_weekly = q_rule.get("min_weekly")
        if min_weekly is not None:
            if qty is not None and qty >= float(min_weekly):
                responses[qid] = "YES"
                reasons[qid] = f"quantity {qty} >= {min_weekly}"
            elif qty is not None and qty < float(min_weekly):
                responses[qid] = "NO"
                reasons[qid] = f"quantity {qty} < {min_weekly}"

    return responses, quantities, reasons


def parse_transcript_csv(csv_path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def run_rule_diagnosis(letter: str, csv_path: str, rules_dir: str = "./baselines/rules") -> Dict[str, Any]:
    config = load_rule_config(letter, rules_dir)
    rows = parse_transcript_csv(csv_path)
    responses, quantities, reasons = classify_rows(rows, config)
    result = evaluate_module(letter, responses, quantities)

    # normalize optional fields (omit if null)
    normalized: Dict[str, Dict[str, Any]] = {}
    for key, val in result.items():
        group: Dict[str, Any] = {
            "diagnosis": bool(val.get("diagnosis", False)),
            "reasoning": str(val.get("reasoning", "")),
        }
        for opt in ("timeFrame", "insight", "ticRelated", "fearRestricted"):
            if opt in val and val[opt] is not None:
                group[opt] = val[opt]
        normalized[key] = group
    return normalized


def prediction_from_result(letter: str, result: Dict[str, Any]) -> str:
    diag_key = DIAGNOSIS_KEY.get(letter.upper(), "current")
    group = result.get(diag_key, {})
    if not group:
        for alt in ("current", "positive", "lifetime"):
            if alt != diag_key and result.get(alt):
                group = result[alt]
                break
    pred = group.get("diagnosis", False)
    return "true" if pred is True else "false"
