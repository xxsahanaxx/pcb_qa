#!/usr/bin/env python3
"""Schematic-level realisation of the XOR-gate-on-spare-GPIO Trojan (RQ2).

:mod:`xor_gpio_trojan` builds this Trojan by splicing the exported ``.net``
directly. This module instead realises *the same* Trojan in the KiCad
*schematic* (``.kicad_sch``) and lets ``kicad-cli`` re-export both the netlist
and the SPICE deck -- so the modification lives in the design source and every
downstream artefact is derived from it, exactly like the RQ1 ``gnd_short``
family.

It consumes the records already produced by :mod:`xor_gpio_trojan` (each
variant's ``xor_gpio_trojan.json``): the gpio pin (input **A**), the tapped net
(input **B**), the route pin (output **Y**), the positive rail and GND are read
back verbatim, so the trojan *definition* is unchanged -- only how it is
realised changes.

How each variant is built (all edits on copies under the output dir; the source
project is SHA-256-checked before and after):

  * The ``74LVC1G86`` single XOR gate is added to ``lib_symbols`` of the root
    sheet and placed in free space to the right of the existing drawing, with
    one ``(instances ...)`` block cloned from a neighbouring symbol (so its
    project name and sheet path are correct for this design).
  * Each of the gate's five pins gets a *global label* on its exact connection
    point: ``Troj_XOR_A`` / ``Troj_XOR_B`` / ``Troj_XOR_Y`` on the three signal
    pins, and the rail / GND net names on the two power pins.
  * A matching global label is dropped on the *target* component pin for each
    signal: the gpio pin (A), one pin of the tapped net (B) and the route pin
    (Y). Because the labels are global they join across sheets. The tapped net
    therefore takes the explicit name ``Troj_XOR_B`` in the export (same
    membership as before, plus the gate's B pin -- only its auto-generated name
    changes).
  * KiCad refuses to connect a pin whose electrical type is ``no_connect`` (a
    "N.C." spare pin), so when a target pin is of that type its definition in
    the copied sheet's ``lib_symbols`` is retyped to ``passive`` and any
    no-connect flag on that point is removed -- the minimal change that lets the
    Trojan reach the spare pin. This is recorded per variant.

Ground truth is measured, never assumed: the modified schematic is re-exported
and :func:`verify` confirms exactly the XOR gate was added, the two spare pins
moved onto the Trojan nets, the tapped net gained the B pin, the rails gained
the power pins, and nothing else changed. A variant that fails verification is
reported and skipped.

Layout (default out-root ``outputs/Infected/Scenarios/RQ2_ComplexMods/XorGpioTrojan``,
overwriting the netlist-level outputs in place)::

    <out-root>/Xor<i>/<board>/_clean/<name>.net   # clean kicad-cli re-export
    <out-root>/Xor<i>/<board>/kicad/...           # modified project copy
    <out-root>/Xor<i>/<board>/<name>.net          # infected netlist (re-exported)
    <out-root>/Xor<i>/<board>/<name>.cir          # infected SPICE deck
    <out-root>/Xor<i>/<board>/xor_gpio_trojan.json
"""

import glob
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

DEFAULT_OUT_ROOT = "outputs/Infected/Scenarios/RQ2_ComplexMods/XorGpioTrojan"
KICAD_SYMBOL_LIB = ("/Applications/KiCad/KiCad.app/Contents/SharedSupport/"
                    "symbols/74xGxx.kicad_sym")

XOR_LIBID = "74xGxx:74LVC1G86"
XOR_VALUE = "74LVC1G86"
XOR_FOOTPRINT = "Package_TO_SOT_SMD:SOT-23-5"
XOR_SYM_NAME = "74LVC1G86"
# gate pin number -> (net role, label text source); power pins carry rail/gnd
PIN_ROLE = {"1": "A", "2": "B", "4": "Y", "5": "VCC", "3": "GND"}

_fmt = gs._fmt


# --------------------------------------------------------------------------- #
# The XOR library symbol
# --------------------------------------------------------------------------- #

def _xor_lib_entry() -> str:
    """The ``74LVC1G86`` definition, re-keyed to its lib_id and indented for a
    schematic's ``lib_symbols`` block (two tabs base, one deeper than the
    standalone .kicad_sym it is lifted from)."""
    sym_lib = os.environ.get("XOR_SYMBOL_LIB", KICAD_SYMBOL_LIB)
    if not os.path.isfile(sym_lib):
        raise FileNotFoundError(
            f"XOR symbol library not found at {sym_lib!r}; set XOR_SYMBOL_LIB")
    text = nt.read(sym_lib)
    m = re.search(r'\t\(symbol "' + re.escape(XOR_SYM_NAME) + '"', text)
    if not m:
        raise ValueError(f"{XOR_SYM_NAME!r} not in {sym_lib}")
    start = m.start() + 1
    block = text[start: nt.find_matching_paren(text, start) + 1]
    block = block.replace(f'(symbol "{XOR_SYM_NAME}"', f'(symbol "{XOR_LIBID}"', 1)
    return "\t\t" + block.replace("\n", "\n\t")


def _local_xor_pins() -> Dict[str, Tuple[float, float]]:
    """{pin number: (x, y)} in the lib symbol's own coordinates."""
    lib = _xor_lib_entry()
    return {n: (px, py) for n, px, py in gsr._lib_pins(lib, 1)}


def _inject_lib_symbol(root_text: str) -> str:
    """Add the XOR lib entry to the root sheet's ``lib_symbols`` (idempotent)."""
    if XOR_LIBID in root_text:
        return root_text
    entry = _xor_lib_entry()
    i = root_text.index("\t(lib_symbols")
    nl = root_text.index("\n", i) + 1
    return root_text[:nl] + entry + "\n" + root_text[nl:]


def _neighbour_instances(root_text: str, root_sch: str) -> str:
    """An ``(instances ...)`` block to clone for the new symbol.

    Prefers an existing placed symbol on the root sheet (its project name and
    sheet path are exactly right); falls back to a minimal block built from the
    root uuid and project stem.
    """
    for k, s, e in gs.top_level_blocks(root_text):
        if k != "symbol":
            continue
        blk = root_text[s:e]
        m = re.search(r"\(instances\b", blk)
        if m and "(lib_id" in blk:
            js = m.start()
            return blk[js: nt.find_matching_paren(blk, js) + 1]
    root_uuid = re.search(r'\(uuid "([^"]*)"', root_text).group(1)
    stem = os.path.splitext(os.path.basename(root_sch))[0]
    return (f'(instances\n\t\t\t(project "{stem}"\n\t\t\t\t(path "/{root_uuid}"\n'
            f'\t\t\t\t\t(reference "U?")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)')


def _xor_symbol_block(sx: float, sy: float, uref: str, inst_block: str) -> str:
    """A placed ``74LVC1G86`` symbol at (sx, sy), reference ``uref``."""
    inst = re.sub(r'\(reference "[^"]*"\)', f'(reference "{uref}")', inst_block)
    inst = re.sub(r"\(unit \d+\)", "(unit 1)", inst)

    def prop(name: str, val: str, dy: float, hide: bool = False) -> str:
        h = "\n\t\t\t\t(hide yes)" if hide else ""
        return (f'\t\t(property "{name}" "{val}"\n\t\t\t(at {_fmt(sx)} {_fmt(sy + dy)} 0)\n'
                f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){h}\n'
                f'\t\t\t)\n\t\t)\n')

    pins = "".join(f'\t\t(pin "{p}"\n\t\t\t(uuid "{uuid.uuid4()}")\n\t\t)\n'
                   for p in PIN_ROLE)
    return (
        f'\t(symbol\n\t\t(lib_id "{XOR_LIBID}")\n\t\t(at {_fmt(sx)} {_fmt(sy)} 0)\n'
        f'\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n'
        f'\t\t(dnp no)\n\t\t(uuid "{uuid.uuid4()}")\n'
        + prop("Reference", uref, 10.16)
        + prop("Value", XOR_VALUE, -10.16)
        + prop("Footprint", XOR_FOOTPRINT, 0, hide=True)
        + prop("Datasheet", "~", 0, hide=True)
        + prop("Description", "Single 2-input XOR gate", 0, hide=True)
        + pins
        + "\t\t" + inst + "\n"
        + "\t)"
    )


# --------------------------------------------------------------------------- #
# Labels and generic sheet edits
# --------------------------------------------------------------------------- #

def _glabel(text: str, x: float, y: float, ang: int = 0) -> str:
    return (f'(global_label "{text}"\n\t\t(shape bidirectional)\n'
            f'\t\t(at {_fmt(x)} {_fmt(y)} {ang})\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify left)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)')


def _append_items(text: str, blocks: List[str]) -> str:
    """Append top-level blocks just before ``sheet_instances`` (or the final
    paren on sub-sheets, which have none)."""
    insertion = "".join(f"\t{b}\n" for b in blocks)
    anchor = text.find("\n\t(sheet_instances")
    if anchor < 0:
        anchor = text.rstrip().rfind(")") - 1
    return text[: anchor + 1] + insertion + text[anchor + 1:]


def _retype_pin(lib_entry: str, pin_number: str, new_type: str) -> str:
    """Set the electrical type of ``pin_number`` in a lib symbol entry."""
    for m in re.finditer(r"\(pin\s+(\w+)\s+(\w+)", lib_entry):
        s = m.start()
        e = nt.find_matching_paren(lib_entry, s)
        num = re.search(r'\(number "([^"]*)"', lib_entry[s:e + 1])
        if num and num.group(1) == pin_number and m.group(1) != new_type:
            return lib_entry[:s] + f"(pin {new_type} {m.group(2)}" + lib_entry[m.end():]
    return lib_entry


def _remove_no_connect_markers(text: str, points: set) -> str:
    """Drop any top-level ``(no_connect (at x y ...))`` sitting on a target pin."""
    out = text
    for k, s, e in reversed(gs.top_level_blocks(text)):
        if k != "no_connect":
            continue
        m = re.search(r"\(at (-?[\d.]+) (-?[\d.]+)", text[s:e])
        if m and (round(float(m.group(1)), 4), round(float(m.group(2)), 4)) in points:
            ls = out.rfind("\n", 0, s) + 1
            le = out.find("\n", e)
            out = out[:ls] + out[le + 1:]
    return out


# --------------------------------------------------------------------------- #
# Locating a target pin on the hierarchy
# --------------------------------------------------------------------------- #

def _pin_etype(lib_entry: str, unit: int, pin_number: str) -> Optional[str]:
    for sub in re.finditer(r'\(symbol "[^"]*_(\d+)_(\d+)"', lib_entry):
        u = int(sub.group(1))
        if u not in (0, unit):
            continue
        s = sub.start()
        body = lib_entry[s: nt.find_matching_paren(lib_entry, s) + 1]
        for m in re.finditer(r"\(pin\s+(\w+)\s+\w+", body):
            ps = m.start()
            pe = nt.find_matching_paren(body, ps)
            num = re.search(r'\(number "([^"]*)"', body[ps:pe + 1])
            if num and num.group(1) == pin_number:
                return m.group(1)
    return None


class PinSite:
    def __init__(self, sheet_file, lib_name, unit, x, y, etype):
        self.sheet_file = sheet_file
        self.lib_name = lib_name
        self.unit = unit
        self.x = x
        self.y = y
        self.etype = etype


def _locate_pin(root_sch: str, ref: str, pin: str) -> Optional[PinSite]:
    """Find ``ref``.``pin`` on a singly-instantiated sheet, with its coordinate
    and electrical type."""
    proj = os.path.dirname(root_sch)
    for sheet in gs.walk_sheets(root_sch):
        text = nt.read(os.path.join(proj, sheet.file))
        for k, s, e in gs.top_level_blocks(text):
            if k != "symbol":
                continue
            blk = text[s:e]
            if gsr._ref_of(blk) != ref and ref not in gsr._instance_refs(blk):
                continue
            if [r for r in gsr._instance_refs(blk) if r != ref]:
                continue  # reused sheet: editing it would hit every instance
            try:
                x, y = gsr.pin_xy(text, blk, pin)
            except ValueError:
                continue
            lib_name = gsr._lib_name(blk)
            etype = _pin_etype(gsr._lib_entry(text, lib_name), gsr._unit(blk), pin)
            return PinSite(sheet.file, lib_name, gsr._unit(blk), x, y, etype)
    return None


# --------------------------------------------------------------------------- #
# Verify (node membership; the tapped net is renamed to Troj_XOR_B)
# --------------------------------------------------------------------------- #

def verify(clean_net: str, infected_net: str, rec: Dict, tap_key: Tuple[str, str]) -> bool:
    """Ground truth by node membership, independent of the names kicad-cli
    assigns: a *named* tap net (e.g. ``I2C_SCL``) keeps its name, while an
    auto-named tap becomes ``Troj_XOR_B`` -- either way the B pin must join
    exactly that net."""
    clean_nets = nt.parse_nets(nt.read(clean_net))
    inf_nets = nt.parse_nets(nt.read(infected_net))
    clean = {n.name: n.node_set() for n in clean_nets}
    cnodes = {k: n.name for n in clean_nets for k in n.node_set()}
    inf = {n.name: n.node_set() for n in inf_nets}

    uref = rec["trojan_ref"]
    gpio = (rec["gpio_ref"], rec["gpio_pin"])
    route = (rec["route_ref"], rec["route_pin"])
    rail, gnd = rec["rail"], rec["gnd"]
    tap_name = cnodes.get(tap_key)
    if tap_name is None:
        return False

    def net_of(pin_key):
        hits = [n.node_set() for n in inf_nets if pin_key in n.node_set()]
        return hits[0] if len(hits) == 1 else None

    if net_of((uref, "1")) != {gpio, (uref, "1")}:
        return False
    if net_of((uref, "4")) != {route, (uref, "4")}:
        return False
    if net_of((uref, "2")) != clean[tap_name] | {(uref, "2")}:
        return False
    if inf.get(rail) != clean[rail] | {(uref, "5")}:
        return False
    if inf.get(gnd) != clean[gnd] | {(uref, "3")}:
        return False
    gate = {(uref, p) for p in PIN_ROLE}
    if {k for s in inf.values() for k in s if k[0] == uref} != gate:
        return False

    # only the five touched nets (plus the two freed spare nets, and any rename
    # of the tap net to Troj_XOR_B) may differ
    changed = {k for k in set(clean) | set(inf)
               if clean.get(k, set()) != inf.get(k, set())}
    allowed = {"Troj_XOR_A", "Troj_XOR_B", "Troj_XOR_Y", rail, gnd, tap_name,
               cnodes.get(gpio, ""), cnodes.get(route, "")}
    return changed <= allowed


# --------------------------------------------------------------------------- #
# Build one variant
# --------------------------------------------------------------------------- #

def _choose_tap_pin(root_sch: str, rec: Dict) -> Optional[Tuple[Tuple[str, str], PinSite]]:
    """First node of the tapped net that can be located and labelled."""
    for node in rec["tap_net_nodes"]:
        ref, pin = node.rsplit(".", 1)
        site = _locate_pin(root_sch, ref, pin)
        if site is not None:
            return (ref, pin), site
    return None


def build_variant(rec: Dict, dest: str) -> Dict:
    """Realise ``rec`` in the schematic under ``dest`` and re-export; returns the
    updated record (``verified`` tells whether ground truth matched)."""
    root_sch = gsr._schematic_for(rec["clean"])
    if not root_sch:
        raise ValueError(f"no schematic resolved for {rec['clean']}")
    sheets = gs.walk_sheets(root_sch)
    proj_dir = os.path.dirname(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]
    root_file = os.path.basename(root_sch)
    uref = rec["trojan_ref"]
    before = gsr._hash_tree(proj_dir)

    # locate the three signal targets
    gpio_site = _locate_pin(root_sch, rec["gpio_ref"], rec["gpio_pin"])
    route_site = _locate_pin(root_sch, rec["route_ref"], rec["route_pin"])
    tap = _choose_tap_pin(root_sch, rec)
    if not (gpio_site and route_site and tap):
        raise ValueError(f"{rec['board']} {rec['variant']}: a target pin could not "
                         f"be located on a singly-instantiated sheet")
    tap_key, tap_site = tap
    targets = [("Troj_XOR_A", gpio_site), ("Troj_XOR_B", tap_site),
               ("Troj_XOR_Y", route_site)]

    # fresh project copy
    kicad_dir = os.path.join(dest, "kicad")
    if os.path.isdir(kicad_dir):
        shutil.rmtree(kicad_dir)
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)

    # accumulate per-sheet edits: labels, lib retypes, no-connect removals
    labels = defaultdict(list)          # sheet_file -> [label block]
    retypes = defaultdict(list)         # sheet_file -> [(lib_name, pin)]
    nc_points = defaultdict(set)        # sheet_file -> {(x, y)}
    retyped_record = []
    for netname, site in targets:
        labels[site.sheet_file].append(_glabel(netname, site.x, site.y))
        nc_points[site.sheet_file].add((round(site.x, 4), round(site.y, 4)))
        if site.etype == "no_connect":
            retypes[site.sheet_file].append((site.lib_name, _target_pin(netname, rec)))
            retyped_record.append(f"{_target_ref(netname, rec)}.{_target_pin(netname, rec)}")

    # the XOR gate + its five pin labels live on the root sheet
    root_text = nt.read(new_root)
    root_text = _inject_lib_symbol(root_text)
    _, min_y, max_x, _ = gs.drawing_bbox(root_text)
    sx, sy = gs._snap(max_x + gs.MARGIN), gs._snap(min_y + gs.MARGIN)
    local = _local_xor_pins()
    inst = _neighbour_instances(root_text, root_sch)
    root_blocks = [_xor_symbol_block(sx, sy, uref, inst)]
    pin_label = {"1": "Troj_XOR_A", "2": "Troj_XOR_B", "4": "Troj_XOR_Y",
                 "5": rec["rail"], "3": rec["gnd"]}
    for pn, lab in pin_label.items():
        px, py = gsr._transform(sx, sy, 0, None, *local[pn])
        root_blocks.append(_glabel(lab, px, py))

    # apply edits to every touched sheet (root gets the gate too)
    touched = set(labels) | {root_file}
    for sf in touched:
        path = os.path.join(kicad_dir, sf)
        text = root_text if sf == root_file else nt.read(path)
        for lib_name, pin in retypes.get(sf, []):
            entry = gsr._lib_entry(text, lib_name)
            text = text.replace(entry, _retype_pin(entry, pin, "passive"), 1)
        if nc_points.get(sf):
            text = _remove_no_connect_markers(text, nc_points[sf])
        blocks = list(labels.get(sf, []))
        if sf == root_file:
            blocks = root_blocks + blocks
        text = _append_items(text, blocks)
        nt.write(path, text)

    # re-export clean + infected, and the SPICE deck
    clean_net = os.path.join(dest, "_clean", f"{stem}.net")
    gs.export_netlist(root_sch, clean_net)
    out_net = os.path.join(dest, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    cir_status = "ok"
    try:
        gsx.export_spice(new_root, os.path.join(dest, f"{stem}.cir"))
    except Exception as exc:  # SPICE export is best-effort (no model for the gate)
        cir_status = f"error: {exc}"

    verified = verify(clean_net, out_net, rec, tap_key)
    if gsr._hash_tree(proj_dir) != before:
        raise RuntimeError(f"source project changed under {proj_dir}; aborting")

    merged_tap = next((n.name for n in nt.parse_nets(nt.read(out_net))
                       if (uref, "2") in n.node_set()), None)

    out = dict(rec)
    out.update({
        "realisation": "schematic",
        "schematic_root": root_sch,
        "schematic": new_root,
        "output": out_net,
        "clean_reexport": clean_net,
        "cir": os.path.join(dest, f"{stem}.cir"),
        "cir_status": cir_status,
        "xor_at": [sx, sy],
        "tap_pin": f"{tap_key[0]}.{tap_key[1]}",
        "merged_tap_net": merged_tap,
        "retyped_no_connect_pins": retyped_record,
        "sheets_edited": sorted(touched),
        "verified": verified,
    })
    out.pop("_infected_text", None)
    return out


def _target_ref(netname: str, rec: Dict) -> str:
    return {"Troj_XOR_A": rec["gpio_ref"], "Troj_XOR_Y": rec["route_ref"]}.get(netname, "")


def _target_pin(netname: str, rec: Dict) -> str:
    return {"Troj_XOR_A": rec["gpio_pin"], "Troj_XOR_Y": rec["route_pin"]}.get(netname, "")


# --------------------------------------------------------------------------- #
# Batch runner over existing records
# --------------------------------------------------------------------------- #

def run_from_records(out_root: str = DEFAULT_OUT_ROOT) -> int:
    """Rebuild every variant under ``out_root`` from its ``xor_gpio_trojan.json``
    record, now realised in the schematic. Overwrites each variant in place."""
    records = sorted(glob.glob(os.path.join(out_root, "Xor*", "*", "xor_gpio_trojan.json")))
    if not records:
        raise FileNotFoundError(f"no xor_gpio_trojan.json records under {out_root}")

    manifest: List[Dict] = []
    per_var: Dict[str, List[Dict]] = defaultdict(list)
    built = skipped = unverified = 0
    for rec_path in records:
        rec = json.load(open(rec_path))
        dest = os.path.dirname(rec_path)
        variant, board = rec["variant"], rec["board"]
        try:
            out = build_variant(rec, dest)
        except Exception as exc:
            # cannot be realised in-schematic (typically a target pin on a
            # hierarchical sheet instantiated more than once). Leave the
            # netlist-level output in place and record why.
            out = dict(rec)
            out.update({"realisation": "netlist",
                        "schematic_realisable": False,
                        "schematic_skip_reason": str(exc)})
            out.pop("_infected_text", None)
            with open(rec_path, "w") as f:
                json.dump(out, f, indent=2)
            manifest.append(out)
            per_var[variant].append(out)
            skipped += 1
            print(f"SKIP {board:22} {variant}: {str(exc).split(': ', 2)[-1]}")
            continue
        out["schematic_realisable"] = True
        with open(rec_path, "w") as f:
            json.dump(out, f, indent=2)
        manifest.append(out)
        per_var[variant].append(out)
        built += 1
        flag = "" if out["verified"] else "  !! UNVERIFIED"
        if not out["verified"]:
            unverified += 1
        nc = f"  retyped={out['retyped_no_connect_pins']}" if out["retyped_no_connect_pins"] else ""
        print(f"{'OK ' if out['verified'] else 'BAD'} {board:22} {variant}: "
              f"{out['trojan_ref']} XOR  A={out['gpio_ref']}.{out['gpio_pin']}  "
              f"B=tap[{out['tap_net']}->{out['merged_tap_net']}]  "
              f"Y={out['route_ref']}.{out['route_pin']}  cir={out['cir_status']}{nc}{flag}")

    for variant, recs in per_var.items():
        with open(os.path.join(out_root, variant, "manifest.json"), "w") as f:
            json.dump(recs, f, indent=2)
    with open(os.path.join(out_root, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{built} realised in schematic ({unverified} unverified), "
          f"{skipped} left at netlist level (reused sheet). "
          f"Manifest: {os.path.join(out_root, 'manifest.json')}")
    return 1 if unverified else 0
