"""KiCad netlist processor — converts ``.net`` files to hierarchical JSON.

Refactored from the original ``kicad_netlist_processer.py``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from simp_sexp import Sexp

from pcb_qa.parsers import hierarchical_reader
from pcb_qa.utils.file_ops import JSONFileOperator


class KiCadNetlistProcesser:
    """Pre-process KiCad netlists and convert them to hierarchical circuit JSON.

    Parameters
    ----------
    netlist_path:
        Filesystem path to the ``.net`` netlist file.
    output_dir:
        Directory where converted output files are written.
    project_name:
        Optional KiCad schematic path — if provided the netlist is
        exported automatically via ``kicad-cli``.
    """

    def __init__(
        self,
        netlist_path: str,
        output_dir: str | None = None,
        project_name: str | None = None,
    ) -> None:
        self.output_dir = output_dir or os.getcwd()
        self.project_name = project_name
        self.netlist_path = netlist_path

        self.json_file_operations = JSONFileOperator()
        self._top_sheet_attributes: dict[str, Any] = {}

        self.converter = hierarchical_reader.HierarchicalReader(netlist_path)

        if project_name is not None:
            self.export_project_netlist()

    # -- conversion -----------------------------------------------------------

    def convert_project_netlist_to_circuit(self) -> None:
        """Convert the KiCad netlist to a hierarchical circuit JSON dict."""
        self._top_sheet_attributes = self.converter.generate_top_sheet_circuit()

    def get_top_sheet_attributes(self) -> dict[str, Any]:
        return self._top_sheet_attributes

    def get_number_of_components(self) -> int:
        return self.find_number_of_components()

    # -- export ---------------------------------------------------------------

    def export_project_netlist(self) -> None:
        from pcb_qa.kicad.cli import KiCadInterface

        logger.info("Exporting project netlist using KiCad CLI...")
        kicad = KiCadInterface()
        kicad.export_netlist_with_kicad_cli(self.project_name, self.netlist_path)

    def export_circuit_to_file(self, output_file: str | None = None) -> None:
        if output_file is None:
            output_file = (
                self.output_dir
                + "/"
                + self.converter.get_top_sheet_source_file().split(".")[0]
                + ".json"
            )
        self.json_file_operations.write_to_json_file(self._top_sheet_attributes, output_file)

    # -- queries --------------------------------------------------------------

    def find_connections_for_trace(self, target_trace: str) -> tuple[str, list] | None:
        for name, net_connections in self._top_sheet_attributes.get("nets", {}).items():
            if name == target_trace:
                return name, net_connections
        return None

    def find_number_of_components(self) -> int:
        total = len(self._top_sheet_attributes.get("components", {}))
        for sub in self._top_sheet_attributes.get("subcircuits", []):
            total += len(sub.get("components", {}))
        return total

    def find_number_of_nets(self) -> int:
        total = len(self._top_sheet_attributes.get("nets", {}))
        for sub in self._top_sheet_attributes.get("subcircuits", []):
            total += len(sub.get("nets", {}))
        return total

    def load_circuit_from_file(self, read_file: str | None = None) -> None:
        if read_file is None:
            read_file = (
                self.output_dir
                + self._top_sheet_attributes["source_file"].split(".")[0]
                + ".json"
            )
        self._top_sheet_attributes = self.json_file_operations.read_from_json_file(read_file)

    # -- S-expression lookups -------------------------------------------------

    def _find_component_from_netlist_file(self, component_ref: str) -> str | None:
        with open(self.netlist_path, "r") as fh:
            netlist_contents = Sexp(fh.read())
        for comp in netlist_contents.search("components/comp"):
            if comp.search("comp/ref").value == component_ref:
                return comp.to_str()
        return None

    def _find_all_nets_from_netlist_file(self, component_ref: str) -> list:
        contents: list = ["nets"]
        with open(self.netlist_path, "r") as fh:
            netlist_contents = Sexp(fh.read())
        for net in netlist_contents.search("nets/net"):
            for node in net.search("net/node"):
                if node.search("node/ref").value == component_ref:
                    contents.append(["net", ["name", net.search("net/name").value], node.to_str()])
        return contents

    def find_all_entries_from_netlist_file_with(self, component_ref: str) -> Sexp:
        contents = Sexp()
        comp = self._find_component_from_netlist_file(component_ref)
        if comp is not None:
            contents.append(comp)
        nets = self._find_all_nets_from_netlist_file(component_ref)
        contents.append(nets)
        return Sexp(contents)