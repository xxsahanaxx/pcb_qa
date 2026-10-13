#!/usr/bin/env python3
"""GND short by component pin, on whichever sheet carries the part.

Where :mod:`gnd_short` targets a *labelled* net, this module targets a component
pin (e.g. ``C1`` pin 1). It locates the symbol on any sheet of the hierarchy,
computes where the chosen pin connects on that sheet, and drops a clone of that
sheet's GND power symbol so the clone's pin lands exactly on that point. KiCad
connects items by coincident endpoints, so no wire is needed and the
clean-vs-modified ``.kicad_sch`` diff is a single added symbol. This works even
when the pin's net has no label (power rails, auto-named nets like
``Net-(D2-K)``, ...), which the label-based module cannot reach.

The target may be on the root sheet or on any sub-sheet, as long as that sheet is
instantiated exactly once. A sheet that is reused (instantiated more than once) is
refused, because editing the one shared symbol would short the pin in every
instance, not just the one asked for; :func:`locate` reports that as the reason.

The source project is never modified. Everything is built from a copy under the
output directory, and :func:`_hash_tree` is checked before and after so an
accidental write to the original aborts the run.

Pin selection: by default the pin that is *not* already tied to GND in the clean
export (a decoupling cap typically has one pin on GND already); ``--pin`` forces a
specific pin. Ground truth comes from :func:`gnd_short.diff_against_gnd` over the
two kicad-cli exports, and the run fails if the chosen pin did not move onto GND.
"""

import glob
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import core as nt
from . import gnd_short as gs
from .snip import sanitise

CLEAN_GLOB = gs.CLEAN_GLOB
SCHEMATIC_ROOT = gs.SCHEMATIC_ROOT


# --------------------------------------------------------------------------- #
# Block helpers
# --------------------------------------------------------------------------- #

def _ref_of(sym_block: str) -> Optional[str]:
    """Reference of a placed symbol, from its Reference property (the sheet's own
    name for it, independent of how the sheet is instantiated elsewhere)."""
    m = re.search(r'\(property "Reference" "([^"]*)"', sym_block)
    if m:
        return m.group(1)
    m = re.search(r'\(reference "([^"]*)"', sym_block)
    return m.group(1) if m else None


def _instance_refs(sym_block: str) -> List[str]:
    """Every distinct reference this symbol takes across its instance paths.

    More than one means the symbol's sheet is instantiated multiple times, so
    the one symbol is a different part in each (e.g. C1 here, C26/C120 elsewhere).
    """
    inst = re.search(r"\(instances\b", sym_block)
    if not inst:
        return []
    body = sym_block[inst.start(): nt.find_matching_paren(sym_block, inst.start()) + 1]
    seen = []
    for m in re.finditer(r'\(reference "([^"]*)"', body):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def _lib_name(sym_block: str) -> str:
    m = re.search(r'\(lib_name "([^"]*)"', sym_block) or re.search(r'\(lib_id "([^"]*)"', sym_block)
    return m.group(1)


def _lib_entry(text: str, name: str) -> str:
    """The lib_symbols definition a placed symbol is drawn from."""
    lib = next(text[s:e] for k, s, e in gs.top_level_blocks(text) if k == "lib_symbols")
    m = re.search(r'\n\t\t\(symbol "' + re.escape(name) + '"', lib)
    if not m:
        raise ValueError(f"lib symbol {name!r} not in lib_symbols")
    start = m.start() + 3
    return lib[start: nt.find_matching_paren(lib, start) + 1]


def _placement(sym_block: str) -> Tuple[float, float, int, Optional[str]]:
    """(x, y, angle, mirror) of a placed symbol."""
    m = re.search(r"\(at (-?[\d.]+) (-?[\d.]+) (\d+)\)", sym_block)
    x, y, ang = float(m.group(1)), float(m.group(2)), int(m.group(3))
    mm = re.search(r"\(mirror (x|y)\)", sym_block[:500])
    return x, y, ang, (mm.group(1) if mm else None)


def _unit(sym_block: str) -> int:
    m = re.search(r"\(unit (\d+)\)", sym_block)
    return int(m.group(1)) if m else 1


def _lib_pins(lib_entry: str, unit: int) -> List[Tuple[str, float, float]]:
    """(number, x, y) of each pin in the lib symbol, for `unit` (and common unit 0)."""
    pins: List[Tuple[str, float, float]] = []
    for sub in re.finditer(r'\(symbol "[^"]*_(\d+)_(\d+)"', lib_entry):
        u = int(sub.group(1))
        if u not in (0, unit):
            continue
        s = sub.start()
        body = lib_entry[s: nt.find_matching_paren(lib_entry, s) + 1]
        for pin in re.finditer(r"\(pin\s+\w+\s+\w+\s*\(at (-?[\d.]+) (-?[\d.]+) \d+\)", body):
            e = nt.find_matching_paren(body, pin.start())
            num = re.search(r'\(number "([^"]*)"', body[pin.start():e + 1])
            if num:
                pins.append((num.group(1), float(pin.group(1)), float(pin.group(2))))
    return pins


def _transform(x: float, y: float, ang: int, mirror: Optional[str],
               px: float, py: float) -> Tuple[float, float]:
    """Sheet coords of a lib pin at (px, py): flip Y, rotate, then mirror, offset.

    Rotate-then-mirror matches KiCad's wire endpoints on this dataset's
    schematics (verified against every rotated/mirrored symbol).
    """
    py = -py
    t = math.radians(ang)
    rx = px * math.cos(t) + py * math.sin(t)
    ry = -px * math.sin(t) + py * math.cos(t)
    if mirror == "x":
        ry = -ry
    elif mirror == "y":
        rx = -rx
    return round(x + rx, 4), round(y + ry, 4)


def pin_xy(text: str, sym_block: str, pin: str) -> Tuple[float, float]:
    """Sheet (x, y) where `pin` of the placed symbol connects."""
    lib = _lib_entry(text, _lib_name(sym_block))
    pins = {n: (px, py) for n, px, py in _lib_pins(lib, _unit(sym_block))}
    if pin not in pins:
        raise ValueError(f"{_ref_of(sym_block)} has no pin {pin!r} "
                         f"(pins: {', '.join(sorted(pins)) or 'none'})")
    x, y, ang, mirror = _placement(sym_block)
    return _transform(x, y, ang, mirror, *pins[pin])


def gnd_pin_offset(text: str, gnd_block: str) -> Tuple[float, float]:
    """Vector from the GND symbol's origin to its single pin, on the sheet."""
    x, y, _, _ = _placement(gnd_block)
    pins = _lib_pins(_lib_entry(text, _lib_name(gnd_block)), _unit(gnd_block))
    gx, gy = pin_xy(text, gnd_block, pins[0][0])
    return gx - x, gy - y


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #

@dataclass
class Target:
    sheet_file: str  # the sheet file (relative to the project dir) carrying `ref`
    sym_block: str   # the placed target symbol
    gnd_block: str   # a GND power symbol to clone from the SAME sheet


def _find_on_sheet(text: str, ref: str) -> Tuple[Optional[str], Optional[str]]:
    """(target symbol, a GND symbol) on one sheet, by block text; None if absent."""
    sym = gnd = None
    for k, s, e in gs.top_level_blocks(text):
        if k != "symbol":
            continue
        block = text[s:e]
        if _ref_of(block) == ref or ref in _instance_refs(block):
            sym = block
        elif gs._is_gnd(block) and gnd is None:
            gnd = block
    return sym, gnd


def locate(root_sch: str, ref: str) -> Optional[Target]:
    """Locate `ref` on any sheet in the hierarchy, with a GND symbol to clone.

    Returns None if `ref` is on no sheet. Raises ValueError (so callers can skip
    with the reason) if `ref`'s sheet is instantiated more than once -- editing
    the one shared symbol would short every instance, not just `ref` -- or if its
    sheet has no GND symbol to clone a correctly-scoped one from.
    """
    proj_dir = os.path.dirname(root_sch)
    for sheet in gs.walk_sheets(root_sch):
        text = nt.read(os.path.join(proj_dir, sheet.file))
        sym, gnd = _find_on_sheet(text, ref)
        if sym is None:
            continue
        others = [r for r in _instance_refs(sym) if r != ref]
        if others:
            raise ValueError(f"{ref} is on a sheet reused {len(others) + 1} times "
                             f"(also {', '.join(others)}); editing it would short "
                             f"every instance, not just {ref}")
        if gnd is None:
            raise ValueError(f"{ref}'s sheet ({sheet.file}) has no GND symbol to clone")
        return Target(sheet.file, sym, gnd)
    return None


def choose_pin(clean_net: str, ref: str, forced: Optional[str]) -> str:
    """Pin of `ref` to short: forced, else the one not already on GND."""
    nets = nt.parse_nets(nt.read(clean_net))
    pins = {n.pin for net in nets for n in net.nodes if n.ref == ref}
    if not pins:
        raise ValueError(f"{ref} not found in clean netlist {clean_net}")
    if forced is not None:
        if forced not in pins:
            raise ValueError(f"{ref} has no pin {forced!r} (pins: {', '.join(sorted(pins))})")
        return forced
    on_gnd = {n.pin for net in nets if net.name == "GND" for n in net.nodes if n.ref == ref}
    free = sorted(pins - on_gnd)
    if not free:
        raise ValueError(f"every pin of {ref} is already on GND; pass --pin to force")
    return free[0]


# --------------------------------------------------------------------------- #
# Insertion
# --------------------------------------------------------------------------- #

def insert_gnd_on_pin(text: str, target: Target, pin: str, used_refs: set) -> Tuple[str, Dict]:
    """Return (modified sheet text, info): a GND clone placed on `ref`.`pin`."""
    tx, ty = pin_xy(text, target.sym_block, pin)
    ox, oy = gnd_pin_offset(text, target.gnd_block)
    # place the clone so its pin coincides with the target pin
    new_x, new_y = tx - ox, ty - oy

    gx, gy, _, _ = _placement(target.gnd_block)
    gnd = gs._shift(target.gnd_block, new_x - gx, new_y - gy)
    gnd = gs._fresh_uuids(gnd)

    refs: List[str] = []

    def _ref(m):
        refs.append(gs._next_ref(used_refs))
        return f'(reference "{refs[-1]}")'
    gnd = re.sub(r'\(reference "[^"]*"\)', _ref, gnd)
    if refs:
        gnd = re.sub(r'(\(property "Reference" )"[^"]*"', rf'\1"{refs[0]}"', gnd, count=1)

    insertion = f"\t{gnd}\n"
    anchor = text.find("\n\t(sheet_instances")
    if anchor < 0:
        anchor = text.rstrip().rfind(")") - 1
    modified = text[: anchor + 1] + insertion + text[anchor + 1:]
    info = {"ref_pin": pin, "pin_at": [round(tx, 4), round(ty, 4)], "gnd_refs": refs}
    return modified, info


# --------------------------------------------------------------------------- #
# Guard: the original project must not change
# --------------------------------------------------------------------------- #

def _hash_tree(proj_dir: str) -> Dict[str, str]:
    out = {}
    for dp, _, files in os.walk(proj_dir):
        for name in files:
            p = os.path.join(dp, name)
            with open(p, "rb") as f:
                out[os.path.relpath(p, proj_dir)] = hashlib.sha256(f.read()).hexdigest()
    return out


# --------------------------------------------------------------------------- #
# Build one variant
# --------------------------------------------------------------------------- #

def build_variant(root_sch: str, ref: str, out_dir: str, clean_net: str,
                  pin: Optional[str] = None, erc: bool = False) -> Dict:
    """Write one modified project copy + its exported netlist into `out_dir`."""
    sheets = gs.walk_sheets(root_sch)
    proj_dir = os.path.dirname(root_sch)

    target = locate(root_sch, ref)
    if target is None:
        raise ValueError(f"{ref} is on no sheet of {os.path.basename(root_sch)}")
    which = choose_pin(clean_net, ref, pin)

    stem = os.path.splitext(os.path.basename(root_sch))[0]
    kicad_dir = os.path.join(out_dir, "kicad")
    if os.path.isdir(kicad_dir):
        shutil.rmtree(kicad_dir)
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)

    # edit only the copied sheet that carries the target (root or sub-sheet)
    copied_sheet = os.path.join(kicad_dir, target.sheet_file)
    modified, info = insert_gnd_on_pin(nt.read(copied_sheet), target, which,
                                       gs._used_pwr_refs(proj_dir, sheets))
    nt.write(copied_sheet, modified)

    out_net = os.path.join(out_dir, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    record = {
        "ref": ref, "sheet": target.sheet_file,
        "schematic": copied_sheet, "output": out_net,
        **info, **gs.diff_against_gnd(clean_net, out_net),
    }
    if erc:
        record["erc_modified"] = gs.run_erc(new_root, os.path.join(out_dir, "erc.json"))
    return record


# --------------------------------------------------------------------------- #
# Runners
# --------------------------------------------------------------------------- #

def run_single(input_path: str, ref: str = "C1", pin: Optional[str] = None,
               output: Optional[str] = None, erc: bool = False) -> int:
    """GND-short one component pin on whichever sheet carries it, in one project."""
    root = gs.resolve_root(input_path)
    proj_dir = os.path.dirname(root)
    before = _hash_tree(proj_dir)

    stem = os.path.splitext(os.path.basename(root))[0]
    out_dir = output or os.path.join("outputs/Infected/GndShortRef", stem, ref)
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        clean_net = os.path.join(tmp, f"{stem}.net")
        gs.export_netlist(root, clean_net)
        rec = build_variant(root, ref, out_dir, clean_net, pin=pin, erc=erc)
        if erc:
            rec["erc_clean"] = gs.run_erc(root, os.path.join(tmp, "erc.json"))

    if _hash_tree(proj_dir) != before:
        raise RuntimeError(f"source project changed under {proj_dir}; aborting")

    moved = rec["moved_nodes"]
    print(f"Shorted {ref} pin {rec['ref_pin']} to GND on {rec['sheet']}")
    print(f"  victim net(s): {', '.join(rec['victim_nets']) or '-'}")
    print(f"  pins now on {rec['merged_net']}: {', '.join(moved) or '-'}")
    if erc:
        print(f"  ERC clean={rec['erc_clean']} modified={rec['erc_modified']}")
    print(f"Wrote {rec['schematic']}\n      {rec['output']}")
    with open(os.path.join(out_dir, "gnd_short_ref.json"), "w") as f:
        json.dump(rec, f, indent=2)
    if not any(n.startswith(f"{ref}.") for n in moved):
        print(f"error: {ref} did not move onto GND; discarding", file=sys.stderr)
        return 1
    return 0


def run_batch(ref: str = "C1", clean_glob: str = CLEAN_GLOB,
              out_root: Optional[str] = None, pin: Optional[str] = None,
              erc: bool = False) -> int:
    """GND-short `ref` on its own (single-instance) sheet in every clean design."""
    out_root = out_root or f"outputs/Infected/GndShortRef/{ref}"
    manifest = []

    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        sch = _schematic_for(path)
        if not sch:
            print(f"{board:24} skipped: no KiCad 6+ schematic resolved", file=sys.stderr)
            continue
        try:
            if locate(sch, ref) is None:
                print(f"{board:24} skipped: {ref} on no sheet of this design")
                continue
        except ValueError as exc:
            print(f"{board:24} skipped: {exc}")
            continue

        proj_dir = os.path.dirname(sch)
        before = _hash_tree(proj_dir)

        clean_dir = os.path.join(out_root, board, "_clean")
        clean_net = os.path.join(clean_dir, os.path.basename(path))
        gs.export_netlist(sch, clean_net)

        out_dir = os.path.join(out_root, board)
        try:
            rec = build_variant(sch, ref, out_dir, clean_net, pin=pin, erc=erc)
        except ValueError as exc:
            print(f"{board:24} skipped: {exc}")
            continue
        if _hash_tree(proj_dir) != before:
            raise RuntimeError(f"source project changed under {proj_dir}; aborting")

        if not any(n.startswith(f"{ref}.") for n in rec["moved_nodes"]):
            shutil.rmtree(out_dir)
            print(f"{board:24} skipped: {ref} did not move onto GND")
            continue
        if erc:
            rec["erc_clean"] = gs.run_erc(sch, os.path.join(clean_dir, "erc.json"))
        rec.update({"board": board, "clean": path, "clean_reexport": clean_net})
        manifest.append(rec)
        print(f"{board:24} {ref} pin {rec['ref_pin']:2} -> {rec['output']} "
              f"({len(rec['moved_nodes'])} pin(s) onto {rec['merged_net']})")

    os.makedirs(out_root, exist_ok=True)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} modified design(s) written. Manifest: {manifest_path}")
    return 0


def _schematic_for(clean_net_path: str) -> Optional[str]:
    """Map a clean .net's (source ...) header onto OSHP_files/Clean/...

    Falls back to a basename search under SCHEMATIC_ROOT when the header's
    directory does not exist (e.g. HadesFCS's header names a moved folder).
    """
    sch = gs._schematic_for(clean_net_path)
    if sch:
        return sch
    m = re.search(r'\(source "[^"]*?OSHP_files/([^"]+)"\)', nt.read(clean_net_path))
    if not m:
        return None
    base = os.path.basename(m.group(1))
    hits = glob.glob(os.path.join(SCHEMATIC_ROOT, "**", base), recursive=True)
    return hits[0] if len(hits) == 1 else None
