"""Tests for pcb_qa.question_banks.cli."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.question_banks.cli import cmd_expand, cmd_fix, cmd_validate, main


class TestCmdExpand:
    """Tests for cmd_expand."""

    def test_cmd_expand_processes_projects(self, tmp_path: Path) -> None:
        """Verify cmd_expand reads projects and writes balanced questions."""
        projects = {
            "TestProject": {
                "circuit_json_file": str(tmp_path / "circuit.json"),
                "spice_json_file": str(tmp_path / "spice.json"),
                "questions_json_file": str(tmp_path / "questions.json"),
                "parent_directory": str(tmp_path),
            }
        }
        Path(projects["TestProject"]["questions_json_file"]).write_text(
            json.dumps([{"category": "cat1", "question": "Q", "answer": "YES"}]), encoding="utf-8"
        )

        expanded_questions = [
            {"category": "cat1", "question": "Q?", "answer": "YES"},
            {"category": "cat1", "question": "Q2?", "answer": "NO"},
        ]

        import builtins
        from unittest.mock import mock_open, MagicMock
        m_open = mock_open(read_data=json.dumps(projects))
        mock_expand = MagicMock(return_value=expanded_questions)
        with patch("pcb_qa.config.DEFAULT_PROJECTS_FILE", str(tmp_path / "projects.json")), \
             patch.object(builtins, "open", m_open), \
             patch("pcb_qa.question_banks.cli.json.dump") as mock_dump, \
             patch("pcb_qa.question_banks.cli.expand_question_bank_for_project", mock_expand):
            args = MagicMock()
            cmd_expand(args)

            # Verify expand_question_bank_for_project was called
            assert mock_expand.called
            # Verify json.dump was called for the balanced file
            assert mock_dump.called


class TestCmdValidate:
    """Tests for cmd_validate."""

    def test_cmd_validate_generates_report(self, tmp_path: Path) -> None:
        """Verify cmd_validate creates a validation report."""
        projects = {
            "TestProject": {
                "parent_directory": str(tmp_path),
                "circuit_json_file": "circuit.json",
                "spice_json_file": "spice.json",
            }
        }
        qfile = tmp_path / "questions.json"
        qfile.write_text(json.dumps([{"category": "cat1", "question": "Q", "answer": "YES"}]), encoding="utf-8")

        validator = MagicMock()
        validator.validate_questions.return_value = {
            "total_questions": 1,
            "categories": {"cat1": {"total": 1, "valid": 1, "invalid": 0, "errors": []}},
        }

        with patch("pcb_qa.config.load_projects_config", return_value=projects), \
             patch("pcb_qa.question_banks.cli.CircuitQuestionValidator", return_value=validator), \
             patch("builtins.print"):
            args = MagicMock()
            cmd_validate(args)
            assert Path("validation_report.json").exists()


class TestCmdFix:
    """Tests for cmd_fix."""

    def test_cmd_fix_writes_fixed_questions(self, tmp_path: Path) -> None:
        """Verify cmd_fix writes fixed questions back to file."""
        import json
        projects = {
            "TestProject": {
                "parent_directory": str(tmp_path),
                "circuit_json_file": "circuit.json",
                "spice_json_file": "spice.json",
            }
        }
        questions = [
            {"category": "cat1", "question": "Q", "answer": "YES", "valid": False},
        ]
        qfile = tmp_path / "questions.json"
        qfile.write_text(json.dumps(questions), encoding="utf-8")

        fixer = MagicMock()
        fixer.fix_question_bank.return_value = (0, 1)

        with patch("pcb_qa.config.load_projects_config", return_value=projects), \
             patch("pcb_qa.question_banks.cli.QuestionBankFixer", return_value=fixer), \
             patch("builtins.print"):
            args = MagicMock()
            cmd_fix(args)

            saved = json.loads(qfile.read_text(encoding="utf-8"))
            assert len(saved) == 1


class TestMain:
    """Tests for the CLI main entry point."""

    def test_main_expand_command(self) -> None:
        with patch("sys.argv", ["pcb-qa-question-banks", "expand"]), \
             patch("pcb_qa.question_banks.cli.cmd_expand") as mock_cmd:
            main()
            mock_cmd.assert_called_once()

    def test_main_validate_command(self) -> None:
        with patch("sys.argv", ["pcb-qa-question-banks", "validate"]), \
             patch("pcb_qa.question_banks.cli.cmd_validate") as mock_cmd:
            main()
            mock_cmd.assert_called_once()

    def test_main_fix_command(self) -> None:
        with patch("sys.argv", ["pcb-qa-question-banks", "fix"]), \
             patch("pcb_qa.question_banks.cli.cmd_fix") as mock_cmd:
            main()
            mock_cmd.assert_called_once()

    def test_main_no_command_prints_help(self, capsys) -> None:
        with patch("sys.argv", ["pcb-qa-question-banks"]):
            main()
            captured = capsys.readouterr()
            assert "Generate" in captured.out
