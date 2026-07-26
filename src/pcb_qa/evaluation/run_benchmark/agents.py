"""LLM agent runners for benchmark question answering.

Each agent implements a different strategy for getting an LLM to answer a
single benchmark question:

- ``ask_agent`` — full tool-calling pipeline (the LLM selects a tool, the
  tool is executed, then a second LLM call produces the final answer).
- ``ask_agent_primitive`` — direct reasoning with raw netlist + SPICE file
  contents injected into the prompt.
- ``ask_agent_with_json_netlist_and_spice_circuit`` — JSON netlist + raw
  ``.cir`` SPICE text, with optional tool calls.
- ``ask_agent_with_json_spice_and_netlist`` — JSON SPICE + raw netlist,
  with optional tool calls.
- ``ask_agent_with_schematic_as_pdf`` — schematic PDF is base-64 encoded
  and sent as a vision-style ``file`` message.

All agents return a dict with keys ``category``, ``question``, and
``response`` (a ``QuestionReasoning``-shaped dict with ``answer``,
``reasoning``, ``is_final``). Tool-calling agents also include a
``tool_calls`` key.

Utility
-------
``parse_llm_response`` normalises an LLM's raw text response (possibly
wrapped in markdown fences) into a :class:`pcb_qa.models.tool_definitions.QuestionReasoning`.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from pcb_qa.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from pcb_qa.logging_config import logger
from pcb_qa.models.project import Project
from pcb_qa.models.tool_definitions import QuestionReasoning, ToolMode, tools_for_mode
from pcb_qa.parsers.circuit_json import find_component
from pcb_qa.tools.caller import ToolCaller
from pcb_qa.utils.file_ops import save_debug_json


DEFAULT_TEMPERATURE: float = 0.0


def _get_openai_client():
    """Create an OpenAI-compatible client from environment config."""
    from openai import OpenAI

    api_key = OPENROUTER_API_KEY
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY environment variable is not set.")
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------


def parse_llm_response(raw_content: str) -> QuestionReasoning:
    """Parse a JSON response (possibly wrapped in markdown fences) into a QuestionReasoning model."""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_content, re.DOTALL)
    clean = match.group(1).strip() if match else raw_content.strip()
    return QuestionReasoning.model_validate_json(clean)


# ---------------------------------------------------------------------------
# Tool-calling agent: full pipeline
# ---------------------------------------------------------------------------


def ask_agent(
    model: str,
    question: str,
    category: str,
    project_context: dict,
    component_ref: str | None = None,
    tool_mode: ToolMode = ToolMode.NNET_AND_NCIR,
) -> dict:
    """Run the tool-calling agent for a single question."""
    llm_tools = tools_for_mode(tool_mode)

    tool_caller = ToolCaller()
    client = _get_openai_client()

    prompt = (
        "You are a Hardware Engineering Assistant. "
        "You must select one of the provided tools to help answer the question. "
        "You only have to decide which tool to use and the appropriate arguments "
        "to call the tool with, not generate the actual answer.\n\n"
        f"The circuit JSON file is located at: {project_context['circuit_json_file']}\n"
        f"The spice circuit file is located at: {project_context['spice_json_file']}"
    )

    project = Project(
        name="",
        parent_directory=project_context["parent_directory"],
        datasheet_files=project_context.get("datasheet_files", []),
    )

    if component_ref is not None:
        ds_file = project.find_datasheet_for_component(component_ref)
        if ds_file:
            prompt += f"\nThe datasheet file for this component is located at: {ds_file}"

    prompt += (
        "\n1. Use 'get_relevant_context_from_question' for querying component "
        "specifications and component information available in the datasheets.\n"
        "2. Use 'calculate_spice_behaviour' for simulation signals.\n"
        "3. Use 'find_connections_for_component' for connections and pins.\n"
        "Do not hallucinate answers.\n\n"
        "Only output your response in the specified format and make sure to "
        "fill in all required fields."
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]

    llm_response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=llm_tools,
        temperature=DEFAULT_TEMPERATURE,
        response_format={"type": "json_schema"},
        extra_body={"reasoning": {"enabled": True}},
    )

    save_debug_json("agent_response.json", llm_response.model_dump())

    tool_calls = llm_response.choices[0].message.tool_calls[0]
    if isinstance(tool_calls, ChatCompletionMessageToolCall):
        selected_tool_name = tool_calls.function.name
        selected_tool_args = json.loads(tool_calls.function.arguments)

        if component_ref is not None:
            selected_tool_args["component_ref"] = component_ref

        function_response = tool_caller.available_functions[selected_tool_name](**selected_tool_args)

    # Build second-pass messages with tool output
    if selected_tool_name == "get_relevant_context_from_question":
        tool_output_text = (
            f"The relevant context for this question is in this struct: {function_response}. "
            f"The previous run generated this message: {messages[-1]}"
        )
    else:
        tool_output_text = (
            f"By running the selected tool: {selected_tool_name} on backend, "
            f"the obtained answer is {function_response}. "
            f"The previous run generated this message: {messages[-1]}"
        )

    messages.append({
        "role": "system",
        "content": (
            "You are a Hardware Engineering Expert.\n"
            f"{tool_output_text}\n"
            "Only use this information to answer the question and reason with your responses.\n"
            "Answer the question in the specified format requested by the user.\n"
            "Once you are completely sure with your answer, set the 'is_final' attribute "
            "to True in your output response.\n"
            "Make sure you explain your reasoning clearly in the 'reasoning' attribute "
            "of the output response."
        ),
    })
    messages.append({"role": "user", "content": question})

    second_response = client.responses.parse(
        model=model,
        input=messages,
        text_format=QuestionReasoning,
        temperature=DEFAULT_TEMPERATURE,
    )

    save_debug_json("final_response.json", second_response.model_dump())

    final_response = {
        "category": category,
        "question": question,
        "tool_calls": llm_response.choices[0].message.tool_calls[0].function.model_dump(),
        "response": second_response.output[0].content[0].parsed.model_dump(),
    }
    final_response["response"]["answer"] = (
        "YES" if final_response["response"]["answer"] is True else "NO"
    )
    return final_response


# ---------------------------------------------------------------------------
# Tool-calling agent: primitive (no tools, direct reasoning)
# ---------------------------------------------------------------------------


def ask_agent_primitive(
    model: str,
    question: str,
    category: str,
    project_context: dict,
    component_ref: str | None = None,
    tool_mode: ToolMode = ToolMode.PNET_AND_PCIR,
    output_dir: str | None = None,
    question_index: int | None = None,
) -> dict:
    """Run a primitive agent that answers directly without tool calls."""
    caller = ToolCaller()
    client = _get_openai_client()

    netlist_contents = caller.find_all_entries_from_netlist_file_with(project_context, component_ref)

    with open(project_context["spice_circuit_file"], "r", encoding="utf-8") as scf:
        spice_circuit_contents = scf.read()

    prompt = (
        "You are a Hardware Engineering Assistant. "
        "You must use the files I have provided to answer the questions.\n\n"
        f"The netlist contents for the project is: {netlist_contents}\n"
        f"The SPICE circuit file contains: {spice_circuit_contents}\n\n"
        "Do not hallucinate answers.\n"
        "Answer the question in the specified format requested by the user.\n"
        "Once you are completely sure with your answer, set the 'is_final' "
        "attribute to True in your output response.\n"
        "Make sure you explain your reasoning clearly in the 'reasoning' "
        "attribute of the output response.\n\n"
        "Only output your response in the specified format and make sure to "
        "fill in all required fields."
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]

    llm_response = client.responses.parse(
        model=model,
        input=messages,
        text_format=QuestionReasoning,
        temperature=DEFAULT_TEMPERATURE,
    )

    raw = llm_response.model_dump()
    if output_dir and question_index:
        save_debug_json(os.path.join(output_dir, f"{question_index}_raw_llm_response.json"), raw)

    final_response = {
        "category": category,
        "question": question,
        "response": llm_response.output[0].content[0].parsed.model_dump(),
    }
    final_response["response"]["answer"] = (
        "YES" if final_response["response"]["answer"] is True else "NO"
    )
    return final_response


# ---------------------------------------------------------------------------
# Tool-calling agent: JSON circuit + SPICE circuit contents
# ---------------------------------------------------------------------------


def ask_agent_with_json_netlist_and_spice_circuit(
    model: str,
    question: str,
    category: str,
    project_context: dict,
    component_ref: str | None = None,
    tool_mode: ToolMode = ToolMode.NNET_AND_PCIR,
) -> dict:
    """Collect a response using .cir contents and JSON.net as inputs."""
    llm_tools = tools_for_mode(tool_mode)

    tool_caller = ToolCaller()
    client = _get_openai_client()

    with open(project_context["spice_circuit_file"], "r", encoding="utf-8") as sf:
        spice_file_contents = sf.read()

    project = Project(
        name="",
        parent_directory=project_context["parent_directory"],
        datasheet_files=project_context.get("datasheet_files", []),
    )

    prompt = (
        "You are a Hardware Engineering Assistant. "
        "You must select one of the provided tools to help answer the question. "
        "You only have to decide which tool to use and the appropriate arguments "
        "to call the tool with, not generate the actual answer.\n\n"
        f"The circuit JSON file is located at: {project_context['circuit_json_file']}\n"
        f"The spice circuit contents is: {spice_file_contents}"
    )

    if component_ref is not None:
        ds_file = project.find_datasheet_for_component(component_ref)
        if ds_file:
            prompt += f"\nThe datasheet file for this component is located at: {ds_file}"

    prompt += (
        "\n1. Use 'get_relevant_context_from_question' for querying component "
        "specifications and component information available in the datasheets.\n"
        "2. Use 'find_connections_for_component' for connections and pins.\n"
        "Do not hallucinate answers.\n\n"
        "Only output your response in the specified format and make sure to "
        "fill in all required fields."
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]

    llm_response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=llm_tools,
        temperature=DEFAULT_TEMPERATURE,
        response_format={"type": "json_schema"},
        extra_body={"reasoning": {"enabled": True}},
    )

    save_debug_json("agent_response.json", llm_response.model_dump())

    function_response = None
    selected_tool_name = None

    if llm_response.choices[0].message.tool_calls and llm_response.choices[0].message.tool_calls[0]:
        tool_calls = llm_response.choices[0].message.tool_calls[0]
        if isinstance(tool_calls, ChatCompletionMessageToolCall):
            selected_tool_name = tool_calls.function.name
            selected_tool_args = json.loads(tool_calls.function.arguments)

            if component_ref is not None:
                selected_tool_args["component_ref"] = component_ref

            function_response = tool_caller.available_functions[selected_tool_name](**selected_tool_args)
    else:
        tool_calls = None

    if selected_tool_name == "get_relevant_context_from_question":
        tool_output_text = (
            f"The relevant context for this question is in this struct: {function_response}. "
            f"The previous run generated this message: {messages[-1]}"
        )
    else:
        tool_output_text = (
            f"By running the selected tool: {selected_tool_name} on backend, "
            f"the obtained answer is {function_response}. "
            f"The previous run generated this message: {messages[-1]}"
        )

    messages.append({
        "role": "system",
        "content": (
            "You are a Hardware Engineering Expert.\n"
            f"{tool_output_text}\n"
            "Only use this information to answer the question and reason with your responses.\n"
            "Answer the question in the specified format requested by the user.\n"
            "Once you are completely sure with your answer, set the 'is_final' attribute "
            "to True in your output response.\n"
            "Make sure you explain your reasoning clearly in the 'reasoning' attribute "
            "of the output response."
        ),
    })
    messages.append({"role": "user", "content": question})

    second_response = client.responses.parse(
        model=model,
        input=messages,
        text_format=QuestionReasoning,
        temperature=DEFAULT_TEMPERATURE,
    )

    save_debug_json("final_response.json", second_response.model_dump())

    final_response = {
        "category": category,
        "question": question,
        "tool_calls": tool_calls.function.model_dump() if tool_calls else None,
        "response": second_response.output[0].content[0].parsed.model_dump(),
    }
    final_response["response"]["answer"] = (
        "YES" if final_response["response"]["answer"] is True else "NO"
    )
    return final_response


# ---------------------------------------------------------------------------
# Tool-calling agent: JSON SPICE + netlist contents
# ---------------------------------------------------------------------------


def ask_agent_with_json_spice_and_netlist(
    model: str,
    question: str,
    category: str,
    project_context: dict,
    component_ref: str | None = None,
    tool_mode: ToolMode = ToolMode.PNET_AND_NCIR,
) -> dict:
    """Collect a response using .JSON.cir and .net contents as inputs."""
    llm_tools = tools_for_mode(tool_mode)

    tool_caller = ToolCaller()
    client = _get_openai_client()

    circuit_file_contents = tool_caller.find_all_entries_from_netlist_file_with(project_context, component_ref)

    prompt = (
        "You are a Hardware Engineering Assistant. "
        "You must select one of the provided tools to help answer the question. "
        "You only have to decide which tool to use and the appropriate arguments "
        "to call the tool with, not generate the actual answer.\n\n"
        f"The netlist file contents are: {circuit_file_contents}\n"
        f"The SPICE simulated JSON file is located at: {project_context['spice_json_file']}"
    )

    project = Project(
        name="",
        parent_directory=project_context["parent_directory"],
        datasheet_files=project_context.get("datasheet_files", []),
    )

    if component_ref is not None:
        ds_file = project.find_datasheet_for_component(component_ref)
        if ds_file:
            prompt += f"\nThe datasheet file for this component is located at: {ds_file}"

    prompt += (
        "\n1. Use 'get_relevant_context_from_question' for querying component "
        "specifications and component information available in the datasheets.\n"
        "2. Use 'calculate_spice_behaviour' for simulation signals.\n"
        "Do not hallucinate answers.\n\n"
        "Only output your response in the specified format and make sure to "
        "fill in all required fields."
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]

    try:
        llm_response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=llm_tools,
            temperature=DEFAULT_TEMPERATURE,
            response_format={"type": "json_schema"},
            extra_body={"reasoning": {"enabled": True}},
        )

        save_debug_json("agent_response.json", llm_response.model_dump())

        function_response = None
        selected_tool_name = None

        tool_calls = llm_response.choices[0].message.tool_calls[0]
        if isinstance(tool_calls, ChatCompletionMessageToolCall):
            selected_tool_name = tool_calls.function.name
            selected_tool_args = json.loads(tool_calls.function.arguments)

            if component_ref is not None:
                selected_tool_args["component_ref"] = component_ref

            function_response = tool_caller.available_functions[selected_tool_name](**selected_tool_args)

        if selected_tool_name == "get_relevant_context_from_question":
            tool_output_text = (
                f"The relevant context for this question is in this struct: {function_response}. "
                f"The previous run generated this message: {messages[-1]}"
            )
        else:
            tool_output_text = (
                f"By running the selected tool: {selected_tool_name} on backend, "
                f"the obtained answer is {function_response}. "
                f"The previous run generated this message: {messages[-1]}"
            )
    except Exception as e:
        return {
            "category": category,
            "question": question,
            "tool_calls": None,
            "response": {
                "answer": "N/A",
                "reasoning": str(e),
                "is_final": True,
            },
        }

    messages.append({
        "role": "system",
        "content": (
            "You are a Hardware Engineering Expert.\n"
            f"{tool_output_text}\n"
            "Only use this information to answer the question and reason with your responses.\n"
            "Answer the question in the specified format requested by the user.\n"
            "Once you are completely sure with your answer, set the 'is_final' attribute "
            "to True in your output response.\n"
            "Make sure you explain your reasoning clearly in the 'reasoning' attribute "
            "of the output response."
        ),
    })
    messages.append({"role": "user", "content": question})

    try:
        second_response = client.responses.parse(
            model=model,
            input=messages,
            text_format=QuestionReasoning,
            temperature=DEFAULT_TEMPERATURE,
        )

        save_debug_json("final_response.json", second_response.model_dump())

        final_response = {
            "category": category,
            "question": question,
            "tool_calls": llm_response.choices[0].message.tool_calls[0].function.model_dump(),
            "response": second_response.output[0].content[0].parsed.model_dump(),
        }
        final_response["response"]["answer"] = (
            "YES" if final_response["response"]["answer"] is True else "NO"
        )
    except Exception as e:
        return {
            "category": category,
            "question": question,
            "response": {
                "answer": "N/A",
                "reasoning": str(e),
                "is_final": True,
            },
        }

    return final_response


# ---------------------------------------------------------------------------
# Schematic-as-PDF agent
# ---------------------------------------------------------------------------


def ask_agent_with_schematic_as_pdf(
    model: str,
    question: str,
    category: str,
    project_context: dict,
    component_ref: str | None = None,
    tool_mode: ToolMode = ToolMode.PDF,
) -> dict:
    """Answer a question by sending a schematic PDF to the LLM as vision input."""
    api_key = OPENROUTER_API_KEY
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY environment variable is not set.")

    pdf_file = list(Path(project_context["parent_directory"]).glob("*.pdf"))[0]
    with open(pdf_file, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode("utf-8")
    data_url = f"data:application/pdf;base64,{base64_pdf}"

    prompt = (
        "You are a Hardware Engineering Assistant. "
        "You must use the files I have provided to answer the questions.\n\n"
        "Do not hallucinate answers.\n"
        "Answer the question in the specified format requested by the user.\n"
        "Once you are completely sure with your answer, set the 'is_final' "
        "attribute to True in your output response.\n"
        "Make sure you explain your reasoning clearly in the 'reasoning' "
        "attribute of the output response.\n\n"
        "Only output your response in the specified format and make sure to "
        "fill in all required fields.\n\n"
        f"* Required format: JSON\n"
        f"* Schema: {QuestionReasoning.model_json_schema()}"
    )

    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {
                    "type": "file",
                    "file": {
                        "filename": "document.pdf",
                        "file_data": data_url,
                    },
                },
            ],
        },
    ]

    payload = {"model": model, "messages": messages}

    llm_response = requests.post(url, headers=headers, json=payload)

    save_debug_json("agent_response.json", llm_response.json())

    content = llm_response.json()["choices"][0]["message"]["content"]
    match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
    if match:
        content = re.sub(r"^```json\s*|\s*```$", "", match.group(1))

    final_response = {
        "category": category,
        "question": question,
        "response": json.loads(content),
        "usage_stats": llm_response.json().get("usage"),
    }
    final_response["response"]["answer"] = (
        "YES" if final_response["response"]["answer"] is True else "NO"
    )
    return final_response