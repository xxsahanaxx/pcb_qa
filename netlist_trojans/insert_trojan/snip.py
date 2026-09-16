#!/usr/bin/env python3
"""Bus "snip" Trojan (SDA, SCL, MISO, MOSI, ... any signal keyword).

A snip splits one bus-signal net into two nets, ``Troj_<SIGNAL>0`` and
``Troj_<SIGNAL>1``: the net's first node is isolated on side 0, the rest go on
side 1. The same rule serves every signal, so all bus Trojans behave
identically. Drive it from the CLI (``netlist_trojans.cli``) with ``snip`` /
``snip-batch --signal <NAME>``.
"""

import glob
import json
import os
import re
import sys

from . import core as nt

CLEAN_GLOB = "outputs/Clean/*/*.net"


def sanitise(name: str) -> str:
    """Turn a net name into a safe folder name (drop /, {, } etc.)."""
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", name)).strip("_")


def bus_nets(nets, signal: str):
    """Real, snip-able nets whose name carries `signal` (>=2 nodes)."""
    key = signal.upper()
    return [
        n for n in nets
        if key in n.name.upper()
        and not n.name.lower().startswith("unconnected-")
        and len(n.nodes) >= 2
    ]


def build_split(net, signal: str) -> dict:
    """One-op spec snipping `net` into Troj_<SIGNAL>0 (first node) / ...1 (rest)."""
    prefix = f"Troj_{signal.upper()}"
    keys = [f"{nd.ref}.{nd.pin}" for nd in net.nodes]
    return {
        "meta": {"label": signal.upper(), "tool": "netlist_trojan.py"},
        "ops": [{
            "type": "split_net",
            "net": net.name,
            "into": [
                {"name": f"{prefix}0", "nodes": keys[:1]},
                {"name": f"{prefix}1", "nodes": keys[1:]},
            ],
        }],
    }


# --------------------------------------------------------------------------- #
# Batch: one output per matching net, across every Clean design
# --------------------------------------------------------------------------- #

def run_batch(signal: str, clean_glob: str = CLEAN_GLOB,
              out_root: str = None) -> int:
    """Snip every matching net in every file under `clean_glob`, one output each."""
    signal = signal.upper()
    out_root = out_root or f"outputs/Infected/{signal}"
    prefix = f"Troj_{signal}"
    manifest = []

    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        base = os.path.basename(path)
        content = nt.read(path)
        for net in bus_nets(nt.parse_nets(content), signal):
            spec = build_split(net, signal)
            infected, _ = nt.apply_spec(content, spec, strict=True)
            out_dir = os.path.join(out_root, board, sanitise(net.name))
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, base)
            nt.write(out_path, infected)
            into = spec["ops"][0]["into"]
            manifest.append({
                "board": board,
                "clean": path,
                "net": net.name,
                "output": out_path,
                f"{prefix}0": into[0]["nodes"],
                f"{prefix}1": into[1]["nodes"],
            })
            print(f"{board:24} {net.name:16} -> {out_path}")

    os.makedirs(out_root, exist_ok=True)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} infected netlist(s) written. Manifest: {manifest_path}")
    return 0


# --------------------------------------------------------------------------- #
# Single: snip one net in one file
# --------------------------------------------------------------------------- #

def _default_output(input_path: str) -> str:
    root, ext = os.path.splitext(input_path)
    return f"{root}_infected{ext}"


def run_single(signal: str, input_path: str, output: str = None,
               net_name: str = None, list_only: bool = False) -> int:
    """Snip one `signal` net in a single netlist file."""
    signal = signal.upper()
    content = nt.read(input_path)
    candidates = bus_nets(nt.parse_nets(content), signal)
    if not candidates:
        print(f"No snip-able {signal}-bearing nets found in {input_path}",
              file=sys.stderr)
        return 1

    if list_only:
        print(f"{signal}-bearing nets in {input_path}:")
        for n in candidates:
            nodes = ", ".join(f"{nd.ref}.{nd.pin}" for nd in n.nodes)
            print(f"  {n.name:18} ({len(n.nodes)} nodes: {nodes})")
        return 0

    if net_name:
        target = next((n for n in candidates if n.name == net_name), None)
        if target is None:
            names = ", ".join(n.name for n in candidates)
            print(f"error: net {net_name!r} is not a snip-able {signal} net. "
                  f"Available: {names}", file=sys.stderr)
            return 1
    else:
        target = candidates[0]
        if len(candidates) > 1:
            print(f"note: {len(candidates)} {signal} nets found; snipping the "
                  f"first ({target.name!r}). Use --net to choose or --list.",
                  file=sys.stderr)

    spec = build_split(target, signal)
    infected, _ = nt.apply_spec(content, spec, strict=True)
    out_path = output or _default_output(input_path)
    nt.write(out_path, infected)

    prefix = f"Troj_{signal}"
    into = spec["ops"][0]["into"]
    print(f"Snipped {target.name!r} -> {prefix}0 {into[0]['nodes']} | "
          f"{prefix}1 {into[1]['nodes']}")
    print(f"Wrote {out_path}")
    return 0
