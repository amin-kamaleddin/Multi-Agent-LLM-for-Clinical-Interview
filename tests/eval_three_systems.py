import argparse
from pathlib import Path

import pandas as pd


METRICS = ["accuracy", "sensitivity", "specificity", "f1", "f2"]
KEY_COLS = ["module", "group", "condition"]
SYSTEM_COLS = {
    "multi": "multi",
    "single": "single",
    "rule": "rule",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Build a unified 3-system benchmark summary.")
    parser.add_argument(
        "--multi-csv",
        default="patient_agent_results/evaluation_results.csv",
        help="Multi-agent bootstrap evaluation CSV.",
    )
    parser.add_argument(
        "--single-csv",
        default="baselines/evaluation_results_single_agent.csv",
        help="Single-agent bootstrap evaluation CSV.",
    )
    parser.add_argument(
        "--rule-csv",
        default="baselines/evaluation_results_rule_based.csv",
        help="Rule-based bootstrap evaluation CSV.",
    )
    parser.add_argument(
        "--summary-csv",
        default="baselines/three_systems_summary.csv",
        help="Output machine-readable summary CSV.",
    )
    parser.add_argument(
        "--summary-md",
        default="baselines/three_systems_summary.md",
        help="Output concise markdown summary report.",
    )
    return parser.parse_args()


def _load_eval(path: str, prefix: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = set(KEY_COLS + ["n_total"] + [f"{m}_mean" for m in METRICS])
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path}: missing required columns: {', '.join(missing)}")

    keep = KEY_COLS + ["n_total"] + [f"{m}_mean" for m in METRICS]
    df = df[keep].copy()
    rename_map = {"n_total": f"n_total_{prefix}"}
    rename_map.update({f"{m}_mean": f"{m}_{prefix}" for m in METRICS})
    df = df.rename(columns=rename_map)
    return df


def _validate_alignment(df: pd.DataFrame) -> None:
    for m in METRICS:
        cols = [f"{m}_multi", f"{m}_single", f"{m}_rule"]
        if any(c not in df.columns for c in cols):
            raise ValueError(f"Aligned dataset missing expected metric columns for {m}")


def _macro_metric_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for metric in METRICS:
        mv = df[f"{metric}_multi"].mean()
        sv = df[f"{metric}_single"].mean()
        rv = df[f"{metric}_rule"].mean()
        rows.append(
            {
                "section": "macro_by_metric",
                "metric": metric,
                "group": "ALL",
                "module": "ALL",
                "multi": round(float(mv), 4),
                "single": round(float(sv), 4),
                "rule": round(float(rv), 4),
                "single_minus_multi": round(float(sv - mv), 4),
                "rule_minus_multi": round(float(rv - mv), 4),
                "rule_minus_single": round(float(rv - sv), 4),
                "winner": max(
                    [("multi", mv), ("single", sv), ("rule", rv)],
                    key=lambda x: x[1],
                )[0],
            }
        )
    return rows


def _group_metric_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for group, gdf in df.groupby("group"):
        for metric in METRICS:
            mv = gdf[f"{metric}_multi"].mean()
            sv = gdf[f"{metric}_single"].mean()
            rv = gdf[f"{metric}_rule"].mean()
            rows.append(
                {
                    "section": "group_metric_means",
                    "metric": metric,
                    "group": group,
                    "module": "ALL",
                    "multi": round(float(mv), 4),
                    "single": round(float(sv), 4),
                    "rule": round(float(rv), 4),
                    "single_minus_multi": round(float(sv - mv), 4),
                    "rule_minus_multi": round(float(rv - mv), 4),
                    "rule_minus_single": round(float(rv - sv), 4),
                    "winner": max(
                        [("multi", mv), ("single", sv), ("rule", rv)],
                        key=lambda x: x[1],
                    )[0],
                }
            )
    return rows


def _win_count_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for metric in METRICS:
        wins = {"multi": 0, "single": 0, "rule": 0, "tie": 0}
        for _, row in df.iterrows():
            values = {
                "multi": row[f"{metric}_multi"],
                "single": row[f"{metric}_single"],
                "rule": row[f"{metric}_rule"],
            }
            best_val = max(values.values())
            winners = [name for name, val in values.items() if abs(val - best_val) < 1e-12]
            if len(winners) == 1:
                wins[winners[0]] += 1
            else:
                wins["tie"] += 1

        rows.append(
            {
                "section": "cell_win_counts",
                "metric": metric,
                "group": "ALL",
                "module": "ALL",
                "multi": wins["multi"],
                "single": wins["single"],
                "rule": wins["rule"],
                "ties": wins["tie"],
            }
        )
    return rows


def _module_ranking_rows(df: pd.DataFrame, metric: str) -> list[dict]:
    section = f"module_rank_{metric}"
    rows = []
    grouped = df.groupby("module").agg(
        multi=(f"{metric}_multi", "mean"),
        single=(f"{metric}_single", "mean"),
        rule=(f"{metric}_rule", "mean"),
    )
    grouped["best_score"] = grouped[["multi", "single", "rule"]].max(axis=1)
    grouped["winner"] = grouped[["multi", "single", "rule"]].idxmax(axis=1)
    grouped = grouped.sort_values(["best_score", "module"], ascending=[False, True])

    for rank, (module, row) in enumerate(grouped.iterrows(), start=1):
        mv = float(row["multi"])
        sv = float(row["single"])
        rv = float(row["rule"])
        rows.append(
            {
                "section": section,
                "metric": metric,
                "group": "ALL",
                "module": module,
                "rank": rank,
                "multi": round(mv, 4),
                "single": round(sv, 4),
                "rule": round(rv, 4),
                "single_minus_multi": round(sv - mv, 4),
                "rule_minus_multi": round(rv - mv, 4),
                "rule_minus_single": round(rv - sv, 4),
                "winner": row["winner"],
                "best_score": round(float(row["best_score"]), 4),
            }
        )
    return rows


def _build_markdown(summary_df: pd.DataFrame, out_path: Path) -> None:
    macro = summary_df[summary_df["section"] == "macro_by_metric"].copy()
    group_rows = summary_df[summary_df["section"] == "group_metric_means"].copy()
    wins = summary_df[summary_df["section"] == "cell_win_counts"].copy()
    rank_f2 = summary_df[summary_df["section"] == "module_rank_f2"].copy()
    rank_acc = summary_df[summary_df["section"] == "module_rank_accuracy"].copy()

    lines = []
    lines.append("# Three-System Benchmark Summary")
    lines.append("")
    lines.append("Systems: `multi-agent`, `single-agent`, `rule-based`")
    lines.append("")

    lines.append("## Macro Means by Metric")
    lines.append("")
    lines.append("| Metric | Multi | Single | Rule | Single-Multi | Rule-Multi | Rule-Single | Winner |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for _, r in macro.iterrows():
        lines.append(
            f"| {r['metric']} | {r['multi']:.2f} | {r['single']:.2f} | {r['rule']:.2f} | "
            f"{r['single_minus_multi']:.2f} | {r['rule_minus_multi']:.2f} | {r['rule_minus_single']:.2f} | {r['winner']} |"
        )
    lines.append("")

    lines.append("## Group Means by Metric")
    lines.append("")
    lines.append("| Group | Metric | Multi | Single | Rule | Single-Multi | Rule-Multi | Rule-Single | Winner |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for _, r in group_rows.iterrows():
        lines.append(
            f"| {r['group']} | {r['metric']} | {r['multi']:.2f} | {r['single']:.2f} | {r['rule']:.2f} | "
            f"{r['single_minus_multi']:.2f} | {r['rule_minus_multi']:.2f} | {r['rule_minus_single']:.2f} | {r['winner']} |"
        )
    lines.append("")

    lines.append("## Cell Win Counts")
    lines.append("")
    lines.append("| Metric | Multi Wins | Single Wins | Rule Wins | Ties |")
    lines.append("|---|---:|---:|---:|---:|")
    for _, r in wins.iterrows():
        lines.append(f"| {r['metric']} | {int(r['multi'])} | {int(r['single'])} | {int(r['rule'])} | {int(r['ties'])} |")
    lines.append("")

    def _top5_block(title: str, df_rank: pd.DataFrame) -> None:
        lines.append(title)
        lines.append("")
        lines.append("| Rank | Module | Multi | Single | Rule | Winner | Best Score |")
        lines.append("|---:|---|---:|---:|---:|---|---:|")
        for _, r in df_rank.head(5).iterrows():
            lines.append(
                f"| {int(r['rank'])} | {r['module']} | {r['multi']:.2f} | {r['single']:.2f} | {r['rule']:.2f} | {r['winner']} | {r['best_score']:.2f} |"
            )
        lines.append("")

    _top5_block("## Top 5 Modules by F2", rank_f2)
    _top5_block("## Top 5 Modules by Accuracy", rank_acc)

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()

    multi = _load_eval(args.multi_csv, "multi")
    single = _load_eval(args.single_csv, "single")
    rule = _load_eval(args.rule_csv, "rule")

    aligned = multi.merge(single, on=KEY_COLS, how="inner").merge(rule, on=KEY_COLS, how="inner")
    expected_rows = len(multi)
    if len(aligned) != expected_rows or len(single) != expected_rows or len(rule) != expected_rows:
        raise ValueError(
            f"Row alignment mismatch across system CSVs: multi={len(multi)}, single={len(single)}, "
            f"rule={len(rule)}, aligned={len(aligned)}"
        )
    _validate_alignment(aligned)

    summary_rows = []
    summary_rows.extend(_macro_metric_rows(aligned))
    summary_rows.extend(_group_metric_rows(aligned))
    summary_rows.extend(_win_count_rows(aligned))
    summary_rows.extend(_module_ranking_rows(aligned, "f2"))
    summary_rows.extend(_module_ranking_rows(aligned, "accuracy"))

    out_df = pd.DataFrame(summary_rows)

    summary_csv_path = Path(args.summary_csv)
    summary_md_path = Path(args.summary_md)
    summary_csv_path.parent.mkdir(parents=True, exist_ok=True)
    summary_md_path.parent.mkdir(parents=True, exist_ok=True)

    out_df.to_csv(summary_csv_path, index=False)
    _build_markdown(out_df, summary_md_path)

    print(f"Wrote summary CSV: {summary_csv_path}")
    print(f"Wrote summary report: {summary_md_path}")


if __name__ == "__main__":
    main()

