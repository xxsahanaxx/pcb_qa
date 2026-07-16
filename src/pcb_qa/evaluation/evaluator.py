"""Benchmark evaluation — compare LLM responses to expected answers.

Refactored from the original ``evaluate_results.py``.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any

from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
import requests

from pcb_qa.config import (
    DEFAULT_LLM_MODELS,
    DEFAULT_TEMPERATURE,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    get_openai_client,
    load_projects_config,
)
from pcb_qa.logging_config import logger
from pcb_qa.models.project import Project
from pcb_qa.models.tool_definitions import QuestionReasoning, ToolMode, tools_for_mode
from pcb_qa.parsers.circuit_json import find_component
from pcb_qa.tools.caller import ToolCaller
from pcb_qa.utils.file_ops import CSVFileOperator, JSONFileOperator, save_debug_json


class EvaluateResults:
    """Evaluate LLM responses against ground-truth answers.

    For each project and model, responses are loaded from the results
    directory, compared to expected answers, and metrics (accuracy,
    precision, recall, F1) are written to a CSV file.
    """

    def __init__(self, projects_config_path: str | None = None) -> None:
        self.llm_models = list(DEFAULT_LLM_MODELS)
        self.actual_responses: list[str] = []
        self.predicted_responses: list[str] = []

        self.csv_file_operator = CSVFileOperator()
        self.json_file_operator = JSONFileOperator()
        self.project_files_dict = load_projects_config(projects_config_path)

    # -- private helpers ------------------------------------------------------

    def _evaluate_n_responses_for_mode(
        self,
        num_questions: int,
        mode: ToolMode,
        models: list[str] | None = None,
    ) -> None:
        from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

        models = models or self.llm_models

        for model in models:
            logger.info("--- Evaluating model: %s, mode: %s ---", model, mode)

            for project_key, project in self.project_files_dict.items():
                self.actual_responses = []
                self.predicted_responses = []

                target_csv = f'{project["parent_directory"]}/results/{mode.value}/{model}_{project_key}.csv'
                self.csv_file_operator.create_header_for_csv(
                    csv_file=target_csv,
                    fields=["Model", "Question", "Category", "Actual_Response", "Predicted_Response"],
                )

                questions = self._load_questions_from_file(project["questions_json_file"])

                for idx in range(num_questions):
                    category = questions[idx]["category"]
                    self.actual_responses.append(questions[idx]["answer"])

                    results_file = f'{project["parent_directory"]}/results/{mode.value}/{model}/{category}/{idx + 1}.json'
                    self._read_response_from_file(results_file)

                    row = [model, f"Q{idx + 1}", category, questions[idx]["answer"], self.predicted_responses[idx]]
                    self.csv_file_operator.write_row_to_csv(target_csv, row)

                actual = self.actual_responses[:num_questions]
                predicted = self.predicted_responses[:num_questions]

                accuracy = accuracy_score(actual, predicted)
                precision = precision_score(actual, predicted, pos_label="YES", average="macro")
                recall = recall_score(actual, predicted, pos_label="YES", average="macro")
                f1 = f1_score(actual, predicted, pos_label="YES", average="macro")

                logger.info("  Accuracy: %.4f | Precision: %.4f | Recall: %.4f | F1: %.4f", accuracy, precision, recall, f1)

                self.csv_file_operator.write_row_to_csv(target_csv, row=["Accuracy", "Precision", "Recall", "F1 Score"])
                self.csv_file_operator.write_row_to_csv(target_csv, row=[str(accuracy), str(precision), str(recall), str(f1)])

    def _load_questions_from_file(self, path: str) -> list[dict[str, Any]]:
        return self.json_file_operator.read_from_json_file(path)

    def _read_response_from_file(self, results_file: str) -> None:
        try:
            result = self.json_file_operator.read_from_json_file(results_file)
            self.predicted_responses.append(result["response"]["answer"])
        except FileNotFoundError:
            logger.warning("Result file not found: %s", results_file)
            self.predicted_responses.append("N/A")

    # -- public API (one per mode) -------------------------------------------

    def write_nnet_and_ncir_responses_to_csv(self, num_questions: int = 60, models: list[str] | None = None) -> None:
        """Evaluate the ``NNET_AND_NCIR`` mode."""
        self._evaluate_n_responses_for_mode(num_questions, ToolMode.NNET_AND_NCIR, models)

    def write_nnet_and_pcir_responses_to_csv(self, num_questions: int = 15, models: list[str] | None = None) -> None:
        """Evaluate the ``NNET_AND_PCIR`` mode."""
        self._evaluate_n_responses_for_mode(num_questions, ToolMode.NNET_AND_PCIR, models)

    def write_pnet_and_ncir_responses_to_csv(self, num_questions: int = 15, models: list[str] | None = None) -> None:
        """Evaluate the ``PNET_AND_NCIR`` mode."""
        self._evaluate_n_responses_for_mode(num_questions, ToolMode.PNET_AND_NCIR, models)

    def write_pnet_and_pcir_responses_to_csv(self, num_questions: int = 60, models: list[str] | None = None) -> None:
        """Evaluate the ``PNET_AND_PCIR`` mode."""
        self._evaluate_n_responses_for_mode(num_questions, ToolMode.PNET_AND_PCIR, models)

    def write_schematic_as_pdfs_responses_to_csv(
        self,
        num_questions: int = 15,
        models: list[str] | None = None,
    ) -> None:
        """Evaluate the ``PDF`` mode."""
        models = models or ["gpt-5.4-nano"]
        self._evaluate_n_responses_for_mode(num_questions, ToolMode.PDF, models)


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------


def parse_llm_response(raw_content: str) -> QuestionReasoning:
    """Parse a JSON response (possibly wrapped in markdown fences) into a QuestionReasoning model."""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_content, re.DOTALL)
    clean = match.group(1).strip() if match else raw_content.strip()
    return QuestionReasoning.model_validate_json(clean)


# ---------------------------------------------------------------------------
# Tool-calling agent: tool-based pipeline
# ---------------------------------------------------------------------------


def ask_agent(
    model: str,
    question: str,
    category: str,
    project_context: dict,
    component_ref: str | None = None,
    tool_mode: ToolMode = ToolMode.NNET_AND_NCIR,
) -> dict:
    """Run the tool-calling agent for a single question.

    Parameters
    ----------
    model:
        LLM model identifier (e.g. ``"meta-llama/llama-3.3-70b-instruct"``).
    question:
        The benchmark question text.
    category:
        Question category (e.g. ``"component_datasheet"``).
    project_context:
        Dictionary of project file paths.
    component_ref:
        Optional component reference designator.
    tool_mode:
        Operating mode that selects which tools are available to the LLM.
    """
    llm_tools = tools_for_mode(tool_mode)

    tool_caller = ToolCaller()
    client = get_openai_client()

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
) -> dict:
    """Run a primitive agent that answers directly without tool calls.

    Parameters
    ----------
    tool_mode:
        Operating mode. Defaults to ``ToolMode.PNET_AND_PCIR``.
    """
    caller = ToolCaller()
    client = get_openai_client()

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

    save_debug_json("agent_response.json", llm_response.model_dump())

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
    """Collect a response using .cir contents and JSON.net as inputs.

    Parameters
    ----------
    tool_mode:
        Operating mode. Defaults to ``ToolMode.NNET_AND_PCIR``.
    """
    llm_tools = tools_for_mode(tool_mode)

    tool_caller = ToolCaller()
    client = get_openai_client()

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

    # Build second-pass messages
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
    """Collect a response using .JSON.cir and .net contents as inputs.

    Parameters
    ----------
    tool_mode:
        Operating mode. Defaults to ``ToolMode.PNET_AND_NCIR``.
    """
    llm_tools = tools_for_mode(tool_mode)

    tool_caller = ToolCaller()
    client = get_openai_client()

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

        # Build second-pass messages
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
    """Answer a question by sending a schematic PDF to the LLM as vision input.

    Parameters
    ----------
    tool_mode:
        Operating mode. Defaults to ``ToolMode.PDF``.
    """
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


# ---------------------------------------------------------------------------
# Evaluation entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry-point for evaluation."""
    evaluator = EvaluateResults()
    evaluator.write_nnet_and_ncir_responses_to_csv()
    evaluator.write_nnet_and_pcir_responses_to_csv()
    evaluator.write_pnet_and_ncir_responses_to_csv()
    evaluator.write_pnet_and_pcir_responses_to_csv()
    evaluator.write_schematic_as_pdfs_responses_to_csv()


if __name__ == "__main__":
    main()
