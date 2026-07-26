"""Aggregate per-project confusion-matrix CSVs into one CSV per toolmode.

Produces files like ``aggregated_NNet&NCir_confusion.csv`` in the project root.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path

from pcb_qa.config import DEFAULT_PROJECTS_FILE, load_projects_config
from pcb_qa.logging_config import logger


def _extract_metadata_from_path(csv_path: str) -> dict[str, str]:
    """Extract project, model, and mode from a confusion CSV file path.

    Expected path pattern::

        outputs/<project>/results/<mode>/<model>_<project>_confusion.csv

    Returns
    -------
    dict
        Keys ``project``, ``model``, ``mode``.
    """
    path = Path(csv_path)
    parts = path.parts

    try:
        results_idx = parts.index("results")
    except ValueError:
        raise ValueError(f"Path does not contain 'results' directory: {csv_path}")

    project_dir = parts[results_idx - 1]
    mode = parts[results_idx + 1]

    # Extract model from filename: <model>_<project>_confusion.csv
    filename = path.name
    stem = filename.replace("_confusion.csv", "")
    project_name = project_dir
    if stem.endswith(project_name):
        model = stem[: -(len(project_name) + 1)]  # +1 for the underscore
    else:
        last_underscore = stem.rfind("_")
        model = stem[:last_underscore] if last_underscore != -1 else stem

    return {"project": project_dir, "model": model, "mode": mode}


def aggregate_confusion_matrices(
    projects_config_path: str | None = DEFAULT_PROJECTS_FILE,
    output_dir: str = ".",
) -> list[str]:
    """Compile all confusion-matrix CSVs into one CSV per toolmode.

    Scans the results directories of all projects, finds every
    ``*_confusion.csv`` file, groups them by toolmode, and writes one
    aggregated CSV per mode to *output_dir*.

    Each output file is named ``aggregated_<mode>_confusion.csv`` and
    contains columns::

        Project, Model, Category, TP, TN, FP, FN, Total, Accuracy

    Parameters
    ----------
    projects_config_path:
        Path to the projects JSON configuration file.
    output_dir:
        Directory where the aggregated CSVs are written (default: current dir).

    Returns
    -------
    list[str]
        Paths to the written aggregated CSV files.
    """
    project_files_dict = load_projects_config(projects_config_path)

    # Collect all confusion CSV file paths, grouped by mode
    mode_files: dict[str, list[str]] = defaultdict(list)
    for project_key, project in project_files_dict.items():
        results_dir = os.path.join(project["parent_directory"], "results")
        if not os.path.isdir(results_dir):
            logger.warning("Results directory not found: %s", results_dir)
            continue

        for root, _dirs, files in os.walk(results_dir):
            for fname in files:
                if fname.endswith("_confusion.csv"):
                    mode_files["_"].append(os.path.join(root, fname))

    # Re-group by actual mode extracted from the path
    by_mode: dict[str, list[dict[str, str]]] = defaultdict(list)
    for csv_path in mode_files.get("_", []):
        try:
            meta = _extract_metadata_from_path(csv_path)
        except ValueError as exc:
            logger.warning("Skipping %s: %s", csv_path, exc)
            continue

        with open(csv_path, "r", newline="") as fh:
            reader = csv.DictReader(fh)
            for record in reader:
                by_mode[meta["mode"]].append({
                    "Project": meta["project"],
                    "Model": meta["model"],
                    "Category": record.get("Category", ""),
                    "TP": record.get("TP", ""),
                    "TN": record.get("TN", ""),
                    "FP": record.get("FP", ""),
                    "FN": record.get("FN", ""),
                    "Total": record.get("Total", ""),
                    "Accuracy": record.get("Accuracy", ""),
                })

    if not by_mode:
        logger.warning("No confusion matrix CSV files found.")
        return []

    os.makedirs(output_dir, exist_ok=True)
    written: list[str] = []

    header = ["Project", "Model", "Category", "TP", "TN", "FP", "FN", "Total", "Accuracy"]

    for mode in sorted(by_mode):
        output_path = os.path.join(output_dir, f"aggregated_{mode}_confusion.csv")
        rows = by_mode[mode]
        # Sort rows by project, then model, then category
        rows.sort(key=lambda r: (r["Project"], r["Model"], r["Category"]))

        # Compute totals across all rows
        totals: dict[str, float] = {"TP": 0.0, "TN": 0.0, "FP": 0.0, "FN": 0.0}
        for row in rows:
            for key in totals:
                totals[key] += float(row[key]) if row[key] else 0.0
        total_sum = sum(totals.values())
        total_accuracy = (totals["TP"] + totals["TN"]) / total_sum if total_sum > 0 else 0.0

        with open(output_path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            for row in rows:
                writer.writerow([row[h] for h in header])
            # Append summary row
            writer.writerow([
                "TOTAL", "", "",
                str(int(totals["TP"])),
                str(int(totals["TN"])),
                str(int(totals["FP"])),
                str(int(totals["FN"])),
                str(int(total_sum)),
                f"{total_accuracy:.4f}",
            ])

        abs_path = os.path.abspath(output_path)
        logger.info("Wrote %s (%d rows + totals)", abs_path, len(rows))
        written.append(abs_path)

    return written


def aggregate_confusion_matrices_by_category(
    projects_config_path: str | None = DEFAULT_PROJECTS_FILE,
    output_dir: str = ".",
) -> list[str]:
    """Compile all confusion-matrix CSVs into one CSV per (toolmode, category).

    For each toolmode, groups all rows by category (summing TP, TN, FP, FN
    across all projects and models), writes one CSV per mode to *output_dir*.

    Each output file is named ``aggregated_<mode>_confusion_by_category.csv``
    and contains columns::

        Category, TP, TN, FP, FN, Total, Accuracy

    Parameters
    ----------
    projects_config_path:
        Path to the projects JSON configuration file.
    output_dir:
        Directory where the aggregated CSVs are written (default: current dir).

    Returns
    -------
    list[str]
        Paths to the written aggregated CSV files.
    """
    project_files_dict = load_projects_config(projects_config_path)

    # Collect all confusion CSV file paths
    all_csv_paths: list[str] = []
    for project_key, project in project_files_dict.items():
        results_dir = os.path.join(project["parent_directory"], "results")
        if not os.path.isdir(results_dir):
            logger.warning("Results directory not found: %s", results_dir)
            continue
        for root, _dirs, files in os.walk(results_dir):
            for fname in files:
                if fname.endswith("_confusion.csv"):
                    all_csv_paths.append(os.path.join(root, fname))

    # Group records by (mode, category)
    by_mode_cat: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"TP": 0.0, "TN": 0.0, "FP": 0.0, "FN": 0.0})
    )

    for csv_path in all_csv_paths:
        try:
            meta = _extract_metadata_from_path(csv_path)
        except ValueError as exc:
            logger.warning("Skipping %s: %s", csv_path, exc)
            continue

        with open(csv_path, "r", newline="") as fh:
            reader = csv.DictReader(fh)
            for record in reader:
                cat = record.get("Category", "")
                agg = by_mode_cat[meta["mode"]][cat]
                for key in ("TP", "TN", "FP", "FN"):
                    agg[key] += float(record.get(key, 0) or 0)

    if not by_mode_cat:
        logger.warning("No confusion matrix CSV files found.")
        return []

    os.makedirs(output_dir, exist_ok=True)
    written: list[str] = []
    header = ["Category", "TP", "TN", "FP", "FN", "Total", "Accuracy"]

    for mode in sorted(by_mode_cat):
        output_path = os.path.join(output_dir, f"aggregated_{mode}_confusion_by_category.csv")
        categories = by_mode_cat[mode]
        cat_rows = []
        totals_agg: dict[str, float] = {"TP": 0.0, "TN": 0.0, "FP": 0.0, "FN": 0.0}

        for cat in sorted(categories):
            cm = categories[cat]
            total = cm["TP"] + cm["TN"] + cm["FP"] + cm["FN"]
            accuracy = (cm["TP"] + cm["TN"]) / total if total > 0 else 0.0
            cat_rows.append([cat, int(cm["TP"]), int(cm["TN"]), int(cm["FP"]), int(cm["FN"]), int(total), f"{accuracy:.4f}"])
            for k in totals_agg:
                totals_agg[k] += cm[k]

        grand_total = sum(totals_agg.values())
        grand_accuracy = (totals_agg["TP"] + totals_agg["TN"]) / grand_total if grand_total > 0 else 0.0

        with open(output_path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(cat_rows)
            writer.writerow([
                "TOTAL",
                int(totals_agg["TP"]),
                int(totals_agg["TN"]),
                int(totals_agg["FP"]),
                int(totals_agg["FN"]),
                int(grand_total),
                f"{grand_accuracy:.4f}",
            ])

        abs_path = os.path.abspath(output_path)
        logger.info("Wrote %s (%d categories)", abs_path, len(cat_rows))
        written.append(abs_path)

    return written


def main() -> None:
    """CLI entry-point for aggregation."""
    aggregate_confusion_matrices()


if __name__ == "__main__":
    main()
