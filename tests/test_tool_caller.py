"""Tests for pcb_qa.tools.caller."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.tools.caller import ToolCaller


class TestToolCallerInit:
    """Tests for ToolCaller initialisation."""

    def test_init(self) -> None:
        tc = ToolCaller()
        assert isinstance(tc.llm_tools, list)
        assert len(tc.llm_tools) == 3
        assert isinstance(tc.available_functions, dict)

    def test_available_functions_registered(self) -> None:
        tc = ToolCaller()
        expected_functions = {
            "get_relevant_context_from_question",
            "calculate_spice_behaviour",
            "find_connections_for_component",
        }
        assert set(tc.available_functions.keys()) == expected_functions

    def test_available_functions_are_callable(self) -> None:
        tc = ToolCaller()
        for func in tc.available_functions.values():
            assert callable(func)


class TestFindConnectionsForComponent:
    """Tests for find_connections_for_component."""

    def test_component_in_net(self, tmp_path: Path, sample_circuit_dict: dict) -> None:
        circuit_file = tmp_path / "circuit.json"
        circuit_file.write_text(json.dumps(sample_circuit_dict), encoding="utf-8")

        tc = ToolCaller()
        result = tc.find_connections_for_component(
            circuit_json_file=str(circuit_file),
            component_ref="R1",
            net_name="VCC",
        )
        assert result is True

    def test_component_not_in_net(self, tmp_path: Path, sample_circuit_dict: dict) -> None:
        circuit_file = tmp_path / "circuit.json"
        circuit_file.write_text(json.dumps(sample_circuit_dict), encoding="utf-8")

        tc = ToolCaller()
        result = tc.find_connections_for_component(
            circuit_json_file=str(circuit_file),
            component_ref="C1",
            net_name="VCC",
        )
        assert result is False

    def test_nonexistent_circuit_file(self) -> None:
        tc = ToolCaller()
        result = tc.find_connections_for_component(
            circuit_json_file="/nonexistent/circuit.json",
            component_ref="R1",
            net_name="VCC",
        )
        assert result is False


class TestCalculateSpiceBehaviour:
    """Tests for calculate_spice_behaviour."""

    def test_matching_voltage(self, tmp_path: Path) -> None:
        spice_json = {
            "0": {
                "name": "v(net1)",
                "values": {str(i): "3.3" for i in range(15)},
            }
        }
        json_file = tmp_path / "spice.json"
        json_file.write_text(json.dumps(spice_json), encoding="utf-8")

        tc = ToolCaller()
        result = tc.calculate_spice_behaviour(
            spice_json_file=str(json_file),
            net_name="net1",
            expected_voltage="3.3V",
        )
        assert result is True

    def test_non_matching_voltage(self, tmp_path: Path) -> None:
        spice_json = {
            "0": {
                "name": "v(net1)",
                "values": {str(i): "1.8" for i in range(15)},
            }
        }
        json_file = tmp_path / "spice.json"
        json_file.write_text(json.dumps(spice_json), encoding="utf-8")

        tc = ToolCaller()
        result = tc.calculate_spice_behaviour(
            spice_json_file=str(json_file),
            net_name="net1",
            expected_voltage="3.3V",
        )
        assert result is False

    def test_exception_returns_false(self) -> None:
        tc = ToolCaller()
        result = tc.calculate_spice_behaviour(
            spice_json_file="/nonexistent/file.json",
            net_name="net1",
            expected_voltage="3.3V",
        )
        assert result is False


class TestGetRelevantContext:
    """Tests for get_relevant_context_from_question."""

    def test_exception_returns_empty_list(self) -> None:
        tc = ToolCaller()
        result = tc.get_relevant_context_from_question(
            question="What is the voltage?",
            project_context={"circuit_json_file": "/nonexistent"},
            component_ref="R1",
        )
        assert result == []


class TestToolCallerAllTools:
    """Tests for ToolCaller.llm_tools content."""

    def test_tools_have_correct_names(self) -> None:
        tc = ToolCaller()
        tool_names = [t["function"]["name"] for t in tc.llm_tools]
        assert "get_relevant_context_from_question" in tool_names
        assert "calculate_spice_behaviour" in tool_names
        assert "find_connections_for_component" in tool_names