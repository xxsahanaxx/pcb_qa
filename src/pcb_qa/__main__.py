"""CLI entry point for the PCB QA framework.

Usage::

    # Run a full evaluation
    pcb-qa evaluate

    # Initialise KiCad CLI symlink
    pcb-qa init-kicad

    # Show project info
    pcb-qa projects

    # Convert a KiCad SPICE .cir file to SPICE circuit JSON
    pcb-qa convert-spice path/to/circuit.cir
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile

from pcb_qa.models.tool_definitions import ToolMode
from pcb_qa.utils.file_ops import JSONFileOperator


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


def cmd_convert_netlist(args: argparse.Namespace) -> None:
    """Convert a KiCad netlist (.net) to hierarchical circuit JSON.

    Usage::

        pcb-qa convert-netlist path/to/netlist.net
        pcb-qa convert-netlist path/to/netlist.net --output-dir ./output
        pcb-qa convert-netlist path/to/netlist.net --output-file ./output/circuit.json
        pcb-qa convert-netlist path/to/netlist.net --project-name MyProject
    """
    from pcb_qa.parsers.netlist import KiCadNetlistProcesser

    processor = KiCadNetlistProcesser(
        netlist_path=args.netlist_path,
        output_dir=args.output_dir,
        project_name=args.project_name,
    )
    processor.convert_project_netlist_to_circuit()
    processor.export_circuit_to_file(output_file=args.output_file)
    print(f"Circuit JSON written to {args.output_file or processor.output_dir}")


def cmd_convert_spice(args: argparse.Namespace) -> None:
    """Convert a SPICE .cir file to SPICE circuit JSON.

    The pipeline uses the ``KiCadSPICECircuitProcesser`` flow:

    1. The raw KiCad ``.cir`` is normalised so ngspice can parse it
       (ratings stripped, power sources added).
    2. ``convert_project_spice_to_circuit`` builds a simulation-ready ``.cir``
       (appends ngspice ``.control``/``.endc`` commands that write a ``.raw`` file).
    3. ``run_ngspice_simulation`` runs ngspice in batch mode on the converted file.
    4. ``parse_spice_simulated_data`` parses the generated ``.raw`` file into the
       ``{index: {"name": ..., "values": {...}}}`` structure and writes the
       SPICE circuit JSON.

    Usage::

        pcb-qa convert-spice path/to/circuit.cir
        pcb-qa convert-spice path/to/circuit.cir --output-dir ./output
        pcb-qa convert-spice path/to/circuit.cir --output-file ./output/circuit.json
        pcb-qa convert-spice path/to/circuit.cir --project-name MyProject
    """
    from pcb_qa.parsers.spice import KiCadSPICECircuitProcesser

    spice_path = args.spice_circuit_path
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(spice_path))
    stem = os.path.splitext(os.path.basename(spice_path))[0]
    output_file = args.output_file or os.path.join(output_dir, f"{stem}_SPICE_circuit.json")

    processor = KiCadSPICECircuitProcesser(
        spice_circuit_path=spice_path,
        output_dir=output_dir
    )

    # 2. Build the simulation-ready .cir (adds .control/.endc + .raw write).
    #    Use a distinct name so the original input .cir is not overwritten.
    converted_stem = f"{stem}_converted"
    processor.convert_project_spice_to_circuit(converted_stem)

    # 3. Run the ngspice simulation on the converted netlist
    converted_cir = f"{converted_stem}.cir"
    processor.run_ngspice_simulation(converted_cir, f"{stem}_logs.txt")

    # 4. Parse the simulated .raw file into the SPICE JSON structure
    raw_file = os.path.join(output_dir, f"{converted_stem}_raw.raw")
    simulated_data = processor.parse_spice_simulated_data(raw_file)
    
    if os.path.exists(os.path.join(output_dir, f"{stem}_logs.txt")):
        os.remove(os.path.join(output_dir, f"{stem}_logs.txt"))

    # 5. Write the SPICE circuit JSON
    JSONFileOperator.write_to_json_file(simulated_data, output_file)
    print(f"SPICE circuit JSON written to {output_file}")


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

    # -- convert-netlist subcommand -------------------------------------------
    netlist_parser = sub.add_parser(
        "convert-netlist",
        help="Convert a KiCad .net file to hierarchical circuit JSON",
    )
    netlist_parser.add_argument(
        "netlist_path",
        type=str,
        help="Path to the KiCad netlist (.net) file",
    )
    netlist_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory where the output JSON is written (default: current working directory)",
    )
    netlist_parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Explicit output file path (overrides --output-dir)",
    )
    netlist_parser.add_argument(
        "--project-name",
        type=str,
        default=None,
        help="Optional KiCad project name — if set, the netlist is exported via kicad-cli first",
    )

    # -- convert-spice subcommand ---------------------------------------------
    spice_parser = sub.add_parser(
        "convert-spice",
        help="Convert a SPICE .cir file to SPICE circuit JSON (via ngspice simulation)",
    )
    spice_parser.add_argument(
        "spice_circuit_path",
        type=str,
        help="Path to the SPICE circuit (.cir) file",
    )
    spice_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=(
            "Directory where the converted .cir, .raw, logs and JSON are written "
            "(default: the input file's directory)"
        ),
    )
    spice_parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help=(
            "Explicit output JSON file path (overrides --output-dir; "
            "default: <output-dir>/<stem>_SPICE_circuit.json)"
        ),
    )
    spice_parser.add_argument(
        "--project-name",
        type=str,
        default=None,
        help="Optional KiCad project name — if set, the SPICE file is exported via kicad-cli first",
    )

    args = parser.parse_args()

    commands = {
        "run": cmd_run,
        "evaluate": cmd_evaluate,
        "init-kicad": cmd_init_kicad,
        "projects": cmd_projects,
        "embed": cmd_embed,
        "convert-netlist": cmd_convert_netlist,
        "convert-spice": cmd_convert_spice,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()