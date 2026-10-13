"""netlist_modifications — insert hardware Trojans into KiCad S-expression netlists.

Public API
----------
Engine (see ``core``):
    parse_nets, extract_spec, apply_spec, render_net_block, describe_op,
    Net, Node, read, write

Bus "snip" Trojan (see ``snip``): split one net into Troj_<SIGNAL>0 / ...1
    bus_nets, build_split, snip.run_single, snip.run_batch

Bus RX/TX "swap" Trojan (see ``swap``): cross a pair into Troj_RX / Troj_TX
    uart_pairs, build_swap, swap.run_single, swap.run_batch

Passive "tolerance swap" Trojan (see ``tolerance``): re-grade an R/C/L part
    parse_passives, build_substitution, tolerance.run_single, tolerance.run_batch

Passive "magnitude swap" Trojan (see ``value``): shift an R/C/L part's value
    parse_candidates, value.build_substitution, value.run_single, value.run_batch

Schematic "GND short" Trojan (see ``gnd_short``): tie a labelled net to GND
    in the .kicad_sch and re-export with kicad-cli
    gnd_short.find_candidates, gnd_short.run_single, gnd_short.run_batch

Schematic "GND short by pin" Trojan (see ``gnd_short_ref``): tie a component
    pin (e.g. C1) to GND on its sheet and re-export with kicad-cli
    gnd_short_ref.locate, gnd_short_ref.run_single, gnd_short_ref.run_batch

The command-line front end is ``netlist_modifications.insert_modification.cli``
(run it as ``python -m netlist_modifications``).
"""

from .insert_modification import core, gnd_short, snip, swap, tolerance, value
from .insert_modification.core import (
    Net,
    Node,
    apply_spec,
    describe_op,
    extract_spec,
    parse_nets,
    read,
    render_net_block,
    write,
)
from .insert_modification.snip import bus_nets, build_split
from .insert_modification.swap import build_swap, uart_pairs
from .insert_modification.tolerance import build_substitution, parse_passives
from .insert_modification.value import parse_candidates

__all__ = [
    "core",
    "gnd_short",
    "snip",
    "swap",
    "tolerance",
    "value",
    "Net",
    "Node",
    "apply_spec",
    "describe_op",
    "extract_spec",
    "parse_nets",
    "read",
    "render_net_block",
    "write",
    "bus_nets",
    "build_split",
    "uart_pairs",
    "build_swap",
    "parse_passives",
    "build_substitution",
    "parse_candidates",
]
