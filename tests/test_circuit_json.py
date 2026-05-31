"""Tests for pcb_qa.parsers.circuit_json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcb_qa.parsers.circuit_json import CircuitJSON


class TestCircuitJSONInit:
    """Tests for CircuitJSON initialisation."""

    def test_init_without_file(self) -> None:
        cj = CircuitJSON()
        assert cj.top_level_circuit == {}
        assert cj.all_components == []
        assert cj.active_components == []
        assert cj.passive_components == []

    def test_init_with_file(self, tmp_path: Path, sample_circuit_dict: dict) -> None:
        circuit_file = tmp_path / "circuit.json"
        circuit_file.write_text(json.dumps(sample_circuit_dict), encoding="utf-8")

        cj = CircuitJSON(circuit_file=str(circuit_file))
        assert cj.top_level_circuit["name"] == "TestBoard"
        assert "R1" in cj.top_level_circuit["components"]

    def test_init_with_file_missing(self) -> None:
        with pytest.raises(FileNotFoundError):
            CircuitJSON(circuit_file="/nonexistent/circuit.json")


class TestPopulateEmptyCircuit:
    """Tests for _populate_empty_circuit."""

    def test_returns_expected_keys(self) -> None:
        result = CircuitJSON._populate_empty_circuit()
        expected_keys = {"name", "description", "source_file", "tstamps", "components", "nets", "subcircuits", "annotations"}
        assert set(result.keys()) == expected_keys

    def test_components_is_empty_dict(self) -> None:
        result = CircuitJSON._populate_empty_circuit()
        assert result["components"] == {}

    def test_nets_is_empty_dict(self) -> None:
        result = CircuitJSON._populate_empty_circuit()
        assert result["nets"] == {}

    def test_subcircuits_is_empty_list(self) -> None:
        result = CircuitJSON._populate_empty_circuit()
        assert result["subcircuits"] == []


class TestGenerateCircuitDict:
    """Tests for generate_circuit_dict_from_attributes."""

    def test_basic_generation(self) -> None:
        cj = CircuitJSON()
        attrs = {"name": "Sheet1", "source_file": "Sheet1.kicad_sch"}
        result = cj.generate_circuit_dict_from_attributes(attrs)
        assert result["name"] == "Sheet1"
        assert result["source_file"] == "Sheet1.kicad_sch"

    def test_includes_default_keys(self) -> None:
        cj = CircuitJSON()
        result = cj.generate_circuit_dict_from_attributes({})
        assert "components" in result
        assert "nets" in result
        assert "subcircuits" in result

    def test_overrides_defaults(self) -> None:
        cj = CircuitJSON()
        attrs = {"components": {"R1": {"ref": "R1"}}, "nets": {"GND": []}}
        result = cj.generate_circuit_dict_from_attributes(attrs)
        assert "R1" in result["components"]
        assert "GND" in result["nets"]


class TestGetNetConnections:
    """Tests for get_net_connections."""

    def test_get_existing_net_top_level(self, sample_circuit_dict: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict
        connections = cj.get_net_connections("VCC")
        assert len(connections) == 1
        assert connections[0]["component"] == "R1"

    def test_get_nonexistent_net(self, sample_circuit_dict: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict
        connections = cj.get_net_connections("NONEXISTENT")
        assert connections == []

    def test_get_net_from_subcircuit(self, sample_circuit_dict_with_subcircuits: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict_with_subcircuits
        connections = cj.get_net_connections("GND", subcircuit_name="PowerSupply")
        assert len(connections) == 1
        assert connections[0]["component"] == "U1"

    def test_get_net_subcircuit_not_found(self, sample_circuit_dict_with_subcircuits: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict_with_subcircuits
        connections = cj.get_net_connections("GND", subcircuit_name="Nonexistent")
        assert connections == []


class TestFindComponentFromCircuit:
    """Tests for find_component_from_circuit."""

    def test_find_top_level_component(self, sample_circuit_dict: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict
        sub_name, comp = cj.find_component_from_circuit("R1")
        assert sub_name is None
        assert comp is not None
        assert comp["ref"] == "R1"

    def test_find_subcircuit_component(self, sample_circuit_dict_with_subcircuits: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict_with_subcircuits
        sub_name, comp = cj.find_component_from_circuit("U1")
        assert sub_name == "PowerSupply"
        assert comp is not None
        assert comp["ref"] == "U1"

    def test_find_nonexistent_component(self, sample_circuit_dict: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict
        sub_name, comp = cj.find_component_from_circuit("X99")
        assert sub_name is None
        assert comp is None

    def test_find_in_empty_circuit(self) -> None:
        cj = CircuitJSON()
        sub_name, comp = cj.find_component_from_circuit("R1")
        assert sub_name is None
        assert comp is None


class TestIsComponentInNet:
    """Tests for is_component_in_net_from_circuit."""

    def test_component_in_net(self, sample_circuit_dict: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict
        assert cj.is_component_in_net_from_circuit("R1", "VCC") is True

    def test_component_not_in_net(self, sample_circuit_dict: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict
        assert cj.is_component_in_net_from_circuit("C1", "VCC") is False

    def test_component_in_subcircuit_net(self, sample_circuit_dict_with_subcircuits: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict_with_subcircuits
        assert cj.is_component_in_net_from_circuit("U1", "GND") is True

    def test_nonexistent_component(self, sample_circuit_dict: dict) -> None:
        cj = CircuitJSON()
        cj.top_level_circuit = sample_circuit_dict
        assert cj.is_component_in_net_from_circuit("X99", "VCC") is False

    def test_empty_circuit(self) -> None:
        cj = CircuitJSON()
        assert cj.is_component_in_net_from_circuit("R1", "VCC") is False


class TestKeywordLists:
    """Tests for keyword class attributes."""

    def test_active_keywords_non_empty(self) -> None:
        assert len(CircuitJSON.ACTIVE_KEYWORDS) > 0

    def test_passive_keywords_non_empty(self) -> None:
        assert len(CircuitJSON.PASSIVE_KEYWORDS) > 0

    def test_power_keywords_non_empty(self) -> None:
        assert len(CircuitJSON.POWER_KEYWORDS) > 0

    def test_passive_includes_resistor(self) -> None:
        assert "resistor" in CircuitJSON.PASSIVE_KEYWORDS

    def test_passive_includes_capacitor(self) -> None:
        assert "capacitor" in CircuitJSON.PASSIVE_KEYWORDS

    def test_active_includes_mcu(self) -> None:
        assert "mcu" in CircuitJSON.ACTIVE_KEYWORDS