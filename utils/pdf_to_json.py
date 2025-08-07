#!/usr/bin/env python3
"""
robust_mini_extract.py   →   auto_mini.json
--------------------------------------------------
* works even when OCR wraps the question over many lines
* does not care if YES/NO columns are missing or scrambled
* skips the legal / title pages automatically
"""

import re, json, sys, pathlib, pdfplumber

PDF   = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "MINI-Standard.pdf")
OUT   = PDF.with_name("auto_mini.json")

# ---------- helpers ----------
MOD_RE  = re.compile(r"^([A-Z])\.\s+([A-Z][A-Za-z ].+)$")  # A. MAJOR DEPRESSIVE …
Q_START = re.compile(r"^([A-Z])(\d+)([a-z]?)\b")          # A1  /  B12b  /  C3
GARBAGE = {"dethgirypoc", "lagelli", "yna", "tsop", "siht", "FDP"}  # trash tokens
GARB_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in GARBAGE) + r")\b",
                     re.IGNORECASE)

def clean(txt: str) -> str:
    txt = GARB_RE.sub(" ", txt)
    return re.sub(r"\s+", " ", txt).strip(" .")

# ---------- extract ----------
out, module = [], None
qid, qtext  = None, []

with pdfplumber.open(PDF) as pdf:
    for page in pdf.pages:
        for raw in (page.extract_text() or "").splitlines():
            line = raw.strip()
            if not line:
                continue

            # Skip cover until first real module
            if module is None:
                m0 = MOD_RE.match(line)
                if m0:
                    module = m0.group(2).title()
                continue

            # New module header
            if m_mod := MOD_RE.match(line):
                module = m_mod.group(2).title()
                continue

            # Question start?
            m_q = Q_START.match(line)
            if m_q:
                # flush previous question
                if qid:
                    out.append({
                        "id": qid,
                        "module": module,
                        "text": clean(" ".join(qtext)),
                        "response": "yes_no"
                    })
                letter, num, sub = m_q.groups()
                qid   = f"{letter}{num}{sub}"
                # everything after the id on this same line is part of the text
                qtext = [clean(line[m_q.end():].lstrip())]
            else:
                # continuation of current question
                if qid:
                    qtext.append(clean(line))

    # flush last question
    if qid:
        out.append({
            "id": qid,
            "module": module,
            "text": clean(" ".join(qtext)),
            "response": "yes_no"
        })

# ---------- save ----------
OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(f"Extracted {len(out)} questions  →  {OUT}")
assert len(out) > 250, "Still too few – check PDF or add more garbage tokens"