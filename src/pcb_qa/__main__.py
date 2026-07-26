"""CLI entry point for the PCB QA framework.

Usage::

    # Run a full evaluation
    pcb-qa evaluate

    # Initialise KiCad CLI symlink
    pcb-qa init-kicad

    # Show project info
    pcb-qa projects
"""

from __future__ import annotations

import argparse
import sys

from pcb_qa.models.tool_definitions import ToolMode


def cmd_evaluate(args: argparse.Namespace) -> None:
    from pcb_qa.evaluation.compute_results.evaluator import EvaluateResults

    evaluator = EvaluateResults()
    evaluator.write_nnet_and_ncir_responses_to_csv()
    evaluator.write_nnet_and_pcir_responses_to_csv()
    evaluator.write_pnet_and_ncir_responses_to_csv()
    evaluator.write_pnet_and_pcir_responses_to_csv()
    evaluator.write_schematic_as_pdfs_responses_to_csv()


def cmd_run(args: argparse.Namespace) -> None:
    """Run LLM agents against benchmark questions for all projects."""
    from pcb_qa.evaluation.run_benchmark.runner import run_benchmark

    run_benchmark(tool_mode=args.mode, starting_index=args.start)


def cmd_init_kicad(args: argparse.Namespace) -> None:
    from pcb_qa.kicad.cli import KiCadInterface

    KiCadInterface()


def cmd_projects(args: argparse.Namespace) -> None:
    from pcb_qa.config import load_projects_config

    config = load_projects_config()
    for name, data in config.items():
        print(f"\n  {name}")
        for key, value in data.items():
            if key != "datasheet_files":
                print(f"    {key}: {value}")
            else:
                print(f"    datasheet_files: [{len(value)} files]")
    print()


def cmd_embed(args: argparse.Namespace) -> None:
    """Embed datasheets for all projects."""
    from pcb_qa.models.project import ProjectFiles
    from pcb_qa.tools.caller import ToolCaller

    caller = ToolCaller()
    projects = ProjectFiles()
    for name, project in projects.items():
        print(f"Embedding datasheets for {name}...")
        caller.find_and_embed_datasheets_for_project(project)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pcb-qa",
        description="PCB Question Answer Benchmark — evaluate LLMs on PCB circuit analysis.",
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run LLM agents against benchmark questions")
    run_parser.add_argument(
        "--mode",
        type=ToolMode,
        default=ToolMode.NNET_AND_NCIR,
        help="Tool mode (default: NNet&NCir)",
    )
    run_parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Starting question index (default: 0)",
    )
    sub.add_parser("evaluate", help="Run the full evaluation pipeline across all projects and models")
    sub.add_parser("init-kicad", help="Create kicad-cli symlink from KICAD_CLI_PATH env var")
    sub.add_parser("projects", help="List configured projects and their file paths")
    sub.add_parser("embed", help="Embed datasheets for all projects (FAISS indexing)")

    args = parser.parse_args()

    commands = {
        "run": cmd_run,
        "evaluate": cmd_evaluate,
        "init-kicad": cmd_init_kicad,
        "projects": cmd_projects,
        "embed": cmd_embed,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()