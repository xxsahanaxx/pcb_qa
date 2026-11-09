#!/usr/bin/env python3
"""MCU bus-interposer ("man-in-the-middle") Trojan, realised in the schematic.

A complex RQ2 modification: find the board's microcontroller, pick one of its
data-bus lines (SPI ``MOSI``/``MISO``/``SCK``/``CS``, ``UART`` ``TX``/``RX``, or
I2C ``SDA``/``SCL``), **cut that line at the MCU pin** and splice an arbitrary
device in series across the break, so every byte between the MCU and its
peripheral now passes through the inserted part. One variant per data line.

The inserted device is a single-channel buffer (``74LVC1G34``) standing in for
any in-line interposer: pin 2 (input) takes the MCU side, pin 4 (output) drives
the peripheral side, pins 5/3 are ``VCC``/``GND``; pin 1 (NC) is left floating.

How the cut is made in the schematic (all edits on a copy; the source project
is SHA-256-checked before and after):

  * The MCU pin is located on its sheet. Any label sitting on that pin is
    removed and any wire touching it is deleted, capturing the wire's far end
    (the peripheral side of the break).
  * A global label ``Troj_<SIG>_IN`` is dropped on the now-isolated MCU pin, and
    ``Troj_<SIG>_OUT`` on the far end of each cut wire (so the peripheral side
    stays connected, through the buffer). When the pin was joined only by a
    label (no wire), the buffer's output instead carries the original net name,
    rejoining that side.
  * The buffer is added to ``lib_symbols`` and placed in free space, its input
    labelled ``Troj_<SIG>_IN``, its output the peripheral-side name, its power
    pins the board's rail and GND. ``no_connect``-typed targets are retyped to
    ``passive`` so the connection takes (same as the XOR module).

Ground truth is measured: the modified schematic is re-exported and
:func:`verify` confirms the MCU pin moved onto the Trojan input, the buffer
output rejoined exactly the rest of the original net, the rails gained the power
pins, and no net changed except by gaining/losing the MCU pin or a buffer pin.
A variant that cannot be cut in-schematic (MCU pin on a reused sheet, or a
topology the cut doesn't recognise) is reported and skipped.

Layout (default out-root
``outputs/Infected/Scenarios/RQ2_ComplexMods/McuBusInterposer``)::

    <out-root>/<board>/<SIGNAL>/_clean/<name>.net   # clean kicad-cli re-export
    <out-root>/<board>/<SIGNAL>/kicad/...           # modified project copy
    <out-root>/<board>/<SIGNAL>/<name>.net          # infected netlist
    <out-root>/<board>/<SIGNAL>/<name>.cir          # infected SPICE deck
    <out-root>/<board>/<SIGNAL>/mcu_bus_interposer.json
"""

import glob
import hashlib
import json
import os
import re
import shutil
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from . import core as nt
from . import gnd_short as gs
from . import gnd_short_ref as gsr
from . import gnd_short_random as gsx
from . import xor_gpio_trojan as xg
from . import xor_gpio_trojan_sch as X

CLEAN_GLOB = "outputs/Clean/*/*.net"
DEFAULT_OUT_ROOT = "outputs/Infected/Scenarios/RQ2_ComplexMods/McuBusInterposer"

# Single non-inverting buffer, SC70-5 / SOT-23-5. The in-line "interposer".
INTERP_LIBID = "74xGxx:74LVC1G34"
INTERP_VALUE = "74LVC1G34"
INTERP_FOOTPRINT = "Package_TO_SOT_SMD:SOT-23-5"
INTERP_SYM_NAME = "74LVC1G34"
INTERP_DESC = "Single non-inverting buffer (bus interposer)"
# placed-symbol pin list; roles for the four wired pins (1 = NC, floating)
INTERP_PINS = ["1", "2", "3", "4", "5"]
PIN_IN, PIN_OUT, PIN_VCC, PIN_GND = "2", "4", "5", "3"

# Data-bus signal names worth intercepting (word-ish, case-insensitive).
BUS_RE = re.compile(
    r"\b(SDA|SCL|MOSI|MISO|SCLK|SCK|COPI|CIPO|UART|USART|RXD?|TXD?|"
    r"NSS|SS|CS|CE|I2C|SPI)\b|[_/](SDA|SCL|MOSI|MISO|SCK|RX|TX)", re.I)
_SIG_TOKEN_RE = re.compile(
    r"SDA|SCL|MOSI|MISO|SCLK|SCK|COPI|CIPO|UART|USART|RXD|TXD|RX|TX|NSS|CS|CE|I2C|SPI", re.I)


# --------------------------------------------------------------------------- #
# MCU + data-line discovery
# --------------------------------------------------------------------------- #

def identify_mcu(nets: List[nt.Net]) -> Optional[str]:
    """The board's microcontroller: the ``U``/``Module`` reference with the most
    pins that also sits on at least one data-bus net."""
    pins: Dict[str, int] = defaultdict(int)
    for n in nets:
        for nd in n.nodes:
            if nd.ref.startswith("U") or nd.ref.startswith("Module"):
                pins[nd.ref] += 1
    if not pins:
        return None
    on_bus = {nd.ref for n in nets if BUS_RE.search(n.name) for nd in n.nodes}
    ranked = sorted(pins, key=lambda r: (r in on_bus, pins[r], r), reverse=True)
    return ranked[0]


def data_lines(nets: List[nt.Net], mcu: str) -> List[nt.Net]:
    """MCU data-bus nets that can be cut: >=2 nodes, carry the MCU, not power."""
    out = []
    for n in nets:
        if not BUS_RE.search(n.name) or len(n.nodes) < 2:
            continue
        if n.name.startswith("unconnected-") or xg._RAIL_RE.match(n.name) or "GND" in n.name.upper():
            continue
        if any(nd.ref == mcu for nd in n.nodes):
            out.append(n)
    return out


def signal_tag(net_name: str) -> str:
    m = _SIG_TOKEN_RE.search(net_name)
    return (m.group(0).upper() if m else "BUS")


# --------------------------------------------------------------------------- #
# The interposer symbol (parametrised clone of the XOR helpers)
# --------------------------------------------------------------------------- #

def _lib_entry() -> str:
    sym_lib = os.environ.get("XOR_SYMBOL_LIB", X.KICAD_SYMBOL_LIB)
    text = nt.read(sym_lib)
    m = re.search(r'\t\(symbol "' + re.escape(INTERP_SYM_NAME) + '"', text)
    if not m:
        raise ValueError(f"{INTERP_SYM_NAME!r} not in {sym_lib}")
    start = m.start() + 1
    block = text[start: nt.find_matching_paren(text, start) + 1]
    block = block.replace(f'(symbol "{INTERP_SYM_NAME}"', f'(symbol "{INTERP_LIBID}"', 1)
    return "\t\t" + block.replace("\n", "\n\t")


def _local_pins() -> Dict[str, Tuple[float, float]]:
    return {n: (px, py) for n, px, py in gsr._lib_pins(_lib_entry(), 1)}


def _inject_lib_symbol(root_text: str) -> str:
    if INTERP_LIBID in root_text:
        return root_text
    entry = _lib_entry()
    i = root_text.index("\t(lib_symbols")
    nl = root_text.index("\n", i) + 1
    return root_text[:nl] + entry + "\n" + root_text[nl:]


def _symbol_block(sx: float, sy: float, uref: str, inst_block: str) -> str:
    inst = re.sub(r'\(reference "[^"]*"\)', f'(reference "{uref}")', inst_block)
    inst = re.sub(r"\(unit \d+\)", "(unit 1)", inst)
    f = gs._fmt

    def prop(name, val, dy, hide=False):
        h = "\n\t\t\t\t(hide yes)" if hide else ""
        return (f'\t\t(property "{name}" "{val}"\n\t\t\t(at {f(sx)} {f(sy + dy)} 0)\n'
                f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){h}\n'
                f'\t\t\t)\n\t\t)\n')

    pins = "".join(f'\t\t(pin "{p}"\n\t\t\t(uuid "{uuid.uuid4()}")\n\t\t)\n' for p in INTERP_PINS)
    return (
        f'\t(symbol\n\t\t(lib_id "{INTERP_LIBID}")\n\t\t(at {f(sx)} {f(sy)} 0)\n'
        f'\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n'
        f'\t\t(dnp no)\n\t\t(uuid "{uuid.uuid4()}")\n'
        + prop("Reference", uref, 10.16)
        + prop("Value", INTERP_VALUE, -10.16)
        + prop("Footprint", INTERP_FOOTPRINT, 0, hide=True)
        + prop("Datasheet", "~", 0, hide=True)
        + prop("Description", INTERP_DESC, 0, hide=True)
        + pins
        + "\t\t" + inst + "\n"
        + "\t)"
    )


# --------------------------------------------------------------------------- #
# The cut
# --------------------------------------------------------------------------- #

def _coincident(ax: float, ay: float, bx: float, by: float) -> bool:
    return abs(ax - bx) < 0.01 and abs(ay - by) < 0.01


def _wire(x1: float, y1: float, x2: float, y2: float) -> str:
    f = gs._fmt
    return (f'(wire\n\t\t(pts\n\t\t\t(xy {f(x1)} {f(y1)}) (xy {f(x2)} {f(y2)})\n\t\t)\n'
            f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(uuid "{uuid.uuid4()}")\n\t)')


def _cut_at_pin(text: str, x: float, y: float) -> Tuple[str, List[Tuple[float, float]], bool]:
    """Isolate the pin at (x, y): remove any label on it and delete any wire
    touching it. Returns (new text, far ends of cut wires, had_on_pin_label)."""
    far_ends: List[Tuple[float, float]] = []
    had_label = False
    spans: List[Tuple[int, int]] = []
    for k, s, e in gs.top_level_blocks(text):
        block = text[s:e]
        if k in ("label", "global_label", "hierarchical_label"):
            m = re.search(r"\(at (-?[\d.]+) (-?[\d.]+)", block)
            if m and _coincident(float(m.group(1)), float(m.group(2)), x, y):
                had_label = True
                spans.append((s, e))
        elif k == "wire":
            pts = [(float(a), float(b)) for a, b in re.findall(r"\(xy (-?[\d.]+) (-?[\d.]+)\)", block)]
            if any(_coincident(px, py, x, y) for px, py in pts):
                far_ends += [(px, py) for px, py in pts if not _coincident(px, py, x, y)]
                spans.append((s, e))
    # delete spans high-offset-first, swallowing the whole line
    out = text
    for s, e in sorted(spans, key=lambda sp: -sp[0]):
        ls = out.rfind("\n", 0, s) + 1
        le = out.find("\n", e)
        out = out[:ls] + out[le + 1:]
    # dedupe far ends
    uniq: List[Tuple[float, float]] = []
    for p in far_ends:
        if not any(_coincident(*p, *q) for q in uniq):
            uniq.append((round(p[0], 4), round(p[1], 4)))
    return out, uniq, had_label


# --------------------------------------------------------------------------- #
# Verify (node membership, name-independent)
# --------------------------------------------------------------------------- #

def verify(clean_net: str, infected_net: str, rec: Dict) -> bool:
    clean_nets = nt.parse_nets(nt.read(clean_net))
    inf_nets = nt.parse_nets(nt.read(infected_net))
    clean = {n.name: n.node_set() for n in clean_nets}
    inf = {n.name: n.node_set() for n in inf_nets}
    uref = rec["trojan_ref"]
    mcu_pin = (rec["mcu_ref"], rec["mcu_pin"])
    rail, gnd, orig = rec["rail"], rec["gnd"], rec["line_net"]

    def net_of(pin):
        hits = [n.node_set() for n in inf_nets if pin in n.node_set()]
        return hits[0] if len(hits) == 1 else None

    if net_of((uref, PIN_IN)) != {mcu_pin, (uref, PIN_IN)}:
        return False
    if net_of((uref, PIN_OUT)) != (clean[orig] - {mcu_pin}) | {(uref, PIN_OUT)}:
        return False
    if inf.get(rail) != clean[rail] | {(uref, PIN_VCC)}:
        return False
    if inf.get(gnd) != clean[gnd] | {(uref, PIN_GND)}:
        return False
    present = {k for s in inf.values() for k in s if k[0] == uref}
    if present != {(uref, p) for p in INTERP_PINS}:
        return False
    # Partition preservation (name-independent): every clean net other than the
    # cut line, the rail and GND must survive with its exact membership -- even
    # if the cut renamed it (a wire-only line becomes Troj_<SIG>_OUT). This
    # catches any pin that wrongly moved onto a Trojan or power net.
    inf_sets = [n.node_set() for n in inf_nets]
    for n in clean_nets:
        if n.name in (orig, rail, gnd):
            continue
        if n.node_set() and n.node_set() not in inf_sets:
            return False
    return True


# --------------------------------------------------------------------------- #
# Build one variant
# --------------------------------------------------------------------------- #

def _next_uref(content: str) -> str:
    nums = [int(m.group(1)) for m in re.finditer(r'\(comp \(ref "U(\d+)"\)', content)]
    return f"U{max(nums, default=0) + 1}"


def build_variant(clean_net: str, mcu: str, net: nt.Net, dest: str) -> Dict:
    root_sch = gsr._schematic_for(clean_net)
    if not root_sch:
        raise ValueError(f"no schematic resolved for {clean_net}")
    sheets = gs.walk_sheets(root_sch)
    proj_dir = os.path.dirname(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]
    root_file = os.path.basename(root_sch)
    before = gsr._hash_tree(proj_dir)

    mcu_pin = next(nd.pin for nd in net.nodes if nd.ref == mcu)
    site = X._locate_pin(root_sch, mcu, mcu_pin)
    if site is None:
        raise ValueError(f"{mcu}.{mcu_pin} not on a singly-instantiated sheet")

    rail_net = xg.positive_rail(nt.parse_nets(nt.read(clean_net)))
    gnd_net = xg.gnd_net(nt.parse_nets(nt.read(clean_net)))
    if not (rail_net and gnd_net):
        raise ValueError("no positive rail / GND net on this board")

    uref = _next_uref(nt.read(clean_net))
    sig = signal_tag(net.name)
    in_label, out_label = f"Troj_{sig}_IN", f"Troj_{sig}_OUT"

    kicad_dir = os.path.join(dest, "kicad")
    if os.path.isdir(kicad_dir):
        shutil.rmtree(kicad_dir)
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)

    # The whole edit lives on the MCU's own sheet: the pin and the cut's far
    # end are both there, so IN/OUT can be reconnected with plain wires -- this
    # is topology-independent and works across hierarchical multi-sheet nets
    # that a global label could not rejoin.
    mcu_sheet_path = os.path.join(kicad_dir, site.sheet_file)
    text = nt.read(mcu_sheet_path)
    if site.etype == "no_connect":
        entry = gsr._lib_entry(text, site.lib_name)
        text = text.replace(entry, X._retype_pin(entry, mcu_pin, "passive"), 1)

    # --- cut the line at the MCU pin ---
    text, far_ends, _ = _cut_at_pin(text, site.x, site.y)

    # --- place the interposer on the MCU sheet, wire IN/OUT across the break ---
    text = _inject_lib_symbol(text)
    _, min_y, max_x, _ = gs.drawing_bbox(text)
    sx, sy = gs._snap(max_x + gs.MARGIN), gs._snap(min_y + gs.MARGIN)
    local = _local_pins()
    inst = X._neighbour_instances(text, root_sch)
    in_x, in_y = gsr._transform(sx, sy, 0, None, *local[PIN_IN])
    out_x, out_y = gsr._transform(sx, sy, 0, None, *local[PIN_OUT])
    vcc_x, vcc_y = gsr._transform(sx, sy, 0, None, *local[PIN_VCC])
    gnd_x, gnd_y = gsr._transform(sx, sy, 0, None, *local[PIN_GND])

    blocks = [_symbol_block(sx, sy, uref, inst),
              _wire(in_x, in_y, site.x, site.y),       # MCU pin -> buffer input
              X._glabel(in_label, in_x, in_y),          # name the Trojan input net
              X._glabel(rail_net.name, vcc_x, vcc_y),
              X._glabel(gnd_net.name, gnd_x, gnd_y)]
    if far_ends:
        peripheral_label = out_label
        for fx, fy in far_ends:                         # buffer output -> cut far end(s)
            blocks.append(_wire(out_x, out_y, fx, fy))
        blocks.append(X._glabel(out_label, out_x, out_y))
    else:
        # pin was joined only by a label (now removed): rejoin by name
        peripheral_label = net.name
        blocks.append(X._glabel(net.name, out_x, out_y))
    text = X._append_items(text, blocks)
    nt.write(mcu_sheet_path, text)

    # --- export + verify ---
    clean_reexport = os.path.join(dest, "_clean", f"{stem}.net")
    gs.export_netlist(root_sch, clean_reexport)
    out_net = os.path.join(dest, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    cir_status = "ok"
    try:
        gsx.export_spice(new_root, os.path.join(dest, f"{stem}.cir"))
    except Exception as exc:
        cir_status = f"error: {exc}"

    rec = {
        "trojan_ref": uref, "trojan_part": f"{INTERP_LIBID}",
        "mcu_ref": mcu, "mcu_pin": mcu_pin,
        "line_net": net.name, "signal": sig,
        "line_nodes": sorted(f"{r}.{p}" for r, p in net.node_set()),
        "rail": rail_net.name, "gnd": gnd_net.name,
        "added_nets": [in_label] + ([out_label] if far_ends else []),
        "peripheral_label": peripheral_label,
        "cut": "wire" if far_ends else "label",
        "wiring": {"IN": f"{mcu}.{mcu_pin} ({net.name}) -> {uref}.{PIN_IN}",
                   "OUT": f"{uref}.{PIN_OUT} -> {peripheral_label}",
                   "VCC": rail_net.name, "GND": gnd_net.name},
        "realisation": "schematic", "schematic_root": root_sch,
        "schematic": new_root, "output": out_net, "clean_reexport": clean_reexport,
        "cir": os.path.join(dest, f"{stem}.cir"), "cir_status": cir_status,
        "interposer_at": [sx, sy], "sheet": site.sheet_file,
        "retyped_no_connect": site.etype == "no_connect",
    }
    rec["verified"] = verify(clean_reexport, out_net, rec)
    if gsr._hash_tree(proj_dir) != before:
        raise RuntimeError(f"source project changed under {proj_dir}; aborting")
    return rec


# --------------------------------------------------------------------------- #
# Batch runner over every clean board
# --------------------------------------------------------------------------- #

def run_batch(clean_glob: str = CLEAN_GLOB, out_root: str = DEFAULT_OUT_ROOT) -> int:
    manifest: List[Dict] = []
    built = skipped = unverified = 0
    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        if not gsr._schematic_for(path):
            continue
        nets = nt.parse_nets(nt.read(path))
        mcu = identify_mcu(nets)
        if not mcu:
            continue
        lines = data_lines(nets, mcu)
        for net in lines:
            dest = os.path.join(out_root, board, snip_dir(net.name))
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            os.makedirs(os.path.join(dest, "_clean"), exist_ok=True)
            try:
                rec = build_variant(path, mcu, net, dest)
            except Exception as exc:
                shutil.rmtree(dest, ignore_errors=True)
                print(f"SKIP {board:22} {net.name:20} MCU={mcu}: {exc}")
                skipped += 1
                continue
            # Only emit measured-correct variants: a failed verify means the
            # cut/interpose did not reproduce exactly the intended change
            # (e.g. a net named by a label on the cut wire stub), so drop it.
            if not rec["verified"]:
                shutil.rmtree(dest, ignore_errors=True)
                print(f"SKIP {board:22} {net.name:20} MCU={mcu}: unverified "
                      f"(could not cut this topology cleanly)")
                skipped += 1
                continue
            with open(os.path.join(dest, "mcu_bus_interposer.json"), "w") as f:
                json.dump(rec, f, indent=2)
            manifest.append(rec)
            built += 1
            print(f"OK  {board:22} {net.name:20} "
                  f"MCU={mcu}.{rec['mcu_pin']} -> {rec['trojan_ref']} buffer "
                  f"(cut={rec['cut']}, cir={rec['cir_status']})")

    os.makedirs(out_root, exist_ok=True)
    with open(os.path.join(out_root, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{built} interposer variant(s) built, {skipped} skipped. "
          f"Manifest: {os.path.join(out_root, 'manifest.json')}")
    return 0


def snip_dir(net_name: str) -> str:
    from .snip import sanitise
    return sanitise(net_name)
