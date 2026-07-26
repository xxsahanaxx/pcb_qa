"""Tests for the question_banks.generator module."""

from __future__ import annotations

import json

import pytest

from pcb_qa.question_banks.generator import (
    DATASHEET_PROPERTIES,
    SPICE_QUESTION_TEMPLATES,
    VOLTAGE_LEVELS,
    extract_components_from_circuit,
    extract_nets_from_circuit,
    extract_nets_from_spice,
    format_property,
    generate_datasheet_questions_balanced,
    generate_spice_questions_balanced,
    generate_layout_questions_balanced,
    get_component_net_connections,
)


@pytest.fixture
def minimal_circuit_json(tmp_path):
    """Write a minimal circuit JSON file and return its path."""
    data = {
        "components": {
            "U1": {"ref": "U1", "value": "LM1117"},
            "R1": {"ref": "R1", "value": "10k"},
            "C1": {"ref": "C1", "value": "100n"},
        },
        "nets": {
            "VCC": [{"component": "U1", "pin": {"number": "1"}}],
            "GND": [
                {"component": "U1", "pin": {"number": "3"}},
                {"component": "C1", "pin": {"number": "2"}},
            ],
            "NET1": [{"component": "R1", "pin": {"number": "1"}}],
        },
        "subcircuits": [],
    }
    path = tmp_path / "circuit.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return str(path)


@pytest.fixture
def circuit_json_with_ics(tmp_path):
    """Write a circuit JSON with IC components and return its path."""
    data = {
        "components": {
            "U1": {"ref": "U1", "value": "LM1117-3.3"},
            "U2": {"ref": "U2", "value": "STM32F103"},
            "U3": {"ref": "U3", "value": "MCP2515"},
            "REG1": {"ref": "REG1", "value": "AMS1117"},
            "R1": {"ref": "R1", "value": "10k"},
            "C1": {"ref": "C1", "value": "100n"},
        },
        "nets": {
            "VCC": [{"component": "U1", "pin": {"number": "3"}}],
            "GND": [{"component": "U1", "pin": {"number": "1"}}],
            "CAN_H": [{"component": "U3", "pin": {"number": "7"}}],
        },
        "subcircuits": [],
    }
    path = tmp_path / "circuit_ics.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return str(path)


@pytest.fixture
def minimal_spice_json(tmp_path):
    """Write a minimal SPICE simulation JSON file and return its path."""
    data = {
        "VCC": {
            "name": "v(VCC)",
            "values": {"0": 3.3, "1": 3.3, "2": 3.3},
        },
        "GND": {
            "name": "v(GND)",
            "values": {"0": 0.0, "1": 0.0, "2": 0.0},
        },
    }
    path = tmp_path / "spice.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return str(path)


class TestExtractFunctions:
    """Tests for extract_components/nets functions."""

    def test_extract_components_from_circuit(self, minimal_circuit_json):
        comps = extract_components_from_circuit(minimal_circuit_json)
        assert "U1" in comps
        assert "R1" in comps
        assert "C1" in comps
        assert len(comps) == 3

    def test_extract_components_with_subcircuits(self, tmp_path):
        data = {
            "components": {"R1": {}},
            "subcircuits": [{"components": {"U1": {}, "U2": {}}, "nets": {}}],
        }
        path = tmp_path / "subcircuit.json"
        with open(path, "w") as f:
            json.dump(data, f)
        comps = extract_components_from_circuit(str(path))
        assert len(comps) == 3

    def test_extract_components_file_not_found(self):
        comps = extract_components_from_circuit("/nonexistent/file.json")
        assert comps == []

    def test_extract_nets_from_circuit(self, minimal_circuit_json):
        nets = extract_nets_from_circuit(minimal_circuit_json)
        assert "VCC" in nets
        assert "GND" in nets
        assert "NET1" in nets
        assert len(nets) == 3

    def test_extract_nets_from_spice(self, minimal_spice_json):
        nets = extract_nets_from_spice(minimal_spice_json)
        assert "VCC" in nets
        assert "GND" in nets

    def test_extract_nets_from_spice_file_not_found(self):
        nets = extract_nets_from_spice("/nonexistent/file.json")
        assert nets == []


class TestGetComponentNetConnections:
    """Tests for get_component_net_connections."""

    def test_basic_connections(self, minimal_circuit_json):
        connections = get_component_net_connections(minimal_circuit_json)
        assert "U1" in connections
        assert "R1" in connections
        assert "C1" in connections
        assert "VCC" in connections["U1"]
        assert "GND" in connections["U1"]

    def test_file_not_found(self):
        connections = get_component_net_connections("/nonexistent/file.json")
        assert connections == {}


class TestDatasheetQuestionGeneration:
    """Tests for generate_datasheet_questions_balanced."""

    def test_generates_balanced_questions(self, circuit_json_with_ics):
        components = extract_components_from_circuit(circuit_json_with_ics)
        questions = generate_datasheet_questions_balanced(components, count=80)

        assert len(questions) == 80

        yes_count = sum(1 for q in questions if q["answer"] == "YES")
        no_count = sum(1 for q in questions if q["answer"] == "NO")
        assert yes_count == 40
        assert no_count == 40

        for q in questions:
            assert q["category"] == "component_datasheet"
            assert q["question"].startswith("Does the component")
            assert "according to its datasheet" in q["question"]

    def test_not_enough_ics(self):
        questions = generate_datasheet_questions_balanced(["R1", "C1", "R2"], count=80)
        assert questions == []

    def test_empty_components_list(self):
        questions = generate_datasheet_questions_balanced([], count=80)
        assert questions == []

    def test_no_duplicates(self, circuit_json_with_ics):
        components = extract_components_from_circuit(circuit_json_with_ics)
        questions = generate_datasheet_questions_balanced(components, count=20)
        texts = [q["question"] for q in questions]
        assert len(texts) == len(set(texts)), "Questions should have no duplicates"


class TestSpiceQuestionGeneration:
    """Tests for generate_spice_questions_balanced."""

    def test_generates_balanced_questions(self, minimal_spice_json):
        nets = ["VCC", "GND"]
        questions = generate_spice_questions_balanced(nets, minimal_spice_json, count=20)

        assert len(questions) <= 20

        for q in questions:
            assert q["category"] == "spice_behaviour"
            assert q["answer"] in ("YES", "NO")

    def test_empty_nets_list(self, minimal_spice_json):
        questions = generate_spice_questions_balanced([], minimal_spice_json, count=80)
        assert questions == []

    def test_nets_without_spice_data(self, tmp_path):
        """SPICE file has no matching nets - should generate no questions."""
        empty_spice = tmp_path / "empty.json"
        with open(empty_spice, "w") as f:
            json.dump({"SOME_NET": {"name": "v(SOME_NET)", "values": {"0": 5.0}}}, f)
        questions = generate_spice_questions_balanced(
            ["VCC", "GND"], str(empty_spice), count=20
        )
        # VCC/GND not in spice data, so spice_data.get() returns None -> skipped
        assert len(questions) == 0


class TestLayoutQuestionGeneration:
    """Tests for generate_layout_questions_balanced."""

    def test_generates_balanced_questions(self):
        connections = {
            "U1": ["VCC", "GND", "SDA", "SCL"],
            "R1": ["NET1", "VCC"],
            "C1": ["GND", "NET1"],
            "U2": ["VCC", "SDA"],
            "R2": ["SCL"],
        }
        nets = ["VCC", "GND", "NET1", "SDA", "SCL"]
        questions = generate_layout_questions_balanced(connections, nets, count=20)

        assert len(questions) == 20

        yes_count = sum(1 for q in questions if q["answer"] == "YES")
        no_count = sum(1 for q in questions if q["answer"] == "NO")
        assert yes_count == 10
        assert no_count == 10

        for q in questions:
            assert q["category"] == "theory_layout"
            assert q["question"].startswith("Is the component")
            assert "connected to" in q["question"]

    def test_empty_connections(self):
        questions = generate_layout_questions_balanced({}, ["VCC"], count=80)
        assert questions == []

    def test_empty_nets(self):
        questions = generate_layout_questions_balanced({"U1": ["VCC"]}, [], count=80)
        assert questions == []

    def test_no_duplicates(self):
        connections = {"U1": ["VCC", "GND"], "R1": ["NET1"], "C1": ["GND", "NET1"]}
        questions = generate_layout_questions_balanced(connections, ["VCC", "GND", "NET1"], count=40)
        texts = [q["question"] for q in questions]
        assert len(texts) == len(set(texts))


class TestFormatProperty:
    """Tests for format_property."""

    def test_temperature_with_value(self):
        result = format_property("maximum operating temperature of {value}°C", "temperature")
        assert "temperature of " in result
        assert "°C" in result

    def test_voltage_with_value(self):
        result = format_property("maximum supply voltage of {value}V", "voltage")
        assert result.startswith("maximum supply voltage of ")
        assert result.endswith("V")

    def test_current_no_placeholder(self):
        # Properties like I2C/SPI capabilities don't have {value}
        result = format_property("I2C capabilities", "interface")
        assert result == "I2C capabilities"

    def test_quiescent_current(self):
        result = format_property("quiescent current of {value}µA", "current")
        assert "µA" in result
        assert "current of " in result

    def test_no_value_placeholder(self):
        result = format_property("PWM module", "feature")
        assert result == "PWM module"


class TestConstants:
    """Verify module-level constants are well-formed."""

    def test_datasheet_properties_non_empty(self):
        assert len(DATASHEET_PROPERTIES) > 0

    def test_datasheet_properties_structure(self):
        for prop_type, template in DATASHEET_PROPERTIES:
            assert isinstance(prop_type, str)
            assert isinstance(template, str)
            assert prop_type in ("temperature", "voltage", "current", "interface", "feature")

    def test_voltage_levels(self):
        assert "0" in VOLTAGE_LEVELS
        assert "3.3" in VOLTAGE_LEVELS
        assert "5" in VOLTAGE_LEVELS
        assert "12" in VOLTAGE_LEVELS

    def test_spice_question_templates_non_empty(self):
        assert len(SPICE_QUESTION_TEMPLATES) > 0

    def test_spice_templates_have_placeholders(self):
        for template in SPICE_QUESTION_TEMPLATES:
            assert "{voltage}" in template