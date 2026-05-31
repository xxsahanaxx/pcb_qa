"""Benchmark evaluation — compare LLM responses to expected answers.

Refactored from the original ``evaluate_results.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from pcb_qa.config import DEFAULT_LLM_MODELS, load_projects_config
from pcb_qa.logging_config import logger
from pcb_qa.models.tool_definitions import ToolMode
from pcb_qa.utils.file_ops import CSVFileOperator, JSONFileOperator


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