#!/usr/bin/env python3
"""Passive "magnitude swap" Trojan (R, C, L families in the Device library).

Where ``tolerance`` fakes a manufacturing grade, this one tampers with the
component's actual nominal value: it shifts the SI-prefix magnitude (p, n,
u, m, k, M, ...) while leaving every digit, the decimal point, and the base
unit (ohms / farads / henries) exactly as printed. A 10k pull-up silently
becomes a 10M one; a 100n decoupling cap becomes a 100u; a bare "47" (ohm)
resistor becomes "47k". Nothing else in the file changes -- ref, footprint,
every wire -- so the tamper reads, at a glance, like a plausible component
value rather than an obvious corruption.

KiCad values in this corpus come in three shapes, all handled the same way:
  - a plain SI-shorthand token: "10k", "100n", "3.9uH", "1.8M"
  - the KiCad decimal-in-letter form, where the prefix letter also marks
    the decimal point: "4k7" (4.7k), "2u2" (2.2u), "10k7" (10.7k)
  - a bare/no-prefix number, with or without a spelled-out unit:
    "47", "100R", "0.47ohm", "100Ω" (all "no SI prefix" -- unity)
A trailing rating/tolerance/description ("47uF 63V solid", "1nF 2kV",
"2.2k 1%", "0.1uF/16V") is split off first and left untouched, so a prefix
letter buried in a voltage rating (the "k" in "2kV") is never mistaken for
the component's own magnitude.

Rule-based, like ``tolerance``: no spec file, a deterministic per-component
pick (hash of board + ref) so re-runs are reproducible. Drive it from the
CLI (``netlist_trojans.cli``) with ``value`` / ``value-batch``.
"""

import glob
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional

from . import core as nt
from . import tolerance as tol

CLEAN_GLOB = "outputs/Clean/*/*.net"

# Same family classification as the tolerance Trojan (R/C/L two-terminal
# passives only); reused so both Trojans agree on what counts as "passive".
FAMILY_OF_PART = tol.FAMILY_OF_PART

# Plausible SI-prefix decades to substitute between, per family. "" means
# "no prefix" (bare/unity base unit) -- only resistors in this corpus are
# ever written that way ("47", "100R", "0.47ohm").
FAMILY_DECADES = {
    "R": ["", "m", "k", "M"],
    "C": ["p", "n", "u", "m"],
    "L": ["n", "u", "m"],
}

# µ (U+00B5) and μ (U+03BC) both appear in this corpus as spellings of
# "micro"; normalised to "u" for matching and for any newly-written prefix.
_PREFIX_NORMALISE = {"µ": "u", "μ": "u", "K": "k", "R": ""}


# --------------------------------------------------------------------------- #
# Value-token parsing
# --------------------------------------------------------------------------- #

_TOKEN_SPLIT_RE = re.compile(r"[\s/]")

# num1 [prefix] [num2] [unit], where `prefix` doubles as the decimal point in
# KiCad's "4k7" shorthand, and a bare "R" both marks that spot AND implies
# ohms (so "100R" needs no separate unit letter). Longer unit words must be
# tried before their prefixes ("ohms" before "ohm") or the match truncates.
_VALUE_TOKEN_RE = re.compile(
    r"^(?P<num1>\d*\.?\d*)"
    r"(?P<prefix>[pnuµμmkKMG]|R)?"
    r"(?P<num2>\d*)"
    r"(?P<unit>ohms|ohm|Ω|F|H)?$"
)


@dataclass
class ValueToken:
    num1: str
    prefix: str       # "" if none matched (bare/unity)
    num2: str
    unit: str          # "" if none matched
    token_start: int    # char offset of the token within the full netlist
    token_end: int


def parse_value_token(value: str, token_offset: int) -> Optional[ValueToken]:
    """Parse the leading (magnitude) token of a component's value string.

    Returns None if the token isn't a recognisable magnitude (e.g. the "??"
    placeholder seen in one board) or if its mantissa is exactly zero (a
    0-ohm link has no meaningful "magnitude" to shift).
    """
    split = _TOKEN_SPLIT_RE.search(value)
    token = value[:split.start()] if split else value
    m = _VALUE_TOKEN_RE.match(token)
    if not m or (not m.group("num1") and not m.group("prefix")
                 and not m.group("num2") and not m.group("unit")):
        return None
    num1 = m.group("num1") or ""
    try:
        if not num1 or float(num1) == 0:
            return None
    except ValueError:
        return None
    return ValueToken(
        num1=num1,
        prefix=m.group("prefix") or "",
        num2=m.group("num2") or "",
        unit=m.group("unit") or "",
        token_start=token_offset,
        token_end=token_offset + len(token),
    )


def _normalise(prefix: str) -> str:
    return _PREFIX_NORMALISE.get(prefix, prefix)


def pick_substitute_decade(family: str, current_decade: str, board: str, ref: str) -> str:
    """Deterministically pick a same-family decade != current (hash of board+ref)."""
    decades = [d for d in FAMILY_DECADES[family] if d != current_decade]
    digest = hashlib.sha1(f"{board}:{ref}:value".encode()).hexdigest()
    return decades[int(digest, 16) % len(decades)]


def render_token(tok: ValueToken, new_prefix: str) -> str:
    """Digits/decimal point/unit preserved; only the prefix letter changes."""
    return tok.num1 + new_prefix + tok.num2 + tok.unit


# --------------------------------------------------------------------------- #
# Candidate discovery (reuses tolerance's family/component parsing)
# --------------------------------------------------------------------------- #

@dataclass
class Candidate:
    ref: str
    family: str
    old_value: str
    footprint: Optional[str]
    token: ValueToken


def parse_candidates(content: str) -> List[Candidate]:
    """Every passive with a magnitude-shiftable value, in document order."""
    out: List[Candidate] = []
    for comp in tol.parse_passives(content):
        if comp.value is None:
            continue
        # `(value "...")` is always the line right after `(comp (ref "REF")`,
        # which disambiguates it from `(property ... (value "..."))` blocks
        # (e.g. an existing Tolerance property) later in the same comp block.
        anchor = re.compile(
            r'\(comp \(ref "' + re.escape(comp.ref) + r'"\)\s*\n\s*\(value "([^"]*)"\)')
        m = anchor.match(content, comp.start)
        if not m:
            continue
        token = parse_value_token(m.group(1), m.start(1))
        if token is None:
            continue
        out.append(Candidate(
            ref=comp.ref, family=comp.family, old_value=m.group(1),
            footprint=comp.footprint, token=token,
        ))
    return out


def build_substitution(cand: Candidate, board: str) -> dict:
    """Describe (without applying) the magnitude swap chosen for `cand`."""
    current_decade = _normalise(cand.token.prefix)
    new_decade = pick_substitute_decade(cand.family, current_decade, board, cand.ref)
    new_value = render_token(cand.token, new_decade)
    return {
        "ref": cand.ref,
        "family": cand.family,
        "footprint": cand.footprint,
        "old_value": cand.old_value,
        "new_value": new_value,
    }


def apply_value(content: str, cand: Candidate, new_value: str) -> str:
    """Return `content` with `cand`'s value token replaced by `new_value`."""
    t = cand.token
    return content[:t.token_start] + new_value + content[t.token_end:]


# --------------------------------------------------------------------------- #
# Batch: one output per substituted passive, across every Clean design
# --------------------------------------------------------------------------- #

def run_batch(clean_glob: str = CLEAN_GLOB, out_root: str = None,
              families: Optional[List[str]] = None) -> int:
    """Swap the magnitude of every qualifying passive, one output file each."""
    out_root = out_root or "outputs/Infected/Value"
    families = set(families) if families else {"R", "C", "L"}
    manifest = []

    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        base = os.path.basename(path)
        content = nt.read(path)
        for cand in parse_candidates(content):
            if cand.family not in families:
                continue
            sub = build_substitution(cand, board)
            infected = apply_value(content, cand, sub["new_value"])
            out_dir = os.path.join(out_root, board, cand.ref)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, base)
            nt.write(out_path, infected)
            manifest.append({
                "board": board,
                "clean": path,
                "output": out_path,
                **sub,
            })
            print(f"{board:24} {cand.ref:10} {sub['old_value']:>12} -> "
                  f"{sub['new_value']:<12} {out_path}")

    os.makedirs(out_root, exist_ok=True)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} infected netlist(s) written. Manifest: {manifest_path}")
    return 0


# --------------------------------------------------------------------------- #
# Single: swap the magnitude of one passive in one file
# --------------------------------------------------------------------------- #

def _default_output(input_path: str) -> str:
    root, ext = os.path.splitext(input_path)
    return f"{root}_infected{ext}"


def run_single(input_path: str, output: str = None, ref: str = None,
              list_only: bool = False) -> int:
    """Swap the magnitude of one passive in a single netlist file."""
    board = os.path.basename(os.path.dirname(input_path)) or "board"
    content = nt.read(input_path)
    candidates = parse_candidates(content)
    if not candidates:
        print(f"No magnitude-shiftable R/C/L passives found in {input_path}",
              file=sys.stderr)
        return 1

    if list_only:
        print(f"Passives in {input_path}:")
        for c in candidates:
            print(f"  {c.ref:10} family={c.family:2} value={c.old_value}")
        return 0

    if ref:
        target = next((c for c in candidates if c.ref == ref), None)
        if target is None:
            refs = ", ".join(c.ref for c in candidates)
            print(f"error: {ref!r} is not a magnitude-shiftable passive in this "
                  f"netlist. Available: {refs}", file=sys.stderr)
            return 1
    else:
        target = candidates[0]
        if len(candidates) > 1:
            print(f"note: {len(candidates)} passives found; substituting the "
                  f"first ({target.ref!r}). Use --ref to choose or --list.",
                  file=sys.stderr)

    sub = build_substitution(target, board)
    infected = apply_value(content, target, sub["new_value"])
    out_path = output or _default_output(input_path)
    nt.write(out_path, infected)

    print(f"{target.ref}: value {sub['old_value']} -> {sub['new_value']} "
          f"(family {target.family})")
    print(f"Wrote {out_path}")
    return 0
