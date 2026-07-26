#!/usr/bin/env python3
"""
Compute per-category sklearn metrics (accuracy, precision, recall, F1) for each
toolmode, project, and model, using the existing result CSV files.

Output: outputs/per_category_sklearn_metrics.csv
"""

import csv
import glob
import os
import sys

from collections import defaultdict

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


# Map directory names to human-readable toolmode labels
TOOLMODE_MAP = {
    "NNet&NCir": "NNet&NCir",
    "NNet&PCir": "NNet&PCir",
    "PNet&NCir": "PNet&NCir",
    "PNet&PCir": "PNet&PCir",
    "PDF": "PDF",
}


def extract_project_and_model_from_csv(csv_path):
    """Given a path like outputs/CF-Chef/results/NNet&NCir/claude-sonnet-4.6_CF-Chef.csv
    return (toolmode, project, model)."""
    parts = csv_path.split("/")
    toolmode_dir = parts[-2]  # e.g. NNet&NCir
    toolmode = TOOLMODE_MAP.get(toolmode_dir, toolmode_dir)
    
    basename = os.path.basename(csv_path).replace(".csv", "")
    # Remove confusion suffix if present
    basename = basename.replace("_confusion", "")
    
    # Extract model and project: format is <model>_<project>
    # Models can have dots and hyphens, project names are the rest
    # Known models: claude-sonnet-4.6, gemini-3-flash-preview, gpt-5.4-nano, llama-3.3-70b-instruct
    known_models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]
    
    model = None
    for known in known_models:
        if basename.startswith(known):
            model = known
            project = basename[len(known) + 1:]  # +1 for the underscore
            break
    
    if model is None:
        # Fallback: try splitting on first underscore after model pattern
        # This is a heuristic - model names don't have underscores, project names might
        parts = basename.split("_")
        # Assume first part is model prefix, last parts are project
        model = parts[0]
        project = "_".join(parts[1:])
    
    return toolmode, project, model


def parse_result_csv(csv_path):
    """Parse a result CSV and return list of (category, actual, predicted) tuples."""
    rows = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader)
        # Expected header: Model, Question, Category, Actual_Response, Predicted_Response
        try:
            cat_idx = header.index("Category")
            actual_idx = header.index("Actual_Response")
            pred_idx = header.index("Predicted_Response")
        except ValueError:
            return rows  # Skip files without expected headers
        
        for row in reader:
            if len(row) <= max(cat_idx, actual_idx, pred_idx):
                continue
            # Skip summary rows
            if row[0] in ("Accuracy", ""):
                continue
            category = row[cat_idx]
            actual = row[actual_idx].strip().upper()
            predicted = row[pred_idx].strip().upper()
            if actual in ("YES", "NO") and predicted in ("YES", "NO"):
                rows.append((category, actual, predicted))
    
    return rows


def compute_metrics(actuals, predictions):
    """Compute accuracy, precision, recall, F1 using sklearn.

    Uses binary (YES/NO) classification with macro-averaging and
    zero_division=0 to gracefully handle edge cases.
    """
    if not actuals:
        return 0.0, 0.0, 0.0, 0.0

    acc = accuracy_score(actuals, predictions)
    prec = precision_score(actuals, predictions, pos_label="YES", average="macro", zero_division=0)
    rec = recall_score(actuals, predictions, pos_label="YES", average="macro", zero_division=0)
    f1 = f1_score(actuals, predictions, pos_label="YES", average="macro", zero_division=0)

    return acc, prec, rec, f1


def main():
    results = []
    
    # Find all result CSVs (not confusion matrices)
    patterns = [
        "outputs/*/results/NNet&NCir/*.csv",
        "outputs/*/results/NNet&PCir/*.csv",
        "outputs/*/results/PNet&NCir/*.csv",
        "outputs/*/results/PNet&PCir/*.csv",
        "outputs/*/results/PDF/*.csv",
    ]
    
    for pattern in patterns:
        for csv_path in sorted(glob.glob(pattern)):
            basename = os.path.basename(csv_path)
            # Skip confusion CSVs and directories
            if "confusion" in basename:
                continue
            
            toolmode, project, model = extract_project_and_model_from_csv(csv_path)
            
            rows = parse_result_csv(csv_path)
            if not rows:
                print(f"  [SKIP] No data rows in {csv_path}")
                continue
            
            # Group by category
            category_data = defaultdict(lambda: {"actual": [], "predicted": []})
            for category, actual, predicted in rows:
                category_data[category]["actual"].append(actual)
                category_data[category]["predicted"].append(predicted)
            
            # Compute per-category metrics
            for category in sorted(category_data.keys()):
                actuals = category_data[category]["actual"]
                predictions = category_data[category]["predicted"]
                acc, prec, rec, f1 = compute_metrics(actuals, predictions)
                
                results.append({
                    "toolmode": toolmode,
                    "project": project,
                    "model": model,
                    "category": category,
                    "accuracy": round(acc, 4),
                    "precision": round(prec, 4),
                    "recall": round(rec, 4),
                    "f1_score": round(f1, 4),
                    "count": len(actuals),
                })
            
            # Also compute overall metrics per file
            all_actuals = [a for _, a, _ in rows]
            all_predictions = [p for _, _, p in rows]
            acc, prec, rec, f1 = compute_metrics(all_actuals, all_predictions)
            results.append({
                "toolmode": toolmode,
                "project": project,
                "model": model,
                "category": "ALL",
                "accuracy": round(acc, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
                "count": len(all_actuals),
            })
    
    if not results:
        print("No results found. Check the paths.")
        return
    
    # Write CSV
    csv_path = "outputs/per_category_sklearn_metrics.csv"
    fieldnames = ["toolmode", "project", "model", "category", "accuracy", "precision", "recall", "f1_score", "count"]
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"CSV exported to: {csv_path}")
    print(f"Total rows: {len(results)}")
    
    # Print a compact summary
    print("\n=== Summary: Average metrics per (toolmode, category) ===")
    agg = defaultdict(lambda: {"acc": [], "prec": [], "rec": [], "f1": []})
    for r in results:
        key = (r["toolmode"], r["category"])
        agg[key]["acc"].append(r["accuracy"])
        agg[key]["prec"].append(r["precision"])
        agg[key]["rec"].append(r["recall"])
        agg[key]["f1"].append(r["f1_score"])
    
    print(f"{'ToolMode':<15} {'Category':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 80)
    for key in sorted(agg.keys()):
        toolmode, category = key
        vals = agg[key]
        avg_acc = sum(vals["acc"]) / len(vals["acc"])
        avg_prec = sum(vals["prec"]) / len(vals["prec"])
        avg_rec = sum(vals["rec"]) / len(vals["rec"])
        avg_f1 = sum(vals["f1"]) / len(vals["f1"])
        print(f"{toolmode:<15} {category:<25} {avg_acc:>10.4f} {avg_prec:>10.4f} {avg_rec:>10.4f} {avg_f1:>10.4f}")


if __name__ == "__main__":
    main()