"""SPICE circuit parser and simulator interface.

Refactored from the original ``kicad_spice_circuit_processer.py``.
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from pcb_qa.logging_config import logger
from pcb_qa.utils.file_ops import JSONFileOperator


class KiCadSPICECircuitProcesser:
    """Parse SPICE ``.cir`` files, run ngspice simulations, and analyse results.

    Parameters
    ----------
    spice_circuit_path:
        Path to the ``.cir`` file.
    output_dir:
        Directory for simulation output files.
    project_name:
        Optional KiCad schematic — if given the SPICE file is exported
        via ``kicad-cli``.
    output_file:
        Explicit SPICE JSON output path (overrides the default).
    """

    def __init__(
        self,
        spice_circuit_path: str,
        output_dir: str | None = None,
        project_name: str | None = None,
        output_file: str | None = None,
    ) -> None:
        self.spice_circuit_path = spice_circuit_path
        self.output_dir = output_dir or os.getcwd()
        self.spice_json_file = output_file or (
            self.output_dir + "/" + os.path.basename(spice_circuit_path)
        )
        self.project_name = project_name
        self.json_file_operations = JSONFileOperator()
        self.components_needing_models: list[dict[str, Any]] = []

        if project_name is not None:
            self.export_project_spice()

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _convert_voltage_str(voltage_str: str) -> float:
        cleaned = voltage_str.upper().replace("V", ".", 1)
        return float(cleaned)

    # -- SPICE parsing --------------------------------------------------------

    def _parse_spice_netlist(self) -> dict[str, Any]:
        """Parse a ``.cir`` file into components and nets."""
        parsed_data: dict[str, Any] = {"components": {}, "nets": {}}

        with open(self.spice_circuit_path, "r") as fh:
            spice_content = fh.read()

        for line in spice_content.split("\n"):
            line = line.strip()
            if not line or line.startswith("*") or line.startswith(".") or line.lower().startswith(".end"):
                continue

            # R/C/L
            match_rcl = re.match(r"^(R|C|L)(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$", line, re.IGNORECASE)
            if match_rcl:
                comp_type = match_rcl.group(1).upper()
                ref_id = comp_type + match_rcl.group(2)
                node1, node2, value = match_rcl.group(3), match_rcl.group(4), match_rcl.group(5)
                parsed_data["components"][ref_id] = {"type": comp_type, "value": value, "nodes": [node1, node2]}
                for node in (node1, node2):
                    parsed_data["nets"].setdefault(node, []).append({"component": ref_id, "pin": node})
                continue

            # LED
            match_d = re.match(r"^(LED)(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$", line, re.IGNORECASE)
            if match_d:
                ref_id = "LED" + match_d.group(2)
                node1, node2 = match_d.group(3), match_d.group(4)
                model_name = match_d.group(5)
                parsed_data["components"][ref_id] = {"type": "LED", "model": model_name, "nodes": [node1, node2]}
                for node in (node1, node2):
                    parsed_data["nets"].setdefault(node, []).append({"component": ref_id, "pin": node})
                continue

            # U / X (ICs, subcircuits)
            match_ux = re.match(r"^(U|X)(\S+)", line, re.IGNORECASE)
            if match_ux:
                parts = line.split()
                if len(parts) >= 3:
                    ref_id = parts[0].upper()
                    model_name = parts[-1]
                    nodes = parts[1:-1]
                    parsed_data["components"][ref_id] = {"type": ref_id[0], "model": model_name, "nodes": nodes}
                    for node in nodes:
                        parsed_data["nets"].setdefault(node, []).append({"component": ref_id, "pin": node})

        return parsed_data

    # -- model helpers --------------------------------------------------------

    def _find_component_spice_models(self) -> list[dict[str, Any]]:
        self.components_needing_models = []
        parsed = self._parse_spice_netlist()

        for ref_id, comp_data in parsed["components"].items():
            comp_type = comp_data["type"].upper()
            if comp_type in ("D", "LED", "Q", "U", "X"):
                self.components_needing_models.append({
                    "ref_id": ref_id,
                    "type": comp_type,
                    "identifier": comp_data.get("model") or comp_data.get("value"),
                    "reason": f"Type '{comp_type}' requires a SPICE model definition.",
                })
            elif comp_type == "L" and "LED" in ref_id.upper():
                self.components_needing_models.append({
                    "ref_id": ref_id,
                    "type": "LED",
                    "identifier": comp_data.get("value"),
                    "reason": f"LED '{ref_id}' requires a SPICE diode model.",
                })
            elif comp_type in ("R", "C", "L"):
                value = comp_data.get("value")
                if value and not re.fullmatch(r"[\d\.]+[MGTKmunpfa]?", str(value), re.IGNORECASE):
                    self.components_needing_models.append({
                        "ref_id": ref_id,
                        "type": comp_type,
                        "identifier": value,
                        "reason": f"Non-standard value '{value}' for {comp_type}.",
                    })

        return self.components_needing_models

    @staticmethod
    def _generate_led_model(model_name: str, is_val: str = "1p", rs_val: str = "10", n_val: str = "1.7") -> str:
        return f".model {model_name} D (Is={is_val} Rs={rs_val} N={n_val})"

    def generate_spice_models(self, components: list[dict[str, Any]]) -> list[str]:
        generated: list[str] = []
        for comp in components:
            if comp["type"] == "LED":
                model_name = f"LED_D_{comp['identifier']}"
                generated.append(self._generate_led_model(model_name))
        return list(dict.fromkeys(generated))

    # -- conversion -----------------------------------------------------------

    def export_project_spice(self) -> None:
        from pcb_qa.kicad.cli import KiCadInterface

        logger.info("Exporting project SPICE circuit using KiCad CLI...")
        kicad = KiCadInterface()
        kicad.export_spice_with_kicad_cli(self.project_name, self.spice_circuit_path)

    def _normalise_spice_circuit(self):
        """Create an ngspice-compatible copy of a raw KiCad ``.cir`` file.

        KiCad SPICE exports contain capacitor/inductor values with voltage
        ratings, e.g. ``1uF/25V``.  ngspice cannot parse the ``/`` suffix, so it
        is stripped (``1uF``).  Power rails (``+3V3``, ``BAT+``) are left as-is —
        ``KiCadSPICECircuitProcesser.convert_project_spice_to_circuit`` detects
        them and appends the appropriate DC voltage sources.

        Returns the path to the normalised copy (in a temporary directory).
        """

        with open(self.spice_circuit_path, "r") as fh:
            lines = fh.readlines()

        normalised_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("*") or stripped.startswith("."):
                normalised_lines.append(line)
                continue

            # Strip voltage ratings from values: 1uF/25V -> 1uF, 10u/25V -> 10u
            line = re.sub(r"/(\d+(?:\.\d+)?)V", "", line, flags=re.IGNORECASE)
            normalised_lines.append(line)

        with open(self.spice_circuit_path, "w") as fh:
            fh.writelines(normalised_lines)

    def convert_project_spice_to_circuit(self, output_file_name: str) -> None:
        new_lines: list[str] = []
        spice_commands = "\n \n"
        power_lines = {}

        self._normalise_spice_circuit()

        with open(self.spice_circuit_path, "r") as fh:
            original_content = fh.readlines()

        first_line = original_content[0]
        last_line = original_content[-1]

        spice_model_defs = self.generate_spice_models(self._find_component_spice_models())

        for line in original_content[1:-2]:
            entries = line.split(" ")
            if len(entries) == 2:
                continue
            line = re.sub(r"GND", "0", line, flags=re.IGNORECASE)
            if "LED" in line.split(" ")[0]:
                first_word = re.sub(r"LED", "DLED", line.split(" ")[0] + " ", flags=re.IGNORECASE)
                last_word = f"LED_D_{line.split()[-1]}"
                line = first_word + " ".join(map(str, line.split(" ")[1:-1])) + " " + last_word
            new_lines.append(line)

        # Find power rails from new_lines
        for line in new_lines:
            entries = line.split(" ")
            for entry in entries:
                matches = re.findall(r"\+\d+", entry)
                if len(matches) > 0 and not entry.startswith("Net"): 
                    power_lines[entry] = True

        for power in power_lines.keys():
            spice_commands += f"V_{power[1:]} {power} 0 DC {self._convert_voltage_str(power[1:])}" + "\n"
        
        spice_commands += (
            "\n \n"
            ".control \n"
            "tran 100u 10m \n"
            "set filetype=ascii \n"
            f"write {self.output_dir}/{output_file_name}_raw.raw all \n"
            ".endc \n\n"
        )

        content = first_line + "\n" + "\n".join(spice_model_defs) + "\n\n" + "".join(new_lines) + spice_commands + last_line

        with open(os.path.join(self.output_dir, f"{output_file_name}.cir"), "w") as fh:
            fh.writelines(content)

    # -- simulation -----------------------------------------------------------

    def run_ngspice_simulation(self, input_spice_path: str, output_spice_logs: str) -> None:
        subprocess.run(["ngspice", "-b", "-o", output_spice_logs, input_spice_path], capture_output=True)
        self.retrieve_ngspice_simulated_data(output_spice_logs)

    def retrieve_ngspice_simulated_data(self, output_spice_logs: str) -> dict[str, float]:
        file_contents = ""
        ngspice_contents: dict[str, float] = {}
        with open(output_spice_logs, "r") as fh:
            for line in fh.readlines():
                if len(line) == 47:
                    file_contents += line
        file_contents = file_contents.strip().split("\n")[2:]
        for line in file_contents:
            words = line.split(" ")
            ngspice_contents[words[0]] = float(words[-1])
        return ngspice_contents

    def parse_spice_simulated_data(self, output_raw_file_path: str) -> dict[str, Any]:
        with open(output_raw_file_path, 'r') as f:
            raw_content = f.read()

        num_vars = re.search(r'No\. Variables:\s*(\d+)', raw_content, re.IGNORECASE)
        num_points = re.search(r'No\. Points:\s*(\d+)', raw_content, re.IGNORECASE)

        print(f"No. of variables from SPICE simulated file: {int(num_vars.group(1))}")
        print(f"No. of points from SPICE simulated file: {int(num_points.group(1))}")

        ngspice_contents = {}

        variables_section_match = re.search(r'Variables:\n(.*?)(?:\n[\w ]+:\s*\S+|\Z)', raw_content, re.DOTALL)

        if variables_section_match:
            variables_text = variables_section_match.group(1).strip()
            for var_line in variables_text.split('\n'):
                if var_line.strip():
                    parts = var_line.strip().split('\t')
                    if len(parts) >= 3:
                        idx = parts[0]
                        name = parts[1]
                        ngspice_contents[idx] = {'name': name, 'values': {}}

        values_section_match = re.search(r'Values:\n(.*)', raw_content, re.DOTALL) 
        
        if values_section_match:
            values_text = values_section_match.group(1).strip()
            for val_line in values_text.split('\n'):
                if val_line.strip():
                    values = val_line.strip().split('\t')
                    if (len(values) > 1):
                        count = 0 # First line
                        data_point = values[0]
                        ngspice_contents[f"{count}"]['values'][f"{data_point}"] = values[1]
                    else:
                        count = count + 1
                        ngspice_contents[f"{count}"]['values'][f"{data_point}"] = values[0]

        return ngspice_contents

    def check_steady_state_average_matches_expected_voltage(
        self,
        spice_json_file: str,
        net_name: str,
        expected_voltage: str,
    ) -> bool:
        """Check if the steady-state average of the last 10 voltage values matches."""
        spice_contents = self.json_file_operations.read_from_json_file(spice_json_file)

        for entry in spice_contents:
            signal_match = re.search(r"v\(([^)]+)\)", spice_contents[entry]["name"])
            if signal_match and signal_match.group(1).lower() == net_name.lower():
                values = [float(v) for v in spice_contents[entry]["values"].values()][-10:]
                rounded_avg = round(sum(values) / len(values), 2)
                return rounded_avg == float(expected_voltage.replace("V", ""))

        return False

    def find_all_entries_from_SPICE_circuit_with(self, net_name: str) -> list[str]:
        relevant_lines: list[str] = []
        with open(self.spice_circuit_path) as fh:
            for line in fh.readlines():
                if net_name.upper() in line:
                    relevant_lines.append(line)
        return list(set(relevant_lines))