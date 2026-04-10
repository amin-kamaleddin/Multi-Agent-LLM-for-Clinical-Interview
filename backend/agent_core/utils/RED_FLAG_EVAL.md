# Red Flag Detection — Dataset Simulation & Classification

## Overview

The red-flag module detects suicidal ideation and self-harm signals in free-text
patient messages. This document describes how the evaluation dataset is generated
(`generate_redflag_dataset.py`) and how the classifier works (`red_flag.py`).

---

## 1. Dataset Simulation (`generate_redflag_dataset.py`)

### Structure

The dataset contains **2000 rows** organised into four quadrants:

| Quadrant | Rows | Positives (label=1) | Negatives (label=0) |
|---|---|---|---|
| explicit / active | 500 | 250 | 250 |
| explicit / passive | 500 | 250 | 250 |
| implicit / active | 500 | 250 | 250 |
| implicit / passive | 500 | 250 | 250 |

CSV columns: `data`, `label`, `expression_type`, `ideation_type`

### Taxonomy

**Expression type**
- `explicit` — suicidal intent or self-harm is named directly (suicide, kill myself,
  end my life, want to die, overdose, etc.)
- `implicit` — the same underlying crisis expressed indirectly through metaphor,
  vague phrasing, coded language, or emotional signals — without naming it.

**Ideation type**
- `active` — a plan, method, time, location, or concrete intent is present.
- `passive` — a general wish to die or not exist, without a specific plan or method.

### Generation model

- Model: `gpt-4o`, temperature `1.0`
- Batch size: 25 sentences per API call
- Output parsed as a JSON array of strings

### Positive examples (label=1)

A single system prompt covers all four quadrants. Diversity requirements:
- Vary speaker demographics (teens, adults, elderly, genders)
- Vary contexts (text messages, therapy notes, diary entries, clinical interviews)
- Vary triggers (relationship loss, financial stress, chronic pain, isolation, grief)
- Vary tone (colloquial, clinical, poetic, fragmented, matter-of-fact)
- Length: 6–30 words

### Negative examples (label=0)

Each quadrant uses a dedicated negative prompt. Negatives are intentionally hard —
they superficially resemble crisis language but have a clear non-suicidal reading.

#### explicit / active negatives
Patterns used:
- **Figurative idioms** in non-distress contexts ("my trainer is killing me with these sprints")
- **Detached news/factual reporting** of past events ("the coroner confirmed the method")
- **Professional/clinical knowledge** — speaker's role makes it academic ("as a toxicologist I study lethal dose thresholds")

Strictly avoided: first-person method language even with hedging; speaker personally acquiring means.

#### explicit / passive negatives
Patterns used:
- **Hyperbole about positive or trivially negative experiences** ("I could die of happiness", "to die for", "die of boredom")
- **Exhaustion hyperbole** about workload ("this commute will be the death of me")
- **Escape/off-grid wish** — wanting rest, not death ("I want to vanish for a month and go off-grid")
- **Academic literary analysis** discussing a character's death wish, not the speaker's own

Strictly avoided: genuine personal weariness of life; sentences a clinician could plausibly treat as a real disclosure.

#### implicit / active negatives
Patterns used:
- **Research/creative writing** with clear positive/professional framing ("mapping bridge networks for an urban planning dissertation")
- **Outdoor/adventure activities** near hazardous settings with positive tone ("love the cliff trail at sunrise")
- **Life-change/exit planning** — starting over, not ending life ("researching what it would take to move abroad")
- **Professional clinical observation** — documenting a patient, not themselves

Strictly avoided: first-person proximity to lethal means without strong positive/professional framing; "strange allure" near hazardous locations.

#### implicit / passive negatives
Patterns used:
- **Burnout and energy depletion** ("running on empty", "absolutely fried")
- **Cognitive fog / dissociation from overwork** ("going through the motions, nothing feels real")
- **Escape fantasy** — wanting solitude, not death ("I just want to disappear from all the noise")
- **Mild professional burden language** ("I feel like dead weight on the team")
- **Existential wondering** — questioning purpose, not wishing to die ("I wonder what all of this is for")
- **Social invisibility** in a relational sense ("I feel invisible in this relationship")

Strictly avoided: explicit death wishes; "no reason to go on"; "tired of existing"; void/abyss/non-existence references.

### Running generation

```bash
# from backend/agent_core/
python utils/generate_redflag_dataset.py

# custom output path
python utils/generate_redflag_dataset.py --output path/to/output.csv
```

---

## 2. Classification (`red_flag.py`)

### Model

- Model: `gpt-4o-mini`, temperature `0`
- Structured output: `{"answer": "YES|NO", "explanation": "<20 words"}`
- Parsed via Pydantic (`RedFlagResponse`); defaults to NO on parse failure

### What gets flagged (RED FLAG = YES)

**Explicit signals**
- Direct naming of suicide, self-harm, wanting to die, ending one's life
- Coded method references — specific lethal means at a specific time even without
  naming suicide (e.g. "the hose in the garage is ready", "I'm checking train
  schedules for tonight", "each letter I wrote is stamped and sealed")

**Implicit passive ideation**
- Passive death wish — longing for non-existence, welcoming silence/darkness/ending
- Wanting mental/emotional cessation permanently (distinct from wanting a break)
- Ghost/fading/shadow imagery expressing feeling already non-existent
- Burden/invisibility — absence would be unnoticed or beneficial
- Exhaustion from existing — profound tiredness of being alive
- Feeling trapped with no future ("I see no way out")

**Implicit active ideation**
- Behavioural proximity to means (repeated visits, calculating depth/height)
- Cryptic planning language (marking a private date, feeling peace as planning progresses)
- Writing unsent farewell communications
- Vague research into methods framed as seeking peace/rest
- Giving away possessions or settling affairs without explanation

### What is NOT flagged (carve-outs)

| Category | Examples |
|---|---|
| Ordinary stress/sadness | Frustration, job dissatisfaction, feeling stuck in a situation |
| Figurative idioms | "murdered my knees", "killing it at the gym", "I died laughing", "to die for" |
| Clinical/forensic documentation | "my patient had been researching methods", "the coroner confirmed the method" |
| Academic/literary analysis | "Hamlet's soliloquy expresses passive ideation", "Victorian poets romanticised death as a trope" |
| Creative writing with authorial distance | "plotting the villain's escape route — love this part", "my mystery novel research" |

> **Safety bias**: when in doubt about implicit signals with no clear carve-out, the classifier errs on the side of flagging (favours recall over precision).

### Running evaluation

```bash
# from backend/agent_core/
python utils/red_flag.py \
  --input  utils/redflag_dataset.csv \
  --output utils/redflag_dataset_with_predictions.csv
```

Outputs:
- `redflag_dataset_with_predictions.csv` — row-level predictions + explanations (crash-safe, written incrementally)
- `redflag_dataset_with_predictions_summary_metrics.csv` — per-subset metrics

### Metrics reported

Accuracy, Precision, Recall, Specificity, F1, F2, FP count, FN count — broken down for:
- Overall (n=2000)
- `expression_type=explicit` (n=1000)
- `expression_type=implicit` (n=1000)
- `ideation_type=active` (n=1000)
- `ideation_type=passive` (n=1000)

### Latest results (hard-negative dataset)

| Subset | Accuracy | Precision | Recall | FP | FN |
|---|---|---|---|---|---|
| Overall | 93.9% | 0.936 | 0.942 | 64 | 58 |
| explicit | 98.4% | 0.969 | 1.000 | 16 | 0 |
| implicit | 89.4% | 0.902 | 0.884 | 48 | 58 |
| active | 97.6% | 0.996 | 0.956 | 2 | 22 |
| passive | 90.2% | 0.882 | 0.928 | 62 | 36 |
