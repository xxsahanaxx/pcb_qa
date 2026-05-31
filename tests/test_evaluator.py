"""Tests for pcb_qa.evaluation.evaluator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pcb_qa.evaluation.evaluator import EvaluateResults
from pcb_qa.models.tool_definitions import ToolMode


class TestEvaluateResultsInit:
    """Tests for EvaluateResults initialisation."""

    def test_init_with_default_config(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config") as mock_load:
            mock_load.return_value = {}
            ev = EvaluateResults()
            assert isinstance(ev.llm_models, list)
            assert len(ev.llm_models) > 0

    def test_init_with_custom_config(self, tmp_path: Path) -> None:
        config = {"TestProject": {"parent_directory": "/tmp"}}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")

        ev = EvaluateResults(projects_config_path=str(config_file))
        assert "TestProject" in ev.project_files_dict

    def test_initial_state(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            assert ev.actual_responses == []
            assert ev.predicted_responses == []


class TestLoadQuestionsFromFile:
    """Tests for _load_questions_from_file."""

    def test_load_valid_file(self, tmp_path: Path) -> None:
        questions = [
            {"question": "Is R1 a resistor?", "answer": "YES", "category": "component_type"},
            {"question": "Is C1 connected to GND?", "answer": "NO", "category": "connections"},
        ]
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps(questions), encoding="utf-8")

        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            result = ev._load_questions_from_file(str(q_file))
            assert len(result) == 2
            assert result[0]["answer"] == "YES"

    def test_load_nonexistent_file(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            with pytest.raises(FileNotFoundError):
                ev._load_questions_from_file("/nonexistent/questions.json")


class TestReadResponseFromFile:
    """Tests for _read_response_from_file."""

    def test_read_valid_response(self, tmp_path: Path) -> None:
        response_data = {"response": {"answer": "YES", "reasoning": "Because"}}
        result_file = tmp_path / "result.json"
        result_file.write_text(json.dumps(response_data), encoding="utf-8")

        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            ev._read_response_from_file(str(result_file))
            assert ev.predicted_responses == ["YES"]

    def test_read_missing_file_appends_na(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            ev._read_response_from_file("/nonexistent/result.json")
            assert ev.predicted_responses == ["N/A"]


class TestEvaluateNResponsesForMode:
    """Tests for _evaluate_n_responses_for_mode."""

    def test_evaluate_creates_csv(self, tmp_path: Path) -> None:
        parent_dir = tmp_path / "project"
        results_dir = parent_dir / "results" / "NNet&NCir" / "test-model"
        results_dir.mkdir(parents=True, exist_ok=True)
        (parent_dir / "results" / "NNet&NCir").mkdir(parents=True, exist_ok=True)

        questions = [
            {"question": "Q1", "answer": "YES", "category": "cat1"},
            {"question": "Q2", "answer": "NO", "category": "cat1"},
        ]
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps(questions), encoding="utf-8")

        for i, q in enumerate(questions):
            cat_dir = results_dir / q["category"]
            cat_dir.mkdir(parents=True, exist_ok=True)
            response_file = cat_dir / f"{i + 1}.json"
            response_file.write_text(
                json.dumps({"response": {"answer": q["answer"]}}),
                encoding="utf-8",
            )

        config = {
            "test_project": {
                "parent_directory": str(parent_dir),
                "circuit_json_file": "",
                "netlist_file": "",
                "spice_circuit_file": "",
                "spice_json_file": "",
                "questions_json_file": str(q_file),
                "datasheet_files": [],
            }
        }

        ev = EvaluateResults.__new__(EvaluateResults)
        ev.llm_models = ["test-model"]
        ev.actual_responses = []
        ev.predicted_responses = []
        ev.csv_file_operator = __import__("pcb_qa.utils.file_ops", fromlist=["CSVFileOperator"]).CSVFileOperator()
        ev.json_file_operator = __import__("pcb_qa.utils.file_ops", fromlist=["JSONFileOperator"]).JSONFileOperator()
        ev.project_files_dict = config

        ev._evaluate_n_responses_for_mode(2, ToolMode.NNET_AND_NCIR, models=["test-model"])

        csv_path = parent_dir / "results" / "NNet&NCir" / "test-model_test_project.csv"
        assert csv_path.exists()


class TestPublicModeMethods:
    """Tests for the public evaluation mode methods."""

    def test_write_nnet_and_ncir(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            with patch.object(ev, "_evaluate_n_responses_for_mode") as mock_eval:
                ev.write_nnet_and_ncir_responses_to_csv(num_questions=10, models=["m1"])
                mock_eval.assert_called_once_with(10, ToolMode.NNET_AND_NCIR, ["m1"])

    def test_write_nnet_and_pcir(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            with patch.object(ev, "_evaluate_n_responses_for_mode") as mock_eval:
                ev.write_nnet_and_pcir_responses_to_csv(num_questions=5, models=["m2"])
                mock_eval.assert_called_once_with(5, ToolMode.NNET_AND_PCIR, ["m2"])

    def test_write_pnet_and_ncir(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            with patch.object(ev, "_evaluate_n_responses_for_mode") as mock_eval:
                ev.write_pnet_and_ncir_responses_to_csv(num_questions=8, models=["m3"])
                mock_eval.assert_called_once_with(8, ToolMode.PNET_AND_NCIR, ["m3"])

    def test_write_pnet_and_pcir(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            with patch.object(ev, "_evaluate_n_responses_for_mode") as mock_eval:
                ev.write_pnet_and_pcir_responses_to_csv(num_questions=12, models=["m4"])
                mock_eval.assert_called_once_with(12, ToolMode.PNET_AND_PCIR, ["m4"])

    def test_write_schematic_as_pdfs(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            with patch.object(ev, "_evaluate_n_responses_for_mode") as mock_eval:
                ev.write_schematic_as_pdfs_responses_to_csv(num_questions=3)
                mock_eval.assert_called_once_with(3, ToolMode.PDF, ["gpt-5.4-nano"])

    def test_write_schematic_as_pdfs_custom_models(self) -> None:
        with patch("pcb_qa.evaluation.evaluator.load_projects_config", return_value={}):
            ev = EvaluateResults()
            with patch.object(ev, "_evaluate_n_responses_for_mode") as mock_eval:
                ev.write_schematic_as_pdfs_responses_to_csv(num_questions=5, models=["custom"])
                mock_eval.assert_called_once_with(5, ToolMode.PDF, ["custom"])
