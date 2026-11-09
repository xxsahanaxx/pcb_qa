#!/usr/bin/env python3
"""Generate Trojan-detection question banks next to each infected netlist.

Reads every ``outputs/Infected/<SIGNAL>/manifest.json`` and, for each infected
variant, writes ``<stem>_trojan_questions.json`` into that variant's folder.

Design of the questions
-----------------------
Every question's ``answer`` is the ground truth **on the infected netlist**, and
the questions are chosen so that this truth *reveals* the tamper:

  * an expected net is now missing (renamed / removed),
  * a ``Troj_*`` net has appeared,
  * a signal endpoint has moved to the wrong net (RX/TX swap), or
  * two components that shared a bus net are no longer on a common net (snip).

Each answer is computed from the parsed netlists, and a candidate is kept only
when the clean and infected answers actually differ -- so every emitted question
is guaranteed to discriminate clean from infected. Both answers are stored
(``answer`` = infected truth, ``clean_answer`` = healthy design) so the bank
supports either single-file scoring or clean-vs-infected differential scoring.

Usage (run with the project venv, from the repo root):
  .venv/bin/python -m netlist_modifications.gen_trojan_questions
  .venv/bin/python -m netlist_modifications.gen_trojan_questions --root outputs/Infected/SDA
"""

import argparse
import glob
import json
import os
import re
import sys

from .insert_modification import core

CATEGORY = "trojan_detection"


# --------------------------------------------------------------------------- #
# Predicates over parsed nets (core.Net list)
# --------------------------------------------------------------------------- #

def _exists(nets, name):
    return any(n.name == name for n in nets)


def _pin_net(nets, ref, pin):
    for n in nets:
        for nd in n.nodes:
            if nd.ref == ref and nd.pin == pin:
                return n.name
    return None


def _share_net(nets, a, b):
    for n in nets:
        refs = {nd.ref for nd in n.nodes}
        if a in refs and b in refs:
            return True
    return False


def _yn(flag):
    return "YES" if flag else "NO"


def _net_degree(nets, ref, pin):
    """Number of component pins on the net that carries `ref`/`pin` (0 if none)."""
    name = _pin_net(nets, ref, pin)
    if name is None:
        return 0
    return sum(len(n.nodes) for n in nets if n.name == name)


def _func_role(pinfunction):
    """Classify a pin function as a UART 'TX'/'RX' line, else None.

    Only fires on functions that clearly denote a role (e.g. UART_TXD0,
    RXD, ..._TX), not on generic GPIO names like PB14.
    """
    if not pinfunction:
        return None
    u = pinfunction.upper()
    if "TXD" in u or re.search(r"(^|[_/])TX([_/0-9]|$)", u):
        return "TX"
    if "RXD" in u or re.search(r"(^|[_/])RX([_/0-9]|$)", u):
        return "RX"
    return None


def _keep_differing(candidates):
    """candidates: list of (question, clean_answer, infected_answer).

    Keep only those where the two answers differ; return question dicts with
    the infected answer as ``answer`` and the clean answer recorded.
    """
    out = []
    for question, clean_ans, inf_ans in candidates:
        if clean_ans != inf_ans:
            out.append({
                "category": CATEGORY,
                "question": question,
                "answer": inf_ans,
                "clean_answer": clean_ans,
            })
    return out


# --------------------------------------------------------------------------- #
# Per-family question builders
# --------------------------------------------------------------------------- #

def _swap_candidates(clean, inf, entry):
    rx, tx = entry["rx_net"], entry["tx_net"]
    c = []
    # A named signal net vanished (renamed to Troj_*).
    c.append((f"Does the design contain a net named '{rx}'?",
              _yn(_exists(clean, rx)), _yn(_exists(inf, rx))))
    c.append((f"Does the design contain a net named '{tx}'?",
              _yn(_exists(clean, tx)), _yn(_exists(inf, tx))))
    # Canary: a Troj_ net appeared.
    troj_c = _exists(clean, "Troj_RX") or _exists(clean, "Troj_TX")
    troj_i = _exists(inf, "Troj_RX") or _exists(inf, "Troj_TX")
    c.append(("Does the design contain a net named 'Troj_RX' or 'Troj_TX'?",
              _yn(troj_c), _yn(troj_i)))
    # The RX endpoint moved onto a transmit-labelled net (the crossover).
    crx = next((n for n in clean if n.name == rx), None)
    if crx and crx.nodes:
        nd = crx.nodes[0]
        c.append((f"Is {nd.ref} pin {nd.pin} connected to the net '{rx}'?",
                  _yn(_pin_net(clean, nd.ref, nd.pin) == rx),
                  _yn(_pin_net(inf, nd.ref, nd.pin) == rx)))
        c.append((f"Is {nd.ref} pin {nd.pin} (the '{rx}' endpoint) now connected "
                  f"to a net named 'Troj_TX'?",
                  _yn(_pin_net(clean, nd.ref, nd.pin) == "Troj_TX"),
                  _yn(_pin_net(inf, nd.ref, nd.pin) == "Troj_TX")))

    # Pin-function vs net-role mismatch (reference-free; only when pin functions
    # actually denote a role). After the swap a transmit pin lands on the
    # receive-named 'Troj_RX' net, and vice-versa.
    for role, wrong_net, word in (("TX", "Troj_RX", "receive"),
                                  ("RX", "Troj_TX", "transmit")):
        src = rx if role == "RX" else tx
        cnet = next((n for n in clean if n.name == src), None)
        if not cnet:
            continue
        nd = next((x for x in cnet.nodes if _func_role(x.pinfunction) == role), None)
        if nd is None:
            continue
        line = "transmit" if role == "TX" else "receive"
        c.append((f"Is {nd.ref} pin {nd.pin} (function '{nd.pinfunction}', a "
                  f"UART {line} line) connected to a {word}-named net "
                  f"'{wrong_net}'?",
                  _yn(_pin_net(clean, nd.ref, nd.pin) == wrong_net),
                  _yn(_pin_net(inf, nd.ref, nd.pin) == wrong_net)))
    return _keep_differing(c)


def _snip_candidates(clean, inf, entry, signal, net):
    troj0, troj1 = f"Troj_{signal}0", f"Troj_{signal}1"
    c = []
    # The bus net vanished (split + renamed).
    c.append((f"Does the design contain a net named '{net}'?",
              _yn(_exists(clean, net)), _yn(_exists(inf, net))))
    # Canary: the split nets appeared.
    can_c = _exists(clean, troj0) or _exists(clean, troj1)
    can_i = _exists(inf, troj0) or _exists(inf, troj1)
    c.append((f"Does the design contain nets named '{troj0}' and '{troj1}'?",
              _yn(can_c), _yn(can_i)))
    # Broken connectivity: two components that shared the bus net are severed.
    iso_keys = entry.get(troj0, [])
    side0 = [k.split(".")[0] for k in iso_keys]
    side1 = [k.split(".")[0] for k in entry.get(troj1, [])]
    a = side0[0] if side0 else None
    b = next((r for r in side1 if r != a), None)
    if a and b:
        # Broken connectivity: the isolated component (often the I2C pull-up) is
        # severed from a device that shared the bus.
        c.append((f"Are components {a} and {b} connected to a common net?",
                  _yn(_share_net(clean, a, b)), _yn(_share_net(inf, a, b))))
        c.append((f"Is component {b} connected to the net '{net}'?",
                  _yn(_pin_net_has(clean, b, net)),
                  _yn(_pin_net_has(inf, b, net))))
    # Dangling pin: the isolated node now sits on a one-pin (floating) net.
    if iso_keys:
        ref, _, pin = iso_keys[0].partition(".")
        c.append((f"Is {ref} pin {pin} electrically connected to any other "
                  f"component pin?",
                  _yn(_net_degree(clean, ref, pin) > 1),
                  _yn(_net_degree(inf, ref, pin) > 1)))
    return _keep_differing(c)


def _pin_net_has(nets, ref, net_name):
    """True if component `ref` has any node on the net named `net_name`."""
    for n in nets:
        if n.name == net_name and any(nd.ref == ref for nd in n.nodes):
            return True
    return False


def _detect_signal(entry):
    """Recover the signal keyword from a snip manifest entry's Troj_<SIG>0 key."""
    for k in entry:
        if k.startswith("Troj_") and k.endswith("0"):
            return k[len("Troj_"):-1]
    return None


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def process_manifest(manifest_path):
    with open(manifest_path) as f:
        entries = json.load(f)

    written = []
    for entry in entries:
        infected_path = entry["output"]
        clean = core.parse_nets(core.read(entry["clean"]))
        inf = core.parse_nets(core.read(infected_path))

        if "rx_net" in entry:                         # swap (UART, ...)
            questions = _swap_candidates(clean, inf, entry)
        else:                                         # snip (SDA/SCL/MISO/MOSI)
            signal = _detect_signal(entry)
            questions = _snip_candidates(clean, inf, entry, signal, entry["net"])

        folder = os.path.dirname(infected_path)
        stem = os.path.splitext(os.path.basename(infected_path))[0]
        out_path = os.path.join(folder, f"{stem}_trojan_questions.json")
        with open(out_path, "w") as f:
            json.dump(questions, f, indent=2)
        written.append((out_path, len(questions)))
        print(f"{len(questions):2d} q  -> {out_path}")

    return written


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="netlist_modifications.gen_trojan_questions",
        description="Write Trojan-detection question banks into each infected folder.")
    p.add_argument("--root", default="outputs/Infected",
                   help="Directory tree to scan for manifest.json (default: outputs/Infected)")
    args = p.parse_args(argv)

    manifests = sorted(glob.glob(os.path.join(args.root, "**", "manifest.json"),
                                 recursive=True))
    if not manifests:
        print(f"No manifest.json found under {args.root}", file=sys.stderr)
        return 1

    total = 0
    for m in manifests:
        print(f"\n== {m} ==")
        for _, n in process_manifest(m):
            total += 1
    print(f"\nWrote {total} trojan question bank(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
