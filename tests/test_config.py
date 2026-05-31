"""Tests for pcb_qa.config."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pcb_qa.config import (
    CONFIGS_DIR,
    DEFAULT_LLM_MODELS,
    DEFAULT_PROJECTS_FILE,
    KICAD_CLI_PATH,
    NGSPICE_PATH,
    OUTPUTS_DIR,
    PROJECT_ROOT,
    _env,
    load_projects_config,
)


class TestPathConstants:
    """Tests for path constants."""

    def test_project_root_is_repository_root(self) -> None:
        assert PROJECT_ROOT == Path(__file__).resolve().parent.parent

    def test_configs_dir_under_project_root(self) -> None:
        assert CONFIGS_DIR == PROJECT_ROOT / "configs"

    def test_outputs_dir_under_project_root(self) -> None:
        assert OUTPUTS_DIR == PROJECT_ROOT / "outputs"

    def test_default_projects_file_under_configs_dir(self) -> None:
        assert DEFAULT_PROJECTS_FILE == CONFIGS_DIR / "projects.json"


class TestEnvHelper:
    """Tests for the _env helper."""

    def test_env_returns_value(self) -> None:
        with patch.dict(os.environ, {"TEST_PCB_QA_VAR": "hello"}):
            assert _env("TEST_PCB_QA_VAR") == "hello"

    def test_env_returns_default_when_missing(self) -> None:
        assert _env("NONEXISTENT_VAR_PCB_QA", default="fallback") == "fallback"

    def test_env_returns_none_when_no_default(self) -> None:
        assert _env("NONEXISTENT_VAR_PCB_QA_2") is None


class TestLLMDefaults:
    """Tests for default LLM model list."""

    def test_default_models_is_list(self) -> None:
        assert isinstance(DEFAULT_LLM_MODELS, list)

    def test_default_models_non_empty(self) -> None:
        assert len(DEFAULT_LLM_MODELS) > 0

    def test_default_models_are_strings(self) -> None:
        for model in DEFAULT_LLM_MODELS:
            assert isinstance(model, str)


class TestLoadProjectsConfig:
    """Tests for load_projects_config."""

    def test_load_default_config(self) -> None:
        config = load_projects_config()
        assert isinstance(config, dict)
        assert len(config) > 0

    def test_load_custom_config(self, tmp_path: Path) -> None:
        config_data = {"MyProject": {"parent_directory": "/tmp/test"}}
        config_file = tmp_path / "test_projects.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        result = load_projects_config(config_file)
        assert result == config_data

    def test_load_config_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_projects_config("/nonexistent/path/config.json")

    def test_load_config_invalid_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_projects_config(bad_file)