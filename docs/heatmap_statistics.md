# Heatmap Statistics: Mean and Confidence Interval

This document describes how the values shown in the bootstrap heatmap figures
are computed.

Scripts involved:

- `run_patient_agent_bootstrap.py` — computes and writes `evaluation_results.csv`
- `plot_bootstrap_evaluation_table.py` — reads that CSV and renders the heatmaps

---

## 1. Input Data

The raw input is a combined predictions CSV with one row per patient simulation.
Each row contains:

- `Module` — which clinical module was evaluated
- `label` — ground-truth binary outcome (`0` or `1`)
- `prediction` — system binary prediction (`0` or `1`)
- `Expected Symptom Direction` — condition column for the *Symptom Direction* group
- `Tier of Symptom Disclosure` — condition column for the *Symptom Disclosure* group
- `Emotion/Tone Tier` — condition column for the *Emotional Tone* group

The data is stratified into cells, where each cell is one unique combination of:

$$
(\text{module},\ \text{group},\ \text{condition})
$$

For example: *(Module A, Symptom Direction, Positive Symptom Presentation)*.

---

## 2. Classification Metrics

Within each cell, the following binary classification metrics are computed from
counts of true positives (TP), true negatives (TN), false positives (FP), and
false negatives (FN):

$$
\text{Accuracy} = \frac{TP + TN}{TP + TN + FP + FN}
$$

$$
\text{Sensitivity} = \frac{TP}{TP + FN}
$$

$$
\text{Specificity} = \frac{TN}{TN + FP}
$$

$$
\text{Precision} = \frac{TP}{TP + FP}
$$

$$
F_1 = \frac{2 \cdot \text{Precision} \cdot \text{Sensitivity}}{\text{Precision} + \text{Sensitivity}}
$$

$$
F_2 = \frac{5 \cdot \text{Precision} \cdot \text{Sensitivity}}{4 \cdot \text{Precision} + \text{Sensitivity}}
$$

All metrics that have a zero denominator are set to `0.0`.

All metric values are multiplied by 100 to express them as percentages before
being stored in the CSV and displayed in figures.

---

## 3. Point Estimate (Mean)

The **point estimate** for each cell is the **plug-in estimator**: the metric
computed once on all original observations in that cell (no resampling).

Let $n$ be the number of predictions in a cell, with true labels
$y_1, \dots, y_n$ and predicted labels $\hat{y}_1, \dots, \hat{y}_n$.

The plug-in estimate is:

$$
\hat{\theta} = f(y_1, \dots, y_n,\ \hat{y}_1, \dots, \hat{y}_n)
$$

where $f$ is any of the metric formulas above applied to the full cell.

This is what `evaluation_results.csv` stores as `{metric}_mean`.

---

## 4. Bootstrap Confidence Interval

The 95% confidence interval is computed using the **empirical percentile
bootstrap** method with $B = 10{,}000$ resampling iterations per cell.

### Procedure

For each bootstrap iteration $b = 1, \dots, B$:

1. Draw $n$ indices uniformly at random **with replacement** from
   $\{1, \dots, n\}$.
2. Compute the metric on the resampled rows:

$$
\hat{\theta}^{*b} = f\!\left(y_{i_1}, \dots, y_{i_n},\ \hat{y}_{i_1}, \dots, \hat{y}_{i_n}\right)
$$

This produces a bootstrap distribution $\hat{\theta}^{*1}, \dots, \hat{\theta}^{*B}$.

### CI Bounds

The 95% confidence interval bounds are the 2.5th and 97.5th percentiles of the
bootstrap distribution (all values expressed in %):

$$
\text{CI}_{\text{low}} = \hat{\theta}^{*}_{(0.025)}
\qquad
\text{CI}_{\text{high}} = \hat{\theta}^{*}_{(0.975)}
$$

These are stored in `evaluation_results.csv` as:

- `{metric}_ci_low`
- `{metric}_ci_high`

### Half-width

The scalar half-width stored as `{metric}_ci` is:

$$
\text{CI}_{\text{half}} = \frac{\text{CI}_{\text{high}} - \text{CI}_{\text{low}}}{2}
$$

This is an approximate half-width of the 95% interval. It is **not** symmetric
around the point estimate — the bounds are the actual percentiles of the
bootstrap distribution.

### Random Seed

Each cell uses a deterministic seed derived from a base seed (default `42`) plus
a monotonically increasing counter, so results are fully reproducible:

```python
rng = np.random.default_rng(seed + cell_counter)
```

---

## 5. Heatmap Cell Annotation

`plot_bootstrap_evaluation_table.py` reads `evaluation_results.csv` and
displays each cell as:

```
66.7
±5.8
```

where:

- `66.7` is `{metric}_mean` (the plug-in point estimate, in %)
- `5.8` is the CI half-width computed as:

$$
\text{CI}_{\text{half}} = \frac{\text{CI}_{\text{high}} - \text{CI}_{\text{low}}}{2}
$$

This is derived directly in `build_matrices()`:

```python
ci_pivot = (ci_high_pivot - ci_low_pivot) / 2
```

---

## 6. Mean Row and Mean Column

Each heatmap includes a **Mean** column (rightmost) and a **Mean** row (bottom),
which summarise across conditions and modules respectively.

### Mean Column

For each module row, the Mean column value is the arithmetic mean of the
non-missing cell values across all conditions:

$$
\bar{\theta}_{\text{module}} = \frac{1}{C}\sum_{c=1}^{C} \hat{\theta}_{(\text{module},\, c)}
$$

where $C$ is the number of non-missing conditions for that module.

The CI half-width shown in the Mean column is the arithmetic mean of the
per-condition CI half-widths:

$$
\overline{\text{CI}}_{\text{module}} = \frac{1}{C}\sum_{c=1}^{C} \text{CI}_{\text{half},(\text{module},\,c)}
$$

### Mean Row

For each condition column, the Mean row value is the arithmetic mean of the
non-missing module values for that condition:

$$
\bar{\theta}_{\text{condition}} = \frac{1}{M}\sum_{m=1}^{M} \hat{\theta}_{(m,\,\text{condition})}
$$

The CI half-width shown in the Mean row uses the same arithmetic mean of
per-module CI half-widths.

The bottom-right cell (Mean row, Mean column) is the mean of all Mean-column
values, i.e., the overall average across all cells.

These aggregations are computed by `build_matrices()`:

```python
mean_pivot["Mean"] = mean_pivot.mean(axis=1, skipna=True)
ci_pivot["Mean"]   = ci_pivot.mean(axis=1, skipna=True)

mean_row      = mean_pivot.mean(axis=0, skipna=True)
ci_row        = ci_pivot.mean(axis=0, skipna=True)
```

---

## 7. Heatmap Colour Scale

The colour scale runs from `50.0` to `100.0` (percentage points) using a
custom Blues colormap. Cells with values below 50 are clipped to the lowest
colour.

---

## 8. Edge Cases

| Situation | Behaviour |
|---|---|
| Cell has zero observations | `{metric}_mean`, `{metric}_ci_low`, `{metric}_ci_high` are stored as `None`; displayed as `N/A` |
| Metric denominator is zero | Metric set to `0.0` for that bootstrap sample |
| Mean or CI is `NaN` in pivot | Displayed as `N/A` in annotation |
