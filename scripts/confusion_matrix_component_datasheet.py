#!/usr/bin/env python3
"""
For component_datasheet questions in PNet&NCir and PNet&PCir that used
the tool call "get_relevant_context_from_question", compare the model's
response answer against the expected answer from the question bank.

Generates a confusion matrix (expected vs actual) and outputs to CSV.
"""

import json
import os
import csv
import glob
from collections import defaultdict


def load_question_bank(project_name):
    """Load the questions_json_file for a project from configs/projects.json."""
    config_path = "configs/projects.json"
    with open(config_path) as f:
        projects_config = json.load(f)

    project_info = projects_config.get(project_name)
    if not project_info:
        return None

    questions_file = project_info.get("questions_json_file", "")
    questions_file = questions_file.lstrip("./")

    if not os.path.exists(questions_file):
        return None

    with open(questions_file) as f:
        return json.load(f)


def main():
    config_path = "configs/projects.json"
    with open(config_path) as f:
        projects_config = json.load(f)

    project_names = sorted(projects_config.keys())
    format_sets = ["PNet&NCir", "PNet&PCir"]
    target_tool = "get_relevant_context_from_question"
    target_category = "component_datasheet"

    # Confusion matrix: expected -> actual -> count
    confusion = defaultdict(lambda: defaultdict(int))
    # Also track per format set
    confusion_per_fmt = {
        fmt: defaultdict(lambda: defaultdict(int))
        for fmt in format_sets
    }

    total_checked = 0
    total_matched = 0

    for project_name in project_names:
        question_bank = load_question_bank(project_name)
        if question_bank is None:
            print(f"  WARNING: Could not load question bank for {project_name}")
            continue

        for fmt in format_sets:
            pattern = f"outputs/{project_name}/results/{fmt}/*/{target_category}/*.json"
            files = sorted(glob.glob(pattern))

            for filepath in files:
                # Extract question number from filename (e.g. "4.json" -> 4)
                basename = os.path.basename(filepath)
                stem = os.path.splitext(basename)[0]
                try:
                    q_idx = int(stem) - 1  # Convert 1-based to 0-based
                except ValueError:
                    continue

                if q_idx < 0 or q_idx >= len(question_bank):
                    continue

                expected_entry = question_bank[q_idx]
                if expected_entry.get("category") != target_category:
                    continue

                expected_answer = expected_entry.get("answer", "").upper()

                try:
                    with open(filepath) as f:
                        data = json.load(f)

                    tool_calls = data.get("tool_calls", {})
                    tool_name = tool_calls.get("name", "")

                    if tool_name != target_tool:
                        continue

                    actual_answer = data.get("response", {}).get("answer", "").upper()

                    # Normalise
                    if actual_answer not in ("YES", "NO"):
                        actual_answer = "OTHER"
                    if expected_answer not in ("YES", "NO"):
                        expected_answer = "OTHER"

                    confusion[expected_answer][actual_answer] += 1
                    confusion_per_fmt[fmt][expected_answer][actual_answer] += 1
                    total_checked += 1

                    if expected_answer == actual_answer:
                        total_matched += 1

                except Exception as e:
                    print(f"  Error processing {filepath}: {e}")

    # ── Write CSV ──
    csv_rows = []
    FIELD_NAMES = ["format_set", "expected", "actual_YES", "actual_NO", "total", "accuracy_pct"]

    for fmt in format_sets:
        cm = confusion_per_fmt[fmt]
        for expected in ("YES", "NO"):
            yes_count = cm[expected].get("YES", 0)
            no_count = cm[expected].get("NO", 0)
            total = yes_count + no_count
            acc = round(yes_count / total * 100, 1) if expected == "YES" else round(no_count / total * 100, 1) if total else 0
            csv_rows.append({
                "format_set": fmt,
                "expected": expected,
                "actual_YES": yes_count,
                "actual_NO": no_count,
                "total": total,
                "accuracy_pct": acc,
            })
        # Total row for this format set
        total_yes_expected = cm["YES"]["YES"] + cm["YES"]["NO"]
        total_no_expected = cm["NO"]["YES"] + cm["NO"]["NO"]
        total_all = total_yes_expected + total_no_expected
        correct = cm["YES"]["YES"] + cm["NO"]["NO"]
        acc_all = round(correct / total_all * 100, 1) if total_all else 0
        csv_rows.append({
            "format_set": fmt,
            "expected": "ALL",
            "actual_YES": cm["YES"]["YES"] + cm["NO"]["YES"],
            "actual_NO": cm["YES"]["NO"] + cm["NO"]["NO"],
            "total": total_all,
            "accuracy_pct": acc_all,
        })

    # Overall row
    total_all = sum(sum(v.values()) for v in confusion.values())
    correct_all = confusion["YES"]["YES"] + confusion["NO"]["NO"]
    acc_all = round(correct_all / total_all * 100, 1) if total_all else 0
    csv_rows.append({
        "format_set": "ALL",
        "expected": "ALL",
        "actual_YES": confusion["YES"]["YES"] + confusion["NO"]["YES"],
        "actual_NO": confusion["YES"]["NO"] + confusion["NO"]["NO"],
        "total": total_all,
        "accuracy_pct": acc_all,
    })

    csv_path = "outputs/component_datasheet_confusion_matrix.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"CSV exported to: {csv_path}")

    # ── Print Summary ──
    print(f"\n=== Component Datasheet Confusion Matrix (get_relevant_context_from_question only) ===")
    print(f"Total questions checked: {total_checked}")
    print(f"Total matched: {total_matched} ({round(total_matched/total_checked*100,1) if total_checked else 0}%)")
    print()
    for fmt in format_sets:
        cm = confusion_per_fmt[fmt]
        print(f"  {fmt}:")
        print(f"    {'':>12} {'Actual YES':>10} {'Actual NO':>10} {'Total':>8}")
        for expected in ("YES", "NO"):
            yes_count = cm[expected].get("YES", 0)
            no_count = cm[expected].get("NO", 0)
            total = yes_count + no_count
            print(f"    {'Expected ' + expected:<12} {yes_count:>10} {no_count:>10} {total:>8}")
        total_all = sum(sum(v.values()) for v in cm.values())
        correct = cm["YES"]["YES"] + cm["NO"]["NO"]
        acc = round(correct / total_all * 100, 1) if total_all else 0
        print(f"    {'Accuracy':<12} {'':>10} {'':>10} {acc:>7.1f}%")
        print()


if __name__ == "__main__":
    main()