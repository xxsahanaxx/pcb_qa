#!/usr/bin/env python3
"""Polarity flip on randomly chosen polarised parts: one per variant.

For each clean design this picks ``count`` distinct polarised two-pin parts at
random (seeded, so a run is reproducible): diodes and LEDs (``D<n>``,
``LED<n>``, including Zener, Schottky and unidirectional TVS) and polarised
capacitors (``C<n>`` whose symbol is electrolytic / tantalum / polarised). Each
variant reverses one of them, as if it had been fitted backwards: the symbol is
rotated 180 degrees about its pins' midpoint, so pin 1 lands exactly where pin
2 was and vice versa. Anode and cathode (or + and -) swap nets; nothing else
moves, so the ``.kicad_sch`` diff is that symbol's ``(at ...)``.

Not eligible, since a flip would change nothing: bidirectional TVS diodes
(``D_TVS`` symbols, ``...CA`` part numbers) and parts with both pins on the same
net. Parts on reused sheets are refused, as for the other generators.

Ground truth is measured, not assumed: a variant is kept only if, in the
kicad-cli re-export, the part's two pins have swapped nets and every other net
and component is unchanged.

Layout (default ``--out-root outputs/Infected/Scenarios/PolarityFlipRandom``)::

    <out-root>/Flip<i>/<board>/_clean/<name>.net   # clean kicad-cli re-export
    <out-root>/Flip<i>/<board>/kicad/...           # modified project copy
    <out-root>/Flip<i>/<board>/<name>.net          # modified netlist
    <out-root>/Flip<i>/<board>/<name>.cir          # raw kicad-cli SPICE export
    <out-root>/Flip<i>/<board>/polarity_flip_random.json
    <out-root>/Flip<i>/manifest.json
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
from collections import Counter
from typing import Dict, List

from . import core as nt
from . import gnd_short as gs
from . import gnd_short_ref as gsr
from . import gnd_short_random as gsx
from . import passive_swap_random as psr

CLEAN_GLOB = gs.CLEAN_GLOB
DEFAULT_OUT_ROOT = "outputs/Infected/Scenarios/PolarityFlipRandom"
DEFAULT_COUNT = gsx.DEFAULT_COUNT
DEFAULT_SEED = gsx.DEFAULT_SEED

_POLARISED_CAP_RE = re.compile(r"polar|^Device:CP|ALUM|ELEC|TANT", re.I)
_BIDIRECTIONAL_RE = re.compile(r"D_TVS(?!_?Uni)|bidirectional|\bSMCJ\d+CA\b|\bSMBJ\d+CA\b|\bP6KE\d+CA\b", re.I)


# --------------------------------------------------------------------------- #
# Discovery: polarised two-pin parts
# --------------------------------------------------------------------------- #

def _kind(part: psr.Part) -> str:
    lib = gsr._lib_name(part.sym_block)
    if part.ref.startswith("C"):
        return "polarised_capacitor"
    return "led" if re.search(r"LED", lib, re.I) or part.ref.startswith("LED") else "diode"


def polarised_parts(root_sch: str) -> List[psr.Part]:
    """Diodes/LEDs (minus bidirectional TVS) and polarised capacitors."""
    out = []
    for prefix in ("D", "LED", "C"):
        for part in psr._two_pin_parts(root_sch, prefix):
            lib = gsr._lib_name(part.sym_block)
            desc = " ".join(t for _, (_, _, t) in psr._props(part.sym_block).items())
            if prefix == "C" and not _POLARISED_CAP_RE.search(lib):
                continue
            if _BIDIRECTIONAL_RE.search(lib) or _BIDIRECTIONAL_RE.search(desc):
                continue
            out.append(part)
    return out


# --------------------------------------------------------------------------- #
# Edit: rotate the symbol 180 degrees about its pins' midpoint
# --------------------------------------------------------------------------- #

def flip_block(text: str, part: psr.Part):
    """(new symbol block, info) with `part` reversed: pin 1 on old pin 2's spot."""
    p1 = gsr.pin_xy(text, part.sym_block, "1")
    p2 = gsr.pin_xy(text, part.sym_block, "2")
    x, y, ang, mirror = gsr._placement(part.sym_block)
    new_ang = (ang + 180) % 360
    l1 = gsr._transform(0, 0, new_ang, mirror, *part.pins["1"])
    nx, ny = round(p2[0] - l1[0], 4), round(p2[1] - l1[1], 4)
    l2 = gsr._transform(nx, ny, new_ang, mirror, *part.pins["2"])
    if abs(l2[0] - p1[0]) > 1e-3 or abs(l2[1] - p1[1]) > 1e-3:
        raise ValueError(f"{part.ref}: 180-degree flip does not land pin 2 on old pin 1")
    block = re.sub(r"\(at -?[\d.]+ -?[\d.]+ \d+\)",
                   f"(at {gs._fmt(nx)} {gs._fmt(ny)} {new_ang})", part.sym_block, count=1)
    return block, {"old_at": [x, y, ang], "new_at": [nx, ny, new_ang],
                   "pin1_xy": list(p1), "pin2_xy": list(p2)}


# --------------------------------------------------------------------------- #
# Ground truth
# --------------------------------------------------------------------------- #

def _pin_info(net_text: str, ref: str) -> Dict[str, Dict]:
    return {p: {"net": n.name, "pinfunction": nd.pinfunction}
            for n in nt.parse_nets(net_text) for nd in n.nodes for r, p in [nd.key()] if r == ref}


def diff_flip(clean_net: str, modified_net: str, ref: str) -> Dict:
    clean_text, mod_text = nt.read(clean_net), nt.read(modified_net)
    swap = {"1": "2", "2": "1"}
    flip = lambda r, p: (r, swap[p]) if r == ref and p in swap else (r, p)
    expected = Counter(frozenset(flip(r, p) for r, p in n.node_set()) for n in nt.parse_nets(clean_text))
    got = Counter(frozenset(n.node_set()) for n in nt.parse_nets(mod_text))
    before, after = _pin_info(clean_text, ref), _pin_info(mod_text, ref)
    return {
        "pin_nets": {p: i["net"] for p, i in before.items()},
        "pin_functions": {p: i["pinfunction"] for p, i in before.items()},
        "flipped_pin_nets": {p: i["net"] for p, i in after.items()},
        "exact": (expected == got and psr._comps(clean_text) == psr._comps(mod_text)),
    }


# --------------------------------------------------------------------------- #
# Build + verify one variant
# --------------------------------------------------------------------------- #

def build_variant(root_sch: str, part: psr.Part, out_dir: str, clean_net: str) -> Dict:
    sheets = gs.walk_sheets(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]
    kicad_dir = os.path.join(out_dir, "kicad")
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)
    copied_sheet = os.path.join(kicad_dir, part.sheet_file)
    text = nt.read(copied_sheet)
    start = text.find(part.sym_block)
    if start < 0:
        raise ValueError(f"{part.ref}'s symbol block not found on {part.sheet_file}")
    new_block, info = flip_block(text, part)
    nt.write(copied_sheet, text[:start] + new_block + text[start + len(part.sym_block):])

    out_net = os.path.join(out_dir, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    comp = psr._comps(nt.read(clean_net)).get(part.ref, {})
    return {
        "ref": part.ref, "kind": _kind(part), "value": comp.get("value"),
        "footprint": comp.get("footprint"), "part": f"{comp.get('lib')}:{comp.get('part')}",
        "sheet": part.sheet_file, "schematic": copied_sheet, "output": out_net,
        **info, **diff_flip(clean_net, out_net, part.ref),
    }


def variants_for_board(sch: str, board: str, clean_net: str, count: int,
                       seed: int, tmp_root: str) -> List[Dict]:
    rng = random.Random(f"{seed}:polarity_flip:{board}")
    parts = polarised_parts(sch)
    rng.shuffle(parts)
    pin_nets = {}
    for n in nt.parse_nets(nt.read(clean_net)):
        for r, p in n.node_set():
            pin_nets[(r, p)] = n.name

    found: List[Dict] = []
    for part in parts:
        if len(found) == count:
            break
        if pin_nets.get((part.ref, "1")) == pin_nets.get((part.ref, "2")):
            continue  # both pins on one net: a flip changes nothing
        out_dir = os.path.join(tmp_root, f"{len(found)}_{part.ref}")
        try:
            rec = build_variant(sch, part, out_dir, clean_net)
        except (ValueError, KeyError, subprocess.CalledProcessError) as exc:
            print(f"{board:24} {part.ref}: error ({exc!r}); retrying")
            shutil.rmtree(out_dir, ignore_errors=True)
            continue
        if not rec["exact"]:
            print(f"{board:24} {part.ref}: re-export changed more than the flip; retrying")
            shutil.rmtree(out_dir)
            continue
        rec["_tmp_dir"] = out_dir
        found.append(rec)
    return found


def run_batch(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED,
              clean_glob: str = CLEAN_GLOB, out_root: str = DEFAULT_OUT_ROOT) -> int:
    """`count` single-part polarity flips per resolvable clean design."""
    manifest: List[Dict] = []
    per_var: Dict[int, List[Dict]] = {i: [] for i in range(1, count + 1)}

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
            recs = variants_for_board(sch, board, clean_net, count, seed, tmp)

            for i, rec in enumerate(recs, start=1):
                dest = os.path.join(out_root, f"Flip{i}", board)
                if os.path.exists(dest):
                    raise FileExistsError(f"{dest} already exists; refusing to overwrite")
                src = rec.pop("_tmp_dir")
                shutil.copytree(src, dest)
                shutil.copytree(os.path.dirname(clean_net), os.path.join(dest, "_clean"))
                gsx._retarget(rec, src, dest)
                gsx.export_spice(os.path.join(dest, "kicad", os.path.basename(sch)),
                                 os.path.join(dest, f"{stem}.cir"))
                rec.update({"variant": f"Flip{i}", "board": board, "mode": "polarity_flip",
                            "seed": seed, "clean": path,
                            "clean_reexport": os.path.join(dest, "_clean", f"{stem}.net")})
                with open(os.path.join(dest, "polarity_flip_random.json"), "w") as f:
                    json.dump(rec, f, indent=2)
                manifest.append(rec)
                per_var[i].append(rec)
                print(f"{board:24} Flip{i}: {rec['ref']} ({rec['kind']}, {rec['value']}) "
                      f"{rec['pin_nets']} -> {rec['flipped_pin_nets']}")

        if gsr._hash_tree(proj_dir) != before:
            raise RuntimeError(f"source project changed under {proj_dir}; aborting")
        if len(recs) < count:
            print(f"{board:24} WARNING: only {len(recs)}/{count} variants could be built",
                  file=sys.stderr)

    os.makedirs(out_root, exist_ok=True)
    for i, recs in per_var.items():
        if recs:
            with open(os.path.join(out_root, f"Flip{i}", "manifest.json"), "w") as f:
                json.dump(recs, f, indent=2)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} modified design(s) written. Manifest: {manifest_path}")
    return 0
