#!/usr/bin/env python3
"""Core engine for Trojan insertion in KiCad S-expression netlists (.net).

This module is the reusable library behind the ``netlist_trojans`` package. It
parses netlists, and provides two operations:

  extract_spec(clean, infected)   Diff a CLEAN netlist against an INFECTED one
                                  and return a "Trojan spec" (a dict of net-level
                                  operations: renames, class changes, node-list
                                  rewiring, split/add/remove).

  apply_spec(clean_text, spec)    Replay a spec onto a clean netlist to produce
                                  an infected one. Edits are surgical (a rename
                                  or class change is a single string swap in the
                                  net header; only rewired/split nets have their
                                  node block rebuilt), so formatting elsewhere is
                                  preserved untouched.

Extraction joins the two files by net *code* (KiCad keeps codes stable between
two exports of the same schematic), but every operation is keyed by the clean
net *name*, so a spec can be applied to a freshly regenerated clean netlist even
if codes get reassigned.

The file header (source path, date) is intentionally left alone: it is
environment metadata, not part of the Trojan.

The command-line front end lives in ``netlist_trojans.cli``.
"""

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from simp_sexp import Sexp  # value parsing; the project already depends on it


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

@dataclass
class Node:
    ref: str
    pin: str
    pinfunction: Optional[str]
    pintype: str

    def key(self) -> Tuple[str, str]:
        """Physical identity of a node: which component pin it is."""
        return (self.ref, self.pin)

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "ref": self.ref,
            "pin": self.pin,
            "pinfunction": self.pinfunction,
            "pintype": self.pintype,
        }

    @staticmethod
    def from_dict(d: Dict[str, Optional[str]]) -> "Node":
        return Node(d["ref"], d["pin"], d.get("pinfunction"), d.get("pintype", "passive"))


@dataclass
class Net:
    code: str
    name: str
    net_class: str
    nodes: List[Node]
    start: int  # char offset of block start (after leading indent) in source
    end: int    # char offset just past the block's closing paren

    def node_set(self):
        return frozenset(n.key() for n in self.nodes)


def find_matching_paren(s: str, start: int) -> int:
    """Index of the ')' that closes the '(' at position `start`.

    Quote-aware: parens inside "double-quoted strings" are ignored, so a value
    such as "Resistor (0603)" does not throw the balance off.
    """
    if s[start] != "(":
        raise ValueError(f"Expected '(' at position {start}, got {s[start]!r}")
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"Unmatched parenthesis at position {start}")


# Structural locator only: finds where each (net ...) block starts so its byte
# span can be spliced. Value parsing is done by simp_sexp, not by regex.
_NET_OPEN_RE = re.compile(r"\(net\s")


def _sval(node: "Sexp", tag: str) -> Optional[str]:
    """Value of a single child tag, or None if the tag is absent."""
    res = node.search(f"/{node[0]}/{tag}")
    return str(res.value) if len(res) else None


def _net_spans(content: str) -> List[Tuple[int, int]]:
    """(start, end) byte span of every (net ...) block, in document order.

    simp_sexp gives us parsed values but no source offsets, so we still locate
    the blocks in the raw text to splice edits without reformatting the file.
    """
    nets_open = content.index("(nets")
    nets_end = find_matching_paren(content, nets_open)
    spans: List[Tuple[int, int]] = []
    pos = nets_open + 1
    while True:
        m = _NET_OPEN_RE.search(content, pos, nets_end)
        if not m:
            break
        start = m.start()
        end = find_matching_paren(content, start) + 1
        spans.append((start, end))
        pos = end  # resume past this block, never inside it
    return spans


def parse_nets(content: str) -> List[Net]:
    """Parse every (net ...) block into Net records, in document order.

    Values come from simp_sexp; source spans come from `_net_spans`. The two
    are zipped positionally (both are in document order).
    """
    sexp_nets = Sexp(content).search("/export/nets/net")
    spans = _net_spans(content)
    if len(sexp_nets) != len(spans):
        raise ValueError(
            f"net count mismatch: simp_sexp saw {len(sexp_nets)}, "
            f"text scan saw {len(spans)}")

    nets: List[Net] = []
    for sx, (start, end) in zip(sexp_nets, spans):
        nodes = [
            Node(
                ref=_sval(nd, "ref"),
                pin=_sval(nd, "pin"),
                pinfunction=_sval(nd, "pinfunction"),
                pintype=_sval(nd, "pintype") or "passive",
            )
            for nd in sx.search("/net/node")
        ]
        nets.append(
            Net(
                code=_sval(sx, "code"),
                name=_sval(sx, "name"),
                net_class=_sval(sx, "class"),
                nodes=nodes,
                start=start,
                end=end,
            )
        )
    return nets


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def render_net_block(code: str, name: str, net_class: str, nodes: List[Node],
                     indent: str = "    ") -> str:
    """Render a net block in KiCad's exact formatting (node = indent + 2)."""
    node_indent = indent + "  "
    out = f'{indent}(net (code "{code}") (name "{name}") (class "{net_class}")'
    lines = [out]
    for n in nodes:
        if n.pinfunction is not None:
            line = (f'{node_indent}(node (ref "{n.ref}") (pin "{n.pin}") '
                    f'(pinfunction "{n.pinfunction}") (pintype "{n.pintype}"))')
        else:
            line = (f'{node_indent}(node (ref "{n.ref}") (pin "{n.pin}") '
                    f'(pintype "{n.pintype}"))')
        lines.append(line)
    text = "\n".join(lines)
    # KiCad puts the net's closing paren on the last node's line.
    return text + ")"


def leading_indent(content: str, block_start: int) -> str:
    """The run of spaces/tabs immediately before a block on its line."""
    j = block_start
    while j > 0 and content[j - 1] in (" ", "\t"):
        j -= 1
    return content[j:block_start]


# --------------------------------------------------------------------------- #
# Parameter substitution
# --------------------------------------------------------------------------- #

# Placeholders look like ${CONN} — brace form only, so leftovers are detectable.
_PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def substitute(obj, mapping: Dict[str, str]):
    """Recursively replace ${VAR} in every string with mapping[VAR]."""
    if isinstance(obj, str):
        return _PLACEHOLDER_RE.sub(
            lambda m: mapping.get(m.group(1), m.group(0)), obj)
    if isinstance(obj, list):
        return [substitute(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: substitute(v, mapping) for k, v in obj.items()}
    return obj


def unresolved_placeholders(obj) -> List[str]:
    """Names of any ${VAR} placeholders still present after substitution."""
    found: List[str] = []

    def walk(o):
        if isinstance(o, str):
            found.extend(_PLACEHOLDER_RE.findall(o))
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)

    walk(obj)
    return sorted(set(found))


def parameterize_refs(ops: List[dict], ref_to_var: Dict[str, str]) -> None:
    """In-place: replace node `ref` values equal to a key with ${VAR}."""
    def fix_nodes(node_list):
        for nd in node_list:
            if nd.get("ref") in ref_to_var:
                nd["ref"] = "${" + ref_to_var[nd["ref"]] + "}"

    for op in ops:
        for key in ("set_nodes", "expect_nodes", "nodes"):
            if key in op:
                fix_nodes(op[key])


# --------------------------------------------------------------------------- #
# Extract
# --------------------------------------------------------------------------- #

def nodes_equal(a: List[Node], b: List[Node]) -> bool:
    return [n.as_dict() for n in a] == [n.as_dict() for n in b]


def extract_spec(clean_path: str, infected_path: str,
                 label: Optional[str] = None,
                 params: Optional[Dict[str, str]] = None) -> dict:
    clean = parse_nets(read(clean_path))
    infected = parse_nets(read(infected_path))

    clean_by_code = {n.code: n for n in clean}
    infected_by_code = {n.code: n for n in infected}
    clean_names = {n.name for n in clean}

    ops: List[dict] = []

    # Nets present in both: detect rename / class change / rewire.
    for code, cnet in clean_by_code.items():
        inet = infected_by_code.get(code)
        if inet is None:
            continue
        op: dict = {"type": "modify_net", "net": cnet.name}
        changed = False
        if inet.name != cnet.name:
            op["rename"] = inet.name
            changed = True
        if inet.net_class != cnet.net_class:
            op["set_class"] = {"from": cnet.net_class, "to": inet.net_class}
            changed = True
        if not nodes_equal(cnet.nodes, inet.nodes):
            op["set_nodes"] = [n.as_dict() for n in inet.nodes]
            op["expect_nodes"] = [n.as_dict() for n in cnet.nodes]
            changed = True
        if changed:
            ops.append(op)

    # Nets only in the infected file: additions.
    for code, inet in infected_by_code.items():
        if code not in clean_by_code:
            ops.append({
                "type": "add_net",
                "code": inet.code,
                "name": inet.name,
                "class": inet.net_class,
                "nodes": [n.as_dict() for n in inet.nodes],
            })

    # Nets only in the clean file: removals (matched by name at apply time).
    for code, cnet in clean_by_code.items():
        if code not in infected_by_code:
            ops.append({"type": "remove_net", "net": cnet.name})

    # Turn chosen component refs into ${VAR} placeholders with default values,
    # so the spec still reproduces this sample but can be retargeted at apply.
    param_defaults: Dict[str, str] = {}
    if params:
        parameterize_refs(ops, params)          # params: {old_ref: VAR}
        for old_ref, var in params.items():
            param_defaults[var] = old_ref        # spec stores {VAR: default}

    spec = {
        "meta": {
            "label": label or "",
            "clean_source": os.path.abspath(clean_path),
            "infected_source": os.path.abspath(infected_path),
            "tool": "netlist_trojan.py",
        },
        "ops": ops,
    }
    if param_defaults:
        spec["params"] = param_defaults
    return spec


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #

def apply_spec(clean_content: str, spec: dict, strict: bool = False,
               overrides: Optional[Dict[str, str]] = None) -> Tuple[str, List[str]]:
    """Return (infected_content, log). Edits are spliced back to front."""
    # Resolve ${VAR} placeholders: spec defaults, then --set overrides win.
    mapping = dict(spec.get("params", {}))
    if overrides:
        mapping.update(overrides)
    spec = substitute(spec, mapping)
    missing = unresolved_placeholders(spec.get("ops", []))
    if missing:
        raise KeyError(
            "unresolved parameter(s): " + ", ".join(missing)
            + " — pass them with --set NAME=VALUE")

    nets = parse_nets(clean_content)
    by_name: Dict[str, Net] = {}
    for n in nets:
        by_name.setdefault(n.name, n)  # first wins on the rare duplicate name

    log: List[str] = []
    edits: List[Tuple[int, int, str]] = []  # (start, end, replacement)

    for op in spec.get("ops", []):
        kind = op["type"]

        if kind in ("modify_net", "remove_net"):
            name = op["net"]
            net = by_name.get(name)
            if net is None:
                msg = f"SKIP {kind}: net {name!r} not found in clean netlist"
                if strict:
                    raise KeyError(msg)
                log.append(msg)
                continue

            if kind == "remove_net":
                # Drop the block and the newline that precedes it.
                start = net.start
                while start > 0 and clean_content[start - 1] in (" ", "\t"):
                    start -= 1
                if start > 0 and clean_content[start - 1] == "\n":
                    start -= 1
                edits.append((start, net.end, ""))
                log.append(f"remove_net: {name}")
                continue

            indent = leading_indent(clean_content, net.start)

            if "set_nodes" in op:
                # Node list changed -> rebuild the whole block for exactness.
                if "expect_nodes" in op and not strict:
                    got = [n.as_dict() for n in net.nodes]
                    if got != op["expect_nodes"]:
                        log.append(
                            f"WARN modify_net {name}: current nodes differ from the "
                            f"spec's expected clean nodes (applying anyway)"
                        )
                new_name = op.get("rename", name)
                new_class = op.get("set_class", {}).get("to", net.net_class)
                new_nodes = [Node.from_dict(d) for d in op["set_nodes"]]
                block = render_net_block(net.code, new_name, new_class, new_nodes, indent)
                # net.start points at '(net'; the rendered block re-emits the
                # leading indent, so splice over that indent too.
                edits.append((net.start - len(indent), net.end, block))
                detail = []
                if "rename" in op:
                    detail.append(f"rename->{new_name}")
                if "set_class" in op:
                    detail.append(f"class->{new_class}")
                detail.append("rewire nodes")
                log.append(f"modify_net: {name} ({', '.join(detail)})")
            else:
                # Header-only change: surgical string swaps, node block untouched.
                header_end = clean_content.index("\n", net.start)
                header = clean_content[net.start:header_end]
                new_header = header
                detail = []
                if "rename" in op:
                    new_header = new_header.replace(
                        f'(name "{name}")', f'(name "{op["rename"]}")', 1)
                    detail.append(f"rename->{op['rename']}")
                if "set_class" in op:
                    frm = op["set_class"]["from"]
                    to = op["set_class"]["to"]
                    new_header = new_header.replace(
                        f'(class "{frm}")', f'(class "{to}")', 1)
                    detail.append(f"class {frm}->{to}")
                if new_header != header:
                    edits.append((net.start, header_end, new_header))
                    log.append(f"modify_net: {name} ({', '.join(detail)})")

        elif kind == "add_net":
            # Append a new net just before the closing paren of (nets ...).
            block = render_net_block(
                op["code"], op["name"], op["class"],
                [Node.from_dict(d) for d in op["nodes"]], indent="    ")
            anchor = nets[-1] if nets else None
            if anchor is not None:
                edits.append((anchor.end, anchor.end, "\n" + block))
                log.append(f"add_net: {op['name']}")
            else:
                log.append(f"SKIP add_net {op['name']}: no anchor net found")

        elif kind == "split_net":
            # "Snip a trace": partition one net's nodes into two (or more) new
            # nets. The first side reuses the original code; the rest get fresh
            # codes (max existing + 1, +2, ...).
            name = op["net"]
            net = by_name.get(name)
            if net is None:
                msg = f"SKIP split_net: net {name!r} not found in clean netlist"
                if strict:
                    raise KeyError(msg)
                log.append(msg)
                continue

            indent = leading_indent(clean_content, net.start)
            by_key = {f"{nd.ref}.{nd.pin}": nd for nd in net.nodes}
            existing = [int(n.code) for n in nets if n.code.isdigit()]
            next_code = (max(existing) + 1) if existing else 1

            rendered: List[str] = []
            used: set = set()
            for gi, group in enumerate(op["into"]):
                gnodes: List[Node] = []
                for k in group["nodes"]:
                    if k not in by_key:
                        raise ValueError(
                            f"split_net {name}: node {k!r} is not on this net "
                            f"(has: {sorted(by_key)})")
                    if k in used:
                        raise ValueError(
                            f"split_net {name}: node {k!r} assigned to two sides")
                    used.add(k)
                    gnodes.append(by_key[k])
                code = net.code if gi == 0 else str(next_code)
                if gi != 0:
                    next_code += 1
                gclass = group.get("class", net.net_class)
                rendered.append(
                    render_net_block(code, group["name"], gclass, gnodes, indent))

            leftover = [k for k in by_key if k not in used]
            if leftover:
                raise ValueError(
                    f"split_net {name}: these nodes were not assigned to any "
                    f"side: {leftover}")

            replacement = rendered[0] + "".join("\n" + r for r in rendered[1:])
            edits.append((net.start - len(indent), net.end, replacement))
            log.append(
                f"split_net: {name} -> "
                + ", ".join(g["name"] for g in op["into"]))

        else:
            log.append(f"SKIP unknown op type {kind!r}")

    # Splice edits back-to-front so offsets stay valid.
    content = clean_content
    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        content = content[:start] + replacement + content[end:]

    return content, log


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #

def read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def describe_op(op: dict) -> str:
    """One-line human summary of a spec operation (used by the CLI)."""
    t = op["type"]
    if t == "modify_net":
        bits = []
        if "rename" in op:
            bits.append(f"rename {op['net']} -> {op['rename']}")
        if "set_class" in op:
            bits.append(f"class {op['set_class']['from']} -> {op['set_class']['to']}")
        if "set_nodes" in op:
            bits.append("rewire nodes")
        return f"modify {op['net']}: " + "; ".join(bits)
    if t == "add_net":
        return f"add net {op['name']}"
    if t == "remove_net":
        return f"remove net {op['net']}"
    if t == "split_net":
        return f"split {op['net']} -> " + ", ".join(g["name"] for g in op["into"])
    return t
