"""Tests for pcb_qa.models.tool_definitions."""

from __future__ import annotations

import pytest

from pcb_qa.models.tool_definitions import QuestionReasoning, ToolCalls, ToolDefinitions, ToolMode


class TestToolMode:
    """Tests for the ToolMode enum."""

    def test_enum_members_exist(self) -> None:
        assert ToolMode.NNET_AND_NCIR.value == "NNet&NCir"
        assert ToolMode.NNET_AND_PCIR.value == "NNet&PCir"
        assert ToolMode.PNET_AND_NCIR.value == "PNet&NCir"
        assert ToolMode.PNET_AND_PCIR.value == "PNet&PCir"
        assert ToolMode.PDF.value == "PDF"
        assert ToolMode.PNET.value == "PNet"
        assert ToolMode.PCIR.value == "PCir"
        assert ToolMode.NNET.value == "NNet"
        assert ToolMode.NCIR.value == "NCir"
        assert ToolMode.INVALID.value == "INVALID"

    def test_enum_is_unique(self) -> None:
        values = [m.value for m in ToolMode]
        assert len(values) == len(set(values))


class TestQuestionReasoning:
    """Tests for the QuestionReasoning Pydantic model."""

    def test_valid_construction(self) -> None:
        qr = QuestionReasoning(answer=True, reasoning="Because of R1", is_final=False)
        assert qr.answer is True
        assert qr.reasoning == "Because of R1"
        assert qr.is_final is False

    def test_false_answer(self) -> None:
        qr = QuestionReasoning(answer=False, reasoning="Not connected", is_final=True)
        assert qr.answer is False

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            QuestionReasoning(answer=True, reasoning="ok", is_final=True, extra_field="bad")

    def test_json_serialization(self) -> None:
        qr = QuestionReasoning(answer=True, reasoning="test", is_final=True)
        d = qr.model_dump()
        assert d["answer"] is True
        assert d["reasoning"] == "test"
        assert d["is_final"] is True

    def test_json_roundtrip(self) -> None:
        qr = QuestionReasoning(answer=False, reasoning="No power", is_final=True)
        json_str = qr.model_dump_json()
        qr2 = QuestionReasoning.model_validate_json(json_str)
        assert qr == qr2


class TestToolCalls:
    """Tests for the ToolCalls Pydantic model."""

    def test_valid_construction(self) -> None:
        tc = ToolCalls(function_name="my_func", function_args={"arg1": "val1"})
        assert tc.function_name == "my_func"
        assert tc.function_args == {"arg1": "val1"}

    def test_alias_construction(self) -> None:
        tc = ToolCalls.model_validate({"name": "func", "arguments": {"k": "v"}})
        assert tc.function_name == "func"
        assert tc.function_args == {"k": "v"}

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            ToolCalls(function_name="f", function_args={}, extra="bad")

    def test_json_roundtrip(self) -> None:
        tc = ToolCalls(function_name="calculate", function_args={"x": 1})
        json_str = tc.model_dump_json()
        tc2 = ToolCalls.model_validate_json(json_str)
        assert tc.function_name == tc2.function_name
        assert tc.function_args == tc2.function_args


class TestToolDefinitions:
    """Tests for the ToolDefinitions class."""

    def test_get_relevant_context_tool(self) -> None:
        tool = ToolDefinitions.GET_RELEVANT_CONTEXT
        assert tool["function"]["name"] == "get_relevant_context_from_question"
        params = tool["function"]["parameters"]
        assert "question" in params["properties"]
        assert "project_context" in params["properties"]
        assert "component_ref" in params["properties"]

    def test_calculate_spice_tool(self) -> None:
        tool = ToolDefinitions.CALCULATE_SPICE_BEHAVIOUR
        assert tool["function"]["name"] == "calculate_spice_behaviour"
        params = tool["function"]["parameters"]
        assert "net_name" in params["properties"]
        assert "expected_voltage" in params["properties"]

    def test_find_connections_tool(self) -> None:
        tool = ToolDefinitions.FIND_CONNECTIONS
        assert tool["function"]["name"] == "find_connections_for_component"
        params = tool["function"]["parameters"]
        assert "circuit_json_file" in params["properties"]
        assert "component_ref" in params["properties"]
        assert "net_name" in params["properties"]

