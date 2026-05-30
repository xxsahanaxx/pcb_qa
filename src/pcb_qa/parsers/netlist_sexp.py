"""S-expression wrappers for KiCad netlist parsing.

Refactored from the original ``netlist_sexp.py``.
"""

from __future__ import annotations

import re

from simp_sexp import Sexp
from skidl.netlist_to_skidl import Sheet, find_common_path_prefix, legalize_name


class ComponentSexp:
    """Deliver attributes from a component S-expression."""

    def __init__(self, sexp: Sexp) -> None:
        self.sheetpath: str = sexp.search("/comp/sheetpath/names").value
        self.ref: str = sexp.search("/comp/ref").value
        self.value: str = sexp.search("/comp/value").value
        self.footprint: str = sexp.search("/comp/footprint").value
        self.fields: list[FieldsSexp] = [FieldsSexp(f) for f in sexp.search("/comp/fields/field")]
        self.name: str = sexp.search("/comp/libsource/part").value
        self.lib: str = sexp.search("/comp/libsource/lib").value
        self.properties: list[PropertySexp] = [PropertySexp(p) for p in sexp.search("/comp/property")]
        self.tstamps: str = sexp.search("/comp/tstamps").value

    def component_sexp_to_dict(self) -> dict:
        """Serialise the component to a plain dictionary."""
        props = {p.name: p.value for p in self.properties}
        fields = {f.name: f.value for f in self.fields}

        return {
            "symbol": self.lib,
            "ref": self.ref,
            "value": self.value,
            "footprint": self.footprint,
            "datasheet": fields.get("Datasheet", ""),
            "description": fields.get("Description", ""),
            "properties": props,
            "tstamps": self.tstamps,
            "fields": fields,
            "pins": [],
        }


class FieldsSexp:
    """Deliver attributes from a fields S-expression."""

    def __init__(self, sexp: Sexp) -> None:
        self.name: str = sexp.search("/field/name").value
        result = re.split(r"[\(\)]\s*", sexp.to_str(break_inc=0)[:-1])
        self.value: str = result[-1]


class PropertySexp:
    """Deliver attributes from a property S-expression."""

    def __init__(self, sexp: Sexp) -> None:
        self.name: str = sexp.search("/property/name").value
        self.value: str = sexp.search("/property/value").value


class SheetSexp:
    """Deliver attributes from a sheet S-expression."""

    def __init__(self, sexp: Sexp) -> None:
        self.num: str = sexp.search("/sheet/number").value
        self.name: str = sexp.search("/sheet/name").value
        self.source: str = sexp.search("/sheet/title_block/source").value

    def sheet_sexp_to_dict(self) -> dict:
        return {"num": self.num, "name": self.name, "source": self.source}


class PinSexp:
    """Deliver attributes from a pin S-expression."""

    def __init__(self, sexp: Sexp) -> None:
        self.name: str = sexp.search("/node/ref").value
        self.number: str = sexp.search("/node/pin").value
        self.type: str = sexp.search("/node/pintype").value

    def create_pin_dict(self) -> dict:
        return {"name": self.name, "number": self.number, "type": self.type}

    def map_pin_to_net_dict(self, component_name: str) -> dict:
        return {"component": component_name, "pin": self.create_pin_dict()}


class NetSexp:
    """Deliver attributes from a net S-expression."""

    def __init__(self, sexp: Sexp) -> None:
        self.name: str = sexp.search("/net/name").value
        self.pins: list[PinSexp] = [PinSexp(node) for node in sexp.search("/net/node")]

    def net_sexp_to_dict(self, component_list: list) -> dict:
        pins = []
        for pin in self.pins:
            if any(comp.ref == pin.name for comp in component_list):
                entry = pin.map_pin_to_net_dict(legalize_name(pin.name))
                pins.append(entry)
        return pins


class NetlistSexp:
    """Represents a full KiCad netlist.

    Attributes
    ----------
    components:
        List of components in the netlist.
    nets:
        List of electrical nets in the netlist.
    sheets:
        List of hierarchical sheets in the netlist.
    """

    def __init__(self, sexp: Sexp) -> None:
        self.sheets: list[SheetSexp] = [SheetSexp(s) for s in sexp.search("design/sheet")]
        self.components: list[ComponentSexp] = [ComponentSexp(c) for c in sexp.search("components/comp")]
        self.nets: list[NetSexp] = [NetSexp(n) for n in sexp.search("nets/net")]