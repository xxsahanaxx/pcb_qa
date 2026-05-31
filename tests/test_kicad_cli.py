"""Tests for pcb_qa.kicad.cli."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.kicad.cli import KiCadInterface


class TestKiCadInterfaceInit:
    """Tests for KiCadInterface initialisation."""

    @patch("pcb_qa.kicad.cli.subprocess.run")
    def test_init_sets_executable_path(self, mock_run: MagicMock) -> None:
        ki = KiCadInterface()
        assert ki.executable.endswith("kicad-cli")

    @patch("pcb_qa.kicad.cli.subprocess.run")
    def test_init_with_override_path(self, mock_run: MagicMock, tmp_path: Path) -> None:
        fake_cli = tmp_path / "kicad-cli"
        fake_cli.write_text("#!/bin/sh\necho fake")
        fake_cli.chmod(0o755)

        ki = KiCadInterface(kicad_cli_path=str(fake_cli))
        assert ki.executable.endswith("kicad-cli")

    @patch("pcb_qa.kicad.cli.subprocess.run")
    def test_init_with_invalid_path_logs_warning(self, mock_run: MagicMock) -> None:
        with patch.dict(os.environ, {"KICAD_CLI_PATH": "/nonexistent/path"}):
            ki = KiCadInterface()
            # Should not raise, just log a warning
            assert ki.executable.endswith("kicad-cli")

    @patch("pcb_qa.kicad.cli.subprocess.run")
    def test_init_without_env_var(self, mock_run: MagicMock) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("KICAD_CLI_PATH", None)
            ki = KiCadInterface()
            assert ki.executable.endswith("kicad-cli")


class TestExportNetlist:
    """Tests for export_netlist_with_kicad_cli."""

    @patch("pcb_qa.kicad.cli.subprocess.run")
    def test_export_with_existing_project(self, mock_run: MagicMock, tmp_path: Path) -> None:
        project_file = tmp_path / "test.kicad_sch"
        project_file.write_text("fake schematic")
        output_file = tmp_path / "output.net"

        ki = KiCadInterface()
        ki.export_netlist_with_kicad_cli(str(project_file), str(output_file))

        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        assert "netlist" in call_args
        assert "kicadsexpr" in call_args

    @patch("pcb_qa.kicad.cli.subprocess.run")
    def test_export_with_nonexistent_project(self, mock_run: MagicMock) -> None:
        ki = KiCadInterface()
        with pytest.raises(FileNotFoundError, match="No valid schematic"):
            ki.export_netlist_with_kicad_cli("/nonexistent/file.kicad_sch", "/tmp/output.net")


class TestExportSpice:
    """Tests for export_spice_with_kicad_cli."""

    @patch("pcb_qa.kicad.cli.subprocess.run")
    def test_export_with_existing_project(self, mock_run: MagicMock, tmp_path: Path) -> None:
        project_file = tmp_path / "test.kicad_sch"
        project_file.write_text("fake schematic")
        output_file = tmp_path / "output.cir"

        ki = KiCadInterface()
        ki.export_spice_with_kicad_cli(str(project_file), str(output_file))

        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        assert "netlist" in call_args
        assert "spice" in call_args

    @patch("pcb_qa.kicad.cli.subprocess.run")
    def test_export_with_nonexistent_project(self, mock_run: MagicMock) -> None:
        ki = KiCadInterface()
        with pytest.raises(FileNotFoundError, match="No valid schematic"):
            ki.export_spice_with_kicad_cli("/nonexistent/proj.kicad_pro", "/tmp/out.cir")