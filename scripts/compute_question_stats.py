#!/usr/bin/env python3
"""
Compute per-category YES/NO counts for all question JSON files in outputs/ projects.
Exports results to a CSV file.
"""

import json
import os
import csv
import glob
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


def get_project_name(filepath):
    """Extract project name from path like outputs/CF-Chef/CF-Chef_60_questions_balanced.json"""
    parts = filepath.split("/")
    # The project directory name is the parent of the file
    project_dir = os.path.basename(os.path.dirname(filepath))
    return project_dir


def get_short_filename(filepath):
    """Get just the base filename."""
    return os.path.basename(filepath)


def main():
    output_dir = "outputs"
    results = []
    
    # Find all question JSON files (ending with _questions.json or _questions_balanced.json)
    patterns = [
        "outputs/*/*_questions.json",
        "outputs/*/*_questions_balanced.json",
    ]
    
    files_found = []
    for pattern in patterns:
        files_found.extend(sorted(glob.glob(pattern)))
    
    # Also check for files with "copy" suffix that should be skipped
    files_found = [f for f in files_found if "copy" not in os.path.basename(f)]
    
    for filepath in files_found:
        project = get_project_name(filepath)
        filename = get_short_filename(filepath)
        
        try:
            counts = process_questions_file(filepath)
            total_questions = sum(sum(cat_counts.values()) for cat_counts in counts.values())
            
            # Add a row per category
            for category in sorted(counts.keys()):
                cat_counts = counts[category]
                row = {
                    "project": project,
                    "file": filename,
                    "category": category,
                    "yes_count": cat_counts["YES"],
                    "no_count": cat_counts["NO"],
                    "total": cat_counts["YES"] + cat_counts["NO"],
                }
                results.append(row)
            
            # Also add a "total" row per file
            total_yes = sum(c["YES"] for c in counts.values())
            total_no = sum(c["NO"] for c in counts.values())
            results.append({
                "project": project,
                "file": filename,
                "category": "ALL",
                "yes_count": total_yes,
                "no_count": total_no,
                "total": total_yes + total_no,
            })
                
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
    
    # Write CSV
    csv_path = "outputs/question_stats_per_category.csv"
    fieldnames = ["project", "file", "category", "yes_count", "no_count", "total"]
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"CSV exported to: {csv_path}")
    print(f"Total rows: {len(results)}")
    
    # Also print a summary table
    print("\n=== Summary ===")
    print(f"{'Project':<25} {'File':<35} {'Category':<25} {'YES':>5} {'NO':>5} {'Total':>5}")
    print("-" * 100)
    for row in results:
        print(f"{row['project']:<25} {row['file']:<35} {row['category']:<25} {row['yes_count']:>5} {row['no_count']:>5} {row['total']:>5}")


if __name__ == "__main__":
    main()