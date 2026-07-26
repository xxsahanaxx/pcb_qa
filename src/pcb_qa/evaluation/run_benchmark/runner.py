"""Benchmark runner — orchestrate agents across all projects and models.

This module is the entry-point for ``pcb-qa run``.  It iterates over every
configured project and model, calls the appropriate agent for each question,
and writes the JSON result to ``<project>/<mode>/<model>/<category>/<idx>.json``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pcb_qa.config import DEFAULT_LLM_MODELS
from pcb_qa.logging_config import logger
from pcb_qa.models.project import ProjectFiles
from pcb_qa.models.tool_definitions import ToolMode
from pcb_qa.parsers.circuit_json import find_component

from pcb_qa.evaluation.run_benchmark.agents import ask_agent_primitive


def run_benchmark(
    tool_mode: ToolMode = ToolMode.NNET_AND_NCIR,
    models: list[str] | None = None,
    starting_index: int = 0,
) -> None:
    """Run the LLM benchmark across all projects and models.

    Parameters
    ----------
    tool_mode:
        Operating mode that selects which tools are available to the LLM.
    models:
        List of model identifiers.  Defaults to :data:`pcb_qa.config.DEFAULT_LLM_MODELS`.
    starting_index:
        Question index to resume from (useful for restarting a partial run).
    """
    models = models or DEFAULT_LLM_MODELS
    projects = ProjectFiles()

    for model in models:
        for project_name in projects:
            project = projects[project_name]
            project_context = project.to_dict()

            logger.info("Processing project: %s", project_name)
            logger.info("Running model: %s", model)

            with Path(project.questions_json_file).open(encoding="utf-8") as qf:
                data: list[dict[str, Any]] = json.load(qf)

            for idx in range(starting_index, len(data)):
                category = data[idx]["category"]
                question = data[idx]["question"]
                component_ref: str | None = None

                if category == "component_datasheet":
                    pattern = r"Does the component\s+(\S+)\s+(.+?)\s+according to its datasheet\?"
                    match = re.search(pattern, question.strip(), re.IGNORECASE)
                    if match:
                        component_ref = match.group(1).strip()

                    component_info = find_component(project.circuit_json_file, component_ref)
                    if component_info and "value" in component_info:
                        question = re.sub(component_ref, component_info["value"], question)

                logger.info("--- Question %d: %s ---", idx + 1, question)

                output_dir = os.path.join(
                    project.parent_directory,
                    tool_mode.value,
                    model.split("/")[-1],
                    category,
                )
                os.makedirs(output_dir, exist_ok=True)

                contents = ask_agent_primitive(
                    model=model,
                    question=question,
                    category=category,
                    project_context=project_context,
                    component_ref=component_ref,
                    tool_mode=tool_mode,
                    output_dir=output_dir,
                    question_index=idx + 1,
                )

                output_path = os.path.join(output_dir, f"{idx + 1}.json")
                with open(output_path, "w", encoding="utf-8") as of:
                    json.dump(contents, of, indent=4)
