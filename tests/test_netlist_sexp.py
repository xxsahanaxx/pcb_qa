"""Tests for pcb_qa.parsers.netlist_sexp."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pcb_qa.parsers.netlist_sexp import (
    ComponentSexp,
    FieldsSexp,
    NetSexp,
    NetlistSexp,
    PinSexp,
    PropertySexp,
    SheetSexp,
)


class ValueMock:
    """Simple mock with a value attribute."""
    def __init__(self, value):
        self.value = value


class TestComponentSexp:
    """Tests for ComponentSexp."""

    def test_component_sexp_to_dict(self) -> None:
        """Verify component serialization to dict."""
        mock_sexp = MagicMock()
        values = {
            "/comp/sheetpath/names": "/top/",
            "/comp/ref": "U1",
            "/comp/value": "3.3V",
            "/comp/footprint": "Package_SOIC:SOIC-8",
            "/comp/libsource/part": "STM32",
            "/comp/libsource/lib": "stm32",
            "/comp/tstamps": "abc123",
        }

        def side(path):
            if path in ("/comp/property", "/comp/fields/field"):
                return []
            return ValueMock(values.get(path, ""))

        mock_sexp.search.side_effect = side

        comp = ComponentSexp(mock_sexp)
        result = comp.component_sexp_to_dict()

        assert result["ref"] == "U1"
        assert result["value"] == "3.3V"
        assert result["footprint"] == "Package_SOIC:SOIC-8"
        assert result["symbol"] == "stm32"
        assert result["datasheet"] == ""
        assert result["pins"] == []


class TestFieldsSexp:
    """Tests for FieldsSexp."""

    def test_fields_parsing(self) -> None:
        """Verify field name and value extraction."""
        mock_sexp = MagicMock()
        mock_sexp.search.return_value = ValueMock("Description")
        mock_sexp.to_str.return_value = "(field (name Description) MCU)"

        field = FieldsSexp(mock_sexp)
        assert field.name == "Description"
        assert field.value == "MCU"


class TestPropertySexp:
    """Tests for PropertySexp."""

    def test_property_parsing(self) -> None:
        """Verify property name and value extraction."""
        mock_sexp = MagicMock()
        mock_sexp.search.return_value = ValueMock("Reference")

        prop = PropertySexp(mock_sexp)
        assert prop.name == "Reference"


class TestSheetSexp:
    """Tests for SheetSexp."""

    def test_sheet_sexp_to_dict(self) -> None:
        """Verify sheet serialization to dict."""
        mock_sexp = MagicMock()
        mock_sexp.search.return_value = ValueMock("1")

        sheet = SheetSexp(mock_sexp)
        result = sheet.sheet_sexp_to_dict()

        assert result["num"] == "1"


class TestPinSexp:
    """Tests for PinSexp."""

    def test_create_pin_dict(self) -> None:
        """Verify pin dict creation."""
        mock_sexp = MagicMock()
        mock_sexp.search.return_value = ValueMock("U1")

        pin = PinSexp(mock_sexp)
        result = pin.create_pin_dict()

        assert result["name"] == "U1"


class TestNetSexp:
    """Tests for NetSexp."""

    def test_net_sexp_to_dict_empty_nodes(self) -> None:
        """Verify net dict returns empty when no nodes match."""
        mock_net_sexp = MagicMock()
        mock_net_sexp.search("/net/name").return_value = ValueMock("VCC")
        mock_net_sexp.search("/net/node").return_value = []

        net = NetSexp(mock_net_sexp)
        result = net.net_sexp_to_dict([])

        assert result == []


class TestNetlistSexp:
    """Tests for NetlistSexp."""

    def test_netlist_parse(self) -> None:
        """Verify netlist parsing populates sheets list."""
        mock_sexp = MagicMock()
        mock_sheet = MagicMock()
        mock_sexp.search.side_effect = lambda path: [mock_sheet] if path == "design/sheet" else []

        with patch("pcb_qa.parsers.netlist_sexp.SheetSexp", side_effect=lambda x: x):
            netlist = NetlistSexp(mock_sexp)
            assert len(netlist.sheets) == 1
            assert netlist.sheets == [mock_sheet]