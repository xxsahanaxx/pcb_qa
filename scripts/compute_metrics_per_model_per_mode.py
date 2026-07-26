#!/usr/bin/env python3
"""
Aggregate per-category sklearn metrics per model for each toolmode.

Reads the existing outputs/per_category_sklearn_metrics.csv and produces
a new CSV that averages metrics across all projects for each
(toolmode, model, category) combination, plus an overall 'ALL' category.

Output: outputs/per_model_per_mode_category_metrics.csv
"""

import csv
from collections import defaultdict


def main():
    input_csv = "outputs/per_category_sklearn_metrics.csv"
    output_csv = "outputs/per_model_per_mode_category_metrics.csv"

    # Read the existing metrics
    data = []
    with open(input_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    if not data:
        print("No data found in", input_csv)
        return

    # Group by (toolmode, model, category)
    grouped = defaultdict(lambda: {"accuracy": [], "precision": [], "recall": [], "f1_score": [], "count": []})

    for row in data:
        key = (row["toolmode"], row["model"], row["category"])
        grouped[key]["accuracy"].append(float(row["accuracy"]))
        grouped[key]["precision"].append(float(row["precision"]))
        grouped[key]["recall"].append(float(row["recall"]))
        grouped[key]["f1_score"].append(float(row["f1_score"]))
        grouped[key]["count"].append(int(row["count"]))

    results = []
    for (toolmode, model, category), vals in sorted(grouped.items()):
        n = len(vals["accuracy"])
        results.append({
            "toolmode": toolmode,
            "model": model,
            "category": category,
            "accuracy": round(sum(vals["accuracy"]) / n, 4),
            "precision": round(sum(vals["precision"]) / n, 4),
            "recall": round(sum(vals["recall"]) / n, 4),
            "f1_score": round(sum(vals["f1_score"]) / n, 4),
            "total_questions": sum(vals["count"]),
            "num_projects": n,
        })

    fieldnames = ["toolmode", "model", "category", "accuracy", "precision", "recall", "f1_score", "total_questions", "num_projects"]
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"CSV exported to: {output_csv}")
    print(f"Total rows: {len(results)}")

    # Print summary
    print("\n=== Per-Model Per-Mode Category Metrics ===")
    current_mode = None
    for r in results:
        if r["toolmode"] != current_mode:
            current_mode = r["toolmode"]
            print(f"\n--- {current_mode} ---")
            print(f"{'Model':<30} {'Category':<25} {'Acc':>6} {'Prec':>6} {'Rec':>6} {'F1':>6} {'N':>5}")
            print("-" * 85)
        print(f"{r['model']:<30} {r['category']:<25} {r['accuracy']:>6.4f} {r['precision']:>6.4f} {r['recall']:>6.4f} {r['f1_score']:>6.4f} {r['total_questions']:>5}")


if __name__ == "__main__":
    main()