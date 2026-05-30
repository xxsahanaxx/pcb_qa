"""Hierarchical circuit JSON parser.

Refactored from the original ``circuit_json.py``.
"""

from __future__ import annotations

import json
from typing import Any


class CircuitJSON:
    """Parse and query a hierarchical circuit JSON file.

    Parameters
    ----------
    circuit_file:
        Path to the JSON file.  If ``None`` the object starts empty and
        can be populated via :meth:`generate_circuit_dict_from_attributes`.
    """

    ACTIVE_KEYWORDS: list[str] = [
        "mcu", "processor", "controller", "regulator", "opamp", "transistor",
        "diode", "logic", "memory", "sensor", "adc", "dac", "fpga", "asic",
        "ic", "amplifier", "switching", "microcontroller", "crystal", "stm32",
        "ina219", "pca9685",
    ]
    PASSIVE_KEYWORDS: list[str] = ["resistor", "capacitor", "inductor", "ferrite", "bead", "jumper", "testpoint"]
    POWER_KEYWORDS: list[str] = ["gnd", "vcc", "_p"]

    def __init__(self, circuit_file: str | None = None) -> None:
        self.top_level_circuit: dict[str, Any] = {}
        self.all_components: list[str] = []
        self.active_components: list[str] = []
        self.passive_components: list[str] = []

        if circuit_file is not None:
            with open(circuit_file) as fh:
                self.top_level_circuit = json.load(fh)
            self._initialise_component_lists()

    # -- private helpers -------------------------------------------------------

    @staticmethod
    def _populate_empty_circuit() -> dict[str, Any]:
        return {
            "name": "",
            "description": "",
            "source_file": "",
            "tstamps": "",
            "components": {},
            "nets": {},
            "subcircuits": [],
            "annotations": [],
        }

    def _initialise_component_lists(self) -> None:
        for subcircuit in self.top_level_circuit.get("subcircuits", []):
            connections = self.get_net_connections("GND", subcircuit["name"])
            for conn in connections:
                if conn["pin"]["type"] == "passive" and conn["component"] not in self.passive_components:
                    self.passive_components.append(conn["component"])

        connections = self.get_net_connections("GND")
        for conn in connections:
            if conn["pin"]["type"] == "passive" and conn["component"] not in self.passive_components:
                self.passive_components.append(conn["component"])

    # -- public API ------------------------------------------------------------

    def generate_circuit_dict_from_attributes(self, sheet_attributes: dict[str, Any]) -> dict[str, Any]:
        """Build a circuit dictionary from the given *sheet_attributes*."""
        sheet_contents = self._populate_empty_circuit()
        for attr, value in sheet_attributes.items():
            sheet_contents[attr] = value
        return sheet_contents

    def get_net_connections(self, net_name: str, subcircuit_name: str | None = None) -> list[dict[str, Any]]:
        """Return the list of connections for *net_name*.

        Parameters
        ----------
        net_name:
            The electrical net to search for.
        subcircuit_name:
            If provided, search within that subcircuit; otherwise search
            the top-level circuit.
        """
        target_nets = None
        if subcircuit_name is None:
            target_nets = self.top_level_circuit.get("nets", {})
        else:
            for subcircuit in self.top_level_circuit.get("subcircuits", []):
                if subcircuit["name"] == subcircuit_name:
                    target_nets = subcircuit.get("nets", {})
                    break
        if target_nets and net_name in target_nets:
            return target_nets[net_name]
        return []

    def find_component_from_circuit(self, component_ref: str) -> tuple[str | None, dict | None]:
        """Locate a component by reference designator.

        Returns
        -------
        tuple[str | None, dict | None]:
            ``(subcircuit_name, component_dict)`` or ``(None, None)`` if not found.
        """
        if self.top_level_circuit:
            if component_ref in self.top_level_circuit.get("components", {}):
                return None, self.top_level_circuit["components"][component_ref]
            for subcircuit in self.top_level_circuit.get("subcircuits", []):
                if component_ref in subcircuit.get("components", {}):
                    return subcircuit["name"], subcircuit["components"][component_ref]
        return None, None

    def is_component_in_net_from_circuit(self, component_ref: str, net_name: str) -> bool:
        """Check whether *component_ref* is connected to *net_name*."""
        if self.top_level_circuit:
            if component_ref in self.top_level_circuit.get("components", {}) and net_name in self.top_level_circuit.get("nets", {}):
                for conn in self.top_level_circuit["nets"][net_name]:
                    if component_ref in conn["component"]:
                        return True
            for subcircuit in self.top_level_circuit.get("subcircuits", []):
                if component_ref in subcircuit.get("components", {}) and net_name in subcircuit.get("nets", {}):
                    for conn in subcircuit["nets"][net_name]:
                        if component_ref in conn["component"]:
                            return True
        return False