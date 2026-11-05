#!/usr/bin/env python3
"""Resistor <-> capacitor substitution on randomly chosen parts: one per variant.

Two modes, mirror images of each other:

- ``r_to_c``: a random resistor becomes a capacitor;
- ``c_to_r``: a random capacitor becomes a resistor.

For each clean design this picks ``count`` distinct *victims* (two-pin parts of
the source kind) at random (seeded, so a run is reproducible) and builds one
variant per victim. Each variant replaces that single part, in place, with a
part of the other kind cloned from one of the design's own parts (the
*template*): its library symbol, ``Value``, ``Footprint`` and the other
properties both parts share. Properties only the victim carries (``Sim.*``,
``MPN``, ...) are dropped, so the part no longer claims to be what it was
anywhere. The reference becomes the next free ``C<n>`` / ``R<n>``, which is
also what makes kicad-cli's SPICE export emit the new element type.

Placement: the template is rotated so its pin 1 -> pin 2 axis matches the
victim's, and pin 1 lands exactly on the victim's pin 1. Where the two parts'
pin spacings agree (``Device:R`` / ``Device:C``, ``R_Small`` / ``C_Small``),
pin 2 lands on the victim's pin 2 too and the ``.kicad_sch`` diff is the one
changed symbol (plus the template's lib symbol, if the sheet lacked it). Where
they differ, one collinear wire from the new pin 2 to the victim's old pin 2
position closes the gap.

Eligible victims: two-pin symbols whose reference is ``R<n>`` / ``C<n>`` on a
sheet that is instantiated once (see :func:`gnd_short_ref.locate` for why
reused sheets are refused). Templates: two-pin symbols of the other kind whose
lib symbol resolves. Templates with a numeric value are preferred (ngspice
drops e.g. ``??``); capacitor templates are preferably non-polarised, so an
``r_to_c`` substitution does not also introduce a polarity question; resistor
templates are preferably not 0-ohm jumpers, so a ``c_to_r`` substitution is a
resistor and not a wire.

Ground truth is measured, not assumed: a variant is kept only if, in the
kicad-cli re-export, the victim's ref is gone, the new part sits on exactly
the victim's nets pin for pin, its library part is the template's, and every
other component and net is unchanged. Otherwise the next random pick is tried.

Layout (default ``--out-root outputs/Infected/Scenarios/ResistorToCapacitorRandom``,
or ``CapacitorToResistorRandom`` for ``c_to_r``)::

    <out-root>/Swap<i>/<board>/_clean/<name>.net   # clean kicad-cli re-export
    <out-root>/Swap<i>/<board>/kicad/...           # modified project copy
    <out-root>/Swap<i>/<board>/<name>.net          # modified netlist
    <out-root>/Swap<i>/<board>/<name>.cir          # raw kicad-cli SPICE export
    <out-root>/Swap<i>/<board>/<mode>_random.json
    <out-root>/Swap<i>/manifest.json
    <out-root>/manifest.json                       # every variant, all boards

The source project is never modified (SHA-256-checked before and after).
"""

import glob
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import core as nt
from . import gnd_short as gs
from . import gnd_short_ref as gsr
from . import gnd_short_random as gsx
from . import bridge_random as br

CLEAN_GLOB = gs.CLEAN_GLOB
# mode -> (victim ref prefix, template / new ref prefix)
MODES = {"r_to_c": ("R", "C"), "c_to_r": ("C", "R")}
DEFAULT_OUT_ROOTS = {"r_to_c": "outputs/Infected/Scenarios/ResistorToCapacitorRandom",
                     "c_to_r": "outputs/Infected/Scenarios/CapacitorToResistorRandom"}
DEFAULT_COUNT = gsx.DEFAULT_COUNT
DEFAULT_SEED = gsx.DEFAULT_SEED

_POLARISED_RE = re.compile(r"polar|^Device:CP|ALUM|ELEC|TANT", re.I)
_ZERO_OHM_RE = re.compile(r"^0+(\.0*)?\s*(r|ohm|Ω)?$", re.I)
_KEEP_PROPS = ("Reference", "Value", "Footprint", "Datasheet")


# --------------------------------------------------------------------------- #
# Discovery: parts to replace, parts to clone
# --------------------------------------------------------------------------- #

@dataclass
class Part:
    ref: str
    sheet_file: str
    sym_block: str
    lib_entry: str
    pins: Dict[str, Tuple[float, float]]  # pin number -> lib (x, y), unit-resolved


def _two_pin_parts(root_sch: str, prefix: str) -> List[Part]:
    """Single-instance two-pin symbols (pins "1" and "2") named ``<prefix><n>``."""
    ref_re = re.compile(rf"^{prefix}\d+$")
    proj_dir = os.path.dirname(root_sch)
    out: List[Part] = []
    for sheet in gs.walk_sheets(root_sch):
        text = nt.read(os.path.join(proj_dir, sheet.file))
        for k, s, e in gs.top_level_blocks(text):
            if k != "symbol":
                continue
            block = text[s:e]
            ref = gsr._ref_of(block)
            inst = gsr._instance_refs(block)
            if len(inst) > 1:
                continue  # reused sheet: one edit would change every instance
            ref = inst[0] if inst else ref
            if not ref or not ref_re.match(ref):
                continue
            try:
                lib = gsr._lib_entry(text, gsr._lib_name(block))
            except ValueError:
                continue
            pins = gsr._lib_pins(lib, gsr._unit(block))
            nums = [n for n, _, _ in pins]
            if sorted(nums) != ["1", "2"]:
                continue  # arrays, multi-pad parts, duplicated pin numbers
            out.append(Part(ref, sheet.file, block, lib,
                            {n: (x, y) for n, x, y in pins}))
    return out


def _is_polarised(part: Part) -> bool:
    return bool(_POLARISED_RE.search(gsr._lib_name(part.sym_block)))


def _value(part: Part) -> str:
    return gs._prop(part.sym_block, "Value") or ""


def _templates(parts: List[Part]) -> List[Part]:
    """`parts` narrowed, where possible, to the best templates to clone."""
    parts = [p for p in parts if re.match(r"\d", _value(p))] or parts
    parts = [p for p in parts if not _is_polarised(p)] or parts
    return [p for p in parts if not _ZERO_OHM_RE.match(_value(p).strip())] or parts


def _next_ref(clean_net_text: str, prefix: str) -> str:
    nums = [int(m.group(1)) for m in
            re.finditer(r'\(comp \(ref "' + prefix + r'(\d+)"\)', clean_net_text)]
    return f"{prefix}{max(nums, default=0) + 1}"


# --------------------------------------------------------------------------- #
# Geometry: where the new part goes
# --------------------------------------------------------------------------- #

def _unit_vec(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    return (round(dx / d, 4), round(dy / d, 4)) if d else (0.0, 0.0)


def place_part(text: str, old: Part, tmpl: Part) -> Tuple[Tuple[float, float, int],
                                                          Optional[Tuple[Tuple[float, float],
                                                                         Tuple[float, float]]]]:
    """((x, y, angle), wire or None) placing `tmpl` over `old`, pin 1 on pin 1.

    The angle is the one (of 0/90/180/270, no mirror) that lines the
    template's pin 1 -> pin 2 axis up with the old part's. The wire, when
    returned, joins the new pin 2 to the old part's pin 2.
    """
    o1 = gsr.pin_xy(text, old.sym_block, "1")
    o2 = gsr.pin_xy(text, old.sym_block, "2")
    want = _unit_vec(o1, o2)
    for ang in (0, 90, 180, 270):
        t1 = gsr._transform(0, 0, ang, None, *tmpl.pins["1"])
        t2 = gsr._transform(0, 0, ang, None, *tmpl.pins["2"])
        if _unit_vec(t1, t2) != want:
            continue
        x, y = round(o1[0] - t1[0], 4), round(o1[1] - t1[1], 4)
        p2 = (round(x + t2[0], 4), round(y + t2[1], 4))
        wire = None if math.isclose(p2[0], o2[0], abs_tol=1e-3) and \
            math.isclose(p2[1], o2[1], abs_tol=1e-3) else (p2, o2)
        return (x, y, ang), wire
    raise ValueError(f"no rotation of {tmpl.ref} lines up with {old.ref}")


# --------------------------------------------------------------------------- #
# Edit: rewrite the old part's symbol block as the template
# --------------------------------------------------------------------------- #

def _props(block: str) -> Dict[str, Tuple[int, int, str]]:
    """{name: (start, end, value)} of every top-level property in a symbol block."""
    out: Dict[str, Tuple[int, int, str]] = {}
    for m in re.finditer(r'\n\t\t\(property "([^"]*)" "((?:[^"\\]|\\.)*)"', block):
        s = m.start() + 1
        out[m.group(1)] = (s, nt.find_matching_paren(block, s + 2) + 1, m.group(2))
    return out


def _quote(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def substitute_block(old_block: str, tmpl_block: str, new_ref: str,
                     at: Tuple[float, float, int]) -> str:
    """The old part's block (uuid, pins, instance path kept) dressed as the template."""
    block = old_block
    tmpl_props = {k: v[2] for k, v in _props(tmpl_block).items()}
    # properties: shared ones take the template's value, old-only ones go
    for name, (s, e, _) in sorted(_props(block).items(), key=lambda kv: -kv[1][0]):
        if name == "Reference":
            continue
        if name in tmpl_props:
            head = re.compile(r'\(property "' + re.escape(name) + r'" "(?:[^"\\]|\\.)*"')
            repl = f'(property "{name}" "{tmpl_props[name]}"'
            block = block[:s] + head.sub(lambda _: repl, block[s:e], count=1) + block[e:]
        elif name not in _KEEP_PROPS:
            ws = len(block[:s]) - len(block[:s].rstrip())
            block = block[:s - ws] + block[e:]
    block = re.sub(r'\(property "Reference" "[^"]*"', f'(property "Reference" "{new_ref}"',
                   block, count=1)
    block = re.sub(r'\(reference "[^"]*"\)', f'(reference "{_quote(new_ref)}")', block)

    # library symbol: lib_id (+ lib_name when the template has one)
    block = re.sub(r'\n\t\t\(lib_name "[^"]*"\)', "", block, count=1)
    lib_id = re.search(r'\(lib_id "[^"]*"\)', tmpl_block).group(0)
    lib_name = re.search(r'\(lib_name "[^"]*"\)', tmpl_block)
    block = re.sub(r'\(lib_id "[^"]*"\)',
                   lambda _: (lib_name.group(0) + "\n\t\t" if lib_name else "") + lib_id,
                   block, count=1)

    # placement: the old part's (at ...) and any (mirror ...) belong to its body
    x, y, ang = at
    block = re.sub(r"\(at -?[\d.]+ -?[\d.]+ \d+\)",
                   f"(at {gs._fmt(x)} {gs._fmt(y)} {ang})", block, count=1)
    head_end = block.find("(property")
    block = re.sub(r"\n\t\t\(mirror (x|y)\)", "", block[:head_end]) + block[head_end:]
    return block


def ensure_lib_symbol(text: str, lib_entry: str) -> Tuple[str, bool]:
    """`text` with `lib_entry` in its lib_symbols (added only if missing)."""
    name = re.match(r'\(symbol "([^"]*)"', lib_entry).group(1)
    try:
        gsr._lib_entry(text, name)
        return text, False
    except ValueError:
        pass
    _, s, e = next(b for b in gs.top_level_blocks(text) if b[0] == "lib_symbols")
    close = text.rfind("\n", s, e - 1)
    return text[:close] + "\n\t\t" + lib_entry + text[close:], True


def substitute(text: str, old: Part, tmpl: Part, new_ref: str) -> Tuple[str, Dict]:
    """Return (modified sheet text, info) with `old` replaced by a clone of `tmpl`."""
    at, wire = place_part(text, old, tmpl)
    start = text.find(old.sym_block)
    if start < 0:
        raise ValueError(f"{old.ref}'s symbol block not found on {old.sheet_file}")
    new_block = substitute_block(old.sym_block, tmpl.sym_block, new_ref, at)
    text = text[:start] + new_block + text[start + len(old.sym_block):]
    text, lib_added = ensure_lib_symbol(text, tmpl.lib_entry)
    if wire:
        anchor = text.find("\n\t(sheet_instances")
        if anchor < 0:
            anchor = text.rstrip().rfind(")") - 1
        text = text[: anchor + 1] + f"\t{br._wire(*wire)}\n" + text[anchor + 1:]
    return text, {
        "placed_at": [at[0], at[1]], "placed_angle": at[2],
        "wire_added": [list(wire[0]), list(wire[1])] if wire else None,
        "lib_symbol_added": lib_added,
    }


# --------------------------------------------------------------------------- #
# Ground truth: what the re-export says changed
# --------------------------------------------------------------------------- #

def _comps(net_text: str) -> Dict[str, Dict[str, str]]:
    """{ref: {value, footprint, lib, part}} for every component in a netlist."""
    out: Dict[str, Dict[str, str]] = {}
    for m in re.finditer(r'\(comp \(ref "([^"]*)"\)', net_text):
        body = net_text[m.start(): nt.find_matching_paren(net_text, m.start()) + 1]
        get = lambda tag: (re.search(r'\(' + tag + r' "((?:[^"\\]|\\.)*)"\)', body) or [None, None])[1]
        out[m.group(1)] = {"value": get("value"), "footprint": get("footprint"),
                           "lib": get("lib"), "part": get("part")}
    return out


def diff_substitution(clean_net: str, modified_net: str, old_ref: str, new_ref: str,
                      template_ref: str) -> Dict:
    """Measured effect of the substitution, plus whether it is exactly that."""
    clean_text, mod_text = nt.read(clean_net), nt.read(modified_net)
    clean_c, mod_c = _comps(clean_text), _comps(mod_text)

    rename = lambda r: new_ref if r == old_ref else r
    clean_nets = Counter(frozenset((rename(r), p) for r, p in n.node_set())
                         for n in nt.parse_nets(clean_text))
    mod_nets = Counter(frozenset(n.node_set()) for n in nt.parse_nets(mod_text))

    pin_nets = {}
    for n in nt.parse_nets(mod_text):
        for r, p in n.node_set():
            if r == new_ref:
                pin_nets[p] = n.name
    clean_pin_nets = {p: n.name for n in nt.parse_nets(clean_text)
                      for r, p in n.node_set() if r == old_ref}

    others_same = ({k: v for k, v in clean_c.items() if k != old_ref}
                   == {k: v for k, v in mod_c.items() if k != new_ref})
    new = mod_c.get(new_ref, {})
    tmpl = clean_c.get(template_ref, {})
    return {
        "clean_pin_nets": clean_pin_nets,
        "pin_nets": pin_nets,
        "new_part": f"{new.get('lib')}:{new.get('part')}" if new else None,
        "exact": (old_ref not in mod_c and new_ref in mod_c and others_same
                  and clean_nets == mod_nets
                  and (new.get("lib"), new.get("part")) == (tmpl.get("lib"), tmpl.get("part"))),
    }


# --------------------------------------------------------------------------- #
# Build + verify one variant
# --------------------------------------------------------------------------- #

def build_variant(root_sch: str, old: Part, tmpl: Part, new_ref: str,
                  out_dir: str, clean_net: str) -> Dict:
    """Write one modified project copy + its exported netlist into `out_dir`."""
    sheets = gs.walk_sheets(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]

    kicad_dir = os.path.join(out_dir, "kicad")
    new_root = gs.copy_project(root_sch, sheets, kicad_dir)
    copied_sheet = os.path.join(kicad_dir, old.sheet_file)
    modified, info = substitute(nt.read(copied_sheet), old, tmpl, new_ref)
    nt.write(copied_sheet, modified)

    out_net = os.path.join(out_dir, f"{stem}.net")
    gs.export_netlist(new_root, out_net)
    clean_c = _comps(nt.read(clean_net))
    was, like = clean_c.get(old.ref, {}), clean_c.get(tmpl.ref, {})
    return {
        "ref": old.ref, "new_ref": new_ref, "template_ref": tmpl.ref,
        "old_value": was.get("value"), "old_footprint": was.get("footprint"),
        "old_part": f"{was.get('lib')}:{was.get('part')}",
        "new_value": like.get("value"), "new_footprint": like.get("footprint"),
        "template_part": f"{like.get('lib')}:{like.get('part')}",
        "template_polarised": _is_polarised(tmpl), "old_polarised": _is_polarised(old),
        "sheet": old.sheet_file, "template_sheet": tmpl.sheet_file,
        "schematic": copied_sheet, "output": out_net,
        **info, **diff_substitution(clean_net, out_net, old.ref, new_ref, tmpl.ref),
    }


def variants_for_board(sch: str, board: str, clean_net: str, count: int,
                       seed: int, tmp_root: str, mode: str = "r_to_c") -> List[Dict]:
    """Up to `count` verified single-part substitutions, distinct victims."""
    src, dst = MODES[mode]
    rng = random.Random(f"{seed}:{mode}:{board}")
    victims = _two_pin_parts(sch, src)
    templates = _templates(_two_pin_parts(sch, dst))
    if not templates:
        print(f"{board:24} no {dst}<n> part to clone", file=sys.stderr)
        return []
    rng.shuffle(victims)
    new_ref = _next_ref(nt.read(clean_net), dst)

    found: List[Dict] = []
    for old in victims:
        if len(found) == count:
            break
        tmpl = rng.choice(templates)
        out_dir = os.path.join(tmp_root, f"{len(found)}_{old.ref}_{tmpl.ref}")
        try:
            rec = build_variant(sch, old, tmpl, new_ref, out_dir, clean_net)
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(f"{board:24} {old.ref} -> {tmpl.ref}: error ({exc}); retrying")
            shutil.rmtree(out_dir, ignore_errors=True)
            continue
        if not rec["exact"]:
            print(f"{board:24} {old.ref} -> {tmpl.ref}: re-export changed more than "
                  f"the one part; retrying")
            shutil.rmtree(out_dir)
            continue
        rec["_tmp_dir"] = out_dir
        found.append(rec)
    return found


# --------------------------------------------------------------------------- #
# Batch runner
# --------------------------------------------------------------------------- #

def run_batch(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED,
              clean_glob: str = CLEAN_GLOB, out_root: Optional[str] = None,
              mode: str = "r_to_c") -> int:
    """`count` single-part R -> C (or C -> R) substitutions per resolvable design."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {sorted(MODES)}, got {mode!r}")
    out_root = out_root or DEFAULT_OUT_ROOTS[mode]
    manifest: List[Dict] = []
    per_swap: Dict[int, List[Dict]] = {i: [] for i in range(1, count + 1)}

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
                dest = os.path.join(out_root, f"Swap{i}", board)
                if os.path.exists(dest):
                    raise FileExistsError(f"{dest} already exists; refusing to overwrite")
                src = rec.pop("_tmp_dir")
                shutil.copytree(src, dest)
                shutil.copytree(os.path.dirname(clean_net), os.path.join(dest, "_clean"))
                gsx._retarget(rec, src, dest)
                gsx.export_spice(os.path.join(dest, "kicad", os.path.basename(sch)),
                                 os.path.join(dest, f"{stem}.cir"))
                rec.update({"variant": f"Swap{i}", "board": board, "mode": mode,
                            "seed": seed, "clean": path,
                            "clean_reexport": os.path.join(dest, "_clean", f"{stem}.net")})
                with open(os.path.join(dest, f"{mode}_random.json"), "w") as f:
                    json.dump(rec, f, indent=2)
                manifest.append(rec)
                per_swap[i].append(rec)
                print(f"{board:24} Swap{i}: {rec['ref']} ({rec['old_value']}) -> "
                      f"{rec['new_ref']} ({rec['new_value']}, cloned from "
                      f"{rec['template_ref']})" + (" +wire" if rec["wire_added"] else ""))

        if gsr._hash_tree(proj_dir) != before:
            raise RuntimeError(f"source project changed under {proj_dir}; aborting")
        if len(recs) < count:
            print(f"{board:24} WARNING: only {len(recs)}/{count} variants could be built",
                  file=sys.stderr)

    os.makedirs(out_root, exist_ok=True)
    for i, recs in per_swap.items():
        if recs:
            with open(os.path.join(out_root, f"Swap{i}", "manifest.json"), "w") as f:
                json.dump(recs, f, indent=2)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} modified design(s) written. Manifest: {manifest_path}")
    return 0
