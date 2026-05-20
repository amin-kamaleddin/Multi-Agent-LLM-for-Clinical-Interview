# Evaluation Statistics for Overall Comparison

This note documents only the statistics used in:

- `plot_overall_metric_comparison.py`
- `hypothesis_testing.py`

It does not describe the bootstrap heatmap scripts or the baseline evaluation scripts.

## Data Used by Both Scripts

Both scripts load three evaluation CSV files:

- `patient_agent_results/evaluation_results.csv`
- `baselines/evaluation_results_single_agent.csv`
- `baselines/evaluation_results_rule_based.csv`

They align the three systems by an inner join on:

- `module`
- `group`
- `condition`

Formally, one matched observation is one shared `(module, group, condition)` row that exists in all three files.

### Exact Input Columns

From each CSV, the scripts keep only:

- `module`
- `group`
- `condition`
- `accuracy_mean`
- `sensitivity_mean`
- `specificity_mean`
- `f1_mean`
- `f2_mean`

Then each script renames the metric columns by system. For example:

- `accuracy_mean` -> `accuracy_rule`
- `accuracy_mean` -> `accuracy_single`
- `accuracy_mean` -> `accuracy_multi`

and likewise for the other metrics.

So the "raw data" used by these two scripts is not patient-level data. It is the matched row-level metric values already stored in the three evaluation CSVs.

For each matched row $i$, each system contributes one metric value:

$$
x_i^{(\text{rule})}, \quad x_i^{(\text{single})}, \quad x_i^{(\text{multi})}
$$

for each metric in:

- Accuracy
- Sensitivity
- Specificity
- F1
- F2

The scripts therefore compare systems on matched samples, not on independently aggregated datasets.

## 1. Overall Metric Plot

`plot_overall_metric_comparison.py` produces one panel per metric and plots:

- Rule-Based mean +/- 95% CI
- Single-Agent mean +/- 95% CI
- Multi-Agent mean +/- 95% CI

### Exact Construction of the Values Used for Mean and SE

For one metric and one system, the script constructs the input vector exactly as follows.

1. Read the system-specific metric column from the merged table.

Example for Multi-Agent Accuracy: `merged["accuracy_multi"]`

2. Drop missing values.

3. Convert the remaining values to a float NumPy array:

```python
values = values.dropna().to_numpy(dtype=float)
```

If the surviving matched row values are:

$$
x_1, x_2, \dots, x_n
$$

then those are the exact numbers used to compute the mean, standard deviation, standard error, and confidence interval.

Each $x_i$ is one matched `(module, group, condition)` row's metric value for that system.

### Exact Formulas Used

Let the non-missing matched row values for one metric and one system be:

$$
x_1, x_2, \dots, x_n
$$

where:

$$
x_i = \text{the metric value from matched row } i
$$

Then the script computes:

Mean:

$$
\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i
$$

Sample variance:

$$
s^2 = \frac{1}{n-1}\sum_{i=1}^{n}(x_i-\bar{x})^2
$$

Sample standard deviation:

$$
s = \sqrt{\frac{1}{n-1}\sum_{i=1}^{n}(x_i-\bar{x})^2}
$$

Standard error:

$$
SE = \frac{s}{\sqrt{n}}
$$

Substituting the standard deviation formula into the SE gives:

$$
SE =
\sqrt{
\frac{1}{n(n-1)}
\sum_{i=1}^{n}(x_i-\bar{x})^2
}
$$

This is mathematically equivalent to the implementation:

```python
mean = values.mean()
std = values.std(ddof=1)
se = std / np.sqrt(n)
```

### Mean

For one metric and one system, the plotted mean is the arithmetic mean of those matched row values:

$$
\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i
$$

Written out directly:

$$
\bar{x} = \frac{x_1 + x_2 + \cdots + x_n}{n}
$$

### Sample Standard Deviation

The script uses the sample standard deviation with `ddof=1`:

$$
s = \sqrt{\frac{1}{n-1}\sum_{i=1}^{n}(x_i-\bar{x})^2}
$$

### Standard Error

The standard error is then:

$$
SE = \frac{s}{\sqrt{n}}
$$

Substituting the sample standard deviation formula:

$$
SE = \frac{\sqrt{\frac{1}{n-1}\sum_{i=1}^{n}(x_i-\bar{x})^2}}{\sqrt{n}}
$$

So the SE is the sample standard deviation of the matched row values divided by the square root of the number of non-missing matched rows.

### 95% Confidence Interval

The script uses a two-sided Student-$t$ confidence interval:

$$
\bar{x} \pm t_{0.975,\,n-1}\cdot SE
$$

So the plotted half-width is:

$$
\mathrm{CI}_{\text{half}} = t_{0.975,\,n-1}\cdot \frac{s}{\sqrt{n}}
$$

where $t_{0.975,\,n-1}$ is the 97.5th percentile of the $t$-distribution with $n-1$ degrees of freedom.

### Edge Cases

`row_mean_and_ci()` handles special cases as follows:

- if `n = 0`, return `(NaN, NaN)`
- if `n = 1`, return `(x_1, 0.0)`

So a single matched row is plotted with zero error-bar width.

### Important Interpretation Detail

These means and confidence intervals are computed from the row-level metric values in the evaluation CSVs after:

1. inner-joining the three systems on `(module, group, condition)`
2. selecting one metric column for one system
3. dropping `NaN` rows for that metric/system

They are not recomputed from patient-level predictions in this script.

## 2. Hypothesis Testing

`hypothesis_testing.py` compares the same three systems across the same matched rows for each metric.

The testing pipeline is:

1. Friedman test for an omnibus three-system comparison.
2. Pairwise Wilcoxon signed-rank tests for post-hoc comparisons.
3. Multiple-testing correction.
4. Rank-biserial correlation as the Wilcoxon effect size.

The values entering these tests are the same matched row-level vectors described above.

## 3. Friedman Omnibus Test

For each metric separately, the script applies:

$$
\text{Friedman}(x^{(\text{rule})}, x^{(\text{single})}, x^{(\text{multi})})
$$

using `scipy.stats.friedmanchisquare`.

This tests the null hypothesis that the three matched systems come from the same distribution for that metric.

### Reported Quantities

For each metric, the script writes:

- `Friedman_Chi2`
- `p_value`
- `N`
- per-system mean
- per-system sample standard deviation

The means reported are:

$$
\bar{x}^{(\text{rule})}, \quad \bar{x}^{(\text{single})}, \quad \bar{x}^{(\text{multi})}
$$

and the standard deviations are the sample standard deviations with `ddof=1`.

### Significance Threshold

Before correction, the script labels a result significant when:

$$
p < 0.05
$$

### BH-FDR Correction Across Metrics

Because the script runs one Friedman test for each of the 5 metrics, it applies Benjamini-Hochberg FDR correction across those 5 p-values using:

- `multipletests(..., method="fdr_bh")`

The adjusted p-values are stored as:

- `p_fdr_bh`

and significance after correction is stored as:

- `Significant_fdr_bh`

## 4. Pairwise Wilcoxon Signed-Rank Tests

For each metric, the script performs three two-sided paired Wilcoxon signed-rank tests:

- Rule-Based vs Single-Agent
- Rule-Based vs Multi-Agent
- Single-Agent vs Multi-Agent

If two matched systems have row values $x_i$ and $y_i$, define the paired differences:

$$
d_i = x_i - y_i
$$

The script runs:

$$
\text{Wilcoxon}(x, y; \text{two-sided})
$$

using `scipy.stats.wilcoxon`.

This tests the null hypothesis that the paired differences are symmetrically centered at zero.

### Mean Difference

The script also reports the average paired difference:

$$
\overline{d} = \frac{1}{n}\sum_{i=1}^{n}(x_i - y_i)
$$

This is stored as `Mean_Difference`.

### Direction Label

The script assigns a direction based on the sign of `Mean_Difference`:

- if $\overline{d} > 0$, left system > right system
- if $\overline{d} < 0$, right system > left system
- if $\overline{d} = 0$, Equal

## 5. Multiple-Testing Correction for Pairwise Tests

Two corrections are applied to each pairwise Wilcoxon output table.

### Bonferroni Across the 3 System Pairs

The script defines:

$$
N_{\text{pairs}} = 3
$$

and computes:

$$
p_{\text{Bonferroni}} = \min(3p, 1)
$$

This is stored as:

- `p_bonferroni`

and significance is defined as:

$$
p_{\text{Bonferroni}} < 0.05
$$

stored in:

- `Significant_bonferroni`

### BH-FDR Across the 5 Metrics Within Each Pair

Within each pairwise comparison file, the script also applies Benjamini-Hochberg FDR correction across the 5 metric-level Wilcoxon p-values:

- `multipletests(..., method="fdr_bh")`

The adjusted values are stored as:

- `p_fdr_bh`
- `Significant_fdr_bh`

## 6. Effect Size: Rank-Biserial Correlation

For each Wilcoxon test, the script computes the effect size from the Wilcoxon statistic $W$ and the matched sample size $n$:

$$
r = 1 - \frac{2W}{n(n+1)}
$$

This is implemented in:

```python
def rank_biserial(w_stat, n):
    return 1 - (2 * w_stat) / (n * (n + 1))
```

and saved as:

- `Effect_Size_r`

### Interpretation of Sign

Because the effect size is computed after calling Wilcoxon on `(x, y)` in that order:

- positive $r$ means the left-hand system tends to score higher
- negative $r$ means the right-hand system tends to score higher

This interpretation is also reflected in the summary figure colorbar label:

`positive = left system higher`

## 7. Summary Figure in `hypothesis_testing.py`

The script produces a two-panel summary figure.

### Left Panel

A horizontal bar chart of:

$$
\chi^2_{\text{Friedman}}
$$

for each metric.

Bar color is based on FDR-corrected Friedman significance:

- red: significant after BH-FDR
- blue: not significant

### Right Panel

A heatmap of pairwise Wilcoxon effect sizes $r$:

- rows: metrics
- columns: system pairs

Each cell shows:

$$
\text{Effect size } r
$$

with a `*` appended when the Bonferroni-corrected Wilcoxon result is significant.

