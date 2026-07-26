"""Tests for pcb_qa.evaluation.agents."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.evaluation.run_benchmark.agents import (
    ask_agent,
    ask_agent_primitive,
    ask_agent_with_json_netlist_and_spice_circuit,
    ask_agent_with_json_spice_and_netlist,
    parse_llm_response,
)
from pcb_qa.models.tool_definitions import ToolMode


class TestParseLlmResponse:
    """Tests for parse_llm_response."""

    def test_parse_json_in_markdown_fences(self) -> None:
        """Verify JSON wrapped in markdown fences is parsed correctly."""
        raw = '```json\n{"answer": true, "reasoning": "test", "is_final": true}\n```'
        result = parse_llm_response(raw)
        assert result.answer is True
        assert result.reasoning == "test"
        assert result.is_final is True

    def test_parse_plain_json(self) -> None:
        """Verify plain JSON without fences is parsed correctly."""
        raw = '{"answer": false, "reasoning": "test", "is_final": true}'
        result = parse_llm_response(raw)
        assert result.answer is False

    def test_parse_with_extra_whitespace(self) -> None:
        """Verify whitespace around JSON is stripped."""
        raw = '  \n{"answer": true, "reasoning": "test", "is_final": true}\n  '
        result = parse_llm_response(raw)
        assert result.answer is True


class TestAskAgentPrimitive:
    """Tests for ask_agent_primitive."""

    @patch("pcb_qa.evaluation.run_benchmark.agents.save_debug_json")
    @patch("pcb_qa.evaluation.run_benchmark.agents._get_openai_client")
    @patch("pcb_qa.evaluation.run_benchmark.agents.ToolCaller")
    @patch("builtins.open")
    def test_ask_agent_primitive_returns_dict(self, mock_open, mock_tool_caller, mock_client, mock_save) -> None:
        """Verify ask_agent_primitive returns a properly structured dict."""
        mock_caller = MagicMock()
        mock_caller.find_all_entries_from_netlist_file_with.return_value = "netlist contents"
        mock_tool_caller.return_value = mock_caller

        mock_open.return_value.__enter__.return_value.read.return_value = "spice contents"

        mock_parsed = MagicMock()
        mock_parsed.model_dump.return_value = {"answer": True, "reasoning": "test", "is_final": True}
        mock_response = MagicMock()
        mock_response.output = [MagicMock(content=[MagicMock(parsed=mock_parsed)])]
        mock_response.model_dump.return_value = {}
        mock_client.return_value.responses.parse.return_value = mock_response

        project_context = {
            "parent_directory": "/tmp",
            "spice_circuit_file": "/tmp/test.cir",
            "circuit_json_file": "/tmp/test.json",
        }

        result = ask_agent_primitive(
            model="test-model",
            question="Is VCC 3.3V?",
            category="spice",
            project_context=project_context,
        )

        assert result["category"] == "spice"
        assert result["question"] == "Is VCC 3.3V?"
        assert result["response"]["answer"] == "YES"
        assert result["response"]["reasoning"] == "test"


class TestAskAgent:
    """Tests for ask_agent."""

    @patch("pcb_qa.evaluation.run_benchmark.agents.save_debug_json")
    @patch("pcb_qa.evaluation.run_benchmark.agents._get_openai_client")
    @patch("pcb_qa.evaluation.run_benchmark.agents.ToolCaller")
    def test_ask_agent_with_tool_call(self, mock_tool_caller, mock_client, mock_save) -> None:
        """Verify ask_agent handles tool calls correctly."""
        mock_caller = MagicMock()
        mock_caller.available_functions = {"find_connections_for_component": lambda **kwargs: "U1 connects to VCC"}
        mock_tool_caller.return_value = mock_caller

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "find_connections_for_component"
        mock_tool_call.function.arguments = json.dumps({"component_ref": "U1"})

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]

        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock(message=mock_message)]
        mock_llm_response.model_dump.return_value = {}
        mock_client.return_value.chat.completions.create.return_value = mock_llm_response

        mock_parsed = MagicMock()
        mock_parsed.model_dump.return_value = {"answer": True, "reasoning": "test", "is_final": True}
        mock_second_response = MagicMock()
        mock_second_response.output = [MagicMock(content=[MagicMock(parsed=mock_parsed)])]
        mock_second_response.model_dump.return_value = {}
        mock_client.return_value.responses.parse.return_value = mock_second_response

        project_context = {
            "parent_directory": "/tmp",
            "circuit_json_file": "/tmp/test.json",
            "spice_json_file": "/tmp/test.json",
        }

        with patch("pcb_qa.evaluation.run_benchmark.agents.ChatCompletionMessageToolCall", MagicMock):
            result = ask_agent(
                model="test-model",
                question="What does U1 connect to?",
                category="layout",
                project_context=project_context,
                tool_mode=ToolMode.NNET_AND_NCIR,
            )

        assert result["category"] == "layout"
        assert result["response"]["answer"] == "YES"
        assert "tool_calls" in result


class TestAskAgentWithJsonNetlistAndSpiceCircuit:
    """Tests for ask_agent_with_json_netlist_and_spice_circuit."""

    @patch("pcb_qa.evaluation.run_benchmark.agents.save_debug_json")
    @patch("pcb_qa.evaluation.run_benchmark.agents._get_openai_client")
    @patch("pcb_qa.evaluation.run_benchmark.agents.ToolCaller")
    @patch("builtins.open")
    def test_agent_with_circuit_and_spice(self, mock_open, mock_tool_caller, mock_client, mock_save) -> None:
        """Verify agent with JSON netlist and SPICE circuit contents."""
        mock_caller = MagicMock()
        mock_caller.find_all_entries_from_netlist_file_with.return_value = "netlist data"
        mock_tool_caller.return_value = mock_caller

        mock_open.return_value.__enter__.return_value.read.return_value = ".cir contents"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(tool_calls=None))]
        mock_response.model_dump.return_value = {}
        mock_client.return_value.chat.completions.create.return_value = mock_response

        mock_parsed = MagicMock()
        mock_parsed.model_dump.return_value = {"answer": True, "reasoning": "test", "is_final": True}
        mock_second_response = MagicMock()
        mock_second_response.output = [MagicMock(content=[MagicMock(parsed=mock_parsed)])]
        mock_second_response.model_dump.return_value = {}
        mock_client.return_value.responses.parse.return_value = mock_second_response

        project_context = {
            "parent_directory": "/tmp",
            "circuit_json_file": "/tmp/test.json",
            "spice_circuit_file": "/tmp/test.cir",
        }

        result = ask_agent_with_json_netlist_and_spice_circuit(
            model="test-model",
            question="Is there an LED?",
            category="layout",
            project_context=project_context,
            tool_mode=ToolMode.NNET_AND_PCIR,
        )

        assert result["category"] == "layout"
        assert result["response"]["answer"] == "YES"


class TestAskAgentWithJsonSpiceAndNetlist:
    """Tests for ask_agent_with_json_spice_and_netlist."""

    @patch("pcb_qa.evaluation.run_benchmark.agents.save_debug_json")
    @patch("pcb_qa.evaluation.run_benchmark.agents._get_openai_client")
    @patch("pcb_qa.evaluation.run_benchmark.agents.ToolCaller")
    def test_agent_with_spice_json_and_netlist(self, mock_tool_caller, mock_client, mock_save) -> None:
        """Verify agent with JSON SPICE and netlist contents."""
        mock_caller = MagicMock()
        mock_caller.find_all_entries_from_netlist_file_with.return_value = "netlist contents"
        mock_tool_caller.return_value = mock_caller

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "find_connections_for_component"
        mock_tool_call.function.arguments = json.dumps({"component_ref": "U1"})
        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_response.model_dump.return_value = {}
        mock_client.return_value.chat.completions.create.return_value = mock_response

        mock_parsed = MagicMock()
        mock_parsed.model_dump.return_value = {"answer": False, "reasoning": "test", "is_final": True}
        mock_second_response = MagicMock()
        mock_second_response.output = [MagicMock(content=[MagicMock(parsed=mock_parsed)])]
        mock_second_response.model_dump.return_value = {}
        mock_client.return_value.responses.parse.return_value = mock_second_response

        project_context = {
            "parent_directory": "/tmp",
            "circuit_json_file": "/tmp/test.json",
            "spice_json_file": "/tmp/spice.json",
        }

        with patch("pcb_qa.evaluation.run_benchmark.agents.ChatCompletionMessageToolCall", MagicMock):
            result = ask_agent_with_json_spice_and_netlist(
                model="test-model",
                question="Is VCC 5V?",
                category="spice",
                project_context=project_context,
                tool_mode=ToolMode.PNET_AND_NCIR,
            )

        assert result["category"] == "spice"
        assert result["response"]["answer"] == "NO"
