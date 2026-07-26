"""Tests for the question_banks.prompts module."""

from __future__ import annotations

import pathlib

from pcb_qa.question_banks.prompts import get_prompts_path, get_prompts_text


class TestGetPromptsPath:
    """Tests for get_prompts_path()."""

    def test_returns_path_object(self) -> None:
        path = get_prompts_path()
        assert isinstance(path, pathlib.Path)

    def test_resides_in_question_banks(self) -> None:
        path = get_prompts_path()
        assert path.parent.name == "question_banks"

    def test_filename(self) -> None:
        path = get_prompts_path()
        assert path.name == "question_generation_prompts.md"

    def test_file_exists_on_disk(self) -> None:
        path = get_prompts_path()
        assert path.exists(), f"Prompts file not found at {path}"

    def test_is_file_not_directory(self) -> None:
        path = get_prompts_path()
        assert path.is_file()


class TestGetPromptsText:
    """Tests for get_prompts_text()."""

    def test_returns_string(self) -> None:
        text = get_prompts_text()
        assert isinstance(text, str)

    def test_non_empty(self) -> None:
        text = get_prompts_text()
        assert len(text) > 0, "Prompts file should not be empty"

    def test_contains_question_categories(self) -> None:
        text = get_prompts_text()
        assert "component_datasheet" in text
        assert "spice_behaviour" in text
        assert "theory_layout" in text

    def test_contains_summary_table(self) -> None:
        text = get_prompts_text()
        assert "Summary Table" in text or "| Category" in text

    def test_content_readable(self) -> None:
        text = get_prompts_text()
        # Should have proper markdown heading structure
        heading_lines = [line for line in text.splitlines() if line.startswith("#")]
        assert len(heading_lines) >= 3, "Should have multiple markdown headings"

    def test_consistent_with_get_prompts_path(self) -> None:
        path = get_prompts_path()
        text = get_prompts_text()
        assert text == path.read_text(encoding="utf-8"), (
            "get_prompts_text() should return the same content as reading the file directly"
        )