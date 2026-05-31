"""Tests for pcb_qa.__main__."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.__main__ import main


class TestMain:
    """Tests for the CLI entry point."""

    def test_no_command_prints_help(self) -> None:
        with patch("sys.argv", ["pcb-qa"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_evaluate_command(self) -> None:
        with patch("sys.argv", ["pcb-qa", "evaluate"]):
            with patch("pcb_qa.__main__.cmd_evaluate") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_init_kicad_command(self) -> None:
        with patch("sys.argv", ["pcb-qa", "init-kicad"]):
            with patch("pcb_qa.__main__.cmd_init_kicad") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_projects_command(self) -> None:
        with patch("sys.argv", ["pcb-qa", "projects"]):
            with patch("pcb_qa.__main__.cmd_projects") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_embed_command(self) -> None:
        with patch("sys.argv", ["pcb-qa", "embed"]):
            with patch("pcb_qa.__main__.cmd_embed") as mock_cmd:
                main()
                mock_cmd.assert_called_once()


class TestCmdProjects:
    """Tests for the cmd_projects function."""

    def test_cmd_projects_prints_output(self, capsys) -> None:
        from pcb_qa.__main__ import cmd_projects

        args = MagicMock()
        with patch("pcb_qa.config.load_projects_config") as mock_load:
            mock_load.return_value = {
                "TestProject": {
                    "parent_directory": "/tmp/out",
                    "circuit_json_file": "/tmp/out/test.json",
                    "netlist_file": "",
                    "spice_circuit_file": "",
                    "spice_json_file": "",
                    "questions_json_file": "",
                    "datasheet_files": ["a.pdf", "b.pdf"],
                }
            }
            cmd_projects(args)
            captured = capsys.readouterr()
            assert "TestProject" in captured.out
            assert "2 files" in captured.out
