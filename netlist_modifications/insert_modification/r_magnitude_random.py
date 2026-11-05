#!/usr/bin/env python3
"""Resistor magnitude step-up on randomly chosen resistors: one per variant.

For each clean design this picks ``count`` distinct resistors at random (seeded,
so a run is reproducible) and builds one variant per resistor. Each variant
moves that single resistor's ``Value`` up one SI step (x1000): the prefix
letter changes (``m`` -> none -> ``k`` -> ``M``) while every digit, the decimal
point, the unit and any trailing rating are kept, using :mod:`value`'s token
parser. A 470 becomes 470k, a 10k pull-up becomes 10M, a 4k7 becomes 4M7 and
a 110m shunt becomes 110. Only the ``Value`` property is edited, in the
schematic: symbol, reference, footprint, part numbers and every wire stay
as they were, so the ``.kicad_sch`` diff is one property line.

Eligible resistors: two-pin ``R<n>`` symbols on a sheet that is instantiated
once (see :func:`passive_swap_random._two_pin_parts`) whose value parses as a
magnitude below the top step. 0-ohm links, ``??`` placeholders and values
already in ``M`` are skipped, since none has a larger plausible magnitude.

Ground truth is measured, not assumed: a variant is kept only if, in the
kicad-cli re-export, that resistor's value is exactly the new one and every
net and every other component field is unchanged. Otherwise the next random
pick is tried.

Layout (default ``--out-root outputs/Infected/Scenarios/ResistorMagnitudeUpRandom``)::

    <out-root>/Value<i>/<board>/_clean/<name>.net  # clean kicad-cli re-export
    <out-root>/Value<i>/<board>/kicad/...          # modified project copy
    <out-root>/Value<i>/<board>/<name>.net         # modified netlist
    <out-root>/Value<i>/<board>/<name>.cir         # raw kicad-cli SPICE export
    <out-root>/Value<i>/<board>/r_magnitude_random.json
    <out-root>/Value<i>/manifest.json
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
from typing import Dict, List, Optional, Tuple

from . import core as nt
from . import gnd_short as gs
from . import gnd_short_ref as gsr
from . import gnd_short_random as gsx
from . import passive_swap_random as psr
from . import value as val

CLEAN_GLOB = gs.CLEAN_GLOB
DEFAULT_OUT_ROOT = "outputs/Infected/Scenarios/ResistorMagnitudeUpRandom"
DEFAULT_COUNT = gsx.DEFAULT_COUNT
DEFAULT_SEED = gsx.DEFAULT_SEED

# resistor magnitudes, smallest first; a step up is one place to the right
STEPS = ["m", "", "k", "M"]
_FACTOR = 1000


def step_up(value: str) -> Optional[Tuple[str, str, str]]:
    """(new value, old prefix, new prefix) one SI step up, or None if ineligible."""
    tok = val.parse_value_token(value, 0)
    if tok is None:
        return None
    old = val._normalise(tok.prefix)
    if old not in STEPS or old == STEPS[-1]:
        return None
    new = STEPS[STEPS.index(old) + 1]
    # "100R" / "4R7": R marks ohms (and the decimal point); a new letter does both
    new_value = val.render_token(tok, new) + value[tok.token_end:]
    if not new and not tok.num2 and tok.prefix:
        new_value = tok.num1 + tok.unit + value[tok.token_end:]  # "110m" -> "110"
    elif not new and tok.num2:
        new_value = val.render_token(tok, "R") + value[tok.token_end:]  # "4m7" -> "4R7"
    return new_value, old, new


def set_value(block: str, new_value: str) -> str:
    """`block` with its Value property set to `new_value` (nothing else touched)."""
    q = new_value.replace("\\", "\\\\").replace('"', '\\"')
    out, n = re.subn(r'\(property "Value" "(?:[^"\\]|\\.)*"',
                     lambda _: f'(property "Value" "{q}"', block, count=1)
    if not n:
        raise ValueError("symbol has no Value property")
    return out


def diff_value(clean_net: str, modified_net: str, ref: str, new_value: str) -> Dict:
    """Measured effect of the edit, plus whether it is exactly that."""
    clean_text, mod_text = nt.read(clean_net), nt.read(modified_net)
    clean_c, mod_c = psr._comps(clean_text), psr._comps(mod_text)
    nets = lambda t: sorted((n.name, sorted(n.node_set())) for n in nt.parse_nets(t))
    expected = dict(clean_c)
    if ref in expected:
        expected[ref] = {**expected[ref], "value": new_value}
    return {
        "exported_value": mod_c.get(ref, {}).get("value"),
        "exact": mod_c == expected and nets(clean_text) == nets(mod_text),
    }


def build_variant(root_sch: str, res: psr.Part, new_value: str,
                  out_dir: str, clean_net: str) -> Dict:
    """Write one modified project copy + its exported netlist into `out_dir`."""
    sheets = gs.walk_sheets(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]

    kicad_dir = os.path.join(out_dir, "kicad")
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)
    copied_sheet = os.path.join(kicad_dir, res.sheet_file)
    text = nt.read(copied_sheet)
    start = text.find(res.sym_block)
    if start < 0:
        raise ValueError(f"{res.ref}'s symbol block not found on {res.sheet_file}")
    text = text[:start] + set_value(res.sym_block, new_value) + text[start + len(res.sym_block):]
    nt.write(copied_sheet, text)

    out_net = os.path.join(out_dir, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    clean_c = psr._comps(nt.read(clean_net)).get(res.ref, {})
    pin_nets = {p: n.name for n in nt.parse_nets(nt.read(clean_net))
                for r, p in n.node_set() if r == res.ref}
    return {
        "ref": res.ref, "old_value": clean_c.get("value"), "new_value": new_value,
        "footprint": clean_c.get("footprint"), "part": f"{clean_c.get('lib')}:{clean_c.get('part')}",
        "pin_nets": pin_nets, "sheet": res.sheet_file,
        "schematic": copied_sheet, "output": out_net,
        **diff_value(clean_net, out_net, res.ref, new_value),
    }


def variants_for_board(sch: str, board: str, clean_net: str, count: int,
                       seed: int, tmp_root: str) -> List[Dict]:
    """Up to `count` verified single-resistor step-ups, distinct resistors."""
    rng = random.Random(f"{seed}:r_magnitude:{board}")
    resistors = psr._two_pin_parts(sch, "R")
    rng.shuffle(resistors)

    found: List[Dict] = []
    for res in resistors:
        if len(found) == count:
            break
        step = step_up(psr._value(res))
        if step is None:
            continue
        new_value, old_prefix, new_prefix = step
        out_dir = os.path.join(tmp_root, f"{len(found)}_{res.ref}")
        try:
            rec = build_variant(sch, res, new_value, out_dir, clean_net)
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(f"{board:24} {res.ref}: error ({exc}); retrying")
            shutil.rmtree(out_dir, ignore_errors=True)
            continue
        if not rec["exact"]:
            print(f"{board:24} {res.ref}: re-export changed more than its value; retrying")
            shutil.rmtree(out_dir)
            continue
        rec.update({"old_prefix": old_prefix, "new_prefix": new_prefix, "factor": _FACTOR,
                    "_tmp_dir": out_dir})
        found.append(rec)
    return found


def run_batch(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED,
              clean_glob: str = CLEAN_GLOB, out_root: str = DEFAULT_OUT_ROOT) -> int:
    """`count` single-resistor magnitude step-ups per resolvable clean design."""
    manifest: List[Dict] = []
    per_value: Dict[int, List[Dict]] = {i: [] for i in range(1, count + 1)}

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
                dest = os.path.join(out_root, f"Value{i}", board)
                if os.path.exists(dest):
                    raise FileExistsError(f"{dest} already exists; refusing to overwrite")
                src = rec.pop("_tmp_dir")
                shutil.copytree(src, dest)
                shutil.copytree(os.path.dirname(clean_net), os.path.join(dest, "_clean"))
                gsx._retarget(rec, src, dest)
                gsx.export_spice(os.path.join(dest, "kicad", os.path.basename(sch)),
                                 os.path.join(dest, f"{stem}.cir"))
                rec.update({"variant": f"Value{i}", "board": board, "mode": "r_magnitude",
                            "seed": seed, "clean": path,
                            "clean_reexport": os.path.join(dest, "_clean", f"{stem}.net")})
                with open(os.path.join(dest, "r_magnitude_random.json"), "w") as f:
                    json.dump(rec, f, indent=2)
                manifest.append(rec)
                per_value[i].append(rec)
                print(f"{board:24} Value{i}: {rec['ref']} {rec['old_value']} -> {rec['new_value']}")

        if gsr._hash_tree(proj_dir) != before:
            raise RuntimeError(f"source project changed under {proj_dir}; aborting")
        if len(recs) < count:
            print(f"{board:24} WARNING: only {len(recs)}/{count} variants could be built",
                  file=sys.stderr)

    os.makedirs(out_root, exist_ok=True)
    for i, recs in per_value.items():
        if recs:
            with open(os.path.join(out_root, f"Value{i}", "manifest.json"), "w") as f:
                json.dump(recs, f, indent=2)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} modified design(s) written. Manifest: {manifest_path}")
    return 0
