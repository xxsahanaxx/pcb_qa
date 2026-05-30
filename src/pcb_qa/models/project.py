"""Project data models.

Refactored from the original ``project_files.py`` — keeps the clean
class-based representation and drops the legacy function-based helpers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pcb_qa.config import load_projects_config


@dataclass
class Project:
    """Represents a single hardware project's file layout.

    Attributes
    ----------
    name:
        Human-readable project name / key.
    parent_directory:
        Root output directory for the project.
    circuit_json_file:
        Path to the hierarchical circuit JSON.
    netlist_file:
        Path to the KiCad netlist (``.net``).
    spice_circuit_file:
        Path to the SPICE circuit description (``.cir``).
    spice_json_file:
        Path to the SPICE JSON representation.
    questions_json_file:
        Path to the benchmark questions JSON.
    datasheet_files:
        List of PDF datasheet paths for components.
    """

    name: str = ""
    parent_directory: str = ""
    circuit_json_file: str = ""
    netlist_file: str = ""
    spice_circuit_file: str = ""
    spice_json_file: str = ""
    questions_json_file: str = ""
    datasheet_files: list[str] = field(default_factory=list)

    # -- helpers ---------------------------------------------------------------

    def find_datasheet_for_component(self, component_ref: str) -> str:
        """Return the first datasheet path containing *component_ref*, or ``""``."""
        for ds in self.datasheet_files:
            if component_ref in ds:
                return ds
        return ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary (handy for JSON output)."""
        return {
            "name": self.name,
            "parent_directory": self.parent_directory,
            "circuit_json_file": self.circuit_json_file,
            "netlist_file": self.netlist_file,
            "spice_circuit_file": self.spice_circuit_file,
            "spice_json_file": self.spice_json_file,
            "questions_json_file": self.questions_json_file,
            "datasheet_files": self.datasheet_files,
        }


class ProjectFiles:
    """Registry of all benchmark projects loaded from configuration.

    Projects are defined in ``configs/projects.json``.  Each entry is
    converted into a :class:`Project` instance.
    """

    def __init__(self, config_path: str | None = None) -> None:
        raw = load_projects_config(config_path)
        self.projects: dict[str, Project] = {}
        for key, data in raw.items():
            self.projects[key] = Project(
                name=key,
                parent_directory=data["parent_directory"],
                circuit_json_file=data["circuit_json_file"],
                netlist_file=data["netlist_file"],
                spice_circuit_file=data["spice_circuit_file"],
                spice_json_file=data["spice_json_file"],
                questions_json_file=data["questions_json_file"],
                datasheet_files=data.get("datasheet_files", []),
            )

    def __getitem__(self, key: str) -> Project:
        return self.projects[key]

    def __iter__(self):
        return iter(self.projects)

    def keys(self):
        return self.projects.keys()

    def items(self):
        return self.projects.items()

    def to_json(self, output_path: str | None = None) -> dict[str, Any]:
        """Return (and optionally write) a JSON-serialisable dict of all projects."""
        result = {k: v.to_dict() for k, v in self.projects.items()}
        if output_path:
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=3, ensure_ascii=False)
        return result