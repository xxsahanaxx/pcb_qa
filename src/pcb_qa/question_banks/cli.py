"""CLI module for question bank operations.

This module provides command-line interfaces for:
- Expanding question banks (generating questions from circuit data)
- Validating question banks against reference designs
- Fixing invalid questions based on validation results
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from pcb_qa.question_banks import (
    QuestionBankFixer,
    expand_question_bank_for_project,
)
from pcb_qa.question_banks.validator import CircuitQuestionValidator


def cmd_expand(args: argparse.Namespace) -> None:
    """Generate questions for all configured projects."""
    from pcb_qa.config import DEFAULT_PROJECTS_FILE

    with open(DEFAULT_PROJECTS_FILE, 'r') as f:
        projects = json.load(f)

    for project_name, project_data in projects.items():
        print(f"\nExpanding questions for: {project_name}")

        existing_file = project_data.get('questions_json_file')
        output_file = project_data['questions_json_file']
        base, ext = os.path.splitext(output_file)
        expanded_file = f"{base}_balanced{ext}"

        expanded = expand_question_bank_for_project(
            circuit_json_file=project_data['circuit_json_file'],
            spice_json_file=project_data['spice_json_file'],
            existing_questions_file=existing_file,
            output_file=expanded_file,
            total_questions=240,
            shuffle=True,
        )

        print(f"  Total questions: {len(expanded)}")
        print(f"  Saved to: {expanded_file}")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate questions for all projects."""
    from pcb_qa.config import DEFAULT_PROJECTS_FILE

    with open(DEFAULT_PROJECTS_FILE, 'r') as f:
        projects = json.load(f)

    all_reports: dict[str, Any] = {}

    for project_name, project_data in projects.items():
        print(f"\n{'='*60}")
        print(f"Validating questions for: {project_name}")
        print(f"{'='*60}")

        dir_path = project_data['parent_directory']
        existing_files = os.listdir(dir_path) if os.path.exists(dir_path) else []

        question_files = []
        for f in existing_files:
            if 'questions' in f and 'copy' not in f and f.endswith('.json'):
                question_files.append(f)

        circuit_json = project_data['circuit_json_file'].replace('./', '')
        spice_json = project_data['spice_json_file'].replace('./', '')

        for qfile in sorted(question_files):
            found_path = os.path.join(dir_path, qfile)

            print(f"\nValidating: {found_path}")

            with open(found_path, 'r') as qf:
                questions = json.load(qf)
            validator = CircuitQuestionValidator(circuit_json, spice_json)

            report = validator.validate_questions(questions)
            all_reports[f"{project_name}_{qfile.replace('.json', '')}"] = report

            print(f"  Total questions: {report['total_questions']}")

            for cat, stats in report["categories"].items():
                print(f"\n  {cat}:")
                print(f"    Total: {stats['total']}, Valid: {stats['valid']}, Invalid: {stats['invalid']}")
                if stats['invalid'] > 0:
                    print(f"    Sample errors (first 3):")
                    for err in stats['errors'][:3]:
                        print(f"      - {err['error']}")

    with open('validation_report.json', 'w') as f:
        json.dump(all_reports, f, indent=2)
    print(f"\n\nFull report saved to: validation_report.json")


def cmd_fix(args: argparse.Namespace) -> None:
    """Fix invalid questions for all projects."""
    from pcb_qa.config import DEFAULT_PROJECTS_FILE

    with open(DEFAULT_PROJECTS_FILE, 'r') as f:
        projects = json.load(f)

    for project_name, project_data in projects.items():
        print(f"\n{'='*60}")
        print(f"Fixing questions for: {project_name}")
        print(f"{'='*60}")

        dir_path = project_data['parent_directory']
        existing_files = os.listdir(dir_path) if os.path.exists(dir_path) else []

        question_files = []
        for f in existing_files:
            if 'questions' in f and 'copy' not in f and f.endswith('.json'):
                question_files.append(f)

        circuit_json = project_data['circuit_json_file'].replace('./', '')
        spice_json = project_data['spice_json_file'].replace('./', '')

        for qfile in sorted(question_files):
            found_path = os.path.join(dir_path, qfile)

            print(f"\nProcessing: {found_path}")

            with open(found_path, 'r') as qf:
                questions = json.load(qf)

            fixer = QuestionBankFixer(circuit_json, spice_json)
            replaced_count, fixed_count = fixer.fix_question_bank(questions)

            if replaced_count > 0:
                with open(found_path, 'w') as qf:
                    json.dump(questions, qf, indent=2)
                print(f"  Replaced {replaced_count} invalid net names")

            if fixed_count > 0:
                with open(found_path, 'w') as qf:
                    json.dump(questions, qf, indent=2)
                print(f"  Fixed {fixed_count} questions in {found_path}")
            elif replaced_count == 0:
                print(f"  No fixes needed for {found_path}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pcb-qa-question-banks",
        description="Generate, validate, and fix PCB question banks.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("expand", help="Generate balanced question banks for all projects")
    sub.add_parser("validate", help="Validate question banks against reference designs")
    sub.add_parser("fix", help="Fix invalid questions in question banks")

    args = parser.parse_args()

    commands = {
        "expand": cmd_expand,
        "validate": cmd_validate,
        "fix": cmd_fix,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()