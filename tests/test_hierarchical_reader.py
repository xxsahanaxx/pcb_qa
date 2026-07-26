"""Tests for pcb_qa.parsers.hierarchical_reader."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.parsers.hierarchical_reader import HierarchicalReader


class TestHierarchicalReaderInit:
    """Tests for HierarchicalReader initialization."""

    def test_init_with_file_path(self, tmp_path: Path) -> None:
        """Test initialization with a file path string."""
        sample_netlist = """
(kicad_netlist_version 4
 host_dependencies
 (components)
 (nets)
 (design
  (sheet
   (number 1)
   (name /)
   (title_block
    (source /path/to/sheet.sch)
   )
  )
 )
)
"""
        netlist_file = tmp_path / "test.net"
        netlist_file.write_text(sample_netlist, encoding="utf-8")
        with patch("pcb_qa.parsers.hierarchical_reader.netlist_sexp.NetlistSexp"):
            with patch("pcb_qa.parsers.hierarchical_reader.circuit_json.CircuitJSON"):
                with patch.object(HierarchicalReader, "_initialise_converter"):
                    reader = HierarchicalReader(str(netlist_file))
                    assert reader is not None

    def test_init_with_file_object(self) -> None:
        """Test initialization with a file-like object."""
        sample_text = "(kicad_netlist_version 4)"
        with patch("pcb_qa.parsers.hierarchical_reader.netlist_sexp.NetlistSexp"):
            with patch("pcb_qa.parsers.hierarchical_reader.circuit_json.CircuitJSON"):
                with patch.object(HierarchicalReader, "_initialise_converter"):
                    reader = HierarchicalReader(io.StringIO(sample_text))
                    assert reader is not None

    def test_init_with_raw_string(self) -> None:
        """Test initialization with a raw string."""
        with patch("pcb_qa.parsers.hierarchical_reader.netlist_sexp.NetlistSexp"):
            with patch("pcb_qa.parsers.hierarchical_reader.circuit_json.CircuitJSON"):
                with patch.object(HierarchicalReader, "_initialise_converter"):
                    reader = HierarchicalReader("(kicad_netlist_version 4)")
                    assert reader is not None


class TestHierarchicalReaderExtractSheetInfo:
    """Tests for extract_sheet_info."""

    def test_extract_sheet_info_populates_sheets(self) -> None:
        """Verify extract_sheet_info populates the sheets dict."""
        with patch("pcb_qa.parsers.hierarchical_reader.netlist_sexp.NetlistSexp"):
            with patch("pcb_qa.parsers.hierarchical_reader.circuit_json.CircuitJSON"):
                with patch.object(HierarchicalReader, "_initialise_converter"):
                    reader = HierarchicalReader("(kicad_netlist_version 4)")
                reader.netlist = MagicMock()
                reader.netlist.sheets = []
                reader.netlist.components = []
                reader.sheets = {}
                reader.top_sheet = None

                mock_sheet1 = MagicMock()
                mock_sheet1.num = 1
                mock_sheet1.path = "/top/"
                mock_sheet1.name = "top"
                mock_sheet1.parent = ""
                mock_sheet1.components = []
                mock_sheet1.local_nets = set()
                mock_sheet1.imported_nets = set()
                mock_sheet1.children = []

                mock_sheet2 = MagicMock()
                mock_sheet2.num = 2
                mock_sheet2.path = "/top/sub/"
                mock_sheet2.name = "sub"
                mock_sheet2.parent = "/top/"
                mock_sheet2.components = []
                mock_sheet2.local_nets = set()
                mock_sheet2.imported_nets = set()
                mock_sheet2.children = []

                with patch("pcb_qa.parsers.hierarchical_reader.Sheet"):
                    reader.netlist.sheets = [mock_sheet1, mock_sheet2]
                    reader.netlist.components = []

                    reader.extract_sheet_info()
                    assert reader.top_sheet is not None
                    assert len(reader.sheets) >= 1


class TestHierarchicalReaderFindLowestCommonAncestor:
    """Tests for find_lowest_common_ancestor."""

    def test_finds_common_ancestor(self) -> None:
        """Test finding the lowest common ancestor of two sheets."""
        with patch("pcb_qa.parsers.hierarchical_reader.netlist_sexp.NetlistSexp"):
            with patch("pcb_qa.parsers.hierarchical_reader.circuit_json.CircuitJSON"):
                with patch.object(HierarchicalReader, "_initialise_converter"):
                    reader = HierarchicalReader("(kicad_netlist_version 4)")
                reader.sheets = {
                    "/a/b/": MagicMock(path="/a/b/"),
                    "/a/c/": MagicMock(path="/a/c/"),
                }
                with patch("pcb_qa.parsers.hierarchical_reader.find_common_path_prefix", return_value="/a/"):
                    result = reader.find_lowest_common_ancestor("/a/b/", "/a/c/")
                    assert result == "/a/"


class TestHierarchicalReaderGenerateCircuitDict:
    """Tests for circuit dict generation."""

    def test_generate_subcircuits(self) -> None:
        """Verify generate_subcircuits_for_top_sheet_circuit returns list."""
        with patch("pcb_qa.parsers.hierarchical_reader.netlist_sexp.NetlistSexp"):
            with patch("pcb_qa.parsers.hierarchical_reader.circuit_json.CircuitJSON"):
                with patch.object(HierarchicalReader, "_initialise_converter"):
                    reader = HierarchicalReader("(kicad_netlist_version 4)")
                reader.sheets = {}
                reader.top_sheet = MagicMock()
                reader.top_sheet.name = "top"
                subs = reader.generate_subcircuits_for_top_sheet_circuit()
                assert isinstance(subs, list)

    def test_generate_top_sheet_circuit_includes_subcircuits(self) -> None:
        """Verify top sheet circuit includes subcircuits list."""
        with patch("pcb_qa.parsers.hierarchical_reader.netlist_sexp.NetlistSexp"):
            with patch("pcb_qa.parsers.hierarchical_reader.circuit_json.CircuitJSON"):
                with patch.object(HierarchicalReader, "_initialise_converter"):
                    reader = HierarchicalReader("(kicad_netlist_version 4)")
                reader.sheets = {}
                reader.top_sheet = MagicMock()
                reader.top_sheet.name = "top"
                with patch.object(reader, "create_circuit_dict_from_sheet", return_value={"name": "top", "subcircuits": []}):
                    top_circuit = reader.generate_top_sheet_circuit()
                    assert "subcircuits" in top_circuit