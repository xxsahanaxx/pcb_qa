#!/usr/bin/env python3
"""
Check across all projects in configs/projects.json, for the format sets
"PNet&NCir" and "PNet&PCir", how many component_datasheet questions
used the tool call "get_relevant_context_from_question".

Outputs a CSV and summary table.
"""

import json
import os
import csv
import glob
from collections import defaultdict


def main():
    # Load projects from config
    config_path = "configs/projects.json"
    with open(config_path) as f:
        projects_config = json.load(f)

    project_names = sorted(projects_config.keys())
    format_sets = ["PNet&NCir", "PNet&PCir"]
    target_tool = "get_relevant_context_from_question"
    target_category = "component_datasheet"

    # Structure: format_set -> project -> { total, with_tool }
    results = defaultdict(lambda: defaultdict(lambda: {"total": 0, "with_tool": 0}))
    # Also aggregate across all projects per format set
    agg = defaultdict(lambda: {"total": 0, "with_tool": 0})

    for project_name in project_names:
        for fmt in format_sets:
            # Path: outputs/{project}/results/{fmt}/*/component_datasheet/*.json
            pattern = f"outputs/{project_name}/results/{fmt}/*/{target_category}/*.json"
            files = sorted(glob.glob(pattern))

            for filepath in files:
                results[fmt][project_name]["total"] += 1
                agg[fmt]["total"] += 1

                try:
                    with open(filepath) as f:
                        data = json.load(f)

                    tool_calls = data.get("tool_calls", {})
                    tool_name = tool_calls.get("name", "")

                    if tool_name == target_tool:
                        results[fmt][project_name]["with_tool"] += 1
                        agg[fmt]["with_tool"] += 1
                except Exception as e:
                    print(f"  Error reading {filepath}: {e}")

    # ── Write CSV ──
    csv_rows = []
    FIELD_NAMES = ["format_set", "project", "total_component_datasheet", "used_get_relevant_context", "pct"]

    for fmt in format_sets:
        for project in sorted(results[fmt].keys()):
            r = results[fmt][project]
            pct = round(r["with_tool"] / r["total"] * 100, 1) if r["total"] else 0
            csv_rows.append({
                "format_set": fmt,
                "project": project,
                "total_component_datasheet": r["total"],
                "used_get_relevant_context": r["with_tool"],
                "pct": pct,
            })
        # Aggregate row for this format set
        pct = round(agg[fmt]["with_tool"] / agg[fmt]["total"] * 100, 1) if agg[fmt]["total"] else 0
        csv_rows.append({
            "format_set": fmt,
            "project": "ALL",
            "total_component_datasheet": agg[fmt]["total"],
            "used_get_relevant_context": agg[fmt]["with_tool"],
            "pct": pct,
        })

    csv_path = "outputs/component_datasheet_tool_usage_PNet.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"CSV exported to: {csv_path}")

    # ── Print Summary ──
    print(f"\n=== Component Datasheet: Tool Call Usage for PNet&NCir and PNet&PCir ===")
    print(f"Target tool: '{target_tool}'")
    print()
    for fmt in format_sets:
        print(f"  {fmt}:")
        for project in sorted(results[fmt].keys()):
            r = results[fmt][project]
            pct = round(r["with_tool"] / r["total"] * 100, 1) if r["total"] else 0
            print(f"    {project:<25} {r['with_tool']:>3}/{r['total']:>3} ({pct:>5.1f}%)")
        pct = round(agg[fmt]["with_tool"] / agg[fmt]["total"] * 100, 1) if agg[fmt]["total"] else 0
        print(f"    {'ALL':<25} {agg[fmt]['with_tool']:>3}/{agg[fmt]['total']:>3} ({pct:>5.1f}%)")
        print()


if __name__ == "__main__":
    main()