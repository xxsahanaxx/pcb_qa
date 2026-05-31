"""LLM tool definitions and Pydantic schemas.

Refactored from the original ``tool_caller.py`` inner classes.
"""

from __future__ import annotations

from enum import Enum, auto

from pydantic import BaseModel, ConfigDict, Field


class ToolMode(Enum):
    """Operating modes for the tool-calling pipeline."""
    NNET_AND_NCIR = "NNet&NCir"
    NNET_AND_PCIR = "NNet&PCir"
    PNET_AND_NCIR = "PNet&NCir"
    PNET_AND_PCIR = "PNet&PCir"
    PDF = "PDF"
    PNET = "PNet"
    PCIR = "PCir"
    NNET = "NNet"
    NCIR = "NCir"
    INVALID = "INVALID"


class QuestionReasoning(BaseModel):
    """Structured output from the LLM for a single question."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    answer: bool = Field(description="The answer to the question (only answer True/False, no explanations)")
    reasoning: str = Field(description="1 sentence reasoning behind the answer")
    is_final: bool = Field(
        description="Whether this is the final answer or if further tool calls are needed. "
        "Be sure in your decision before marking as final."
    )


class ToolCalls(BaseModel):
    """Schema for a single tool call made by the LLM."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    function_name: str = Field(alias="name", description="Name of the function being called")
    function_args: dict = Field(
        alias="arguments",
        description="Arguments for the function being called",
        required=True,
        json_schema_extra={"additionalProperties": False},
    )


class ToolDefinitions:
    """Static definitions of tools exposed to the LLM."""

    GET_RELEVANT_CONTEXT = {
        "type": "function",
        "function": {
            "name": "get_relevant_context_from_question",
            "description": "Check component specifications in datasheet and see if they match the question",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to answer"},
                    "project_context": {
                        "type": "object",
                        "description": "Context of the project, including file paths for circuit JSON, spice JSON, and datasheet files",
                        "properties": {
                            "circuit_json_file": {"type": "string", "description": "Path to circuit JSON"},
                            "spice_json_file": {"type": "string", "description": "Path to SPICE netlist JSON"},
                            "datasheet_files": {
                                "type": "array",
                                "items": {"type": "string", "description": "Path to datasheet files associated with the project"},
                            },
                        },
                        "required": ["circuit_json_file", "spice_json_file", "datasheet_files"],
                        "additionalProperties": False,
                    },
                    "component_ref": {"type": "string", "description": "Reference designator (e.g., R1, U2)"},
                },
                "required": ["question", "project_context", "component_ref"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }

    CALCULATE_SPICE_BEHAVIOUR = {
        "type": "function",
        "function": {
            "name": "calculate_spice_behaviour",
            "description": "Analyse signal behavior in SPICE simulation and answer the question based on voltage characteristics",
            "parameters": {
                "type": "object",
                "properties": {
                    "net_name": {
                        "type": "string",
                        "description": "Net name (e.g. SWDIO, net-_u4-vcomh_, net-_a2-btn_, GND)",
                    },
                    "spice_json_file": {"type": "string", "description": "Path to the SPICE JSON file"},
                    "expected_voltage": {"type": "string", "description": "Expected voltage level (e.g. 3.3V)"},
                },
                "required": ["net_name", "spice_circuit_file", "expected_voltage"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }

    FIND_CONNECTIONS = {
        "type": "function",
        "function": {
            "name": "find_connections_for_component",
            "description": "Check if a component is connected to a net in the layout and answer the question based on the connections",
            "parameters": {
                "type": "object",
                "properties": {
                    "circuit_json_file": {"type": "string", "description": "Path to the circuit JSON file"},
                    "component_ref": {"type": "string", "description": "Component reference (e.g. C1, U2)"},
                    "net_name": {"type": "string", "description": "Net name (e.g. GND, VCC, SWDIO)"},
                },
                "required": ["circuit_json_file", "component_ref", "net_name"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }

    @classmethod
    def all_tools(cls) -> list[dict]:
        """Return the full list of tool definitions."""
        return [
            cls.GET_RELEVANT_CONTEXT,
            cls.CALCULATE_SPICE_BEHAVIOUR,
            cls.FIND_CONNECTIONS,
            cls.FIND_ALL_NETLIST_ENTRIES,
        ]
