"""Benchmark evaluation — compare LLM responses to expected answers.

Refactored from the original ``evaluate_results.py``.

The agent runners (``ask_agent``, ``ask_agent_primitive``, etc.) now live in
:mod:`pcb_qa.evaluation.agents` and are re-exported here for convenience.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from pcb_qa.config import DEFAULT_LLM_MODELS, DEFAULT_TEMPERATURE, DEFAULT_PROJECTS_FILE, load_projects_config
from pcb_qa.evaluation.run_benchmark.agents import (
    ask_agent,
    ask_agent_primitive,
    ask_agent_with_json_netlist_and_spice_circuit,
    ask_agent_with_json_spice_and_netlist,
    ask_agent_with_schematic_as_pdf,
    parse_llm_response,
)
from pcb_qa.logging_config import logger
from pcb_qa.models.tool_definitions import ToolMode
from pcb_qa.utils.file_ops import CSVFileOperator, JSONFileOperator


__all__ = [
    "EvaluateResults",
    "compute_confusion_matrices_by_category",
    "ask_agent",
    "ask_agent_primitive",
    "ask_agent_with_json_netlist_and_spice_circuit",
    "ask_agent_with_json_spice_and_netlist",
    "ask_agent_with_schematic_as_pdf",
    "parse_llm_response",
]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class EvaluateResults:
    """Evaluate LLM responses against ground-truth answers.

    For each project and model, responses are loaded from the results
    directory, compared to expected answers, and metrics (accuracy,
    precision, recall, F1) are written to a CSV file.
    """

    def __init__(self, projects_config_path: str | None = DEFAULT_PROJECTS_FILE) -> None:
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
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

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

                logger.info(
                    "  Accuracy: %.4f | Precision: %.4f | Recall: %.4f | F1: %.4f",
                    accuracy, precision, recall, f1,
                )

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

    # -- confusion matrices per category -------------------------------------

    def compute_confusion_matrices_by_category(
        self,
        num_questions: int = 60,
        mode: ToolMode = ToolMode.NNET_AND_NCIR,
        models: list[str] | None = None,
        questions_file_suffix: str = "_60_questions_balanced.json",
    ) -> dict[str, dict[str, dict[str, dict[str, int]]]]:
        """Compute confusion matrices per category for each model and project.

        For each (project, model) pair, loads the ground-truth questions from
        the *balanced* 60-questions file and the corresponding LLM responses
        from the results directory, then groups results by category and
        computes a 2x2 confusion matrix (TP, TN, FP, FN) for each category.

        Parameters
        ----------
        num_questions:
            Number of questions to evaluate (default 60).
        mode:
            The evaluation mode (default ``NNET_AND_NCIR``).
        models:
            List of model names.  Defaults to ``DEFAULT_LLM_MODELS``.
        questions_file_suffix:
            Suffix to append to the project key to locate the questions file.
            The default looks for ``<project_key>_60_questions_balanced.json``
            in the project's parent directory.

        Returns
        -------
        dict
            Nested dict::

                {
                    "<project_key>": {
                        "<model>": {
                            "<category>": {
                                "TP": int, "TN": int, "FP": int, "FN": int
                            }
                        }
                    }
                }
        """
        models = models or self.llm_models
        results: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: {"TP": 0, "TN": 0, "FP": 0, "FN": 0}))
        )

        for project_key, project in self.project_files_dict.items():

            questions = self._load_questions_from_file(project["questions_json_file"])

            for model in models:
                logger.info(
                    "Confusion matrices — project: %s, model: %s, mode: %s",
                    project_key, model, mode.value,
                )

                for idx in range(len(questions)):
                    category = questions[idx]["category"]
                    actual = questions[idx]["answer"]

                    results_file = os.path.join(
                        project["parent_directory"], "results", mode.value, model, category, f"{idx + 1}.json"
                    )

                    try:
                        result = self.json_file_operator.read_from_json_file(results_file)
                        predicted = result["response"]["answer"]
                    except FileNotFoundError:
                        logger.warning("Result file not found: %s", results_file)
                        continue

                    # Update confusion matrix counts for this category
                    cm = results[project_key][model][category]
                    if actual == "YES" and predicted == "YES":
                        cm["TP"] += 1
                    elif actual == "NO" and predicted == "NO":
                        cm["TN"] += 1
                    elif actual == "NO" and predicted == "YES":
                        cm["FP"] += 1
                    elif actual == "YES" and predicted == "NO":
                        cm["FN"] += 1

        # Convert defaultdicts to regular dicts for clean output
        return {
            proj: {
                mod: dict(cats)
                for mod, cats in models_dict.items()
            }
            for proj, models_dict in results.items()
        }

    def write_confusion_matrices_to_csv(
        self,
        num_questions: int = 60,
        mode: ToolMode = ToolMode.NNET_AND_NCIR,
        models: list[str] | None = DEFAULT_LLM_MODELS
    ) -> None:
        """Compute per-category confusion matrices and write them to CSV files.

        One CSV per (project, model) pair is written to::

            <parent_dir>/results/<mode>/<model>_<project_key>_confusion.csv

        Each CSV contains columns:
        Category, TP, TN, FP, FN, Total, Accuracy
        """
        matrices = self.compute_confusion_matrices_by_category(
            num_questions=num_questions,
            mode=mode,
            models=models
        )

        for project_key, models_dict in matrices.items():
            parent_dir = self.project_files_dict[project_key]["parent_directory"]
            for model, categories in models_dict.items():
                target_csv = os.path.join(
                    parent_dir, "results", mode.value, f"{model}_{project_key}_confusion.csv"
                )
                self.csv_file_operator.create_header_for_csv(
                    csv_file=target_csv,
                    fields=["Category", "TP", "TN", "FP", "FN", "Total", "Accuracy"],
                )

                for category, cm in sorted(categories.items()):
                    total = cm["TP"] + cm["TN"] + cm["FP"] + cm["FN"]
                    accuracy = (cm["TP"] + cm["TN"]) / total if total > 0 else 0.0
                    row = [
                        category,
                        str(cm["TP"]),
                        str(cm["TN"]),
                        str(cm["FP"]),
                        str(cm["FN"]),
                        str(total),
                        f"{accuracy:.4f}",
                    ]
                    self.csv_file_operator.write_row_to_csv(target_csv, row)

                logger.info(
                    "Wrote confusion matrix CSV: %s", target_csv,
                )


# ---------------------------------------------------------------------------
# Standalone helper
# ---------------------------------------------------------------------------


def compute_confusion_matrices_by_category(
    num_questions: int = 60,
    mode: ToolMode = ToolMode.NNET_AND_NCIR,
    models: list[str] | None = DEFAULT_LLM_MODELS,
    projects_config_path: str | None = DEFAULT_PROJECTS_FILE
) -> dict[str, dict[str, dict[str, dict[str, int]]]]:
    """Standalone convenience wrapper.

    Creates an ``EvaluateResults`` instance and delegates to
    :meth:`EvaluateResults.compute_confusion_matrices_by_category`.
    """
    evaluator = EvaluateResults(projects_config_path=projects_config_path)
    return evaluator.compute_confusion_matrices_by_category(
        num_questions=num_questions,
        mode=mode,
        models=models
    )


# ---------------------------------------------------------------------------
# Evaluation entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry-point for evaluation."""
    evaluator = EvaluateResults()
    modes = [mode for mode in ToolMode]
    for mode in modes:
        evaluator.write_confusion_matrices_to_csv(mode=mode)
    # evaluator.write_nnet_and_ncir_responses_to_csv()
    # evaluator.write_nnet_and_pcir_responses_to_csv()
    # evaluator.write_pnet_and_ncir_responses_to_csv()
    # evaluator.write_pnet_and_pcir_responses_to_csv()
    # evaluator.write_schematic_as_pdfs_responses_to_csv()


if __name__ == "__main__":
    main()