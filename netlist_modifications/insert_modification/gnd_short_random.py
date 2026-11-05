#!/usr/bin/env python3
"""GND / VCC short on randomly chosen nets: one shorted wire per variant.

For each clean design this picks ``count`` distinct nets at random (seeded, so
a run is reproducible) and builds one variant per net. Each variant ties a
single randomly chosen component pin on that net to GND, the same way
:mod:`gnd_short_ref` does: a clone of the sheet's own GND power symbol is placed
so its pin lands exactly on the target pin. The clean-vs-modified
``.kicad_sch`` diff of every variant is therefore one added symbol, and every
variant carries exactly one modification.

The ``vcc`` mode is the same with a positive supply in place of GND: the clone
is one of the sheet's positive-rail power symbols (``VCC``, ``+3V3``, ``+5V``,
``VBUS``, ...). Where a sheet carries several, ``VCC`` is preferred, else the
rail with the most pins in the clean design; the rail used is recorded.

Eligible nets: every net in the clean kicad-cli export except GND-like nets
(any name containing ``GND``), KiCad's ``unconnected-...`` single-pin nets and,
in ``vcc`` mode, positive rails. Eligible pins: visible pins of symbols on a sheet that
is instantiated once and carries a target power symbol to clone (see
:func:`gnd_short_ref.locate` for why reused sheets are refused).

Ground truth is measured, not assumed: a variant is kept only if the pins that
moved onto the rail's net are *exactly* the chosen net's pins. Anything else (a
geometry miss, or a placement that also touches a neighbouring net) is
discarded and the next random pick is tried.

Layout (default ``--out-root outputs/Infected/GndShortRandom``, or
``VccShortRandom`` for the ``vcc`` mode)::

    <out-root>/Wire<i>/<board>/_clean/<name>.net   # clean kicad-cli re-export
    <out-root>/Wire<i>/<board>/kicad/...           # modified project copy
    <out-root>/Wire<i>/<board>/<name>.net          # modified netlist
    <out-root>/Wire<i>/<board>/<name>.cir          # raw kicad-cli SPICE export
    <out-root>/Wire<i>/<board>/<mode>_short_random.json
    <out-root>/Wire<i>/manifest.json
    <out-root>/manifest.json                       # every variant, all boards

The source project is never modified (SHA-256-checked before and after).
"""

import glob
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import core as nt
from . import gnd_short as gs
from . import gnd_short_ref as gsr

CLEAN_GLOB = gs.CLEAN_GLOB
DEFAULT_OUT_ROOTS = {"gnd": "outputs/Infected/GndShortRandom",
                     "vcc": "outputs/Infected/VccShortRandom"}
DEFAULT_COUNT = 3
DEFAULT_SEED = 0

_POSITIVE_RAIL_RE = re.compile(r"^(\+\d|VCC|VDD|VBUS|VBAT|VIN)", re.I)


# --------------------------------------------------------------------------- #
# Discovery: every pin a power symbol can be dropped onto
# --------------------------------------------------------------------------- #

@dataclass
class PinSite:
    sheet_file: str
    sym_block: str
    rails: Dict[str, str]  # rail name -> a power symbol for it on the same sheet


def _power_rails(blocks: List[str], mode: str) -> Dict[str, str]:
    """{rail: first power symbol block} for the `mode`'s target rails on a sheet."""
    rails: Dict[str, str] = {}
    for b in blocks:
        if mode == "gnd":
            if gs._is_gnd(b):
                rails.setdefault("GND", b)
            continue
        ref, val = gs._prop(b, "Reference") or "", gs._prop(b, "Value") or ""
        if ref.startswith("#PWR") and _POSITIVE_RAIL_RE.match(val):
            rails.setdefault(val, b)
    return rails


def _visible_pins(lib_entry: str, unit: int) -> List[str]:
    """Pin numbers of `unit` (and common unit 0) that are not hidden.

    Hidden pins (typically an IC's power pins) join their net implicitly, by
    name; a GND symbol placed on one's coordinates would connect to nothing.
    """
    out: List[str] = []
    for sub in re.finditer(r'\(symbol "[^"]*_(\d+)_(\d+)"', lib_entry):
        if int(sub.group(1)) not in (0, unit):
            continue
        s = sub.start()
        body = lib_entry[s: nt.find_matching_paren(lib_entry, s) + 1]
        for pin in re.finditer(r"\(pin\s+\w+\s+\w+", body):
            e = nt.find_matching_paren(body, pin.start())
            block = body[pin.start(): e + 1]
            head = block.split("(name", 1)[0]
            if re.search(r"\(hide yes\)|\bhide\b(?! no)", head):
                continue
            num = re.search(r'\(number "([^"]*)"', block)
            if num:
                out.append(num.group(1))
    return out


def pin_sites(root_sch: str, mode: str = "gnd") -> Dict[Tuple[str, str], PinSite]:
    """{(ref, pin): site} for every pin a target power clone can be placed on
    (``mode="bridge"``: every eligible pin, power symbol or not)."""
    proj_dir = os.path.dirname(root_sch)
    sites: Dict[Tuple[str, str], PinSite] = {}
    for sheet in gs.walk_sheets(root_sch):
        text = nt.read(os.path.join(proj_dir, sheet.file))
        blocks = [text[s:e] for k, s, e in gs.top_level_blocks(text) if k == "symbol"]
        rails = {} if mode == "bridge" else _power_rails(blocks, mode)
        if not rails and mode != "bridge":
            continue
        for block in blocks:
            ref = gsr._ref_of(block)
            if not ref or ref.startswith("#"):
                continue
            inst = gsr._instance_refs(block)
            if len(inst) > 1:
                continue  # reused sheet: one edit would short every instance
            if inst:
                ref = inst[0]
            try:
                lib = gsr._lib_entry(text, gsr._lib_name(block))
            except ValueError:
                continue
            for pin in _visible_pins(lib, gsr._unit(block)):
                sites.setdefault((ref, pin), PinSite(sheet.file, block, rails))
    return sites


def eligible_nets(nets: List[nt.Net], mode: str = "gnd") -> List[nt.Net]:
    """Nets that may be shorted. In vcc mode positive rails are excluded too:
    tying one rail to another (e.g. ``+3.3V`` to ``+3V3``) is often a no-op."""
    return [n for n in nets
            if "GND" not in n.name.upper() and not n.name.startswith("unconnected-")
            and not (mode == "vcc" and _POSITIVE_RAIL_RE.match(n.name))]


def choose_rail(site: PinSite, net: nt.Net, sizes: Dict[str, int]) -> Optional[str]:
    """Rail to tie `net` to at `site`: VCC first, else the most-connected rail.

    Only rails that exist as a net in the clean design (so the result can be
    verified) and are not `net` itself qualify.
    """
    usable = [r for r in site.rails if r in sizes and r != net.name]
    if not usable:
        return None
    if "VCC" in usable:
        return "VCC"
    return max(usable, key=lambda r: (sizes[r], r))


def diff_against_rail(clean_net: str, modified_net: str, rail: str) -> Dict:
    """Which pins moved onto `rail`'s net (generalises gnd_short.diff_against_gnd)."""
    clean = nt.parse_nets(nt.read(clean_net))
    modified = nt.parse_nets(nt.read(modified_net))
    base = next(n for n in clean if n.name == rail)
    merged = max((n for n in modified if base.node_set() <= n.node_set()),
                 key=lambda n: len(n.nodes))
    moved = merged.node_set() - base.node_set()
    victims = [n for n in clean if n.node_set() and n.node_set() <= moved]
    return {
        "merged_net": merged.name,
        "victim_nets": [n.name for n in victims],
        "moved_nodes": sorted(f"{r}.{p}" for r, p in moved),
    }


# --------------------------------------------------------------------------- #
# Build + verify one variant
# --------------------------------------------------------------------------- #

def export_spice(sch_path: str, out_path: str) -> None:
    subprocess.run([gs.kicad_cli(), "sch", "export", "netlist", "--format", "spice",
                    sch_path, "--output", out_path],
                   check=True, capture_output=True, text=True)


def build_variant(root_sch: str, net: nt.Net, ref: str, pin: str, site: PinSite,
                  rail: str, out_dir: str, clean_net: str) -> Dict:
    """Write one modified project copy + its exported netlist into `out_dir`."""
    sheets = gs.walk_sheets(root_sch)
    proj_dir = os.path.dirname(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]

    kicad_dir = os.path.join(out_dir, "kicad")
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)
    copied_sheet = os.path.join(kicad_dir, site.sheet_file)
    # insert_gnd_on_pin clones whatever single-pin power symbol it is given
    target = gsr.Target(site.sheet_file, site.sym_block, site.rails[rail])
    modified, info = gsr.insert_gnd_on_pin(nt.read(copied_sheet), target, pin,
                                           gs._used_pwr_refs(proj_dir, sheets))
    nt.write(copied_sheet, modified)

    out_net = os.path.join(out_dir, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    node = next(n for n in net.nodes if n.key() == (ref, pin))
    return {
        "net": net.name, "net_code": net.code,
        "net_nodes": sorted(f"{r}.{p}" for r, p in net.node_set()),
        "rail": rail, "ref": ref, "pinfunction": node.pinfunction, "pintype": node.pintype,
        "sheet": site.sheet_file, "schematic": copied_sheet, "output": out_net,
        **info, **diff_against_rail(clean_net, out_net, rail),
    }


def _is_single_short(rec: Dict) -> bool:
    """True if exactly the chosen net's pins, and nothing else, moved onto the rail."""
    return sorted(rec["moved_nodes"]) == rec["net_nodes"]


def variants_for_board(sch: str, board: str, clean_net: str, count: int,
                       seed: int, tmp_root: str, mode: str = "gnd") -> List[Dict]:
    """Up to `count` verified single-wire variants, built under `tmp_root`."""
    rng = random.Random(f"{seed}:{board}")
    all_nets = nt.parse_nets(nt.read(clean_net))
    sizes = {n.name: len(n.nodes) for n in all_nets}
    nets = eligible_nets(all_nets, mode)
    rng.shuffle(nets)
    sites = pin_sites(sch, mode)

    found: List[Dict] = []
    for net in nets:
        if len(found) == count:
            break
        nodes = [n.key() for n in net.nodes
                 if n.key() in sites and choose_rail(sites[n.key()], net, sizes)]
        rng.shuffle(nodes)
        for ref, pin in nodes:
            out_dir = os.path.join(tmp_root, f"{len(found)}_{ref}_{pin}")
            site = sites[(ref, pin)]
            try:
                rec = build_variant(sch, net, ref, pin, site,
                                    choose_rail(site, net, sizes), out_dir, clean_net)
            except (ValueError, subprocess.CalledProcessError) as exc:
                print(f"{board:24} {net.name:28} {ref}.{pin}: error ({exc}); retrying")
                shutil.rmtree(out_dir, ignore_errors=True)
                continue
            if not _is_single_short(rec):
                print(f"{board:24} {net.name:28} {ref}.{pin}: moved "
                      f"{len(rec['moved_nodes'])} pin(s), expected "
                      f"{len(rec['net_nodes'])}; retrying")
                shutil.rmtree(out_dir)
                continue
            rec["_tmp_dir"] = out_dir
            found.append(rec)
            break
    return found


# --------------------------------------------------------------------------- #
# Batch runner
# --------------------------------------------------------------------------- #

def _retarget(rec: Dict, old: str, new: str) -> None:
    for key in ("schematic", "output"):
        rec[key] = rec[key].replace(old, new, 1)


def run_batch(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED,
              clean_glob: str = CLEAN_GLOB, out_root: Optional[str] = None,
              mode: str = "gnd") -> int:
    """`count` single-wire GND- (or VCC-) short variants per resolvable clean design."""
    if mode not in DEFAULT_OUT_ROOTS:
        raise ValueError(f"mode must be one of {sorted(DEFAULT_OUT_ROOTS)}, got {mode!r}")
    out_root = out_root or DEFAULT_OUT_ROOTS[mode]
    manifest: List[Dict] = []
    per_wire: Dict[int, List[Dict]] = {i: [] for i in range(1, count + 1)}

    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        sch = gsr._schematic_for(path)
        if not sch:
            print(f"{board:24} skipped: no KiCad 6+ schematic resolved", file=sys.stderr)
            continue
        proj_dir = os.path.dirname(sch)
        before = gsr._hash_tree(proj_dir)
        stem = os.path.splitext(os.path.basename(sch))[0]

        with tempfile.TemporaryDirectory() as tmp:
            clean_net = os.path.join(tmp, "_clean", f"{stem}.net")
            gs.export_netlist(sch, clean_net)
            recs = variants_for_board(sch, board, clean_net, count, seed, tmp, mode)

            for i, rec in enumerate(recs, start=1):
                dest = os.path.join(out_root, f"Wire{i}", board)
                if os.path.exists(dest):
                    raise FileExistsError(f"{dest} already exists; refusing to overwrite")
                src = rec.pop("_tmp_dir")
                shutil.copytree(src, dest)
                shutil.copytree(os.path.dirname(clean_net), os.path.join(dest, "_clean"))
                _retarget(rec, src, dest)
                export_spice(os.path.join(dest, "kicad", os.path.basename(sch)),
                             os.path.join(dest, f"{stem}.cir"))
                rec.update({"variant": f"Wire{i}", "board": board, "mode": mode,
                            "seed": seed,
                            "clean": path,
                            "clean_reexport": os.path.join(dest, "_clean", f"{stem}.net")})
                with open(os.path.join(dest, f"{mode}_short_random.json"), "w") as f:
                    json.dump(rec, f, indent=2)
                manifest.append(rec)
                per_wire[i].append(rec)
                print(f"{board:24} Wire{i}: {rec['net']} -> {rec['rail']} via "
                      f"{rec['ref']}.{rec['ref_pin']} "
                      f"({len(rec['moved_nodes'])} pin(s) onto {rec['merged_net']}) -> {dest}")

        if _hash_tree_changed(proj_dir, before):
            raise RuntimeError(f"source project changed under {proj_dir}; aborting")
        if len(recs) < count:
            print(f"{board:24} WARNING: only {len(recs)}/{count} variants could be built",
                  file=sys.stderr)

    os.makedirs(out_root, exist_ok=True)
    for i, recs in per_wire.items():
        if recs:
            with open(os.path.join(out_root, f"Wire{i}", "manifest.json"), "w") as f:
                json.dump(recs, f, indent=2)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} modified design(s) written. Manifest: {manifest_path}")
    return 0


def _hash_tree_changed(proj_dir: str, before: Dict[str, str]) -> bool:
    return gsr._hash_tree(proj_dir) != before
