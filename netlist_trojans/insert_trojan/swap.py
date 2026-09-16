#!/usr/bin/env python3
"""Bus RX/TX "swap" Trojan (UART, and any other RX/TX-named pair).

For a matched RX/TX net pair, this swaps the two nets' node lists and renames
them to ``Troj_RX`` / ``Troj_TX`` -- i.e. the receive and transmit lines are
crossed. It is the generalised form of the original Meshinger UART Trojan, built
from the engine's ``modify_net`` op, so it needs no board-specific component
refs.

RX and TX nets are paired by base name: the first ``RX``/``TX`` token is
neutralised, so ``UART_RX``↔``UART_TX`` and ``UART1_RX_FCC``↔``UART1_TX_FCC``
pair up. Filtered by a signal keyword (e.g. ``UART``).

Drive it from the CLI (``netlist_trojans.cli``) with ``swap`` /
``swap-batch --signal UART``.
"""

import glob
import json
import os
import re
import sys

from . import core as nt
from .snip import sanitise

CLEAN_GLOB = "outputs/Clean/*/*.net"

# RX / TX only as a whole token (not inside a word like "TRX" or "MAX").
_ROLE_RE = re.compile(r"(?i)(?<![A-Za-z])(RX|TX)(?![A-Za-z])")


def _role(name: str):
    m = _ROLE_RE.search(name)
    return m.group(1).upper() if m else None


def _base(name: str) -> str:
    """Neutralise the first RX/TX token so an RX net and its TX share a key."""
    return _ROLE_RE.sub("@", name, count=1).upper()


def _pair_label(rx_name: str) -> str:
    return _base(rx_name).replace("@", "")


def _default_output(input_path: str) -> str:
    root, ext = os.path.splitext(input_path)
    return f"{root}_infected{ext}"


def uart_pairs(nets, signal: str):
    """Matched (rx_net, tx_net) pairs whose names carry `signal`, ordered by code."""
    key = signal.upper()
    relevant = [
        n for n in nets
        if key in n.name.upper()
        and not n.name.lower().startswith("unconnected-")
        and n.nodes and _role(n.name)
    ]
    rx, tx = {}, {}
    for n in relevant:
        (rx if _role(n.name) == "RX" else tx).setdefault(_base(n.name), n)
    pairs = [(rx[b], tx[b]) for b in rx if b in tx]
    pairs.sort(key=lambda p: int(p[0].code) if p[0].code.isdigit() else 0)
    return pairs


def build_swap(rx, tx) -> dict:
    """Spec that crosses `rx`/`tx`: swap node lists, rename to Troj_RX / Troj_TX."""
    rx_nodes = [nd.as_dict() for nd in rx.nodes]
    tx_nodes = [nd.as_dict() for nd in tx.nodes]
    return {
        "meta": {"label": "UART", "tool": "netlist_trojan.py"},
        "ops": [
            {"type": "modify_net", "net": rx.name, "rename": "Troj_RX",
             "set_nodes": tx_nodes, "expect_nodes": rx_nodes},
            {"type": "modify_net", "net": tx.name, "rename": "Troj_TX",
             "set_nodes": rx_nodes, "expect_nodes": tx_nodes},
        ],
    }


# --------------------------------------------------------------------------- #
# Batch: one output per RX/TX pair, across every Clean design
# --------------------------------------------------------------------------- #

def run_batch(signal: str, clean_glob: str = CLEAN_GLOB,
              out_root: str = None) -> int:
    signal = signal.upper()
    out_root = out_root or f"outputs/Infected/{signal}"
    manifest = []

    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        base = os.path.basename(path)
        content = nt.read(path)
        for rx, tx in uart_pairs(nt.parse_nets(content), signal):
            spec = build_swap(rx, tx)
            infected, _ = nt.apply_spec(content, spec, strict=True)
            out_dir = os.path.join(out_root, board, sanitise(_pair_label(rx.name)))
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, base)
            nt.write(out_path, infected)
            manifest.append({
                "board": board,
                "clean": path,
                "rx_net": rx.name,
                "tx_net": tx.name,
                "output": out_path,
                "Troj_RX": [nd.as_dict() for nd in tx.nodes],
                "Troj_TX": [nd.as_dict() for nd in rx.nodes],
            })
            print(f"{board:24} {rx.name} <-> {tx.name}  -> {out_path}")

    os.makedirs(out_root, exist_ok=True)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} infected netlist(s) written. Manifest: {manifest_path}")
    return 0


# --------------------------------------------------------------------------- #
# Single: swap one RX/TX pair in one file
# --------------------------------------------------------------------------- #

def run_single(signal: str, input_path: str, output: str = None,
               net_name: str = None, list_only: bool = False) -> int:
    signal = signal.upper()
    content = nt.read(input_path)
    pairs = uart_pairs(nt.parse_nets(content), signal)
    if not pairs:
        print(f"No {signal} RX/TX pairs found in {input_path}", file=sys.stderr)
        return 1

    if list_only:
        print(f"{signal} RX/TX pairs in {input_path}:")
        for rx, tx in pairs:
            print(f"  {rx.name} <-> {tx.name}")
        return 0

    if net_name:
        target = next((p for p in pairs
                       if net_name in (p[0].name, p[1].name)), None)
        if target is None:
            names = ", ".join(p[0].name for p in pairs)
            print(f"error: no {signal} pair whose RX or TX net is {net_name!r}. "
                  f"RX nets: {names}", file=sys.stderr)
            return 1
    else:
        target = pairs[0]
        if len(pairs) > 1:
            print(f"note: {len(pairs)} {signal} pairs found; swapping the first "
                  f"({target[0].name} <-> {target[1].name}). Use --net or --list.",
                  file=sys.stderr)

    rx, tx = target
    spec = build_swap(rx, tx)
    infected, _ = nt.apply_spec(content, spec, strict=True)
    out_path = output or _default_output(input_path)
    nt.write(out_path, infected)
    print(f"Swapped {rx.name} <-> {tx.name} -> Troj_RX / Troj_TX")
    print(f"Wrote {out_path}")
    return 0
