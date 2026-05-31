"""Shared fixtures for the pcb_qa test suite."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def sample_circuit_dict() -> dict[str, Any]:
    """Return a minimal hierarchical circuit JSON dictionary."""
    return {
        "name": "TestBoard",
        "description": "A test board",
        "source_file": "TestBoard.kicad_sch",
        "tstamps": "abc123",
        "components": {
            "R1": {
                "symbol": "Device:R",
                "ref": "R1",
                "value": "10k",
                "footprint": "R_0603_1608Metric",
                "datasheet": "",
                "description": "Resistor",
                "properties": {"Power": "0.1W"},
                "tstamps": "abc123",
                "fields": {"Datasheet": "", "Description": "Resistor"},
                "pins": [],
            },
            "C1": {
                "symbol": "Device:C",
                "ref": "C1",
                "value": "100n",
                "footprint": "C_0603_1608Metric",
                "datasheet": "",
                "description": "Capacitor",
                "properties": {},
                "tstamps": "abc123",
                "fields": {},
                "pins": [],
            },
        },
        "nets": {
            "VCC": [
                {
                    "component": "R1",
                    "pin": {"name": "R1", "number": "1", "type": "passive"},
                }
            ],
            "GND": [
                {
                    "component": "C1",
                    "pin": {"name": "C1", "number": "2", "type": "passive"},
                }
            ],
            "net_VCC_0": [
                {
                    "component": "R1",
                    "pin": {"name": "R1", "number": "2", "type": "passive"},
                },
                {
                    "component": "C1",
                    "pin": {"name": "C1", "number": "1", "type": "passive"},
                },
            ],
        },
        "subcircuits": [],
        "annotations": [],
    }


@pytest.fixture
def sample_circuit_dict_with_subcircuits(sample_circuit_dict: dict[str, Any]) -> dict[str, Any]:
    """Return a circuit dict that includes one subcircuit."""
    circuit = sample_circuit_dict.copy()
    circuit["subcircuits"] = [
        {
            "name": "PowerSupply",
            "description": "Power supply subcircuit",
            "source_file": "PowerSupply.kicad_sch",
            "tstamps": "ps123",
            "components": {
                "U1": {
                    "symbol": "Regulator:LM1117",
                    "ref": "U1",
                    "value": "3.3V",
                    "footprint": "SOT-223",
                    "datasheet": "",
                    "description": "Voltage regulator",
                    "properties": {},
                    "tstamps": "ps123",
                    "fields": {},
                    "pins": [],
                }
            },
            "nets": {
                "GND": [
                    {
                        "component": "U1",
                        "pin": {"name": "U1", "number": "3", "type": "passive"},
                    }
                ],
                "net_VCC_0": [
                    {
                        "component": "U1",
                        "pin": {"name": "U1", "number": "1", "type": "passive"},
                    }
                ],
            },
        }
    ]
    return circuit


@pytest.fixture
def sample_projects_config() -> dict[str, Any]:
    """Return a minimal projects configuration dictionary."""
    return {
        "TestProject": {
            "parent_directory": "./outputs/TestProject",
            "circuit_json_file": "./outputs/TestProject/test.json",
            "netlist_file": "./outputs/TestProject/test.net",
            "spice_circuit_file": "./outputs/TestProject/test.cir",
            "spice_json_file": "./outputs/TestProject/test_SPICE_circuit.json",
            "questions_json_file": "./outputs/TestProject/test_60_questions.json",
            "datasheet_files": [
                "./outputs/TestProject/datasheets/U1.pdf",
                "./outputs/TestProject/datasheets/R1.pdf",
            ],
        }
    }


@pytest.fixture
def sample_spice_circuit_content() -> str:
    """Return a minimal SPICE circuit (.cir) file content."""
    return """\
* Test SPICE Circuit
R1 net1 0 1k
C1 net1 0 100n
V1 net1 0 DC 3.3V
.tran 1u 10m
.end
"""


@pytest.fixture
def sample_spice_circuit_with_led() -> str:
    """Return SPICE circuit content with LED components."""
    return """\
* Test SPICE Circuit with LED
LED1 net1 0 LED_RED
R1 net1 VCC 470
V1 VCC 0 DC 5V
.tran 1u 10m
.end
"""