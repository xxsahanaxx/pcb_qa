#!/usr/bin/env python3
"""Schematic-level "GND short" Trojan: tie an existing labelled net to GND.

Unlike the other Trojans (which edit an exported ``.net``), this one edits the
KiCad *schematic* (``.kicad_sch``) and lets ``kicad-cli`` re-export the netlist,
so the Trojan exists in the design source and every downstream artefact
(netlist, SPICE, ERC) is derived from it. The ``.kicad_pro`` is only copied
alongside -- it holds settings, not connectivity.

The insertion adds three items to the sheet that carries the target label, in
free space just right of everything already drawn (so nothing else is touched
by accident):

    <label "NET">  --wire--  <GND power symbol>

The label is a clone of the existing one (same kind: local / global /
hierarchical), so it joins the target net by name; the GND symbol is a clone
of one already on that sheet (so its lib_id, instance paths and project name
are right for this design). Every other byte of the file is left alone, so a
clean-vs-infected diff of the ``.kicad_sch`` shows only the Trojan.

Ground truth is never assumed: both the clean and the infected schematics are
exported with the same kicad-cli, and the manifest records which component
pins actually moved onto GND.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import core as nt
from .snip import sanitise

CLEAN_GLOB = "outputs/Clean/*/*.net"
SCHEMATIC_ROOT = "OSHP_files/Clean"
DEFAULT_KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"

GRID = 1.27          # KiCad's default connection grid (mm)
MARGIN = 15.24       # gap between the existing drawing and the inserted items
WIRE_LEN = 7.62      # label -> GND wire length

LABEL_KINDS = ("label", "global_label", "hierarchical_label")


# --------------------------------------------------------------------------- #
# kicad-cli
# --------------------------------------------------------------------------- #

def kicad_cli() -> str:
    """Path to kicad-cli: $KICAD_CLI_PATH, then PATH, then the macOS default."""
    for cand in (os.environ.get("KICAD_CLI_PATH"), shutil.which("kicad-cli"),
                 DEFAULT_KICAD_CLI):
        if cand and os.path.exists(cand):
            return cand
    raise FileNotFoundError("kicad-cli not found; set KICAD_CLI_PATH")


def export_netlist(sch_path: str, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    subprocess.run([kicad_cli(), "sch", "export", "netlist", "--format", "kicadsexpr",
                    sch_path, "--output", out_path],
                   check=True, capture_output=True, text=True)


def run_erc(sch_path: str, out_path: str) -> Dict[str, int]:
    """Run ERC and return {severity: count}. kicad-cli exits non-zero on violations."""
    subprocess.run([kicad_cli(), "sch", "erc", "--format", "json", "--severity-all",
                    sch_path, "--output", out_path],
                   check=False, capture_output=True, text=True)
    with open(out_path) as f:
        report = json.load(f)
    counts: Dict[str, int] = {}
    for sheet in report.get("sheets", []):
        for v in sheet.get("violations", []):
            counts[v["severity"]] = counts.get(v["severity"], 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# Schematic text helpers (string-level, like core.apply_spec)
# --------------------------------------------------------------------------- #

_TOP_RE = re.compile(r"^\t\((\w+)", re.M)
_UUID_RE = re.compile(r'\(uuid "[^"]*"\)')
_AT_RE = re.compile(r"\((at|xy|start|end) (-?[\d.]+) (-?[\d.]+)")
_PROP_RE = r'\(property "{}" "([^"]*)"'


def top_level_blocks(text: str) -> List[Tuple[str, int, int]]:
    """(kind, start, end) of every depth-1 item, e.g. ('label', 1234, 1500).

    Relies on KiCad's own formatting (one tab before each top-level item),
    which every eeschema-saved .kicad_sch has.
    """
    out = []
    for m in _TOP_RE.finditer(text):
        start = m.start() + 1
        out.append((m.group(1), start, nt.find_matching_paren(text, start) + 1))
    return out


def _prop(block: str, name: str) -> Optional[str]:
    m = re.search(_PROP_RE.format(name), block)
    return m.group(1) if m else None


def _fmt(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".")


def _snap(v: float) -> float:
    return round(round(v / GRID) * GRID, 4)


def _shift(block: str, dx: float, dy: float) -> str:
    """Translate every coordinate in `block` by (dx, dy)."""
    return _AT_RE.sub(lambda m: f"({m.group(1)} {_fmt(float(m.group(2)) + dx)} "
                                f"{_fmt(float(m.group(3)) + dy)}", block)


def _fresh_uuids(block: str) -> str:
    return _UUID_RE.sub(lambda _: f'(uuid "{uuid.uuid4()}")', block)


def _anchor(block: str) -> Tuple[float, float]:
    m = re.search(r"\(at (-?[\d.]+) (-?[\d.]+)", block)
    return float(m.group(1)), float(m.group(2))


def drawing_bbox(text: str) -> Tuple[float, float, float, float]:
    """Bounding box of the drawn content (lib_symbols' local coords excluded)."""
    xs, ys = [], []
    for kind, s, e in top_level_blocks(text):
        if kind == "lib_symbols":
            continue
        for m in _AT_RE.finditer(text, s, e):
            xs.append(float(m.group(2)))
            ys.append(float(m.group(3)))
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def _is_gnd(block: str) -> bool:
    return (_prop(block, "Value") == "GND"
            and (_prop(block, "Reference") or "").startswith("#"))


def _is_bus(name: str) -> bool:
    return bool(re.search(r"\[.*\.\..*\]", name)) or "{" in name


# --------------------------------------------------------------------------- #
# Project discovery: sheets and label candidates
# --------------------------------------------------------------------------- #

@dataclass
class Sheet:
    file: str        # path relative to the project dir
    path_name: str   # KiCad sheet path as used in net names: "/" or "/Power/"


@dataclass
class Candidate:
    sheet: Sheet
    kind: str        # label | global_label | hierarchical_label
    name: str        # label text
    net: str         # predicted net name (for display/dedupe; truth comes from export)


def resolve_root(path: str) -> str:
    """Accept a .kicad_sch or a .kicad_pro and return the root .kicad_sch."""
    if path.endswith(".kicad_pro"):
        path = path[: -len(".kicad_pro")] + ".kicad_sch"
    if not path.endswith(".kicad_sch") or not os.path.isfile(path):
        raise ValueError(f"No KiCad 6+ root schematic at {path!r} "
                         "(legacy .sch/.pro projects must be re-saved in KiCad first)")
    return path


def walk_sheets(root_sch: str) -> List[Sheet]:
    """Every sheet file reachable from the root, in hierarchy order (deduped)."""
    proj_dir = os.path.dirname(root_sch)
    sheets: List[Sheet] = []
    seen = set()

    def visit(rel: str, path_name: str) -> None:
        if rel in seen:
            return
        seen.add(rel)
        sheets.append(Sheet(rel, path_name))
        text = nt.read(os.path.join(proj_dir, rel))
        for kind, s, e in top_level_blocks(text):
            if kind != "sheet":
                continue
            block = text[s:e]
            name, file = _prop(block, "Sheetname"), _prop(block, "Sheetfile")
            if file:
                child = os.path.normpath(os.path.join(os.path.dirname(rel), file))
                visit(child, f"{path_name}{name}/")

    visit(os.path.basename(root_sch), "/")
    return sheets


def find_candidates(root_sch: str, signal: Optional[str] = None) -> List[Candidate]:
    """One candidate per distinct labelled net (optionally filtered by keyword)."""
    proj_dir = os.path.dirname(root_sch)
    out: List[Candidate] = []
    seen = set()
    for sheet in walk_sheets(root_sch):
        text = nt.read(os.path.join(proj_dir, sheet.file))
        if not any(_is_gnd(text[s:e]) for k, s, e in top_level_blocks(text) if k == "symbol"):
            continue  # nothing on this sheet to clone a GND symbol from
        for kind, s, e in top_level_blocks(text):
            if kind not in LABEL_KINDS:
                continue
            name = re.match(r'\(\w+ "([^"]*)"', text[s:e]).group(1)
            if _is_bus(name) or name.upper() == "GND":
                continue
            if signal and signal.upper() not in name.upper():
                continue
            net = name if kind == "global_label" else f"{sheet.path_name}{name}"
            if net in seen:
                continue
            seen.add(net)
            out.append(Candidate(sheet, kind, name, net))
    return out


# --------------------------------------------------------------------------- #
# The insertion
# --------------------------------------------------------------------------- #

def _used_pwr_refs(proj_dir: str, sheets: List[Sheet]) -> set:
    refs = set()
    for sh in sheets:
        refs |= set(re.findall(r'"(#PWR\w*)"', nt.read(os.path.join(proj_dir, sh.file))))
    return refs


def _next_ref(used: set) -> str:
    n = 9001
    while f"#PWR{n}" in used:
        n += 1
    used.add(f"#PWR{n}")
    return f"#PWR{n}"


def insert_gnd_short(text: str, cand: Candidate, used_refs: set) -> Tuple[str, Dict]:
    """Return (infected sheet text, info) with label->wire->GND appended."""
    blocks = top_level_blocks(text)
    label_src = next(text[s:e] for k, s, e in blocks
                     if k == cand.kind and text[s:e].startswith(f'({k} "{cand.name}"'))
    gnd_src = next(text[s:e] for k, s, e in blocks if k == "symbol" and _is_gnd(text[s:e]))

    _, min_y, max_x, _ = drawing_bbox(text)
    x, y = _snap(max_x + MARGIN), _snap(min_y + MARGIN)
    gy = _snap(y + WIRE_LEN)

    lx, ly = _anchor(label_src)
    label = _fresh_uuids(_shift(label_src, x - lx, y - ly))

    wire = (f"(wire\n\t\t(pts\n\t\t\t(xy {_fmt(x)} {_fmt(y)}) (xy {_fmt(x)} {_fmt(gy)})\n\t\t)\n"
            f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f"\t\t(uuid \"{uuid.uuid4()}\")\n\t)")

    gx0, gy0 = _anchor(gnd_src)
    gnd = _fresh_uuids(_shift(gnd_src, x - gx0, gy - gy0))
    # one fresh #PWR ref per instance path (a multi-instance sheet has several)
    refs = []

    def _ref(m):
        refs.append(_next_ref(used_refs))
        return f'(reference "{refs[-1]}")'
    gnd = re.sub(r'\(reference "[^"]*"\)', _ref, gnd)
    if refs:
        gnd = re.sub(r'(\(property "Reference" )"[^"]*"', rf'\1"{refs[0]}"', gnd, count=1)

    insertion = "".join(f"\t{b}\n" for b in (label, wire, gnd))
    anchor = text.find("\n\t(sheet_instances")
    if anchor < 0:
        anchor = text.rstrip().rfind(")") - 1
    infected = text[: anchor + 1] + insertion + text[anchor + 1:]
    info = {"label_at": [x, y], "gnd_at": [x, gy], "gnd_refs": refs}
    return infected, info


def copy_project(root_sch: str, sheets: List[Sheet], dest: str) -> str:
    """Copy only what kicad-cli needs (project file, sheets, lib tables)."""
    proj_dir = os.path.dirname(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]
    files = [sh.file for sh in sheets] + [f"{stem}.kicad_pro", "sym-lib-table", "fp-lib-table"]
    for rel in files:
        src = os.path.join(proj_dir, rel)
        if os.path.isfile(src):
            dst = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    return os.path.join(dest, os.path.basename(root_sch))


# --------------------------------------------------------------------------- #
# Ground truth: what actually moved onto GND
# --------------------------------------------------------------------------- #

def diff_against_gnd(clean_net: str, infected_net: str) -> Dict:
    clean = nt.parse_nets(nt.read(clean_net))
    infected = nt.parse_nets(nt.read(infected_net))
    gnd = next((n for n in clean if n.name == "GND"), None)
    if gnd is None:
        raise ValueError(f"No net named GND in {clean_net}")
    merged = max((n for n in infected if gnd.node_set() <= n.node_set()),
                 key=lambda n: len(n.nodes))
    moved = merged.node_set() - gnd.node_set()
    victims = [n for n in clean if n.node_set() and n.node_set() <= moved]
    return {
        "merged_net": merged.name,
        "victim_nets": [n.name for n in victims],
        "moved_nodes": sorted(f"{r}.{p}" for r, p in moved),
    }


# --------------------------------------------------------------------------- #
# Single + batch runners
# --------------------------------------------------------------------------- #

def build_variant(root_sch: str, cand: Candidate, out_dir: str,
                  clean_net: str, erc: bool = False) -> Dict:
    """Write one infected project copy + its exported netlist into `out_dir`."""
    sheets = walk_sheets(root_sch)
    proj_dir = os.path.dirname(root_sch)
    stem = os.path.splitext(os.path.basename(root_sch))[0]

    kicad_dir = os.path.join(out_dir, "kicad")
    if os.path.isdir(kicad_dir):
        shutil.rmtree(kicad_dir)
    new_root = copy_project(root_sch, sheets, kicad_dir)

    target = os.path.join(kicad_dir, cand.sheet.file)
    infected, info = insert_gnd_short(nt.read(target), cand,
                                      _used_pwr_refs(proj_dir, sheets))
    nt.write(target, infected)

    out_net = os.path.join(out_dir, f"{stem}.net")
    export_netlist(new_root, out_net)
    record = {
        "label": cand.name, "label_kind": cand.kind, "sheet": cand.sheet.file,
        "predicted_net": cand.net, "schematic": target, "output": out_net,
        **info, **diff_against_gnd(clean_net, out_net),
    }
    if erc:
        record["erc_infected"] = run_erc(new_root, os.path.join(out_dir, "erc.json"))
    return record


def _schematic_for(clean_net_path: str) -> Optional[str]:
    """Map a clean .net's (source ...) header onto OSHP_files/Clean/..."""
    m = re.search(r'\(source "[^"]*?OSHP_files/([^"]+)"\)', nt.read(clean_net_path))
    if not m:
        return None
    sch = os.path.join(SCHEMATIC_ROOT, m.group(1))
    return sch if os.path.isfile(sch) else None


def run_batch(signal: str, clean_glob: str = CLEAN_GLOB, out_root: str = None,
              erc: bool = False) -> int:
    """GND-short every labelled `signal` net in every resolvable clean design."""
    signal = signal.upper()
    out_root = out_root or f"outputs/Infected/GndShort/{signal}"
    manifest = []

    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        sch = _schematic_for(path)
        if not sch:
            print(f"{board:24} skipped: no KiCad 6+ schematic found for {path}",
                  file=sys.stderr)
            continue
        cands = find_candidates(sch, signal)
        if not cands:
            continue

        # re-export the clean design with the same kicad-cli for a fair diff
        clean_dir = os.path.join(out_root, board, "_clean")
        clean_net = os.path.join(clean_dir, os.path.basename(path))
        export_netlist(sch, clean_net)
        erc_clean = run_erc(sch, os.path.join(clean_dir, "erc.json")) if erc else None

        used_dirs, seen_moves = set(), set()
        for cand in cands:
            # sanitising can collide: local "/SDA6" vs global "SDA6", "TX+" vs "TX-"
            base = folder = sanitise(cand.net)
            n = 1
            while folder in used_dirs:
                n += 1
                folder = f"{base}_{n}"
            used_dirs.add(folder)
            out_dir = os.path.join(out_root, board, folder)
            rec = build_variant(sch, cand, out_dir, clean_net, erc=erc)
            moved = frozenset(rec["moved_nodes"])
            if not moved or moved in seen_moves:
                shutil.rmtree(out_dir)
                why = "no pins moved" if not moved else "same net as an earlier label"
                print(f"{board:24} {cand.net:20} skipped: {why}")
                continue
            seen_moves.add(moved)
            rec.update({"board": board, "clean": path, "clean_reexport": clean_net})
            if erc_clean is not None:
                rec["erc_clean"] = erc_clean
            manifest.append(rec)
            print(f"{board:24} {cand.net:20} -> {rec['output']} "
                  f"({len(rec['moved_nodes'])} pin(s) onto {rec['merged_net']})")

    os.makedirs(out_root, exist_ok=True)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} infected design(s) written. Manifest: {manifest_path}")
    return 0


def run_single(input_path: str, label: str = None, sheet: str = None,
               output: str = None, list_only: bool = False, erc: bool = False) -> int:
    """GND-short one labelled net in one project (.kicad_sch or .kicad_pro)."""
    root = resolve_root(input_path)
    cands = find_candidates(root)
    if sheet:
        cands = [c for c in cands if c.sheet.file == sheet]
    if not cands:
        print(f"No labelled nets (on sheets with a GND symbol) in {root}", file=sys.stderr)
        return 1

    if list_only:
        print(f"Labelled nets in {root}:")
        for c in cands:
            print(f"  {c.name:20} {c.kind:18} sheet={c.sheet.file}  net~{c.net}")
        return 0

    if label:
        matches = [c for c in cands if c.name == label]
        if not matches:
            print(f"error: no label {label!r}. Use --list to see candidates.",
                  file=sys.stderr)
            return 1
        cand = matches[0]
    else:
        cand = cands[0]
        print(f"note: no --label given; shorting the first ({cand.name!r}).",
              file=sys.stderr)

    stem = os.path.splitext(os.path.basename(root))[0]
    out_dir = output or os.path.join("outputs/Infected/GndShort", stem, sanitise(cand.net))
    with tempfile.TemporaryDirectory() as tmp:
        clean_net = os.path.join(tmp, f"{stem}.net")
        export_netlist(root, clean_net)
        rec = build_variant(root, cand, out_dir, clean_net, erc=erc)
        if erc:
            rec["erc_clean"] = run_erc(root, os.path.join(tmp, "erc.json"))

    print(f"Shorted {cand.name!r} ({cand.kind}, {cand.sheet.file}) to GND")
    print(f"  victim net(s): {', '.join(rec['victim_nets']) or '-'}")
    print(f"  pins now on {rec['merged_net']}: {', '.join(rec['moved_nodes']) or '-'}")
    if erc:
        print(f"  ERC clean={rec['erc_clean']} infected={rec['erc_infected']}")
    print(f"Wrote {rec['schematic']}\n      {rec['output']}")
    with open(os.path.join(out_dir, "gnd_short.json"), "w") as f:
        json.dump(rec, f, indent=2)
    return 0 if rec["moved_nodes"] else 1
