"""Tests for the prompt_runner modularisation.

Covers every function that was previously defined in ``src/prompt_runner.py``
and now lives inside the ``pcb_qa`` package.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.config import DEFAULT_TEMPERATURE, get_openai_client
from pcb_qa.evaluation.compute_results.evaluator import (
    parse_llm_response,
    ask_agent,
    ask_agent_primitive,
    ask_agent_with_json_netlist_and_spice_circuit,
    ask_agent_with_json_spice_and_netlist,
    ask_agent_with_schematic_as_pdf,
)
from pcb_qa.models.tool_definitions import QuestionReasoning, ToolDefinitions, ToolMode, tools_for_mode
from pcb_qa.parsers.circuit_json import find_component
from pcb_qa.utils.file_ops import save_debug_json


# ---------------------------------------------------------------------------
# parse_llm_response
# ---------------------------------------------------------------------------


class TestParseLlmResponse:
    """Tests for the LLM response parser."""

    def test_valid_json(self) -> None:
        raw = '{"answer": true, "reasoning": "OK", "is_final": true}'
        result = parse_llm_response(raw)
        assert isinstance(result, QuestionReasoning)
        assert result.answer is True
        assert result.reasoning == "OK"
        assert result.is_final is True

    def test_json_in_markdown_fences(self) -> None:
        raw = '```json\n{"answer": false, "reasoning": "No", "is_final": true}\n```'
        result = parse_llm_response(raw)
        assert result.answer is False
        assert result.reasoning == "No"

    def test_json_in_plain_fences(self) -> None:
        raw = '```\n{"answer": true, "reasoning": "Yes", "is_final": false}\n```'
        result = parse_llm_response(raw)
        assert result.answer is True
        assert result.is_final is False

    def test_surrounding_whitespace(self) -> None:
        raw = '  \n {"answer": true, "reasoning": "x", "is_final": true} \n  '
        result = parse_llm_response(raw)
        assert result.answer is True

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(Exception):
            parse_llm_response("not json at all")

    def test_missing_required_field(self) -> None:
        raw = '{"answer": true}'
        with pytest.raises(Exception):
            parse_llm_response(raw)


# ---------------------------------------------------------------------------
# tools_for_mode
# ---------------------------------------------------------------------------


class TestToolsForMode:
    """Tests for the mode → tool mapping."""

    def test_nnet_and_ncir_returns_all_tools(self) -> None:
        tools = tools_for_mode(ToolMode.NNET_AND_NCIR)
        assert tools is not None
        assert len(tools) == len(ToolDefinitions.all_tools())

    def test_pnet_and_pcir_returns_none(self) -> None:
        assert tools_for_mode(ToolMode.PNET_AND_PCIR) is None

    def test_pdf_returns_none(self) -> None:
        assert tools_for_mode(ToolMode.PDF) is None

    def test_nnet_and_pcir_returns_subset(self) -> None:
        tools = tools_for_mode(ToolMode.NNET_AND_PCIR)
        assert tools is not None
        names = {t["function"]["name"] for t in tools}
        assert "get_relevant_context_from_question" in names
        assert "find_connections_for_component" in names
        assert "calculate_spice_behaviour" not in names

    def test_pnet_and_ncir_returns_subset(self) -> None:
        tools = tools_for_mode(ToolMode.PNET_AND_NCIR)
        assert tools is not None
        names = {t["function"]["name"] for t in tools}
        assert "get_relevant_context_from_question" in names
        assert "calculate_spice_behaviour" in names
        assert "find_connections_for_component" not in names

    def test_invalid_mode_returns_none(self) -> None:
        # ToolMode.INVALID is not in the mapping, so .get() returns None.
        assert tools_for_mode(ToolMode.INVALID) is None


# ---------------------------------------------------------------------------
# get_openai_client
# ---------------------------------------------------------------------------


class TestGetOpenaiClient:
    """Tests for the OpenAI client factory."""

    @patch("pcb_qa.config.OPENROUTER_API_KEY", None)
    def test_raises_without_api_key(self) -> None:
        with pytest.raises(EnvironmentError, match="OPENROUTER_API_KEY"):
            get_openai_client()

    @patch("pcb_qa.config.OPENROUTER_API_KEY", "test-key-123")
    @patch("pcb_qa.config.OPENROUTER_BASE_URL", "https://example.com/v1")
    @patch("openai.OpenAI")
    def test_creates_client_with_correct_params(self, mock_cls: MagicMock) -> None:
        mock_cls.return_value = MagicMock()
        client = get_openai_client()
        mock_cls.assert_called_once_with(
            base_url="https://example.com/v1",
            api_key="test-key-123",
        )
        assert client is mock_cls.return_value


# ---------------------------------------------------------------------------
# DEFAULT_TEMPERATURE
# ---------------------------------------------------------------------------


class TestDefaultTemperature:
    """Verify the constant has the expected value."""

    def test_is_zero(self) -> None:
        assert DEFAULT_TEMPERATURE == 0.0


# ---------------------------------------------------------------------------
# save_debug_json
# ---------------------------------------------------------------------------


class TestSaveDebugJson:
    """Tests for the debug JSON saver."""

    def test_creates_file(self, tmp_path: Path) -> None:
        target = str(tmp_path / "debug.json")
        save_debug_json(target, {"key": "value"})
        assert Path(target).exists()
        data = json.loads(Path(target).read_text(encoding="utf-8"))
        assert data["key"] == "value"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = str(tmp_path / "debug.json")
        save_debug_json(target, {"a": 1})
        save_debug_json(target, {"b": 2})
        data = json.loads(Path(target).read_text(encoding="utf-8"))
        assert data == {"b": 2}

    def test_pretty_printed(self, tmp_path: Path) -> None:
        target = str(tmp_path / "debug.json")
        save_debug_json(target, {"x": 1})
        content = Path(target).read_text(encoding="utf-8")
        # indent=4 produces 4-space indentation
        assert '    "x": 1' in content

    def test_does_not_raise_on_bad_path(self, tmp_path: Path) -> None:
        # Should not raise — save_debug_json swallows OSError.
        save_debug_json("/nonexistent/dir/file.json", {"a": 1})


# ---------------------------------------------------------------------------
# find_component (moved from prompt_runner to parsers/circuit_json)
# ---------------------------------------------------------------------------


class TestFindComponentModuleLevel:
    """Tests for the module-level find_component helper."""

    def test_finds_existing_component(self, tmp_path: Path, sample_circuit_dict: dict[str, Any]) -> None:
        circuit_file = tmp_path / "circuit.json"
        circuit_file.write_text(json.dumps(sample_circuit_dict), encoding="utf-8")
        result = find_component(str(circuit_file), "R1")
        assert result["ref"] == "R1"
        assert result["value"] == "10k"

    def test_returns_empty_dict_for_missing(self, tmp_path: Path, sample_circuit_dict: dict[str, Any]) -> None:
        circuit_file = tmp_path / "circuit.json"
        circuit_file.write_text(json.dumps(sample_circuit_dict), encoding="utf-8")
        result = find_component(str(circuit_file), "X99")
        assert result == {}


