#!/usr/bin/env python3
"""Generate infected SPICE (.cir) circuits from infected ComponentSubstitution netlists.

For each infected ``.net`` under
``outputs/Infected/ComponentSubstitution/{Value,Tolerance}/<board>/<ref>/``, write
a sibling ``.cir`` next to it, derived from that board's Clean ``.cir`` template
(``outputs/Clean/<board>/*.cir``) with the same substitution applied.

KiCad only produces a ``.cir`` from a *schematic* (via ``kicad-cli``); the
infected netlists here have no schematic, only the ``.net`` diff, so this
script does not re-run that export. Instead it reproduces its effect
directly, in SPICE terms:

  - Value substitution (``insert_modification.value``): shifts one component's
    SI-magnitude prefix (e.g. ``10k`` -> ``10M``) while leaving every digit
    untouched. The Clean ``.cir`` line for that ref has already been resolved
    by KiCad's exporter into decimal SPICE notation (``4k7`` -> ``4.7k``,
    ``1.8M`` -> ``1.8Meg``) — the script parses just the prefix off both the
    Clean and infected ``.net`` values (via
    ``insert_modification.value.parse_value_token``), then rewrites *only* the
    matching ``.cir`` line's trailing prefix letter(s) to the SPICE spelling
    of the new decade (``Meg`` for mega, since bare SPICE ``M`` means milli),
    reusing the already-correct mantissa verbatim.
  - Tolerance substitution (``insert_modification.tolerance``): adds/changes a
    ``Tolerance`` *property*; the component's ``value`` field is never
    touched, and KiCad's SPICE exporter has no notion of tolerance at all —
    so the resulting ``.cir`` is a copy of the Clean template with only its
    ``write`` output path retargeted (see below), every simulated component
    value left exactly as in the Clean board.

If the changed ref isn't part of the Clean ``.cir``'s exported passives (KiCad
excludes some schematic components from its SPICE export even in the Clean
board — see e.g. fan_controller's R6), the ``.cir`` is written out unchanged
and the manifest notes why.

Never reads a Clean ``.net``/``.cir`` for anything other than as an unmodified
template, and never writes under ``outputs/Clean/``.

Usage (run with the project venv, from the repo root):
  .venv/bin/python -m netlist_modifications.conversions.convert_spice
  .venv/bin/python -m netlist_modifications.conversions.convert_spice --root outputs/Infected/ComponentSubstitution/Value
  .venv/bin/python -m netlist_modifications.conversions.convert_spice --dry-run
"""

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

from ..insert_modification import core as nt
from ..insert_modification import tolerance as tol
from ..insert_modification import value as val

DEFAULT_ROOT = "outputs/Infected/ComponentSubstitution"
CLEAN_ROOT = "outputs/Clean"

# SPICE spelling for each decade `insert_modification.value` can substitute between.
# "M" is deliberately mapped to "Meg": bare SPICE/ngspice "M" means milli, so a
# naive passthrough would silently turn a mega-ohm resistor into a milli-ohm
# one. Mirrors `insert_modification.value._PREFIX_NORMALISE` for the reverse map.
SPICE_PREFIX = {"": "", "p": "p", "n": "n", "u": "u", "m": "m", "k": "k", "M": "Meg"}
_PREFIX_NORMALISE = {"µ": "u", "μ": "u", "K": "k", "R": ""}

# A Clean .cir's value field, already resolved by KiCad's exporter into plain
# decimal SPICE notation (no "4k7" shorthand left): mantissa + optional prefix
# + an optional explicit base-unit letter some boards' exports still carry
# (e.g. "47uF", "18pF" -- others have already had it stripped, e.g. "100n").
_CIR_VALUE_RE = re.compile(r"^(?P<mantissa>\d+\.?\d*)(?P<prefix>Meg|[pnumkMG])?(?P<unit>[FH])?$")

# The Clean template's `.control` block writes its ngspice .raw dump to a
# single shared path (e.g. `write ./outputs/spice_circuits/fan_controller_raw.raw
# all`). Copied verbatim, every one of a board's ~100 infected variants would
# collide on that same path. Retargeted below to sit next to each variant's
# own .cir instead, keeping the raw file's original basename.
_WRITE_LINE_RE = re.compile(r"^(write\s+)(\S+)(\s+all.*)$")

# stack-chan's Clean .cir (outputs/Clean/stack-chan/m5-pantilt.cir) was checked
# in at the *raw* kicad-cli export stage -- component lines plus a bare
# `.title`/`.end`, no `.control`/`tran`/`write`/DC sources -- rather than the
# finished stage every other board's Clean .cir is already at. `_complete_raw_kicad_cir`
# below finishes it, exactly mirroring
# `pcb_qa.parsers.spice.KiCadSPICECircuitProcesser.convert_project_spice_to_circuit`
# (voltage-rating stripping, GND -> 0, dropping unmodeled 2-token component
# lines, a DC source for every `+<digits>...` power rail, then appending the
# `.control`/tran/write/`.endc` block). Reimplemented here as a pure in-memory
# transform -- never touching disk -- because that method normalises its input
# file *in place*, and the whole point is to never write to outputs/Clean/.
_RATING_STRIP_RE = re.compile(r"/(\d+(?:\.\d+)?)V", re.IGNORECASE)
_GND_RE = re.compile(r"GND", re.IGNORECASE)
_POWER_RAIL_RE = re.compile(r"\+\d+")
_STACK_CHAN_BOARD = "stack-chan"


def _normalise(prefix: str) -> str:
    return _PREFIX_NORMALISE.get(prefix, prefix)


def _convert_voltage_str(voltage_str: str) -> float:
    return float(voltage_str.upper().replace("V", ".", 1))


def _complete_raw_kicad_cir(raw_lines: List[str], cir_stem: str) -> List[str]:
    lines = [_RATING_STRIP_RE.sub("", ln) for ln in raw_lines]
    first_line, last_line = lines[0], lines[-1]

    new_lines: List[str] = []
    for line in lines[1:-2]:
        entries = line.split(" ")
        if len(entries) == 2:
            continue  # unmodeled component (connector/transistor/diode/IC/switch)
        new_lines.append(_GND_RE.sub("0", line))

    power_lines: Dict[str, bool] = {}
    for line in new_lines:
        for entry in line.split(" "):
            if _POWER_RAIL_RE.search(entry) and not entry.startswith("Net"):
                power_lines[entry] = True

    spice_commands = "\n \n"
    for power in power_lines:
        spice_commands += f"V_{power[1:]} {power} 0 DC {_convert_voltage_str(power[1:])}\n"
    spice_commands += (
        "\n \n"
        ".control \n"
        "tran 100u 10m \n"
        "set filetype=ascii \n"
        f"write ./outputs/spice_circuits/{cir_stem}_raw.raw all \n"
        ".endc \n\n"
    )

    content = first_line + "\n" + "".join(new_lines) + spice_commands + last_line
    return content.splitlines(keepends=True)


@dataclass
class CleanBoard:
    net_path: str
    cir_path: str
    cir_lines: List[str]


def _find_clean_board(board: str) -> Optional[CleanBoard]:
    nets = glob.glob(os.path.join(CLEAN_ROOT, board, "*.net"))
    cirs = glob.glob(os.path.join(CLEAN_ROOT, board, "*.cir"))
    if not nets or not cirs:
        return None
    with open(cirs[0]) as f:
        cir_lines = f.readlines()
    if board == _STACK_CHAN_BOARD:
        stem = os.path.splitext(os.path.basename(cirs[0]))[0]
        cir_lines = _complete_raw_kicad_cir(cir_lines, stem)
    return CleanBoard(net_path=nets[0], cir_path=cirs[0], cir_lines=cir_lines)


def _component_value(content: str, ref: str) -> Optional[str]:
    """Raw `value` field of one R/C/L-family component ref in a `.net` file."""
    for comp in tol.parse_passives(content):
        if comp.ref == ref:
            return comp.value
    return None


def _find_cir_line(cir_lines: List[str], ref: str) -> Optional[Tuple[int, str, str, str, str, Optional[str]]]:
    """(index, ref, node1, node2, value, rating) for `ref`'s R/C/L line, or None.

    Anchored on the ref token so "R1" never matches an "R10" line. Most boards'
    exports are exactly 4 tokens (ref, node1, node2, value); some (e.g.
    AcornRobotElectronics) still carry a 5th trailing voltage-rating token
    (``C18 +5V 0 4.7uF 25V``), which is captured separately and preserved
    verbatim rather than mistaken for part of the value.
    """
    pattern = re.compile(
        r"^(" + re.escape(ref) + r")\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(\S+))?\s*$")
    for i, line in enumerate(cir_lines):
        m = pattern.match(line.rstrip("\n"))
        if m:
            return i, m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    return None


def _shift_cir_value(cir_value: str, new_decade: str) -> Optional[str]:
    m = _CIR_VALUE_RE.match(cir_value)
    if not m:
        return None
    return (m.group("mantissa") + SPICE_PREFIX.get(new_decade, new_decade)
            + (m.group("unit") or ""))


@dataclass
class Result:
    category: str       # "Value" or "Tolerance"
    board: str
    ref: str
    infected_net: str
    out_cir: str
    status: str          # "changed" | "unchanged" | "skipped"
    detail: str


def _retarget_raw_output(lines: List[str], out_cir_path: str) -> List[str]:
    """Point this variant's `write ..._raw.raw all` at its own directory."""
    out_dir = os.path.dirname(out_cir_path)
    new_lines = []
    for line in lines:
        m = _WRITE_LINE_RE.match(line.rstrip("\n"))
        if m:
            raw_basename = os.path.basename(m.group(2))
            new_path = f"./{out_dir}/{raw_basename}"
            new_lines.append(f"{m.group(1)}{new_path}{m.group(3)}\n")
        else:
            new_lines.append(line)
    return new_lines


def _write(path: str, lines: List[str], dry_run: bool) -> None:
    lines = _retarget_raw_output(lines, path)
    if dry_run:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.writelines(lines)


def _process_one(category: str, board: str, ref: str, infected_net_path: str,
                  clean: CleanBoard, dry_run: bool) -> Result:
    out_cir = os.path.join(os.path.dirname(infected_net_path),
                            os.path.basename(clean.cir_path))

    if category == "Tolerance":
        _write(out_cir, clean.cir_lines, dry_run)
        return Result(category, board, ref, infected_net_path, out_cir,
                      "unchanged", "tolerance-only change; SPICE export has no "
                      "notion of tolerance, so simulated values == Clean template")

    # category == "Value"
    clean_content = nt.read(clean.net_path)
    infected_content = nt.read(infected_net_path)
    clean_value = _component_value(clean_content, ref)
    infected_value = _component_value(infected_content, ref)
    if clean_value is None or infected_value is None:
        return Result(category, board, ref, infected_net_path, out_cir,
                      "skipped",
                      f"couldn't read value ({clean_value!r} -> {infected_value!r})")

    clean_tok = val.parse_value_token(clean_value, 0)
    infected_tok = val.parse_value_token(infected_value, 0)
    if clean_tok is None or infected_tok is None:
        return Result(category, board, ref, infected_net_path, out_cir,
                      "skipped",
                      f"unparseable value token ({clean_value!r} -> {infected_value!r})")

    old_decade = _normalise(clean_tok.prefix)
    new_decade = _normalise(infected_tok.prefix)

    found = _find_cir_line(clean.cir_lines, ref)
    if found is None:
        _write(out_cir, clean.cir_lines, dry_run)
        return Result(category, board, ref, infected_net_path, out_cir,
                      "unchanged",
                      f"{ref} not present in Clean .cir (excluded from SPICE export)")

    idx, cir_ref, n1, n2, cir_value, rating = found

    if old_decade == new_decade:
        _write(out_cir, clean.cir_lines, dry_run)
        return Result(category, board, ref, infected_net_path, out_cir,
                      "unchanged", f"same SI decade ({clean_value!r} -> {infected_value!r})")

    new_cir_value = _shift_cir_value(cir_value, new_decade)
    if new_cir_value is None:
        return Result(category, board, ref, infected_net_path, out_cir,
                      "skipped", f"couldn't parse Clean .cir value {cir_value!r}")

    new_lines = list(clean.cir_lines)
    rating_suffix = f" {rating}" if rating else ""
    new_lines[idx] = f"{cir_ref} {n1} {n2} {new_cir_value}{rating_suffix}\n"
    _write(out_cir, new_lines, dry_run)

    return Result(category, board, ref, infected_net_path, out_cir, "changed",
                  f"{cir_ref} {n1} {n2} {cir_value}{rating_suffix} -> "
                  f"{new_cir_value}{rating_suffix}")


def run(root: str = DEFAULT_ROOT, dry_run: bool = False) -> List[Result]:
    results: List[Result] = []
    board_cache: Dict[str, Optional[CleanBoard]] = {}

    for category in ("Value", "Tolerance"):
        cat_root = os.path.join(root, category)
        if not os.path.isdir(cat_root):
            continue
        for board in sorted(os.listdir(cat_root)):
            board_dir = os.path.join(cat_root, board)
            if not os.path.isdir(board_dir):
                continue
            if board not in board_cache:
                board_cache[board] = _find_clean_board(board)
            clean = board_cache[board]
            if clean is None:
                print(f"SKIP board {board!r}: no Clean .net/.cir found")
                continue
            for ref in sorted(os.listdir(board_dir)):
                ref_dir = os.path.join(board_dir, ref)
                nets = glob.glob(os.path.join(ref_dir, "*.net"))
                if not nets:
                    continue
                res = _process_one(category, board, ref, nets[0], clean, dry_run)
                results.append(res)
                print(f"{res.status:9} {category:10} {board:24} {ref:8} {res.detail}")

    return results


# --- Raw kicad-cli exports (e.g. GndShortRef) --------------------------------
#
# Modifications that edit the *schematic* (GndShortRef) get a real infected
# `.cir` straight from `kicad-cli`, so there is no Clean template to patch --
# the raw export only needs finishing into a runnable deck. `--raw-exports`
# does that in place, keeping the untouched export beside it as
# `<stem>.kicad_cir` (not globbed by run_spice, and re-used as the source on
# re-runs so the step is idempotent).
#
# Same transform as `_complete_raw_kicad_cir` / pcb_qa's
# `convert_project_spice_to_circuit`, with these differences:
#   - only the `.title` and `.end` lines are peeled off (both of those slice
#     `[1:-2]`, which silently drops the last component when the export has
#     no trailing blank line -- true of every GndShortRef export);
#   - `LEDn` lines become `DLEDn` with a generated LED diode model, and any
#     other diode whose model isn't defined (KiCad's bare `LED`) gets one too;
#   - R/C/L lines are cut to `ref n1 n2 value`, and dropped if the value isn't
#     numeric (e.g. PortalHardware's `??`), since ngspice aborts on them --
#     likewise V/I source symbols with a part name for a value (OPNhydro's
#     `V1 ... DC DIGITEN-24V`; the rail sources below drive those nets);
#   - rail voltages parse every KiCad spelling (`+3V3`, `+3.3V`, `+24VF`);
#   - the matching Clean board's `.cir` supplies its `tran` line and any
#     source whose node is still present (e.g. PortalHardware's `VCC`), so
#     infected and Clean simulations stay comparable.
RAW_EXPORT_SUFFIX = ".kicad_cir"
_DEFAULT_TRAN = "tran 100u 10m"
_LED_MODEL = "D (Is=1p Rs=10 N=1.7)"
_RAIL_VOLTAGE_RE = re.compile(r"^\+(\d+)(?:V(\d+)|(\.\d+)V|V)?")
_NUMERIC_VALUE_RE = re.compile(
    r"^\d+\.?\d*(?:e[+-]?\d+)?(?:meg|[tgkmunpf])?[a-z]*$", re.IGNORECASE)
_SOURCE_LINE_RE = re.compile(r"^V\S*\s+(\S+)\s+0\s+DC\s+\S+", re.IGNORECASE)


@dataclass
class RawResult:
    cir: str
    clean_template: Optional[str]
    sources: List[str]
    dropped: List[str]


def _rail_voltage(rail: str) -> Optional[float]:
    m = _RAIL_VOLTAGE_RE.match(rail)
    if not m:
        return None
    whole, frac_v, frac_dot = m.groups()
    return float(whole + "." + frac_v) if frac_v else float(whole + (frac_dot or ""))


def _clean_template_for(board_dir: str) -> Optional[str]:
    """Clean `.cir` whose board dir matches `board_dir`, ignoring case/punctuation."""
    key = re.sub(r"[^a-z0-9]", "", os.path.basename(board_dir).lower())
    for d in sorted(os.listdir(CLEAN_ROOT)):
        if re.sub(r"[^a-z0-9]", "", d.lower()) == key:
            cirs = glob.glob(os.path.join(CLEAN_ROOT, d, "*.cir"))
            return cirs[0] if cirs else None
    return None


def _complete_raw_export(raw_lines: List[str], out_cir: str,
                         clean_cir: Optional[str]) -> Tuple[List[str], RawResult]:
    lines = [_RATING_STRIP_RE.sub("", ln).rstrip("\n") for ln in raw_lines]
    title = lines[0]
    body = [ln for ln in lines[1:] if ln.strip() and ln.strip().lower() != ".end"]

    models: List[str] = []
    defined: set = set()
    comps: List[str] = []
    dropped: List[str] = []
    for line in body:
        tokens = line.split()
        if tokens[0].lower() == ".model":
            defined.add(tokens[1])
            models.append(line)
            continue
        if len(tokens) == 2:
            continue  # unmodeled component (connector/transistor/IC/switch)
        tokens = [_GND_RE.sub("0", t) for t in tokens]
        ref = tokens[0]
        if ref.upper().startswith("LED"):
            tokens[0] = "D" + ref
            tokens[-1] = f"LED_D_{tokens[-1]}"
        if tokens[0][0].upper() in "RCL":
            # Some exports trail rating/tolerance/dielectric tokens
            # (`C5 +5V 0 1000uF 10v solid`); ngspice wants just the value.
            tokens = tokens[:4]
            if not _NUMERIC_VALUE_RE.match(tokens[3]):
                dropped.append(line)
                continue
        elif tokens[0][0].upper() in "VI" and not _NUMERIC_VALUE_RE.match(tokens[-1]):
            dropped.append(line)  # schematic source symbol, e.g. `DC DIGITEN-24V`
            continue
        if tokens[0][0].upper() == "D" and tokens[-1] not in defined:
            defined.add(tokens[-1])
            models.append(f".model {tokens[-1]} {_LED_MODEL}")
        comps.append(" ".join(tokens))

    nodes = {t for c in comps for t in c.split()[1:-1]}
    sources: Dict[str, float] = {}
    for node in sorted(nodes):
        if node.startswith("+"):
            v = _rail_voltage(node)
            if v is not None:
                sources[node] = v

    tran = _DEFAULT_TRAN
    if clean_cir:
        with open(clean_cir) as f:
            for ln in f:
                m = _SOURCE_LINE_RE.match(ln.strip())
                if m and m.group(1) in nodes:
                    sources[m.group(1)] = float(ln.split()[-1])
                elif ln.strip().lower().startswith("tran "):
                    tran = ln.strip()

    source_lines = [f"V_{re.sub(r'[^A-Za-z0-9]', '_', n.lstrip('+'))} {n} 0 DC {v}"
                    for n, v in sources.items()]
    raw_out = f"./{os.path.splitext(out_cir)[0]}_raw.raw"
    content = "\n".join(
        [title, ""] + models + [""] + comps + ["", ""] + source_lines
        + ["", "", ".control", tran, "set filetype=ascii",
           f"write {raw_out} all", ".endc", "", ".end"]) + "\n"
    return (content.splitlines(keepends=True),
            RawResult(out_cir, clean_cir, source_lines, dropped))


def run_raw_exports(root: str, dry_run: bool = False) -> List[RawResult]:
    """Finish every raw kicad-cli `.cir` export under `root` in place."""
    results: List[RawResult] = []
    for cir in sorted(glob.glob(os.path.join(root, "**", "*.cir"), recursive=True)):
        backup = os.path.splitext(cir)[0] + RAW_EXPORT_SUFFIX
        src = backup if os.path.exists(backup) else cir
        with open(src) as f:
            raw_lines = f.readlines()
        if src == cir and any(ln.startswith(".control") for ln in raw_lines):
            print(f"skip      {cir} (already a finished deck, no raw export kept)")
            continue
        lines, res = _complete_raw_export(
            raw_lines, cir, _clean_template_for(os.path.dirname(cir)))
        if not dry_run:
            if src == cir:
                with open(backup, "w") as f:
                    f.writelines(raw_lines)
            with open(cir, "w") as f:
                f.writelines(lines)
        results.append(res)
        print(f"completed {cir}  sources={len(res.sources)} dropped={len(res.dropped)}"
              f"  template={res.clean_template}")
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="netlist_modifications.conversions.convert_spice",
        description="Generate infected SPICE .cir circuits for ComponentSubstitution netlists.")
    p.add_argument("--root", default=DEFAULT_ROOT,
                   help=f"ComponentSubstitution tree to scan (default: {DEFAULT_ROOT})")
    p.add_argument("--dry-run", action="store_true", help="Report only, write nothing")
    p.add_argument("--raw-exports", action="store_true",
                   help="Finish raw kicad-cli .cir exports under --root in place "
                        "(e.g. outputs/Infected/GndShortRef)")
    args = p.parse_args(argv)

    if args.raw_exports:
        raw_results = run_raw_exports(args.root, dry_run=args.dry_run)
        print(f"\n{len(raw_results)} raw export(s) completed")
        if not args.dry_run:
            manifest_path = os.path.join(args.root, "spice_manifest.json")
            with open(manifest_path, "w") as f:
                json.dump([asdict(r) for r in raw_results], f, indent=2)
            print(f"Manifest: {manifest_path}")
        return 0

    results = run(args.root, dry_run=args.dry_run)
    changed = sum(1 for r in results if r.status == "changed")
    unchanged = sum(1 for r in results if r.status == "unchanged")
    skipped = sum(1 for r in results if r.status == "skipped")
    print(f"\n{len(results)} infected .net file(s) processed: "
          f"{changed} changed, {unchanged} unchanged, {skipped} skipped")

    if not args.dry_run:
        manifest_path = os.path.join(args.root, "spice_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        print(f"Manifest: {manifest_path}")

    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
