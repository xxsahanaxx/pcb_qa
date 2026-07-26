"""Tests for pcb_qa.evaluation.runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.evaluation.run_benchmark.runner import run_benchmark
from pcb_qa.models.tool_definitions import ToolMode


class TestRunBenchmark:
    """Tests for the benchmark runner."""

    def test_run_benchmark_creates_output_files(self, tmp_path: Path) -> None:
        """Verify run_benchmark writes JSON result files."""
        fake_projects = {
            "TestProject": MagicMock(
                parent_directory=str(tmp_path / "project"),
                questions_json_file=str(tmp_path / "project" / "questions.json"),
                circuit_json_file=str(tmp_path / "project" / "circuit.json"),
                spice_circuit_file=str(tmp_path / "project" / "circuit.cir"),
                spice_json_file=str(tmp_path / "project" / "spice.json"),
                to_dict=MagicMock(return_value={
                    "parent_directory": str(tmp_path / "project"),
                    "circuit_json_file": str(tmp_path / "project" / "circuit.json"),
                    "spice_circuit_file": str(tmp_path / "project" / "circuit.cir"),
                    "spice_json_file": str(tmp_path / "project" / "spice.json"),
                }),
            )
        }

        questions_data = [
            {
                "category": "component_datasheet",
                "question": "Does the component U1 operate at 3.3V according to its datasheet?",
                "answer": "YES",
            }
        ]

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        Path(fake_projects["TestProject"].questions_json_file).write_text(
            json.dumps(questions_data), encoding="utf-8"
        )
        Path(fake_projects["TestProject"].circuit_json_file).write_text(
            json.dumps({"components": {"U1": {"value": "3.3V"}}, "nets": {}}), encoding="utf-8"
        )

        fake_agent_response = {
            "category": "component_datasheet",
            "question": "Does the component U1 operate at 3.3V according to its datasheet?",
            "response": {
                "answer": "YES",
                "reasoning": "Test reasoning",
                "is_final": True,
            },
        }

        with patch("pcb_qa.evaluation.run_benchmark.runner.ProjectFiles") as mock_files, \
             patch("pcb_qa.evaluation.run_benchmark.runner.ask_agent_primitive", return_value=fake_agent_response) as mock_agent:
            mock_projects = MagicMock()
            mock_projects.__iter__ = MagicMock(return_value=iter(fake_projects))
            mock_projects.__getitem__ = MagicMock(side_effect=lambda k: fake_projects[k])
            mock_files.return_value = mock_projects

            run_benchmark(tool_mode=ToolMode.NNET_AND_NCIR, models=["test-model"], starting_index=0)

            mock_agent.assert_called_once()
            output_dir = project_dir / ToolMode.NNET_AND_NCIR.value / "test-model" / "component_datasheet"
            assert output_dir.exists()
            output_file = output_dir / "1.json"
            assert output_file.exists()
            saved = json.loads(output_file.read_text(encoding="utf-8"))
            assert saved["response"]["answer"] == "YES"

    def test_run_benchmark_starting_index(self, tmp_path: Path) -> None:
        """Verify starting_index skips earlier questions."""
        fake_projects = {
            "TestProject": MagicMock(
                parent_directory=str(tmp_path / "project"),
                questions_json_file=str(tmp_path / "project" / "questions.json"),
                circuit_json_file=str(tmp_path / "project" / "circuit.json"),
                spice_circuit_file=str(tmp_path / "project" / "circuit.cir"),
                spice_json_file=str(tmp_path / "project" / "spice.json"),
                to_dict=MagicMock(return_value={
                    "parent_directory": str(tmp_path / "project"),
                    "circuit_json_file": str(tmp_path / "project" / "circuit.json"),
                    "spice_circuit_file": str(tmp_path / "project" / "circuit.cir"),
                    "spice_json_file": str(tmp_path / "project" / "spice.json"),
                }),
            )
        }

        questions_data = [
            {"category": "cat1", "question": "Q1", "answer": "YES"},
            {"category": "cat2", "question": "Q2", "answer": "NO"},
        ]

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        Path(fake_projects["TestProject"].questions_json_file).write_text(
            json.dumps(questions_data), encoding="utf-8"
        )
        Path(fake_projects["TestProject"].circuit_json_file).write_text(
            json.dumps({"components": {}, "nets": {}}), encoding="utf-8"
        )

        fake_response = {
            "category": "cat2",
            "question": "Q2",
            "response": {"answer": "NO", "reasoning": "", "is_final": True},
        }

        with patch("pcb_qa.evaluation.run_benchmark.runner.ProjectFiles") as mock_files, \
             patch("pcb_qa.evaluation.run_benchmark.runner.ask_agent_primitive", return_value=fake_response) as mock_agent:
            mock_projects = MagicMock()
            mock_projects.__iter__ = MagicMock(return_value=iter(fake_projects))
            mock_projects.__getitem__ = MagicMock(side_effect=lambda k: fake_projects[k])
            mock_files.return_value = mock_projects

            run_benchmark(tool_mode=ToolMode.NNET_AND_NCIR, models=["test-model"], starting_index=1)

            assert mock_agent.call_count == 1
            call_args = mock_agent.call_args
            assert call_args.kwargs["question"] == "Q2"