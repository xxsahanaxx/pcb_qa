#!/usr/bin/env python3
"""Random bridge wire between two components: one added wire per variant.

For each clean design this builds ``count`` variants. Each one draws a single
wire, on one sheet, from a visible pin of one component to a visible pin of a
*different* component on a different net, so the two nets merge. The wire's
endpoints sit exactly on the two pins (same pin geometry as
:mod:`gnd_short_ref`), so the clean-vs-modified ``.kicad_sch`` diff is one added
``(wire ...)``.

Eligible nets (both ends): signal nets only. GND-like nets, positive rails and
KiCad's ``unconnected-...`` nets are excluded, since a bridge to those is the
GND / VCC short scenario (:mod:`gnd_short_random`). Within a design, the
variants use pairwise-distinct nets. Eligible pins: visible pins of symbols on
a sheet that is instantiated once.

Ground truth is measured, not assumed: a variant is kept only if, in the
kicad-cli re-export, the two chosen nets merged into one net with exactly
their combined pins and every other net is unchanged. That also rejects a
wire whose path happens to run over some other pin or wire end. Otherwise the
next random pair is tried.

Layout (default ``--out-root outputs/Infected/BridgeRandom``)::

    <out-root>/Wire<i>/<board>/_clean/<name>.net   # clean kicad-cli re-export
    <out-root>/Wire<i>/<board>/kicad/...           # modified project copy
    <out-root>/Wire<i>/<board>/<name>.net          # modified netlist
    <out-root>/Wire<i>/<board>/<name>.cir          # raw kicad-cli SPICE export
    <out-root>/Wire<i>/<board>/bridge_random.json
    <out-root>/Wire<i>/manifest.json
    <out-root>/manifest.json                       # every variant, all boards

The source project is never modified (SHA-256-checked before and after).
"""

import glob
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Dict, List, Optional, Tuple

from . import core as nt
from . import gnd_short as gs
from . import gnd_short_ref as gsr
from . import gnd_short_random as gsx

CLEAN_GLOB = gs.CLEAN_GLOB
DEFAULT_OUT_ROOT = "outputs/Infected/BridgeRandom"
DEFAULT_COUNT = gsx.DEFAULT_COUNT
DEFAULT_SEED = gsx.DEFAULT_SEED
MAX_ATTEMPTS = 200


def _wire(a: Tuple[float, float], b: Tuple[float, float]) -> str:
    """A KiCad 6+ wire block from `a` to `b` (same format as gnd_short's)."""
    return (f"(wire\n\t\t(pts\n\t\t\t(xy {gs._fmt(a[0])} {gs._fmt(a[1])}) "
            f"(xy {gs._fmt(b[0])} {gs._fmt(b[1])})\n\t\t)\n"
            f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f"\t\t(uuid \"{uuid.uuid4()}\")\n\t)")


def insert_bridge(text: str, a: gsx.PinSite, pin_a: str,
                  b: gsx.PinSite, pin_b: str) -> Tuple[str, Dict]:
    """Return (modified sheet text, info) with one wire from pin A to pin B."""
    pa = gsr.pin_xy(text, a.sym_block, pin_a)
    pb = gsr.pin_xy(text, b.sym_block, pin_b)
    anchor = text.find("\n\t(sheet_instances")
    if anchor < 0:
        anchor = text.rstrip().rfind(")") - 1
    modified = text[: anchor + 1] + f"\t{_wire(pa, pb)}\n" + text[anchor + 1:]
    return modified, {"wire_from": list(pa), "wire_to": list(pb)}


def diff_bridge(clean_net: str, modified_net: str, net_a: str, net_b: str) -> Dict:
    """Measured effect of the bridge, plus whether it is exactly A+B merging."""
    clean = {n.name: n.node_set() for n in nt.parse_nets(nt.read(clean_net))}
    modified = {n.name: n.node_set() for n in nt.parse_nets(nt.read(modified_net))}
    want = clean[net_a] | clean[net_b]
    merged = next((name for name, nodes in modified.items() if nodes == want), None)
    others_clean = {k: v for k, v in clean.items() if k not in (net_a, net_b)}
    others_mod = {k: v for k, v in modified.items() if k != merged}
    return {
        "merged_net": merged,
        "merged_nodes": sorted(f"{r}.{p}" for r, p in want),
        "exact": merged is not None and others_clean == others_mod,
    }


def build_variant(root_sch: str, sites: Dict, a: Tuple[str, str], b: Tuple[str, str],
                  net_of: Dict, out_dir: str, clean_net: str) -> Dict:
    sheets = gs.walk_sheets(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]
    site_a, site_b = sites[a], sites[b]

    kicad_dir = os.path.join(out_dir, "kicad")
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)
    copied_sheet = os.path.join(kicad_dir, site_a.sheet_file)
    modified, info = insert_bridge(nt.read(copied_sheet), site_a, a[1], site_b, b[1])
    nt.write(copied_sheet, modified)

    out_net = os.path.join(out_dir, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    na, nb = net_of[a], net_of[b]
    return {
        "ref_a": a[0], "pin_a": a[1], "pinfunction_a": na[1], "net_a": na[0].name,
        "ref_b": b[0], "pin_b": b[1], "pinfunction_b": nb[1], "net_b": nb[0].name,
        "net_a_nodes": sorted(f"{r}.{p}" for r, p in na[0].node_set()),
        "net_b_nodes": sorted(f"{r}.{p}" for r, p in nb[0].node_set()),
        "sheet": site_a.sheet_file, "schematic": copied_sheet, "output": out_net,
        **info, **diff_bridge(clean_net, out_net, na[0].name, nb[0].name),
    }


def variants_for_board(sch: str, board: str, clean_net: str, count: int,
                       seed: int, tmp_root: str) -> List[Dict]:
    """Up to `count` verified single-wire bridges with pairwise-distinct nets."""
    rng = random.Random(f"{seed}:bridge:{board}")
    # vcc mode's filter: no GND-like, positive-rail or unconnected- nets
    nets = gsx.eligible_nets(nt.parse_nets(nt.read(clean_net)), "vcc")
    net_of = {nd.key(): (n, nd.pinfunction) for n in nets for nd in n.nodes}
    sites = {k: v for k, v in gsx.pin_sites(sch, "bridge").items() if k in net_of}
    keys = sorted(sites)

    found: List[Dict] = []
    used_nets: set = set()
    for _ in range(MAX_ATTEMPTS):
        if len(found) == count:
            break
        a = rng.choice(keys)
        na = net_of[a][0].name
        if na in used_nets:
            continue
        partners = [k for k in keys
                    if sites[k].sheet_file == sites[a].sheet_file and k[0] != a[0]
                    and net_of[k][0].name not in used_nets | {na}]
        if not partners:
            continue
        b = rng.choice(partners)
        out_dir = os.path.join(tmp_root, f"{len(found)}_{a[0]}_{a[1]}_{b[0]}_{b[1]}")
        try:
            rec = build_variant(sch, sites, a, b, net_of, out_dir, clean_net)
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(f"{board:24} {a[0]}.{a[1]} <-> {b[0]}.{b[1]}: error ({exc}); retrying")
            shutil.rmtree(out_dir, ignore_errors=True)
            continue
        if not rec["exact"]:
            print(f"{board:24} {a[0]}.{a[1]} <-> {b[0]}.{b[1]}: wire touched more than "
                  f"the two nets; retrying")
            shutil.rmtree(out_dir)
            continue
        rec["_tmp_dir"] = out_dir
        found.append(rec)
        used_nets |= {rec["net_a"], rec["net_b"]}
    return found


def run_batch(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED,
              clean_glob: str = CLEAN_GLOB, out_root: str = DEFAULT_OUT_ROOT) -> int:
    """`count` single-wire component-to-component bridges per resolvable design."""
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
            recs = variants_for_board(sch, board, clean_net, count, seed, tmp)

            for i, rec in enumerate(recs, start=1):
                dest = os.path.join(out_root, f"Wire{i}", board)
                if os.path.exists(dest):
                    raise FileExistsError(f"{dest} already exists; refusing to overwrite")
                src = rec.pop("_tmp_dir")
                shutil.copytree(src, dest)
                shutil.copytree(os.path.dirname(clean_net), os.path.join(dest, "_clean"))
                gsx._retarget(rec, src, dest)
                gsx.export_spice(os.path.join(dest, "kicad", os.path.basename(sch)),
                                 os.path.join(dest, f"{stem}.cir"))
                rec.update({"variant": f"Wire{i}", "board": board, "mode": "bridge",
                            "seed": seed, "clean": path,
                            "clean_reexport": os.path.join(dest, "_clean", f"{stem}.net")})
                with open(os.path.join(dest, "bridge_random.json"), "w") as f:
                    json.dump(rec, f, indent=2)
                manifest.append(rec)
                per_wire[i].append(rec)
                print(f"{board:24} Wire{i}: {rec['ref_a']}.{rec['pin_a']} ({rec['net_a']}) <-> "
                      f"{rec['ref_b']}.{rec['pin_b']} ({rec['net_b']}) -> {rec['merged_net']}")

        if gsr._hash_tree(proj_dir) != before:
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
