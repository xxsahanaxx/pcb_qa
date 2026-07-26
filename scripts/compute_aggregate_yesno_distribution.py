#!/usr/bin/env python3
"""
Compute YES/NO question distribution across ALL projects listed in
configs/projects.json, broken down by the 3 categories
(component_datasheet, spice_behaviour, theory_layout).

Only processes the "questions_json_file" attribute from each project config
entry (the standard 60-question set per project).

Outputs two CSVs:
  - outputs/yesno_distribution_by_category.csv  (aggregated across all projects)
  - outputs/yesno_distribution_per_project.csv   (per-project breakdown)
"""

import json
import os
import csv
from collections import defaultdict


def process_questions_file(filepath):
    """Process a single questions JSON file and return YES/NO counts per category."""
    with open(filepath) as f:
        data = json.load(f)

    counts = defaultdict(lambda: {"YES": 0, "NO": 0})
    for item in data:
        cat = item.get("category", "unknown")
        ans = item.get("answer", "unknown").upper()
        if ans in ("YES", "NO"):
            counts[cat][ans] += 1
    return counts


def main():
    # Load projects from config
    config_path = "configs/projects.json"
    with open(config_path) as f:
        projects_config = json.load(f)

    project_names = sorted(projects_config.keys())
    print(f"Loaded {len(project_names)} projects from {config_path}: {project_names}")

    # Aggregated counts across ALL projects (by category and total)
    agg_by_category = defaultdict(lambda: {"YES": 0, "NO": 0})
    agg_total = {"YES": 0, "NO": 0}

    # Per-project counts (project -> category -> counts)
    per_project = defaultdict(lambda: defaultdict(lambda: {"YES": 0, "NO": 0}))

    for project_name in project_names:
        project_info = projects_config[project_name]
        questions_file = project_info.get("questions_json_file")

        if not questions_file:
            print(f"  WARNING: No 'questions_json_file' for project '{project_name}', skipping")
            continue

        # Normalise path (remove leading "./" if present)
        questions_file = questions_file.lstrip("./")

        if not os.path.exists(questions_file):
            print(f"  WARNING: File not found for project '{project_name}': {questions_file}")
            continue

        print(f"  {project_name}: {os.path.basename(questions_file)}")

        try:
            counts = process_questions_file(questions_file)
            for category, cat_counts in counts.items():
                agg_by_category[category]["YES"] += cat_counts["YES"]
                agg_by_category[category]["NO"] += cat_counts["NO"]
                per_project[project_name][category]["YES"] += cat_counts["YES"]
                per_project[project_name][category]["NO"] += cat_counts["NO"]
                agg_total["YES"] += cat_counts["YES"]
                agg_total["NO"] += cat_counts["NO"]
        except Exception as e:
            print(f"    Error processing {questions_file}: {e}")

    # ── Aggregate CSV (all projects combined) ──
    agg_rows = []
    FIELD_NAMES_AGG = ["category", "yes_count", "no_count", "total", "yes_pct", "no_pct"]

    for category in sorted(agg_by_category.keys()):
        c = agg_by_category[category]
        total = c["YES"] + c["NO"]
        agg_rows.append({
            "category": category,
            "yes_count": c["YES"],
            "no_count": c["NO"],
            "total": total,
            "yes_pct": round(c["YES"] / total * 100, 1) if total else 0,
            "no_pct": round(c["NO"] / total * 100, 1) if total else 0,
        })

    # Add grand total row
    gt = agg_total["YES"] + agg_total["NO"]
    agg_rows.append({
        "category": "ALL",
        "yes_count": agg_total["YES"],
        "no_count": agg_total["NO"],
        "total": gt,
        "yes_pct": round(agg_total["YES"] / gt * 100, 1) if gt else 0,
        "no_pct": round(agg_total["NO"] / gt * 100, 1) if gt else 0,
    })

    agg_csv = "outputs/yesno_distribution_by_category.csv"
    with open(agg_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES_AGG)
        writer.writeheader()
        writer.writerows(agg_rows)
    print(f"\nAggregate CSV exported to: {agg_csv}")

    # ── Per-Project CSV ──
    proj_rows = []
    FIELD_NAMES_PROJ = ["project", "category", "yes_count", "no_count", "total", "yes_pct", "no_pct"]

    for project in sorted(per_project.keys()):
        for category in sorted(per_project[project].keys()):
            c = per_project[project][category]
            total = c["YES"] + c["NO"]
            proj_rows.append({
                "project": project,
                "category": category,
                "yes_count": c["YES"],
                "no_count": c["NO"],
                "total": total,
                "yes_pct": round(c["YES"] / total * 100, 1) if total else 0,
                "no_pct": round(c["NO"] / total * 100, 1) if total else 0,
            })
        # Per-project total
        proj_yes = sum(per_project[project][cat]["YES"] for cat in per_project[project])
        proj_no = sum(per_project[project][cat]["NO"] for cat in per_project[project])
        proj_total = proj_yes + proj_no
        proj_rows.append({
            "project": project,
            "category": "ALL",
            "yes_count": proj_yes,
            "no_count": proj_no,
            "total": proj_total,
            "yes_pct": round(proj_yes / proj_total * 100, 1) if proj_total else 0,
            "no_pct": round(proj_no / proj_total * 100, 1) if proj_total else 0,
        })

    proj_csv = "outputs/yesno_distribution_per_project.csv"
    with open(proj_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES_PROJ)
        writer.writeheader()
        writer.writerows(proj_rows)
    print(f"Per-project CSV exported to: {proj_csv}")

    # ── Print Summary ──
    print(f"\n=== Aggregate YES/NO Distribution (questions_json_file only) ===")
    print(f"{'Category':<25} {'YES':>5} {'NO':>5} {'Total':>5} {'YES%':>7} {'NO%':>7}")
    print("-" * 55)
    for row in agg_rows:
        print(f"{row['category']:<25} {row['yes_count']:>5} {row['no_count']:>5} {row['total']:>5} {row['yes_pct']:>6}% {row['no_pct']:>6}%")


if __name__ == "__main__":
    main()