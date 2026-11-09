#!/usr/bin/env python3
"""Tolerance-grade substitution on randomly chosen passives: one per variant.

The schematic-level, random counterpart of :mod:`tolerance`, in four modes:
``r_tolerance`` (resistors) and ``c_tolerance`` (capacitors) swap in a
*looser* grade (a higher +/-%, e.g. a +/-1% part fitted as +/-10%);
``r_tolerance_down`` / ``c_tolerance_down`` swap in a *tighter* one (a lower
+/-%, e.g. +/-5% fitted as +/-1%): electrically no worse, but not the part the
design specifies, a costlier or differently-sourced substitution. For each clean
design this picks ``count`` distinct parts of the mode's family at random
(seeded, so a run is reproducible) and builds one variant per part, each with
the same value and footprint.

The part's current grade is, in order of precedence: its ``Tolerance``
property; a ``N%`` token in its ``Value`` (``"2.2k 1%"``); a ``±N%`` in its lib
symbol name or any property (OPNhydro-r2's ``RES 10kΩ ±1% ...`` /
``CAP X7R 100nF ±10% ...``, AcornRobot's LCSC descriptions); else the
family's :data:`tolerance.BASELINE_TOLERANCE` (5% for R, 10% for C). The new
grade is a random one, strictly looser (or, for ``r_tolerance_down``, strictly
tighter, for the ``_down`` modes), from the family's
:data:`tolerance.TOLERANCE_GRADES`; parts already
at the loosest (tightest) grade are skipped, as are 0-value parts and ``??`` placeholders (no tolerance to speak
of).

Edits, all on the part's symbol block in the schematic: a hidden
``Tolerance`` property is set to the new grade (added if missing, cloned from
the block's own ``Datasheet`` property for its layout), and every ``N%`` /
``±N%`` that states the old grade in ``Value`` or another property is
rewritten to the new one, so the part does not contradict itself. A grade
spelled into the lib symbol name (OPNhydro-r2) is left alone, since that is the
symbol itself; the record lists it under ``stale_mentions``. Symbol, reference,
footprint, part numbers and every wire stay as they were.

Ground truth is measured, not assumed: a variant is kept only if, in the
kicad-cli re-export, every net and every other component is byte-identical,
and the resistor carries the new ``Tolerance`` field.

Layout (default ``--out-root outputs/Infected/Scenarios/ResistorToleranceUpRandom``,
``CapacitorToleranceUpRandom`` for ``c_tolerance``,
``ResistorToleranceDownRandom`` for ``r_tolerance_down`` or
``CapacitorToleranceDownRandom`` for ``c_tolerance_down``)::

    <out-root>/Tolerance<i>/<board>/_clean/<name>.net  # clean kicad-cli re-export
    <out-root>/Tolerance<i>/<board>/kicad/...          # modified project copy
    <out-root>/Tolerance<i>/<board>/<name>.net         # modified netlist
    <out-root>/Tolerance<i>/<board>/<name>.cir         # raw kicad-cli SPICE export
    <out-root>/Tolerance<i>/<board>/<mode>_random.json
    <out-root>/Tolerance<i>/manifest.json
    <out-root>/manifest.json                           # every variant, all boards

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
from . import tolerance as tol
from . import value as val

CLEAN_GLOB = gs.CLEAN_GLOB
# mode -> family (ref prefix, and key into tolerance's grade tables)
# mode -> (family: ref prefix and key into tolerance's grade tables,
#          direction: +1 looser / -1 tighter)
MODES = {"r_tolerance": ("R", 1), "c_tolerance": ("C", 1),
         "r_tolerance_down": ("R", -1), "c_tolerance_down": ("C", -1)}
DEFAULT_OUT_ROOTS = {"r_tolerance": "outputs/Infected/Scenarios/ResistorToleranceUpRandom",
                     "c_tolerance": "outputs/Infected/Scenarios/CapacitorToleranceUpRandom",
                     "r_tolerance_down": "outputs/Infected/Scenarios/ResistorToleranceDownRandom",
                     "c_tolerance_down": "outputs/Infected/Scenarios/CapacitorToleranceDownRandom"}
DEFAULT_COUNT = gsx.DEFAULT_COUNT
DEFAULT_SEED = gsx.DEFAULT_SEED

_VALUE_PCT_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")
_PLUSMINUS_PCT_RE = re.compile(r"±\s?(\d+(?:\.\d+)?)\s*%")


def _pct(grade: str) -> float:
    return float(grade.rstrip("%"))


def current_grade(part: psr.Part, family: str = "R") -> Tuple[str, str]:
    """(grade, where it came from) for a part, highest-precedence source first."""
    prop = gs._prop(part.sym_block, "Tolerance")
    if prop and _VALUE_PCT_RE.search(prop):
        return f"{_VALUE_PCT_RE.search(prop).group(1)}%", "Tolerance"
    m = _VALUE_PCT_RE.search(psr._value(part))
    if m:
        return f"{m.group(1)}%", "Value"
    m = _PLUSMINUS_PCT_RE.search(gsr._lib_name(part.sym_block))
    if m:
        return f"{m.group(1)}%", "lib_id"
    for name, (_, _, text) in psr._props(part.sym_block).items():
        m = _PLUSMINUS_PCT_RE.search(text)
        if m:
            return f"{m.group(1)}%", name
    return tol.BASELINE_TOLERANCE[family], "default"


def shifted_grades(grade: str, family: str = "R", direction: int = 1) -> List[str]:
    """Grades strictly looser (direction +1) or tighter (-1) than `grade`."""
    return [g for g in tol.TOLERANCE_GRADES[family]
            if (_pct(g) - _pct(grade)) * direction > 0]


def _restate(text: str, old: str, new: str) -> Tuple[str, int]:
    """`text` with every N% / ±N% equal to `old` rewritten as `new`."""
    def sub(m):
        return m.group(0).replace(m.group(1), new.rstrip("%"), 1) \
            if _pct(m.group(1) + "%") == _pct(old) else m.group(0)
    out = _VALUE_PCT_RE.sub(sub, text)
    return out, int(out != text)


def set_tolerance(block: str, old: str, new: str) -> Tuple[str, Dict]:
    """`block` with its Tolerance property set to `new` and old mentions restated."""
    restated: List[str] = []
    for name, (s, e, text) in sorted(psr._props(block).items(), key=lambda kv: -kv[1][0]):
        if name in ("Reference", "Tolerance", "Footprint", "Datasheet"):
            continue  # Datasheet URLs carry %-escapes, not grades
        new_text, changed = _restate(text, old, new)
        if changed:
            head = f'(property "{name}" "{text}"'
            block = block[:s] + block[s:e].replace(head, f'(property "{name}" "{new_text}"', 1) + block[e:]
            restated.append(name)

    props = psr._props(block)
    if "Tolerance" in props:
        s, e, text = props["Tolerance"]
        block = block[:s] + block[s:e].replace(f'"Tolerance" "{text}"', f'"Tolerance" "{new}"', 1) + block[e:]
        added = False
    else:
        s, e, _ = props["Datasheet"]
        clone = re.sub(r'\(property "Datasheet" "(?:[^"\\]|\\.)*"',
                       lambda _: f'(property "Tolerance" "{new}"', block[s:e], count=1)
        if "(hide yes)" not in clone:
            clone = clone.replace("\t\t\t\t)\n", "\t\t\t\t)\n\t\t\t\t(hide yes)\n", 1)
        last_end = max(pe for _, pe, _ in props.values())
        block = block[:last_end] + "\n" + clone + block[last_end:]  # clone keeps its tabs
        added = True
    return block, {"restated_in": sorted(restated), "tolerance_property_added": added}


def _comp_blocks(net_text: str) -> Dict[str, str]:
    return {m.group(1): net_text[m.start(): nt.find_matching_paren(net_text, m.start()) + 1]
            for m in re.finditer(r'\(comp \(ref "([^"]*)"\)', net_text)}


def diff_tolerance(clean_net: str, modified_net: str, ref: str, new: str) -> Dict:
    """Measured effect of the edit, plus whether it is exactly that."""
    clean_text, mod_text = nt.read(clean_net), nt.read(modified_net)
    clean_b, mod_b = _comp_blocks(clean_text), _comp_blocks(mod_text)
    nets = lambda t: sorted((n.name, sorted(n.node_set())) for n in nt.parse_nets(t))
    field = re.search(r'\(field \(name "Tolerance"\) "([^"]*)"\)', mod_b.get(ref, ""))
    return {
        "exported_tolerance": field.group(1) if field else None,
        "exported_value": psr._comps(mod_text).get(ref, {}).get("value"),
        "exact": (bool(field) and field.group(1) == new
                  and {k: v for k, v in clean_b.items() if k != ref}
                  == {k: v for k, v in mod_b.items() if k != ref}
                  and set(clean_b) == set(mod_b)
                  and nets(clean_text) == nets(mod_text)),
    }


def build_variant(root_sch: str, part: psr.Part, old: str, source: str, new: str,
                  out_dir: str, clean_net: str) -> Dict:
    """Write one modified project copy + its exported netlist into `out_dir`."""
    sheets = gs.walk_sheets(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]

    kicad_dir = os.path.join(out_dir, "kicad")
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)
    copied_sheet = os.path.join(kicad_dir, part.sheet_file)
    text = nt.read(copied_sheet)
    start = text.find(part.sym_block)
    if start < 0:
        raise ValueError(f"{part.ref}'s symbol block not found on {part.sheet_file}")
    new_block, info = set_tolerance(part.sym_block, old, new)
    nt.write(copied_sheet, text[:start] + new_block + text[start + len(part.sym_block):])

    out_net = os.path.join(out_dir, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    clean_c = psr._comps(nt.read(clean_net)).get(part.ref, {})
    pin_nets = {p: n.name for n in nt.parse_nets(nt.read(clean_net))
                for r, p in n.node_set() if r == part.ref}
    stale = ["lib_id"] if _PLUSMINUS_PCT_RE.search(gsr._lib_name(part.sym_block)) else []
    return {
        "ref": part.ref, "value": clean_c.get("value"),
        "footprint": clean_c.get("footprint"), "part": f"{clean_c.get('lib')}:{clean_c.get('part')}",
        "baseline_tolerance": old, "baseline_source": source, "substituted_tolerance": new,
        "pin_nets": pin_nets, "sheet": part.sheet_file,
        "schematic": copied_sheet, "output": out_net, "stale_mentions": stale,
        **info, **diff_tolerance(clean_net, out_net, part.ref, new),
    }


def variants_for_board(sch: str, board: str, clean_net: str, count: int,
                       seed: int, tmp_root: str, mode: str = "r_tolerance") -> List[Dict]:
    """Up to `count` verified single-part tolerance swaps, distinct parts."""
    family, direction = MODES[mode]
    rng = random.Random(f"{seed}:{mode}:{board}")
    parts = psr._two_pin_parts(sch, family)
    rng.shuffle(parts)

    found: List[Dict] = []
    for part in parts:
        if len(found) == count:
            break
        if val.parse_value_token(psr._value(part), 0) is None:
            continue  # 0-value part or "??": no meaningful tolerance
        old, source = current_grade(part, family)
        options = shifted_grades(old, family, direction)
        if not options:
            continue
        new = rng.choice(options)
        out_dir = os.path.join(tmp_root, f"{len(found)}_{part.ref}")
        try:
            rec = build_variant(sch, part, old, source, new, out_dir, clean_net)
        except (ValueError, KeyError, subprocess.CalledProcessError) as exc:
            print(f"{board:24} {part.ref}: error ({exc!r}); retrying")
            shutil.rmtree(out_dir, ignore_errors=True)
            continue
        if not rec["exact"]:
            print(f"{board:24} {part.ref}: re-export changed more than its tolerance; retrying")
            shutil.rmtree(out_dir)
            continue
        rec["_tmp_dir"] = out_dir
        found.append(rec)
    return found


def run_batch(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED,
              clean_glob: str = CLEAN_GLOB, out_root: Optional[str] = None,
              mode: str = "r_tolerance") -> int:
    """`count` single-part tolerance swaps per resolvable clean design."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {sorted(MODES)}, got {mode!r}")
    out_root = out_root or DEFAULT_OUT_ROOTS[mode]
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
            recs = variants_for_board(sch, board, clean_net, count, seed, tmp, mode)

            for i, rec in enumerate(recs, start=1):
                dest = os.path.join(out_root, f"Tolerance{i}", board)
                if os.path.exists(dest):
                    raise FileExistsError(f"{dest} already exists; refusing to overwrite")
                src = rec.pop("_tmp_dir")
                shutil.copytree(src, dest)
                shutil.copytree(os.path.dirname(clean_net), os.path.join(dest, "_clean"))
                gsx._retarget(rec, src, dest)
                gsx.export_spice(os.path.join(dest, "kicad", os.path.basename(sch)),
                                 os.path.join(dest, f"{stem}.cir"))
                rec.update({"variant": f"Tolerance{i}", "board": board, "mode": mode,
                            "seed": seed, "clean": path,
                            "clean_reexport": os.path.join(dest, "_clean", f"{stem}.net")})
                with open(os.path.join(dest, f"{mode}_random.json"), "w") as f:
                    json.dump(rec, f, indent=2)
                manifest.append(rec)
                per_var[i].append(rec)
                print(f"{board:24} Tolerance{i}: {rec['ref']} ({rec['value']}) "
                      f"{rec['baseline_tolerance']} [{rec['baseline_source']}] -> "
                      f"{rec['substituted_tolerance']}")

        if gsr._hash_tree(proj_dir) != before:
            raise RuntimeError(f"source project changed under {proj_dir}; aborting")
        if len(recs) < count:
            print(f"{board:24} WARNING: only {len(recs)}/{count} variants could be built",
                  file=sys.stderr)

    os.makedirs(out_root, exist_ok=True)
    for i, recs in per_var.items():
        if recs:
            with open(os.path.join(out_root, f"Tolerance{i}", "manifest.json"), "w") as f:
                json.dump(recs, f, indent=2)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} modified design(s) written. Manifest: {manifest_path}")
    return 0
