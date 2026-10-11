#!/usr/bin/env python3
"""Passive "tolerance swap" Trojan (R, C, L families in the Device library).

KiCad netlists carry a component's *value* (10k, 100n, ...) and *footprint*,
but never its tolerance grade -- that's a manufacturing detail the schematic
never states. This Trojan models a supply-chain substitution: a passive is
swapped for a same-family, same-value, same-footprint part sourced to a
*different* tolerance grade (e.g. a 10k resistor pulled in at +/-10% where
the board was designed around +/-1%). Nothing else about the component
changes -- ref, value, footprint, and every net it sits on stay byte-for-byte
identical -- so the tamper is invisible unless the ``Tolerance`` property is
checked against the family's assumed baseline grade.

Rule-based, like ``snip``/``swap``: no spec file, just a deterministic
per-component pick (hash of board + ref) so re-runs are reproducible.
Drive it from the CLI (``netlist_trojans.cli``) with ``tolerance`` /
``tolerance-batch``.
"""

import glob
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

from simp_sexp import Sexp

from . import core as nt

CLEAN_GLOB = "outputs/Clean/*/*.net"

# Device-library libsource `part` values that are two-terminal passives with
# a meaningful tolerance grade, grouped into R / C / L families. Deliberately
# excludes LEDs, diodes, transistors, crystals, fuses, etc. -- those aren't
# specified by a +/-% tolerance the way R/C/L are.
FAMILY_OF_PART = {
    "R": "R", "R_Small": "R", "R_US": "R",
    "C": "C", "C_Small": "C", "C_Polarized": "C",
    "L": "L",
}

# Assumed baseline grade for a freshly-designed board (the grade a component
# is presumed to carry until a Trojan says otherwise), and the standard
# grades a same-family/same-footprint part is actually sold in.
BASELINE_TOLERANCE = {"R": "5%", "C": "10%", "L": "10%"}
TOLERANCE_GRADES = {
    "R": ["0.1%", "1%", "5%", "10%", "20%"],
    "C": ["1%", "5%", "10%", "20%"],
    "L": ["5%", "10%", "20%"],
}


@dataclass
class Comp:
    ref: str
    family: str          # "R", "C", or "L"
    part: str             # raw libsource part, e.g. "R_Small" or a full vendor
                           # description like "RES 10kOhm +/-1% 1/8W 0805 Yageo"
    value: str
    footprint: Optional[str]
    start: int             # char offset of '(comp' in source
    end: int               # char offset just past the block's closing paren
    tolerance_value_start: Optional[int] = None  # existing (value "...") span
    tolerance_value_end: Optional[int] = None
    declared_tolerance: Optional[str] = None      # "+/-X%" mined from vendor text


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

_COMP_OPEN_RE = re.compile(r"\(comp\s")
_TOLERANCE_PROP_RE = re.compile(
    r'\(property \(name "Tolerance"\) \(value "([^"]*)"\)\)')

# Some vendor-sourced libraries (e.g. a Digi-Key/Yageo export) spell the
# tolerance grade straight into the part name / description text, e.g.
# `(part "RES 10kΩ ±1% 1/8W 0805 Yageo")`. Mine it out so the
# assumed "baseline" reflects what the board's BOM actually declares.
_DECLARED_TOLERANCE_RE = re.compile(r"±\s?(\d+(?:\.\d+)?%)")
_TEXT_FAMILY_RE = re.compile(r"^\s*(RES|CAP|IND)\b", re.IGNORECASE)
_TEXT_FAMILY_OF = {"RES": "R", "CAP": "C", "IND": "L"}


def _component_spans(content: str) -> List[Tuple[int, int]]:
    """(start, end) byte span of every (comp ...) block, in document order."""
    open_idx = content.index("(components")
    close_idx = nt.find_matching_paren(content, open_idx)
    spans: List[Tuple[int, int]] = []
    pos = open_idx + 1
    while True:
        m = _COMP_OPEN_RE.search(content, pos, close_idx)
        if not m:
            break
        start = m.start()
        end = nt.find_matching_paren(content, start) + 1
        spans.append((start, end))
        pos = end
    return spans


def _val(node: "Sexp", path: str) -> Optional[str]:
    """Value at a (possibly nested) path under `node`, e.g. 'libsource/part'."""
    res = node.search(f"/{node[0]}/{path}")
    return str(res.value) if len(res) else None


def parse_passives(content: str) -> List[Comp]:
    """Every passive (R/C/L-family) component in `content`, in document order."""
    sexp_comps = Sexp(content).search("/export/components/comp")
    spans = _component_spans(content)
    if len(sexp_comps) != len(spans):
        raise ValueError(
            f"component count mismatch: simp_sexp saw {len(sexp_comps)}, "
            f"text scan saw {len(spans)}")

    out: List[Comp] = []
    for sx, (start, end) in zip(sexp_comps, spans):
        part = _val(sx, "libsource/part") or ""
        family = FAMILY_OF_PART.get(part)
        if family is None:
            m = _TEXT_FAMILY_RE.match(part)
            family = _TEXT_FAMILY_OF.get(m.group(1).upper()) if m else None
        if family is None:
            continue
        block = content[start:end]
        m = _TOLERANCE_PROP_RE.search(block)
        tol_start = tol_end = None
        if m:
            tol_start = start + m.start(1)
            tol_end = start + m.end(1)
        declared = _DECLARED_TOLERANCE_RE.search(block)
        out.append(Comp(
            ref=_val(sx, "ref"),
            family=family,
            part=part,
            value=_val(sx, "value"),
            footprint=_val(sx, "footprint"),
            start=start,
            end=end,
            tolerance_value_start=tol_start,
            tolerance_value_end=tol_end,
            declared_tolerance=declared.group(1) if declared else None,
        ))
    return out


# --------------------------------------------------------------------------- #
# Substitution rule
# --------------------------------------------------------------------------- #

def current_tolerance(comp: Comp, content: str) -> str:
    """The tolerance grade `comp` carries today.

    Precedence: an explicit ``Tolerance`` property already in the block, else
    a grade mined from the vendor part/description text (BOM-accurate), else
    the family's generic default (used only when the netlist states neither).
    """
    if comp.tolerance_value_start is not None:
        return content[comp.tolerance_value_start:comp.tolerance_value_end]
    if comp.declared_tolerance is not None:
        return comp.declared_tolerance
    return BASELINE_TOLERANCE[comp.family]


def pick_substitute_tolerance(comp: Comp, baseline: str, board: str) -> str:
    """Deterministically pick a same-family grade != `baseline` (hash of board+ref)."""
    grades = [g for g in TOLERANCE_GRADES[comp.family] if g != baseline]
    digest = hashlib.sha1(f"{board}:{comp.ref}".encode()).hexdigest()
    return grades[int(digest, 16) % len(grades)]


# --------------------------------------------------------------------------- #
# Apply: splice a Tolerance property into (or update it within) a comp block
# --------------------------------------------------------------------------- #

def apply_tolerance(content: str, comp: Comp, new_tolerance: str) -> str:
    """Return `content` with `comp`'s Tolerance property set to `new_tolerance`."""
    if comp.tolerance_value_start is not None:
        return (content[:comp.tolerance_value_start] + new_tolerance
                + content[comp.tolerance_value_end:])

    block = content[comp.start:comp.end]
    m = re.search(r"\(libsource[^\n]*\)\n", block)
    if not m:
        raise ValueError(f"{comp.ref}: no libsource line to anchor the Tolerance insert")
    indent = nt.leading_indent(content, comp.start) + "  "
    insert_at = comp.start + m.end()
    line = f'{indent}(property (name "Tolerance") (value "{new_tolerance}"))\n'
    return content[:insert_at] + line + content[insert_at:]


def build_substitution(comp: Comp, content: str, board: str) -> dict:
    """Describe (without applying) the tolerance swap chosen for `comp`."""
    baseline = current_tolerance(comp, content)
    new_tolerance = pick_substitute_tolerance(comp, baseline, board)
    return {
        "ref": comp.ref,
        "family": comp.family,
        "part": comp.part,
        "value": comp.value,
        "footprint": comp.footprint,
        "baseline_tolerance": baseline,
        "substituted_tolerance": new_tolerance,
    }


# --------------------------------------------------------------------------- #
# Batch: one output per substituted passive, across every Clean design
# --------------------------------------------------------------------------- #

def run_batch(clean_glob: str = CLEAN_GLOB, out_root: str = None,
              families: Optional[List[str]] = None) -> int:
    """Swap the tolerance of every qualifying passive, one output file each."""
    out_root = out_root or "outputs/Infected/Tolerance"
    families = set(families) if families else {"R", "C", "L"}
    manifest = []

    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        base = os.path.basename(path)
        content = nt.read(path)
        for comp in parse_passives(content):
            if comp.family not in families:
                continue
            sub = build_substitution(comp, content, board)
            infected = apply_tolerance(content, comp, sub["substituted_tolerance"])
            out_dir = os.path.join(out_root, board, comp.ref)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, base)
            nt.write(out_path, infected)
            manifest.append({
                "board": board,
                "clean": path,
                "output": out_path,
                **sub,
            })
            print(f"{board:24} {comp.ref:10} {sub['baseline_tolerance']:>10} -> "
                  f"{sub['substituted_tolerance']:<10} {out_path}")

    os.makedirs(out_root, exist_ok=True)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} infected netlist(s) written. Manifest: {manifest_path}")
    return 0


# --------------------------------------------------------------------------- #
# Single: swap the tolerance of one passive in one file
# --------------------------------------------------------------------------- #

def _default_output(input_path: str) -> str:
    root, ext = os.path.splitext(input_path)
    return f"{root}_infected{ext}"


def run_single(input_path: str, output: str = None, ref: str = None,
              list_only: bool = False) -> int:
    """Swap the tolerance of one passive in a single netlist file."""
    board = os.path.basename(os.path.dirname(input_path)) or "board"
    content = nt.read(input_path)
    candidates = parse_passives(content)
    if not candidates:
        print(f"No R/C/L-family passives found in {input_path}", file=sys.stderr)
        return 1

    if list_only:
        print(f"Passives in {input_path}:")
        for c in candidates:
            baseline = current_tolerance(c, content)
            print(f"  {c.ref:10} family={c.family:2} value={c.value or '':8} "
                  f"tolerance={baseline}")
        return 0

    if ref:
        target = next((c for c in candidates if c.ref == ref), None)
        if target is None:
            refs = ", ".join(c.ref for c in candidates)
            print(f"error: {ref!r} is not a passive in this netlist. "
                  f"Available: {refs}", file=sys.stderr)
            return 1
    else:
        target = candidates[0]
        if len(candidates) > 1:
            print(f"note: {len(candidates)} passives found; substituting the "
                  f"first ({target.ref!r}). Use --ref to choose or --list.",
                  file=sys.stderr)

    sub = build_substitution(target, content, board)
    infected = apply_tolerance(content, target, sub["substituted_tolerance"])
    out_path = output or _default_output(input_path)
    nt.write(out_path, infected)

    print(f"{target.ref}: tolerance {sub['baseline_tolerance']} -> "
          f"{sub['substituted_tolerance']} (family {target.family}, "
          f"value {target.value})")
    print(f"Wrote {out_path}")
    return 0
