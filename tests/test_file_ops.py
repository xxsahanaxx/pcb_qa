"""Tests for pcb_qa.utils.file_ops."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pcb_qa.utils.file_ops import CSVFileOperator, JSONFileOperator


class TestJSONFileOperator:
    """Tests for JSONFileOperator."""

    def test_read_from_json_file(self, tmp_path: Path) -> None:
        data = {"key": "value", "number": 42}
        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        result = JSONFileOperator.read_from_json_file(file_path)
        assert result == data

    def test_write_to_json_file(self, tmp_path: Path) -> None:
        data = {"name": "test", "values": [1, 2, 3]}
        output_file = tmp_path / "output.json"

        JSONFileOperator.write_to_json_file(data, output_file)

        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        assert loaded == data

    def test_write_to_json_file_pretty_printed(self, tmp_path: Path) -> None:
        data = {"a": 1}
        output_file = tmp_path / "pretty.json"
        JSONFileOperator.write_to_json_file(data, output_file)

        content = output_file.read_text(encoding="utf-8")
        # Should be indented with 4 spaces
        assert "    " in content

    def test_read_nonexistent_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            JSONFileOperator.read_from_json_file("/nonexistent/file.json")

    def test_read_and_write_roundtrip(self, tmp_path: Path) -> None:
        original = {"unicode": "日本語", "nested": {"a": [True, False]}}
        file_path = tmp_path / "roundtrip.json"
        JSONFileOperator.write_to_json_file(original, file_path)
        loaded = JSONFileOperator.read_from_json_file(file_path)
        assert loaded == original

    def test_write_empty_dict(self, tmp_path: Path) -> None:
        output_file = tmp_path / "empty.json"
        JSONFileOperator.write_to_json_file({}, output_file)
        loaded = JSONFileOperator.read_from_json_file(output_file)
        assert loaded == {}


class TestCSVFileOperator:
    """Tests for CSVFileOperator."""

    def test_create_header_for_csv(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        fields = ["Name", "Value", "Category"]
        CSVFileOperator.create_header_for_csv(csv_file, fields)

        assert csv_file.exists()
        with open(csv_file, "r") as fh:
            reader = csv.DictReader(fh)
            assert reader.fieldnames == fields

    def test_write_row_to_csv(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        fields = ["Name", "Value"]
        CSVFileOperator.create_header_for_csv(csv_file, fields)

        row = ["R1", "10k"]
        CSVFileOperator.write_row_to_csv(csv_file, row)

        with open(csv_file, "r") as fh:
            lines = fh.readlines()
        assert len(lines) == 2  # header + 1 data row
        assert "R1" in lines[1]
        assert "10k" in lines[1]

    def test_write_multiple_rows(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "multi.csv"
        fields = ["Ref", "Value"]
        CSVFileOperator.create_header_for_csv(csv_file, fields)

        CSVFileOperator.write_row_to_csv(csv_file, ["R1", "10k"])
        CSVFileOperator.write_row_to_csv(csv_file, ["C1", "100n"])

        with open(csv_file, "r") as fh:
            lines = fh.readlines()
        assert len(lines) == 3  # header + 2 data rows

    def test_csv_header_only(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "header_only.csv"
        CSVFileOperator.create_header_for_csv(csv_file, ["Col1", "Col2"])

        with open(csv_file, "r") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0] == ["Col1", "Col2"]