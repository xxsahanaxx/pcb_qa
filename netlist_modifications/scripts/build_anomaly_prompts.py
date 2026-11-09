#!/usr/bin/env python3
"""
Build anomaly-detection prompts: one per faulty board version under
outputs/Infected/Scenarios/, plus one clean control per board.

Each prompt is the template in docs/anomaly_detection_prompt.md with the
project name and design spec (docs/design_specs/) filled in, and the
{{NETLIST}} / {{SPICE_CIRCUIT}} placeholders left for the caller. Layout: one
folder per project, one subfolder per anomaly (or the clean control):

    <out>/<Board>/<Scenario>_<Variant>/   prompt.md  netlist.net  spice.cir
    <out>/<Board>/Control/                prompt.md  netlist.net  spice.cir

netlist.net / spice.cir are the build's design files, scrubbed of metadata
that would reveal the answer (the netlist's temp-dir `source` header and
library uris, the SPICE deck's scenario `write` path, export dates) the same
way in faulty and clean files; render() substitutes them. prompts.jsonl
indexes prompt -> files; ground truth goes to a separate answer_key.jsonl,
never into a prompt or its files.

Run from the repo root:
    .venv/bin/python netlist_modifications/scripts/build_anomaly_prompts.py
        [--scenarios A,B] [--boards X,Y] [--no-controls] [--out DIR]
"""

import argparse
import glob
import json
import os
import re
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

from netlist_modifications.conversions import convert_spice as cs  # noqa: E402
from netlist_modifications.insert_modification import gnd_short_random as gsx  # noqa: E402
from netlist_modifications.insert_modification import gnd_short_ref as gsr  # noqa: E402

TEMPLATE_DOC = "docs/anomaly_detection_prompt.md"
SPEC_DIR = "docs/design_specs"
SCENARIOS_ROOT = "outputs/Infected/Scenarios"
DEFAULT_OUT = "outputs/Infected/Prompts/AnomalyDetection"
# design-file kind -> the template placeholder its contents fill, and its file name
PLACEHOLDERS = {"net": "{{NETLIST}}", "cir": "{{SPICE_CIRCUIT}}"}
FILE_NAMES = {"net": "netlist.net", "cir": "spice.cir"}
PROMPT_FILE = "prompt.md"
CONTROL_DIR = "Control"

SPEC_FOR_BOARD = {
    "AcornRobotElectronics": "acorn-robot-electronics.md",
    "CF-Chef": "CF-Chef.md",
    "HadesFCS": "HadesFCS.md",
    "Meshinger": "Meshinger.md",
    "OPNhydro-r2": "OPNhydro.md",
    "PortalHardware": "portal-hardware.md",
    "fan_controller": "MyKiCad.md",  # monorepo overview; no fan_controller-specific spec
    "stack-chan": "stack-chan.md",
}

CATEGORY_FOR_SCENARIO = {
    "GndShortRandom": "short_to_ground",
    "VccShortRandom": "short_to_supply",
    "BridgeRandom": "bridged_nets",
    "ResistorToCapacitorRandom": "wrong_component_type",
    "CapacitorToResistorRandom": "wrong_component_type",
    "ResistorMagnitudeUpRandom": "wrong_value",
    "ResistorMagnitudeDownRandom": "wrong_value",
    "CapacitorMagnitudeUpRandom": "wrong_value",
    "CapacitorMagnitudeDownRandom": "wrong_value",
    "ResistorToleranceUpRandom": "wrong_tolerance",
    "CapacitorToleranceUpRandom": "wrong_tolerance",
    "ResistorToleranceDownRandom": "wrong_tolerance",
    "CapacitorToleranceDownRandom": "wrong_tolerance",
    "PolarityFlipRandom": "polarity",
}

# Substrings that would tell a model where a file came from. Checked on every
# filled prompt; a hit aborts the build rather than writing a leaky prompt.
LEAK_MARKERS = ["/var/folders", "Infected", "Scenarios", "OSHP_files", "outputs/",
                "_clean", *CATEGORY_FOR_SCENARIO]


def load_template() -> str:
    with open(os.path.join(REPO_ROOT, TEMPLATE_DOC)) as f:
        doc = f.read()
    m = re.search(r"<!-- TEMPLATE START -->\n(.*?)<!-- TEMPLATE END -->", doc, re.S)
    if not m:
        raise ValueError(f"no TEMPLATE START/END markers in {TEMPLATE_DOC}")
    return m.group(1)


# --------------------------------------------------------------------------- #
# Sanitising: same normalisation for faulty and clean files
# --------------------------------------------------------------------------- #

def sanitise(kind: str, text: str, stem: str) -> str:
    if kind == "net":
        # library uris are absolute under the exporting project's folder (a temp
        # dir named after the pick, for faulty builds); make them project-relative
        m = re.search(r'^\s*\(source "([^"]*)"\)', text, flags=re.M)
        if m:
            proj_dir = os.path.dirname(m.group(1))
            text = text.replace(f'"{proj_dir}/', '"${KIPRJMOD}/')
        # only the design header's source/date carry values; per-sheet ones are bare
        text = re.sub(r'^(\s*)\(source "[^"]*"\)', rf'\1(source "{stem}.kicad_sch")',
                      text, count=1, flags=re.M)
        text = re.sub(r'\(date "[^"]*"\)', '(date "")', text, count=1)
    elif kind == "cir":
        text = re.sub(r"^write \S+ all$", f"write {stem}_raw.raw all", text, flags=re.M)
    return text


def write_prompt(out_dir: str, template: str, board: str, spec: str, files: dict) -> dict:
    """Write prompt.md (spec filled, design-file placeholders open) and the
    scrubbed design files into `out_dir`; return their paths for prompts.jsonl."""
    for kind, (_, text) in files.items():
        leaks = [m for m in LEAK_MARKERS if m in text]
        if leaks:
            raise RuntimeError(f"{board}: {kind} still contains {leaks}; refusing to write")
    os.makedirs(out_dir, exist_ok=True)
    out_md = os.path.join(out_dir, PROMPT_FILE)
    with open(out_md, "w") as f:
        f.write(template.replace("{{PROJECT_NAME}}", board)
                .replace("{{DESIGN_SPEC}}", spec.strip()))
    paths = {}
    for kind, (_, text) in files.items():
        path = os.path.join(out_dir, FILE_NAMES[kind])
        with open(path, "w") as f:
            f.write(text)
        paths[kind] = path
    return {"prompt": out_md, "netlist": paths.get("net"), "spice_circuit": paths.get("cir")}


def render(prompt_path: str) -> str:
    """The prompt at `prompt_path` (prompt.md, or its folder) with the folder's
    netlist.net / spice.cir substituted in."""
    if os.path.isdir(prompt_path):
        prompt_path = os.path.join(prompt_path, PROMPT_FILE)
    with open(prompt_path) as f:
        text = f.read()
    for kind, placeholder in PLACEHOLDERS.items():
        with open(os.path.join(os.path.dirname(prompt_path), FILE_NAMES[kind])) as f:
            text = text.replace(placeholder, f.read().rstrip())
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left:
        raise ValueError(f"{prompt_path}: unfilled placeholder(s) {left}")
    return text


def read_files(directory: str, stem: str, kinds: list) -> dict:
    files = {}
    for kind in kinds:
        path = os.path.join(directory, f"{stem}.{kind}")
        if os.path.isfile(path):
            with open(path) as f:
                files[kind] = (f"{stem}.{kind}", sanitise(kind, f.read(), stem))
    return files


# --------------------------------------------------------------------------- #
# Ground truth per scenario record
# --------------------------------------------------------------------------- #

def truth(scenario: str, rec: dict) -> dict:
    """Refs/pins/nets the injected fault touched, from the scenario's record."""
    # net_components: every part on the net(s) a short/bridge pulled together.
    # The pin a short was placed on is arbitrary; naming any part on that net
    # (e.g. the IC pin it disables) is a correct localisation.
    refs = lambda nodes: sorted({n.split(".", 1)[0] for n in nodes})
    if scenario in ("GndShortRandom", "VccShortRandom"):
        comps, pins = [rec["ref"]], [f"{rec['ref']}.{rec['ref_pin']}"]
        nets = [rec["net"]] + ([rec["rail"]] if rec.get("rail") else ["GND"])
        net_comps = refs(rec["net_nodes"])
    elif scenario == "BridgeRandom":
        comps = [rec["ref_a"], rec["ref_b"]]
        pins = [f"{rec['ref_a']}.{rec['pin_a']}", f"{rec['ref_b']}.{rec['pin_b']}"]
        nets = [rec["net_a"], rec["net_b"], rec.get("merged_net")]
        net_comps = refs(rec["merged_nodes"])
    elif scenario in ("ResistorToCapacitorRandom", "CapacitorToResistorRandom"):
        comps, pins = [rec["ref"], rec["new_ref"]], []
        nets = sorted(set(rec["clean_pin_nets"].values()) | set(rec["pin_nets"].values()))
        net_comps = comps
    else:  # magnitude / tolerance
        comps, pins = [rec["ref"]], []
        nets = sorted(set(rec["pin_nets"].values()))
        net_comps = comps
    keep = {k: rec[k] for k in ("old_value", "new_value", "baseline_tolerance",
                                "substituted_tolerance", "template_ref") if k in rec}
    nets = list(dict.fromkeys(n for n in nets if n))  # a bridge's merged net repeats one side
    return {"components": comps, "pins": pins, "nets": nets,
            "net_components": net_comps, **keep}


# --------------------------------------------------------------------------- #
# Clean controls: netlist/JSON from a variant's _clean re-export, SPICE deck
# built with the same kicad-cli + raw-export finishing as the scenarios
# --------------------------------------------------------------------------- #

def build_control(board: str, sample_dirs: list, stem: str, clean_net: str,
                  kinds: list) -> dict:
    # every variant's _clean/ holds the same re-export; OneDrive can leave some
    # copies online-only ("dataless"), whose reads time out, so try the next
    for sample_dir in sample_dirs:
        try:
            files = read_files(os.path.join(sample_dir, "_clean"), stem,
                               [k for k in kinds if k != "cir"])
            break
        except (TimeoutError, OSError) as exc:
            print(f"{board:30} {sample_dir}/_clean unreadable ({exc}); trying another copy")
    else:
        raise RuntimeError(f"{board}: no readable _clean/ re-export")
    if "cir" in kinds:
        # built in a temp dir named after the board (the Clean-template lookup
        # matches on that name); only the scrubbed deck is kept, as spice.cir
        with tempfile.TemporaryDirectory() as tmp:
            board_dir = os.path.join(tmp, board)
            os.makedirs(board_dir)
            raw = os.path.join(tmp, f"{stem}.kicad_cir")
            gsx.export_spice(gsr._schematic_for(clean_net), raw)
            with open(raw) as f:
                raw_lines = f.readlines()
            lines, _ = cs._complete_raw_export(raw_lines, os.path.join(board_dir, f"{stem}.cir"),
                                               cs._clean_template_for(board_dir))
        files["cir"] = (f"{stem}.cir", sanitise("cir", "".join(lines), stem))
    return files


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--scenarios", help="Comma list of scenario folders (default: all)")
    p.add_argument("--boards", help="Comma list of boards (default: all)")
    p.add_argument("--no-controls", action="store_true", help="Skip the clean control prompts")
    p.add_argument("--out", default=DEFAULT_OUT, help=f"Output root (default: {DEFAULT_OUT})")
    args = p.parse_args(argv)

    os.chdir(REPO_ROOT)
    kinds = list(PLACEHOLDERS)
    only_sc = set(args.scenarios.split(",")) if args.scenarios else None
    only_b = set(args.boards.split(",")) if args.boards else None

    template = load_template()
    specs = {}
    key, index, samples = [], [], {}

    # Scenario folders may sit directly under SCENARIOS_ROOT or one level deeper
    # in a research-question group (e.g. Scenarios/RQ1_SimpleMods/GndShortRandom).
    manifests = sorted(glob.glob(os.path.join(SCENARIOS_ROOT, "*", "manifest.json")) +
                       glob.glob(os.path.join(SCENARIOS_ROOT, "*", "*", "manifest.json")))
    for manifest in manifests:
        scenario_dir = os.path.dirname(manifest)
        scenario = os.path.basename(scenario_dir)
        if scenario not in CATEGORY_FOR_SCENARIO or (only_sc and scenario not in only_sc):
            continue
        with open(manifest) as f:
            records = json.load(f)
        for rec in records:
            board = rec["board"]
            if only_b and board not in only_b:
                continue
            vdir = os.path.join(scenario_dir, rec["variant"], board)
            stem = os.path.splitext(os.path.basename(rec["clean_reexport"]))[0]
            samples.setdefault(board, ([], stem, rec["clean"]))[0].append(vdir)
            if board not in specs:
                with open(os.path.join(SPEC_DIR, SPEC_FOR_BOARD[board])) as f:
                    specs[board] = f.read()
            pid = f"{board}/{scenario}_{rec['variant']}"
            entry = write_prompt(os.path.join(args.out, pid), template, board, specs[board],
                                 read_files(vdir, stem, kinds))
            index.append({"id": pid, **entry})
            key.append({"id": pid, "prompt": entry["prompt"], "scenario": scenario,
                        "variant": rec["variant"],
                        "board": board, "anomaly": True,
                        "category": CATEGORY_FOR_SCENARIO[scenario], **truth(scenario, rec)})
        print(f"{scenario:30} {sum(1 for k in key if k['scenario'] == scenario):3} prompt(s)")

    if not args.no_controls:
        for board, (vdirs, stem, clean_net) in sorted(samples.items()):
            pid = f"{board}/{CONTROL_DIR}"
            entry = write_prompt(os.path.join(args.out, pid), template, board, specs[board],
                                 build_control(board, vdirs, stem, clean_net, kinds))
            index.append({"id": pid, **entry})
            key.append({"id": pid, "prompt": entry["prompt"], "scenario": "Control",
                        "variant": None, "board": board, "anomaly": False, "category": None,
                        "components": [], "pins": [], "nets": [], "net_components": []})
        print(f"{'Controls':30} {len(samples):3} prompt(s)")

    # Never clobber an existing index/answer key with an empty one: a discovery
    # miss (moved scenario folders, a --scenarios typo) would otherwise silently
    # truncate both files, losing the ground truth for already-built prompts.
    if not key:
        print("No prompts matched - refusing to overwrite prompts.jsonl / "
              "answer_key.jsonl. Check SCENARIOS_ROOT layout and --scenarios/--boards.",
              file=sys.stderr)
        return 1

    os.makedirs(args.out, exist_ok=True)
    for name, rows in (("prompts.jsonl", index), ("answer_key.jsonl", key)):
        with open(os.path.join(args.out, name), "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
    print(f"\n{len(key)} prompt(s) written under {args.out}; "
          f"index: prompts.jsonl, answer key: answer_key.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
