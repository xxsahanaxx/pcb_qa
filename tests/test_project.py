"""Tests for pcb_qa.models.project."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pcb_qa.models.project import Project, ProjectFiles


class TestProject:
    """Tests for the Project dataclass."""

    def test_default_values(self) -> None:
        p = Project()
        assert p.name == ""
        assert p.parent_directory == ""
        assert p.circuit_json_file == ""
        assert p.netlist_file == ""
        assert p.spice_circuit_file == ""
        assert p.spice_json_file == ""
        assert p.questions_json_file == ""
        assert p.datasheet_files == []

    def test_custom_values(self) -> None:
        p = Project(
            name="TestBoard",
            parent_directory="/output",
            circuit_json_file="/output/test.json",
            datasheet_files=["/ds/U1.pdf"],
        )
        assert p.name == "TestBoard"
        assert p.parent_directory == "/output"
        assert p.circuit_json_file == "/output/test.json"
        assert p.datasheet_files == ["/ds/U1.pdf"]

    def test_to_dict(self) -> None:
        p = Project(name="Board", parent_directory="/out", datasheet_files=["a.pdf"])
        d = p.to_dict()
        assert d["name"] == "Board"
        assert d["parent_directory"] == "/out"
        assert d["datasheet_files"] == ["a.pdf"]
        assert isinstance(d, dict)

    def test_to_dict_all_keys(self) -> None:
        p = Project()
        d = p.to_dict()
        expected_keys = {
            "name", "parent_directory", "circuit_json_file", "netlist_file",
            "spice_circuit_file", "spice_json_file", "questions_json_file",
            "datasheet_files",
        }
        assert set(d.keys()) == expected_keys

    def test_find_datasheet_found(self) -> None:
        p = Project(datasheet_files=["/ds/U1.pdf", "/ds/R2.pdf"])
        result = p.find_datasheet_for_component("U1")
        assert result == "/ds/U1.pdf"

    def test_find_datasheet_not_found(self) -> None:
        p = Project(datasheet_files=["/ds/U1.pdf"])
        result = p.find_datasheet_for_component("C5")
        assert result == ""

    def test_find_datasheet_empty_list(self) -> None:
        p = Project()
        result = p.find_datasheet_for_component("U1")
        assert result == ""

    def test_find_datasheet_partial_match(self) -> None:
        p = Project(datasheet_files=["/ds/STM32F103.pdf"])
        result = p.find_datasheet_for_component("STM32")
        assert result == "/ds/STM32F103.pdf"


class TestProjectFiles:
    """Tests for the ProjectFiles registry."""

    def test_load_projects(self, sample_projects_config: dict) -> None:
        config_file = Path("test_config.json")
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            assert "TestProject" in pf

    def test_getitem(self, sample_projects_config: dict) -> None:
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            project = pf["TestProject"]
            assert isinstance(project, Project)
            assert project.name == "TestProject"

    def test_iter(self, sample_projects_config: dict) -> None:
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            keys = list(pf)
            assert "TestProject" in keys

    def test_keys(self, sample_projects_config: dict) -> None:
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            assert "TestProject" in pf.keys()

    def test_items(self, sample_projects_config: dict) -> None:
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            items = list(pf.items())
            assert len(items) == 1
            assert items[0][0] == "TestProject"
            assert isinstance(items[0][1], Project)

    def test_to_json(self, sample_projects_config: dict) -> None:
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            result = pf.to_json()
            assert "TestProject" in result
            assert result["TestProject"]["parent_directory"] == "./outputs/TestProject"

    def test_to_json_write_to_file(self, sample_projects_config: dict, tmp_path: Path) -> None:
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            output_path = str(tmp_path / "output.json")
            pf.to_json(output_path)
            assert (tmp_path / "output.json").exists()
            with open(output_path, "r") as fh:
                loaded = json.load(fh)
            assert "TestProject" in loaded

    def test_project_populates_datasheet_files(self, sample_projects_config: dict) -> None:
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            project = pf["TestProject"]
            assert len(project.datasheet_files) == 2

    def test_missing_datasheet_files_defaults_to_empty(self) -> None:
        config = {
            "Minimal": {
                "parent_directory": "/tmp",
                "circuit_json_file": "",
                "netlist_file": "",
                "spice_circuit_file": "",
                "spice_json_file": "",
                "questions_json_file": "",
            }
        }
        with patch("pcb_qa.models.project.load_projects_config", return_value=config):
            pf = ProjectFiles()
            project = pf["Minimal"]
            assert project.datasheet_files == []

    def test_getitem_key_error(self, sample_projects_config: dict) -> None:
        with patch("pcb_qa.models.project.load_projects_config", return_value=sample_projects_config):
            pf = ProjectFiles()
            with pytest.raises(KeyError):
                _ = pf["NonexistentProject"]