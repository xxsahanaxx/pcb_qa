#!/usr/bin/env python3
"""Command-line front end for the netlist_trojans package.

Subcommands:
  extract      Derive a Trojan spec (JSON) from a clean + infected pair.
  apply        Insert a Trojan spec into a clean netlist.
  snip         Snip one bus-signal net in a single file (SDA/SCL/MISO/MOSI/...).
  snip-batch   Snip every matching net across a tree of clean netlists.
  swap         Cross one RX/TX net pair in a single file.
  swap-batch   Swap every RX/TX pair across a tree of clean netlists.
  tolerance        Swap the tolerance grade of one passive in a single file.
  tolerance-batch  Swap the tolerance grade of every R/C/L passive across a tree.
  value        Shift the magnitude of one passive's value in a single file.
  value-batch  Shift the magnitude of every R/C/L passive's value across a tree.

Run it as a module from the repo root:
  python -m netlist_trojans <subcommand> ...
"""

import argparse
import json
import sys
from typing import Dict, List, Optional

from . import core
from . import snip
from . import swap
from . import tolerance
from . import value


def _parse_kv(pairs: Optional[List[str]], flag: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"{flag} expects KEY=VALUE, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _cmd_extract(args) -> int:
    params = _parse_kv(args.param, "--param")
    spec = core.extract_spec(args.clean, args.infected, label=args.label,
                             params=params or None)
    text = json.dumps(spec, indent=2)
    if args.output:
        core.write(args.output, text + "\n")
        print(f"Wrote Trojan spec to {args.output} ({len(spec['ops'])} op(s)).")
    else:
        print(text)
    for op in spec["ops"]:
        print(f"  - {core.describe_op(op)}", file=sys.stderr)
    return 0


def _cmd_apply(args) -> int:
    spec = json.loads(core.read(args.spec))
    overrides = _parse_kv(args.set, "--set")
    content, log = core.apply_spec(core.read(args.clean), spec,
                                   strict=args.strict, overrides=overrides)
    core.write(args.output, content)
    print(f"Wrote infected netlist to {args.output}")
    for line in log:
        print(f"  {line}")
    return 0


def _cmd_snip(args) -> int:
    return snip.run_single(args.signal, args.input, output=args.output,
                           net_name=args.net, list_only=args.list)


def _cmd_snip_batch(args) -> int:
    return snip.run_batch(args.signal, clean_glob=args.clean_glob,
                          out_root=args.out_root)


def _cmd_swap(args) -> int:
    return swap.run_single(args.signal, args.input, output=args.output,
                           net_name=args.net, list_only=args.list)


def _cmd_swap_batch(args) -> int:
    return swap.run_batch(args.signal, clean_glob=args.clean_glob,
                          out_root=args.out_root)


def _cmd_tolerance(args) -> int:
    return tolerance.run_single(args.input, output=args.output,
                                ref=args.ref, list_only=args.list)


def _cmd_tolerance_batch(args) -> int:
    families = args.families.split(",") if args.families else None
    return tolerance.run_batch(clean_glob=args.clean_glob,
                               out_root=args.out_root, families=families)


def _cmd_value(args) -> int:
    return value.run_single(args.input, output=args.output,
                            ref=args.ref, list_only=args.list)


def _cmd_value_batch(args) -> int:
    families = args.families.split(",") if args.families else None
    return value.run_batch(clean_glob=args.clean_glob,
                           out_root=args.out_root, families=families)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="netlist_trojans", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("extract", help="Derive a Trojan spec from a clean+infected pair")
    e.add_argument("clean", help="Path to the clean .net file")
    e.add_argument("infected", help="Path to the infected .net file")
    e.add_argument("-o", "--output", help="Where to write the spec JSON (default: stdout)")
    e.add_argument("--label", help="Human label stored in the spec meta (e.g. 'UART')")
    e.add_argument("--param", action="append", metavar="OLDREF=VAR",
                   help="Turn a component ref into a ${VAR} placeholder with the ref "
                        "as its default (e.g. --param J7=CONN). Repeatable.")
    e.set_defaults(func=_cmd_extract)

    a = sub.add_parser("apply", help="Insert a Trojan spec into a clean netlist")
    a.add_argument("clean", help="Path to the clean .net file to infect")
    a.add_argument("spec", help="Path to the Trojan spec JSON")
    a.add_argument("-o", "--output", required=True, help="Where to write the infected .net")
    a.add_argument("--set", action="append", metavar="NAME=VALUE",
                   help="Override a spec parameter, e.g. --set CONN=J3. Repeatable.")
    a.add_argument("--strict", action="store_true",
                   help="Error out if a target net is missing or its nodes don't match")
    a.set_defaults(func=_cmd_apply)

    s = sub.add_parser("snip", help="Snip one bus-signal net in a single netlist")
    s.add_argument("input", help="Path to the clean .net file")
    s.add_argument("--signal", required=True, help="Signal keyword, e.g. SDA, SCL, MISO, MOSI")
    s.add_argument("-o", "--output", help="Output .net (default: <input>_infected.net)")
    s.add_argument("--net", help="Name of the net to snip (default: first found)")
    s.add_argument("--list", action="store_true",
                   help="List the snip-able nets in INPUT and exit")
    s.set_defaults(func=_cmd_snip)

    b = sub.add_parser("snip-batch",
                       help="Snip every matching net across a tree of clean netlists")
    b.add_argument("--signal", required=True, help="Signal keyword, e.g. SDA, SCL, MISO, MOSI")
    b.add_argument("--clean-glob", default=snip.CLEAN_GLOB,
                   help=f"Glob for clean netlists (default: {snip.CLEAN_GLOB})")
    b.add_argument("--out-root", default=None,
                   help="Output root (default: outputs/Infected/<SIGNAL>)")
    b.set_defaults(func=_cmd_snip_batch)

    w = sub.add_parser("swap", help="Swap one RX/TX net pair in a single netlist")
    w.add_argument("input", help="Path to the clean .net file")
    w.add_argument("--signal", required=True, help="Signal keyword, e.g. UART")
    w.add_argument("-o", "--output", help="Output .net (default: <input>_infected.net)")
    w.add_argument("--net", help="RX or TX net name identifying the pair (default: first)")
    w.add_argument("--list", action="store_true",
                   help="List the RX/TX pairs in INPUT and exit")
    w.set_defaults(func=_cmd_swap)

    wb = sub.add_parser("swap-batch",
                        help="Swap every RX/TX pair across a tree of clean netlists")
    wb.add_argument("--signal", required=True, help="Signal keyword, e.g. UART")
    wb.add_argument("--clean-glob", default=swap.CLEAN_GLOB,
                    help=f"Glob for clean netlists (default: {swap.CLEAN_GLOB})")
    wb.add_argument("--out-root", default=None,
                    help="Output root (default: outputs/Infected/<SIGNAL>)")
    wb.set_defaults(func=_cmd_swap_batch)

    t = sub.add_parser("tolerance",
                       help="Swap the tolerance grade of one R/C/L passive in a single netlist")
    t.add_argument("input", help="Path to the clean .net file")
    t.add_argument("-o", "--output", help="Output .net (default: <input>_infected.net)")
    t.add_argument("--ref", help="Ref of the passive to substitute (default: first found)")
    t.add_argument("--list", action="store_true",
                   help="List the passives (and their current tolerance) in INPUT and exit")
    t.set_defaults(func=_cmd_tolerance)

    tb = sub.add_parser("tolerance-batch",
                        help="Swap the tolerance grade of every R/C/L passive across a tree "
                             "of clean netlists")
    tb.add_argument("--clean-glob", default=tolerance.CLEAN_GLOB,
                    help=f"Glob for clean netlists (default: {tolerance.CLEAN_GLOB})")
    tb.add_argument("--out-root", default=None,
                    help="Output root (default: outputs/Infected/Tolerance)")
    tb.add_argument("--families", default=None,
                    help="Comma-separated subset of R,C,L (default: all three)")
    tb.set_defaults(func=_cmd_tolerance_batch)

    v = sub.add_parser("value",
                       help="Shift the magnitude of one R/C/L passive's value in a single netlist")
    v.add_argument("input", help="Path to the clean .net file")
    v.add_argument("-o", "--output", help="Output .net (default: <input>_infected.net)")
    v.add_argument("--ref", help="Ref of the passive to substitute (default: first found)")
    v.add_argument("--list", action="store_true",
                   help="List the passives (and their current value) in INPUT and exit")
    v.set_defaults(func=_cmd_value)

    vb = sub.add_parser("value-batch",
                        help="Shift the magnitude of every R/C/L passive's value across a tree "
                             "of clean netlists")
    vb.add_argument("--clean-glob", default=value.CLEAN_GLOB,
                    help=f"Glob for clean netlists (default: {value.CLEAN_GLOB})")
    vb.add_argument("--out-root", default=None,
                    help="Output root (default: outputs/Infected/Value)")
    vb.add_argument("--families", default=None,
                    help="Comma-separated subset of R,C,L (default: all three)")
    vb.set_defaults(func=_cmd_value_batch)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
