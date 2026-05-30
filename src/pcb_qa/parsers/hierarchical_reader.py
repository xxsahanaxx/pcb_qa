"""Hierarchical netlist reader.

Adapted from ``skidl.netlist_to_skidl.HierarchicalConverter`` — only the
reading/analysis portion is kept, and the result is a custom
:class:`netlist_sexp.NetlistSexp` plus a :class:`circuit_json.CircuitJSON`.

Refactored from the original ``hierarchical_reader.py``.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

from simp_sexp import Sexp
from skidl.logger import active_logger
from skidl.netlist_to_skidl import Sheet, find_common_path_prefix, legalize_name

from pcb_qa.parsers import circuit_json, netlist_sexp


class HierarchicalReader:
    """Convert a KiCad netlist into a hierarchical structure.

    Parameters
    ----------
    src:
        Path to a KiCad netlist file, a file-like object, or a raw string
        containing netlist data.
    """

    def __init__(self, src: str | Any) -> None:
        try:
            text = src.read()
        except Exception:
            try:
                text = open(src, "r", encoding="latin_1").read()
            except Exception:
                text = src

        self.netlist = netlist_sexp.NetlistSexp(Sexp(text))
        self.circuit_json = circuit_json.CircuitJSON()

        self.sheets: dict[str, Sheet] = {}
        self.tab = " " * 4
        self.top_sheet: Sheet | None = None
        self.net_hierarchy: dict[str, Any] = {}
        self.net_usage: dict[str, Any] = {}

        self._initialise_converter()

    # -- hierarchy helpers -----------------------------------------------------

    def find_lowest_common_ancestor(self, sheet1: str, sheet2: str) -> str:
        return find_common_path_prefix(self.sheets[sheet1].path, self.sheets[sheet2].path)

    def extract_sheet_info(self) -> None:
        """Populate ``self.sheets`` with :class:`Sheet` objects from the netlist."""
        active_logger.info("=== Extracting Sheet Info ===")

        if getattr(self.netlist, "sheets", None):
            sheet_numbers_paths = [(s.num, s.name) for s in self.netlist.sheets]
            sheet_paths = [p[1] for p in sheet_numbers_paths]
        else:
            sheet_paths = list({p.sheetpath for p in self.netlist.components})
            sheet_numbers_paths = enumerate(sheet_paths)

        for sheet_number, sheet_path in sheet_numbers_paths:
            parent = os.path.dirname(sheet_path.rstrip("/"))
            if parent:
                if not parent.endswith("/"):
                    parent += "/"
                name = os.path.basename(sheet_path.rstrip("/"))
            else:
                name = ""

            sheet = Sheet(
                number=sheet_number,
                path=sheet_path,
                name=name,
                parent=parent,
                components=[],
                local_nets=set(),
                imported_nets=set(),
                children=[],
            )
            if not parent:
                self.top_sheet = sheet
            self.sheets[sheet_path] = sheet
            active_logger.info(f"  Found sheet: '{sheet.path}', name='{sheet.name}', parent='{sheet.parent}'")

        for sheet in self.sheets.values():
            parent_sheet = self.sheets.get(sheet.parent)
            if parent_sheet:
                parent_sheet.children.append(sheet.path)

        active_logger.info("=== Completed extracting sheet info ===")

    def assign_components_to_sheets(self) -> None:
        active_logger.info("=== Assigning Components to Sheets ===")
        for comp in self.netlist.components:
            sheet_path = comp.sheetpath
            if sheet_path in self.sheets:
                self.sheets[sheet_path].components.append(comp)
        active_logger.info("=== Completed assigning components to sheets ===")

    def analyze_nets(self) -> None:
        """Analyze net usage to determine origins and required connections."""

        def find_net_src_dests(net_sheets: list[str]) -> tuple[str, set[str]]:
            src = net_sheets[0]
            for sheet in net_sheets[1:]:
                src = self.find_lowest_common_ancestor(src, sheet)

            dests: set[str] = set()
            src_len = len(src)
            for sheet in set(net_sheets) - {src}:
                sheet = sheet.rstrip("/")
                path_src_to_sheet = sheet[src_len:]
                for piece in path_src_to_sheet.split("/"):
                    path = src + piece + "/"
                    dests.add(path)
            return src, dests

        active_logger.info("=== Starting Net Analysis ===")

        net_usage: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

        for net in self.netlist.nets:
            for pin in net.pins:
                for comp in self.netlist.components:
                    if comp.ref == pin.name:
                        net_usage[net.name][comp.sheetpath].add(f"{comp.ref}.{pin.number}")

        net_hierarchy: dict[str, dict[str, Any]] = {}
        for net_name, sheet_pins in net_usage.items():
            used_sheets = list(sheet_pins.keys())
            origin_sheet, _ = find_net_src_dests(used_sheets)
            destination_sheets = list(set(used_sheets) - {origin_sheet})
            net_hierarchy[net_name] = {
                "origin_sheet": origin_sheet,
                "destination_sheets": destination_sheets,
            }

        for sheet in self.sheets.values():
            sheet.local_nets.clear()
            sheet.imported_nets.clear()

        for net_name, hierarchy in net_hierarchy.items():
            if net_name.startswith("unconnected"):
                continue
            self.sheets[hierarchy["origin_sheet"]].local_nets.add(net_name)
            for dest_sheet in hierarchy["destination_sheets"]:
                self.sheets[dest_sheet].imported_nets.add(net_name)

        self.net_hierarchy = net_hierarchy
        self.net_usage = net_usage
        active_logger.info("=== Completed net analysis ===")

    def cull_from_top(self) -> None:
        """Remove unnecessary empty top-level sheets."""
        top_sheet = self.top_sheet
        while (
            not top_sheet.parent
            and not (top_sheet.components or top_sheet.local_nets)
            and len(top_sheet.children) == 1
        ):
            top_sheet = self.sheets[self.top_sheet.children[0]]
            top_sheet.name = self.top_sheet.name
            del self.sheets[self.top_sheet.path]
            top_sheet.parent = ""
            self.top_sheet = top_sheet

        sheet_names = [s.name for s in self.sheets.values() if s.parent]
        top_sheet_name = "top"
        while top_sheet_name in sheet_names:
            top_sheet_name += "0"
        self.top_sheet.name = top_sheet_name

    # -- circuit JSON generation -----------------------------------------------

    def _assign_components_for_sheet(self, components_list: list) -> dict:
        return {comp.ref: comp.component_sexp_to_dict() for comp in components_list}

    def _assign_connected_nets_for_sheet(self, components_list: list) -> dict:
        current_sheet_nets: dict[str, Any] = {}
        for net in self.netlist.nets:
            legal_name = legalize_name(net.name)
            if not legal_name.startswith("unconnected"):
                net_obj = net.net_sexp_to_dict(components_list)
                if net_obj:
                    current_sheet_nets[legal_name] = net_obj
        return current_sheet_nets

    def create_circuit_dict_from_sheet(self, sheet: Sheet) -> dict[str, Any]:
        sheet_attributes: dict[str, Any] = {}
        sheet_sexp = self.get_sheet_sexp_from_sheet(sheet)
        if sheet_sexp is not None:
            sheet_attributes["name"] = sheet.name
            sheet_attributes["source_file"] = sheet_sexp.source

        sheet_components = self.retrieve_components_for_sheet(sheet)
        sheet_attributes["components"] = self._assign_components_for_sheet(sheet_components)
        sheet_attributes["nets"] = self._assign_connected_nets_for_sheet(sheet_components)

        return self.circuit_json.generate_circuit_dict_from_attributes(sheet_attributes)

    def generate_subcircuits_for_top_sheet_circuit(self) -> list[dict[str, Any]]:
        return [self.create_circuit_dict_from_sheet(s) for s in self.sheets.values() if s.name != "top"]

    def generate_top_sheet_circuit(self) -> dict[str, Any]:
        top_sheet_circuit: dict[str, Any] = {}
        subcircuits = self.generate_subcircuits_for_top_sheet_circuit()

        for sheet in self.sheets.values():
            if sheet.name == "top":
                top_sheet_circuit = self.create_circuit_dict_from_sheet(sheet)

        top_sheet_circuit["subcircuits"] = subcircuits
        return top_sheet_circuit

    def get_sheet_sexp_from_sheet(self, sheet: Sheet) -> netlist_sexp.SheetSexp | None:
        for sheet_obj in self.netlist.sheets:
            if sheet.path == sheet_obj.name:
                return sheet_obj
        return None

    def get_top_sheet_source_file(self) -> str:
        return self.generate_top_sheet_circuit()["source_file"]

    def _initialise_converter(self) -> None:
        self.extract_sheet_info()
        self.assign_components_to_sheets()
        self.analyze_nets()
        self.cull_from_top()

    def retrieve_components_for_sheet(self, sheet: Sheet) -> list:
        return sheet.components