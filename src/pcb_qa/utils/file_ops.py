"""File I/O helpers for JSON and CSV operations.

Refactored from the original ``file_helpers.py``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def save_debug_json(path: str | Path, contents: dict[str, Any]) -> None:
    """Write *contents* to *path* as pretty-printed JSON, ignoring ``OSError``."""
    try:
        JSONFileOperator.write_to_json_file(contents, path)
    except OSError:
        pass


class JSONFileOperator:
    """Read and write JSON files with UTF-8 encoding."""

    @staticmethod
    def read_from_json_file(read_file: str | Path) -> dict[str, Any]:
        """Load and return the contents of a JSON file."""
        with open(read_file, "r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def write_to_json_file(contents: dict[str, Any], output_file: str | Path) -> None:
        """Serialise *contents* to a JSON file with pretty-printing."""
        with open(output_file, "w", encoding="utf-8") as fh:
            json.dump(contents, fh, indent=4, ensure_ascii=False)


class CSVFileOperator:
    """Append-oriented CSV writer."""

    @staticmethod
    def create_header_for_csv(csv_file: str | Path, fields: list[str]) -> None:
        """Write the header row to a fresh CSV file."""
        with open(csv_file, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()

    @staticmethod
    def write_row_to_csv(csv_file: str | Path, row: list[str]) -> None:
        """Append a single row to an existing CSV file."""
        with open(csv_file, "a", newline="\n") as fh:
            writer = csv.writer(fh)
            writer.writerow(row)