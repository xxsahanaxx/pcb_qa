#!/usr/bin/env python3
"""XOR-gate-on-spare-GPIO Trojan: one added gate per variant (netlist level).

A deliberately *complex* modification for RQ2, in contrast to the single-line
RQ1 edits. Each variant inserts a whole foreign subcircuit: a 2-input XOR gate
(``74LVC1G86``) wired so that

- input **A** is driven by an otherwise-**unused IC pin** (a "spare GPIO":
  a single-pin ``unconnected-...`` net on an IC/module, preferring a
  GPIO-/IO-named pin);
- input **B** **taps an existing signal net** on the board, so the gate has a
  real second operand;
- output **Y** **routes to another component**: a spare pin on a *different*
  component, so the payload leaves the gate and reaches elsewhere on the board;
- power pins go to the board's positive rail (``VCC`` first, else the first
  ``+`` rail) and to ``GND``.

This is the classic "spare-pin trigger logic" hardware Trojan: nothing in the
clean design references the gate, it consumes pins that were meant to be
no-connects, and it couples a live signal to a remote node.

Unlike the RQ1 schematic Trojans, this edits the exported ``.net`` S-expression
directly rather than editing the ``.kicad_sch`` and re-exporting with
kicad-cli: synthesising a brand-new multi-pin IC (its symbol, power pins and
wiring) through a schematic round-trip is far more involved and fragile than
the single-component RQ1 edits. The infected ``.net`` is therefore produced and
verified at the netlist level; no ``.cir`` / ngspice deck is generated for it
(the added gate has no SPICE model here). Ground truth is still *measured*: a
variant is kept only if a re-parse shows exactly the XOR gate added, the two
spare pins moved onto the Trojan nets, the tapped net extended by one node, the
rails extended, and every other net unchanged.

Layout (default ``--out-root outputs/Infected/Scenarios/RQ2_ComplexMods/XorGpioTrojan``)::

    <out-root>/Xor<i>/<board>/_clean/<name>.net       # the clean netlist, unchanged
    <out-root>/Xor<i>/<board>/<name>.net              # infected netlist (XOR gate added)
    <out-root>/Xor<i>/<board>/xor_gpio_trojan.json    # this variant's record
    <out-root>/Xor<i>/manifest.json
    <out-root>/manifest.json                          # every variant, all boards

The clean source netlist is never modified (SHA-256-checked before and after).
"""

import glob
import hashlib
import json
import os
import random
import re
import shutil
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import core as nt
from . import gnd_short_random as gsx

CLEAN_GLOB = "outputs/Clean/*/*.net"
DEFAULT_OUT_ROOT = "outputs/Infected/Scenarios/RQ2_ComplexMods/XorGpioTrojan"
DEFAULT_COUNT = 3
DEFAULT_SEED = 0

# 74LVC1G86 single 2-input XOR gate, SC70-5 / SOT-23-5 pinout.
XOR_PART = {
    "value": "74LVC1G86",
    "footprint": "Package_TO_SOT_SMD:SOT-23-5",
    "lib": "74xGxx", "part": "74LVC1G86",
    "description": "Single 2-input XOR gate",
}
# pin number -> (name, pintype) for the inserted gate
XOR_PINS = {"1": ("A", "input"), "2": ("B", "input"), "3": ("GND", "power_in"),
            "4": ("Y", "output"), "5": ("VCC", "power_in")}

_GPIO_RE = re.compile(r"GPIO|\bIO\d|\bPIN\d|\bP[ABCD]\d", re.I)
_RAIL_RE = re.compile(r"^(\+|VCC|VDD|VBUS|VBAT|VIN)", re.I)


@dataclass
class SparePin:
    ref: str
    pin: str
    pinfunction: Optional[str]
    pintype: str
    net: nt.Net          # the single-pin unconnected- net it sits on


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #

def spare_ic_pins(nets: List[nt.Net]) -> List[SparePin]:
    """Unused pins on ICs/modules: single-pin ``unconnected-`` nets, no power pins."""
    out: List[SparePin] = []
    for n in nets:
        if not n.name.startswith("unconnected-") or len(n.nodes) != 1:
            continue
        nd = n.nodes[0]
        if nd.ref.startswith("#") or (nd.ref[0] != "U" and not nd.ref.startswith("Module")):
            continue
        if "power" in (nd.pintype or ""):
            continue  # don't hijack a module's power output
        out.append(SparePin(nd.ref, nd.pin, nd.pinfunction, nd.pintype, n))
    return out


def signal_nets(nets: List[nt.Net]) -> List[nt.Net]:
    """Multi-pin signal nets eligible as the XOR B-input tap."""
    return [n for n in nets
            if len(n.nodes) >= 2 and "GND" not in n.name.upper()
            and not n.name.startswith("unconnected-") and not _RAIL_RE.match(n.name)]


def positive_rail(nets: List[nt.Net]) -> Optional[nt.Net]:
    rails = [n for n in nets if _RAIL_RE.match(n.name) and n.node_set()]
    if not rails:
        return None
    return next((n for n in rails if n.name.upper() == "VCC"),
                max(rails, key=lambda n: (len(n.nodes), n.name)))


def gnd_net(nets: List[nt.Net]) -> Optional[nt.Net]:
    return next((n for n in nets if n.name.upper() == "GND" and n.node_set()), None)


# --------------------------------------------------------------------------- #
# Build the infected netlist text
# --------------------------------------------------------------------------- #

def _node(ref: str, pin: str, fn: Optional[str], pintype: str) -> nt.Node:
    return nt.Node(ref=ref, pin=pin, pinfunction=fn, pintype=pintype)


def _comp_block(ref: str) -> str:
    p = XOR_PART
    return (
        f'    (comp (ref "{ref}")\n'
        f'      (value "{p["value"]}")\n'
        f'      (footprint "{p["footprint"]}")\n'
        f'      (description "{p["description"]}")\n'
        f'      (libsource (lib "{p["lib"]}") (part "{p["part"]}") '
        f'(description "{p["description"]}"))\n'
        f'      (property (name "Sheetname") (value ""))\n'
        f'      (property (name "Sheetfile") (value ""))\n'
        f'      (sheetpath (names "/") (tstamps "/"))\n'
        f'      (tstamps "/{_fake_uuid(ref)}/"))'
    )


def _fake_uuid(seed_text: str) -> str:
    h = hashlib.sha1(seed_text.encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _next_ref(nets_text: str) -> str:
    nums = [int(m.group(1)) for m in re.finditer(r'\(comp \(ref "U(\d+)"\)', nets_text)]
    return f"U{max(nums, default=0) + 1}"


def build_infected(content: str, gpio: SparePin, tap: nt.Net, route: SparePin,
                   rail: nt.Net, gnd: nt.Net) -> Tuple[str, Dict]:
    """Return (infected netlist text, record)."""
    nets = nt.parse_nets(content)
    uref = _next_ref(content)
    max_code = max(int(n.code) for n in nets if n.code and n.code.isdigit())
    code_a, code_y = max_code + 1, max_code + 2

    # new Trojan nets
    net_a = nt.render_net_block(
        str(code_a), "Troj_XOR_A", "Default",
        [_node(gpio.ref, gpio.pin, gpio.pinfunction, gpio.pintype.replace("+no_connect", "")),
         _node(uref, "1", "A", "input")])
    net_y = nt.render_net_block(
        str(code_y), "Troj_XOR_Y", "Default",
        [_node(uref, "4", "Y", "output"),
         _node(route.ref, route.pin, route.pinfunction, route.pintype.replace("+no_connect", ""))])

    def extended(net: nt.Net, pin: str, fn: str, pintype: str) -> str:
        return nt.render_net_block(net.code, net.name, net.net_class,
                                   list(net.nodes) + [_node(uref, pin, fn, pintype)])

    # collect splices as (start, end, replacement); apply high-offset-first
    edits: List[Tuple[int, int, str]] = [
        (gpio.net.start, gpio.net.end, ""),            # drop gpio's unconnected net
        (route.net.start, route.net.end, ""),          # drop route pin's unconnected net
        (tap.start, tap.end, extended(tap, "2", "B", "input")),
        (rail.start, rail.end, extended(rail, "5", "VCC", "power_in")),
        (gnd.start, gnd.end, extended(gnd, "3", "GND", "power_in")),
    ]
    # insert the two new nets just before the end of (nets ...)
    nets_open = content.index("(nets")
    nets_close = nt.find_matching_paren(content, nets_open)
    edits.append((nets_close, nets_close, f"\n{net_a}\n{net_y}"))
    # insert the comp just before the end of (components ...)
    comp_open = content.index("(components")
    comp_close = nt.find_matching_paren(content, comp_open)
    edits.append((comp_close, comp_close, f"\n{_comp_block(uref)}"))

    out = content
    for start, end, repl in sorted(edits, key=lambda e: -e[0]):
        # when dropping a net block, also swallow the trailing newline/indent
        if repl == "":
            line_end = out.find("\n", end)
            if line_end != -1 and out[end:line_end].strip() == "":
                end = line_end + 1
            start = out.rfind("\n", 0, start) + 1
        out = out[:start] + repl + out[end:]

    record = {
        "trojan_ref": uref, "trojan_part": f'{XOR_PART["lib"]}:{XOR_PART["part"]}',
        "gpio_ref": gpio.ref, "gpio_pin": gpio.pin, "gpio_pinfunction": gpio.pinfunction,
        "gpio_pintype": gpio.pintype,
        "tap_net": tap.name, "tap_net_nodes": sorted(f"{r}.{p}" for r, p in tap.node_set()),
        "route_ref": route.ref, "route_pin": route.pin, "route_pinfunction": route.pinfunction,
        "rail": rail.name, "gnd": gnd.name,
        "added_nets": ["Troj_XOR_A", "Troj_XOR_Y"],
        "wiring": {
            "A": f"{gpio.ref}.{gpio.pin} ({gpio.pinfunction})",
            "B": f"tap {tap.name}",
            "Y": f"{route.ref}.{route.pin} ({route.pinfunction})",
            "VCC": rail.name, "GND": gnd.name,
        },
    }
    return out, record


# --------------------------------------------------------------------------- #
# Verify: re-parse and confirm exactly the intended change
# --------------------------------------------------------------------------- #

def verify(clean: str, infected: str, rec: Dict) -> bool:
    c = {n.name: n.node_set() for n in nt.parse_nets(clean)}
    inf = {n.name: n.node_set() for n in nt.parse_nets(infected)}
    uref = rec["trojan_ref"]
    gpio = (rec["gpio_ref"], rec["gpio_pin"])
    route = (rec["route_ref"], rec["route_pin"])

    if inf.get("Troj_XOR_A") != {gpio, (uref, "1")}:
        return False
    if inf.get("Troj_XOR_Y") != {route, (uref, "4")}:
        return False
    if inf.get(rec["tap_net"]) != c[rec["tap_net"]] | {(uref, "2")}:
        return False
    if inf.get(rec["rail"]) != c[rec["rail"]] | {(uref, "5")}:
        return False
    if inf.get(rec["gnd"]) != c[rec["gnd"]] | {(uref, "3")}:
        return False
    # every pin of the gate accounted for
    gate_pins = {(uref, p) for p in XOR_PINS}
    if {k for s in inf.values() for k in s if k[0] == uref} != gate_pins:
        return False
    # only the Trojan nets, the tap, the rails and the two freed spare nets changed
    changed = {k for k in set(c) | set(inf) if c.get(k, set()) != inf.get(k, set())}
    expected_changed = {"Troj_XOR_A", "Troj_XOR_Y", rec["tap_net"], rec["rail"], rec["gnd"],
                        gpio_net_name(clean, gpio), gpio_net_name(clean, route)}
    return changed <= expected_changed


def gpio_net_name(content: str, key: Tuple[str, str]) -> str:
    for n in nt.parse_nets(content):
        if key in n.node_set():
            return n.name
    return ""


# --------------------------------------------------------------------------- #
# One variant
# --------------------------------------------------------------------------- #

def build_variant(clean_net: str, seed_key: str, used_gpio: set) -> Optional[Dict]:
    content = nt.read(clean_net)
    nets = nt.parse_nets(content)
    rail, gnd = positive_rail(nets), gnd_net(nets)
    spares = [s for s in spare_ic_pins(nets) if (s.ref, s.pin) not in used_gpio]
    sigs = signal_nets(nets)
    if not (rail and gnd and len(spares) >= 2 and sigs):
        return None
    rng = random.Random(seed_key)
    rng.shuffle(spares)
    # prefer a GPIO-named pin for input A
    spares.sort(key=lambda s: 0 if _GPIO_RE.search(s.pinfunction or "") else 1)
    gpio = spares[0]
    # route to a spare pin on a *different* component
    route = next((s for s in spares[1:] if s.ref != gpio.ref), None)
    if route is None:
        return None
    tap = rng.choice([n for n in sigs if gpio.ref not in {r for r, _ in n.node_set()}] or sigs)

    infected, rec = build_infected(content, gpio, tap, route, rail, gnd)
    if not verify(content, infected, rec):
        return None
    rec["_infected_text"] = infected
    rec["gpio_is_named_gpio"] = bool(_GPIO_RE.search(gpio.pinfunction or ""))
    return rec


# --------------------------------------------------------------------------- #
# Batch runner
# --------------------------------------------------------------------------- #

def run_batch(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED,
              clean_glob: str = CLEAN_GLOB, out_root: str = DEFAULT_OUT_ROOT) -> int:
    manifest: List[Dict] = []
    per_var: Dict[int, List[Dict]] = {i: [] for i in range(1, count + 1)}

    for path in sorted(glob.glob(clean_glob)):
        board = os.path.basename(os.path.dirname(path))
        stem = os.path.splitext(os.path.basename(path))[0]
        before = hashlib.sha256(nt.read(path).encode()).hexdigest()

        recs: List[Dict] = []
        used: set = set()
        attempt = 0
        while len(recs) < count and attempt < count * 20:
            rec = build_variant(path, f"{seed}:xor:{board}:{attempt}", used)
            attempt += 1
            if rec is None:
                if not spare_ic_pins(nt.parse_nets(nt.read(path))):
                    break  # board has no spare IC pins at all
                continue
            used.add((rec["gpio_ref"], rec["gpio_pin"]))
            used.add((rec["route_ref"], rec["route_pin"]))
            recs.append(rec)

        for i, rec in enumerate(recs, start=1):
            dest = os.path.join(out_root, f"Xor{i}", board)
            if os.path.exists(dest):
                raise FileExistsError(f"{dest} already exists; refusing to overwrite")
            os.makedirs(os.path.join(dest, "_clean"), exist_ok=True)
            infected = rec.pop("_infected_text")
            nt.write(os.path.join(dest, f"{stem}.net"), infected)
            shutil.copy2(path, os.path.join(dest, "_clean", f"{stem}.net"))
            rec.update({"variant": f"Xor{i}", "board": board, "mode": "xor_gpio_trojan",
                        "seed": seed, "clean": path,
                        "output": os.path.join(dest, f"{stem}.net"),
                        "clean_reexport": os.path.join(dest, "_clean", f"{stem}.net")})
            with open(os.path.join(dest, "xor_gpio_trojan.json"), "w") as f:
                json.dump(rec, f, indent=2)
            manifest.append(rec)
            per_var[i].append(rec)
            print(f"{board:24} Xor{i}: {rec['trojan_ref']} XOR  "
                  f"A={rec['gpio_ref']}.{rec['gpio_pin']}({rec['gpio_pinfunction']})  "
                  f"B=tap[{rec['tap_net']}]  Y={rec['route_ref']}.{rec['route_pin']}")

        if hashlib.sha256(nt.read(path).encode()).hexdigest() != before:
            raise RuntimeError(f"source netlist changed under {path}; aborting")
        if len(recs) < count:
            print(f"{board:24} WARNING: only {len(recs)}/{count} variants could be built "
                  f"(needs >=2 spare IC pins on >=2 components)", file=sys.stderr)

    os.makedirs(out_root, exist_ok=True)
    for i, recs in per_var.items():
        if recs:
            with open(os.path.join(out_root, f"Xor{i}", "manifest.json"), "w") as f:
                json.dump(recs, f, indent=2)
    manifest_path = os.path.join(out_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{len(manifest)} modified design(s) written. Manifest: {manifest_path}")
    return 0
