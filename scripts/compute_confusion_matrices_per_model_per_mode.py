#!/usr/bin/env python3
"""
Aggregate category-wise confusion matrices per model for each toolmode.

Uses sklearn's confusion_matrix to compute TP, TN, FP, FN aggregated across
all projects for each (toolmode, model, category) combination.

Output: outputs/per_model_per_mode_category_confusion.csv
"""

import csv
import glob
import os
from collections import defaultdict

from sklearn.metrics import confusion_matrix


TOOLMODE_MAP = {
    "NNet&NCir": "NNet&NCir",
    "NNet&PCir": "NNet&PCir",
    "PNet&NCir": "PNet&NCir",
    "PNet&PCir": "PNet&PCir",
    "PDF": "PDF",
}

KNOWN_MODELS = [
    "claude-sonnet-4.6",
    "gemini-3-flash-preview",
    "gpt-5.4-nano",
    "llama-3.3-70b-instruct",
]


def extract_project_and_model(csv_path):
    parts = csv_path.split("/")
    toolmode_dir = parts[-2]
    toolmode = TOOLMODE_MAP.get(toolmode_dir, toolmode_dir)

    basename = os.path.basename(csv_path).replace(".csv", "").replace("_confusion", "")

    model = None
    for known in KNOWN_MODELS:
        if basename.startswith(known):
            model = known
            project = basename[len(known) + 1:]
            break
    if model is None:
        parts = basename.split("_")
        model = parts[0]
        project = "_".join(parts[1:])

    return toolmode, project, model


def parse_result_csv(csv_path):
    rows = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader)
        try:
            cat_idx = header.index("Category")
            actual_idx = header.index("Actual_Response")
            pred_idx = header.index("Predicted_Response")
        except ValueError:
            return rows

        for row in reader:
            if len(row) <= max(cat_idx, actual_idx, pred_idx):
                continue
            if row[0] in ("Accuracy", ""):
                continue
            category = row[cat_idx]
            actual = row[actual_idx].strip().upper()
            predicted = row[pred_idx].strip().upper()
            if actual in ("YES", "NO") and predicted in ("YES", "NO"):
                rows.append((category, actual, predicted))
    return rows


def compute_confusion_matrix(actuals, predictions, labels=["YES", "NO"]):
    """Return TP, TN, FP, FN using sklearn.confusion_matrix."""
    cm = confusion_matrix(actuals, predictions, labels=labels)
    # sklearn returns [[TN, FP], [FN, TP]] when labels=["NO", "YES"]
    # but with labels=["YES", "NO"] it returns [[TP, FP], [FN, TN]]
    tp = cm[0, 0]
    fp = cm[0, 1]
    fn = cm[1, 0]
    tn = cm[1, 1]
    return tp, tn, fp, fn


def main():
    patterns = [
        "outputs/*/results/NNet&NCir/*.csv",
        "outputs/*/results/NNet&PCir/*.csv",
        "outputs/*/results/PNet&NCir/*.csv",
        "outputs/*/results/PNet&PCir/*.csv",
        "outputs/*/results/PDF/*.csv",
    ]

    # aggregated data per (toolmode, model, category)
    grouped = defaultdict(lambda: {"actuals": [], "predictions": []})

    for pattern in patterns:
        for csv_path in sorted(glob.glob(pattern)):
            basename = os.path.basename(csv_path)
            if "confusion" in basename:
                continue

            toolmode, project, model = extract_project_and_model(csv_path)
            rows = parse_result_csv(csv_path)
            if not rows:
                continue

            for category, actual, predicted in rows:
                key = (toolmode, model, category)
                grouped[key]["actuals"].append(actual)
                grouped[key]["predictions"].append(predicted)

    results = []
    for (toolmode, model, category), data in sorted(grouped.items()):
        actuals = data["actuals"]
        predictions = data["predictions"]
        tp, tn, fp, fn = compute_confusion_matrix(actuals, predictions)
        total = tp + tn + fp + fn
        accuracy = (tp + tn) / total if total > 0 else 0.0

        results.append({
            "toolmode": toolmode,
            "model": model,
            "category": category,
            "TP": tp,
            "TN": tn,
            "FP": fp,
            "FN": fn,
            "Total": total,
            "Accuracy": round(accuracy, 4),
        })

    if not results:
        print("No results found.")
        return

    csv_path = "outputs/per_model_per_mode_category_confusion.csv"
    fieldnames = ["toolmode", "model", "category", "TP", "TN", "FP", "FN", "Total", "Accuracy"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"CSV exported to: {csv_path}")
    print(f"Total rows: {len(results)}")

    print("\n=== Confusion Matrix Summary ===")
    print(f"{'ToolMode':<15} {'Model':<30} {'Category':<25} {'TP':>5} {'TN':>5} {'FP':>5} {'FN':>5} {'Acc':>6}")
    print("-" * 100)
    for r in results:
        print(f"{r['toolmode']:<15} {r['model']:<30} {r['category']:<25} {r['TP']:>5} {r['TN']:>5} {r['FP']:>5} {r['FN']:>5} {r['Accuracy']:>6.4f}")


if __name__ == "__main__":
    main()