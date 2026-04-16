# Rule-Based Diagnostic Baseline

This baseline is a deterministic, non-LLM comparator for the MINI multi-agent system and the single-LLM baseline.

It reads full interview transcripts, applies keyword/pattern rules to patient answers, and outputs per-patient diagnosis JSON plus module-level prediction CSVs in the same benchmark style as existing baselines.

## What It Does

- Uses transcript CSVs from:
  - `patient_agent_results/patients_with_system_prompts_module_{LETTER}`
- Uses raw `patient_response` text only for symptom detection.
- Uses `question_id` only for mapping responses to rule logic.
- Produces:
  - `baselines_rule_based/module_{LETTER}/diagnosis_{id}.json`
  - `baselines_rule_based/module_{LETTER}/predictions_rule_based.csv`
- Supports modules:
  - `A/B/C/D/E/F/G/H/I/J/L/M/MB/N/P`
- Excludes modules:
  - `K/O` (by design for v1)

## Key Files

- Engine:
  - `tests/rule_based_engine.py`
- Baseline runner:
  - `tests/run_rule_based_baseline.py`
- Baseline evaluator:
  - `tests/eval_rule_based_baseline.py`
- Rule configs:
  - `baselines/rules/module_{LETTER}.json`
- Unit + golden tests:
  - `tests/test_rule_based_engine.py`

## How It Works

### 1) Response normalization

For each patient answer, the engine:

- lowercases text
- expands contractions (`don't -> do not`)
- removes punctuation/noise
- compresses whitespace

### 2) Ordered rule matching

Per question, it applies pattern buckets in order:

1. `positive_patterns`
2. `negative_patterns`
3. `exclusion_patterns`

First match wins. If no match is found, it defaults to `NO` (conservative policy).

### 3) Quantity parsing

The engine parses:

- digits and ranges (`2`, `4-7`)
- number words (`one`, `couple`, `few`, etc.)
- frequency phrases (`daily`, `once a week`, `2 times per week`)

Question-level thresholds can be configured in module rule files (for example `min_weekly`).

### 4) Module criteria aggregation

After question-level YES/NO labels are inferred, module-specific deterministic logic computes diagnosis groups (`positive`, `current`, `lifetime`, `recurrent`) and structured reasoning.

Optional fields (`timeFrame`, `insight`, `ticRelated`, `fearRestricted`) are emitted only when available and non-null.

## Running

From repo root:

### Generate rule-based predictions for one module

```bash
python3 tests/run_rule_based_baseline.py --module A --force
```

### Generate for all supported modules

```bash
for m in A B C D E F G H I J L M MB N P; do
  python3 tests/run_rule_based_baseline.py --module "$m" --force
done
```

### Evaluate one module vs multi-agent output

```bash
python3 tests/eval_rule_based_baseline.py --module A --reset-combined
```

### Evaluate all modules (append combined file)

```bash
python3 tests/eval_rule_based_baseline.py --module A --reset-combined
for m in B C D E F G H I J L M MB N P; do
  python3 tests/eval_rule_based_baseline.py --module "$m"
done
```

## Output Format

### Per-patient JSON

Each `diagnosis_{id}.json` contains one or more diagnosis groups, for example:

```json
{
  "positive": {
    "diagnosis": true,
    "reasoning": "...",
    "timeFrame": "recent"
  },
  "recurrent": {
    "diagnosis": false,
    "reasoning": "..."
  }
}
```

### Prediction CSV

`predictions_rule_based.csv` uses:

- `id`
- `label` (`true`/`false` from patient metadata)
- `prediction` (`true`/`false` from rule baseline)

## Dependencies

- Python 3.10+
- `pandas`, `numpy`, `scipy`, `scikit-learn` for evaluation script
- `pytest` for tests

Install minimum extras if needed:

```bash
python3 -m pip install pandas numpy scipy scikit-learn pytest
```

## Testing

```bash
python3 -m pytest -q tests/test_rule_based_engine.py
```

This test file includes:

- normalization/negation checks
- quantity parsing checks
- criteria combinator checks (including timeframe logic)
- module-level golden coverage across all supported modules

## Notes and Limitations

- This is intentionally conservative and deterministic, not a clinical-grade diagnostic system.
- Ambiguous text defaults to `NO`, which may reduce recall.
- Pattern quality controls performance; tune `baselines/rules/module_{LETTER}.json` per module for better accuracy.
- The evaluator compares against the existing multi-agent prediction CSVs and appends combined results to:
  - `baselines/predictions_rule_based_combined.csv`
