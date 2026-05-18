# Three-System Benchmark Summary

Systems: `multi-agent`, `single-agent`, `rule-based`

## Macro Means by Metric

| Metric | Multi | Single | Rule | Single-Multi | Rule-Multi | Rule-Single | Winner |
|---|---:|---:|---:|---:|---:|---:|---|
| accuracy | 87.78 | 67.53 | 72.94 | -20.25 | -14.84 | 5.41 | multi |
| sensitivity | 80.00 | 40.53 | 52.40 | -39.47 | -27.60 | 11.87 | multi |
| specificity | 78.00 | 81.07 | 78.93 | 3.07 | 0.93 | -2.13 | single |
| f1 | 79.11 | 42.90 | 57.96 | -36.20 | -21.15 | 15.06 | multi |
| f2 | 79.43 | 40.97 | 53.96 | -38.46 | -25.47 | 12.99 | multi |

## Group Means by Metric

| Group | Metric | Multi | Single | Rule | Single-Multi | Rule-Multi | Rule-Single | Winner |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Emotional Tone | accuracy | 87.78 | 67.53 | 72.93 | -20.25 | -14.85 | 5.40 | multi |
| Emotional Tone | sensitivity | 88.89 | 45.04 | 58.22 | -43.85 | -30.67 | 13.19 | multi |
| Emotional Tone | specificity | 86.67 | 90.07 | 87.70 | 3.41 | 1.04 | -2.37 | single |
| Emotional Tone | f1 | 87.03 | 47.29 | 63.88 | -39.74 | -23.15 | 16.59 | multi |
| Emotional Tone | f2 | 87.88 | 45.38 | 59.78 | -42.50 | -28.10 | 14.40 | multi |
| Symptom Direction | accuracy | 87.78 | 67.56 | 72.96 | -20.22 | -14.82 | 5.41 | multi |
| Symptom Direction | sensitivity | 44.44 | 22.52 | 29.11 | -21.93 | -15.33 | 6.59 | multi |
| Symptom Direction | specificity | 43.33 | 45.04 | 43.85 | 1.70 | 0.52 | -1.19 | single |
| Symptom Direction | f1 | 46.86 | 25.99 | 34.73 | -20.87 | -12.12 | 8.75 | multi |
| Symptom Direction | f2 | 45.34 | 23.58 | 30.97 | -21.76 | -14.38 | 7.39 | multi |
| Symptom Disclosure | accuracy | 87.78 | 67.52 | 72.93 | -20.26 | -14.85 | 5.41 | multi |
| Symptom Disclosure | sensitivity | 88.89 | 45.04 | 58.22 | -43.85 | -30.67 | 13.18 | multi |
| Symptom Disclosure | specificity | 86.67 | 90.08 | 87.70 | 3.41 | 1.04 | -2.37 | single |
| Symptom Disclosure | f1 | 87.25 | 47.04 | 63.70 | -40.22 | -23.55 | 16.66 | multi |
| Symptom Disclosure | f2 | 87.99 | 45.27 | 59.66 | -42.72 | -28.32 | 14.40 | multi |

## Cell Win Counts

| Metric | Multi Wins | Single Wins | Rule Wins | Ties |
|---|---:|---:|---:|---:|
| accuracy | 71 | 17 | 11 | 51 |
| sensitivity | 57 | 13 | 9 | 71 |
| specificity | 2 | 20 | 35 | 93 |
| f1 | 72 | 15 | 6 | 57 |
| f2 | 70 | 16 | 7 | 57 |

## Top 5 Modules by F2

| Rank | Module | Multi | Single | Rule | Winner | Best Score |
|---:|---|---:|---:|---:|---|---:|
| 1 | Bulimia Nervosa | 66.87 | 90.00 | 52.74 | single | 90.00 |
| 2 | Substance Use Disorders | 90.00 | 2.45 | 90.00 | multi | 90.00 |
| 3 | Manic and Hypomanic Episodes | 86.69 | 23.11 | 11.96 | multi | 86.69 |
| 4 | Agoraphobia | 86.28 | 85.65 | 65.15 | multi | 86.28 |
| 5 | Suicidality | 85.67 | 50.59 | 79.86 | multi | 85.67 |

## Top 5 Modules by Accuracy

| Rank | Module | Multi | Single | Rule | Winner | Best Score |
|---:|---|---:|---:|---:|---|---:|
| 1 | Bulimia Nervosa | 85.56 | 100.00 | 76.67 | single | 100.00 |
| 2 | Substance Use Disorders | 100.00 | 51.11 | 100.00 | multi | 100.00 |
| 3 | Manic and Hypomanic Episodes | 97.78 | 60.74 | 55.14 | multi | 97.78 |
| 4 | Alcohol Use Disorder | 95.55 | 51.11 | 95.55 | multi | 95.55 |
| 5 | Suicidality | 94.44 | 74.45 | 63.33 | multi | 94.44 |
