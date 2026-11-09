#!/usr/bin/env python3
"""
Grade the anomaly-detection results (written by netlist_modifications/scripts/run_anomaly_prompts.py)
against answer_key.jsonl (written by netlist_modifications/scripts/build_anomaly_prompts.py).

Per result, the grader records:

- ``status``: ``ok``, ``repaired`` (malformed JSON recovered by removing stray
  closing brackets), ``incomplete`` (cut off at the output limit), ``unparsed``
  or ``api_error``. Anything but ok/repaired scores as a wrong answer: it is
  kept in every denominator, never dropped.
- ``verdict_correct``: ``anomaly_detected`` matches the key (true on faulty
  prompts, false on the clean controls).
- ``category_hit``: some finding has the expected category.
- ``localised`` (the headline score): a *single* finding has the expected
  category and names the fault. For shorts and bridges that is any part on
  the affected net(s) (``net_components``) or the affected signal net itself;
  for part swaps, value and tolerance faults it must be the modified part.
- ``localised_top1``: the same, for the model's first (most confident) finding.
- ``baseline_only``: every finding only repeats parts the same model flagged on
  that board's clean control, i.e. a standing complaint about the board, not a
  detection of the injected fault.

Outputs, at the prompts root:
    grades.csv          one row per (model, prompt)
    grade_summary.json  per-model totals, plus per-model x scenario and x board
    grade_summary.md    the same as Markdown tables

Run from the repo root:
    .venv/bin/python netlist_modifications/scripts/grade_anomaly_results.py [--root DIR] [--models a/x,b/y]
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

from netlist_modifications.scripts.build_anomaly_prompts import DEFAULT_OUT  # noqa: E402

# faults on one part: a finding must name that part (its nets are shared by many)
COMPONENT_FAULTS = {"wrong_component_type", "wrong_value", "wrong_tolerance", "polarity"}
_RAIL_RE = re.compile(r"^(GND|\+|VCC|VDD|VBUS|VBAT|VIN|VREF)", re.I)


# --------------------------------------------------------------------------- #
# Reading a result
# --------------------------------------------------------------------------- #

def repair_json(text: str):
    """Parse `text` as JSON, removing stray ']' / '}' the parser trips on
    (e.g. ``}]], "summary"`` for ``}], "summary"``). Returns (obj, repaired)."""
    body = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", (text or "").strip())
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None, False
    body = body[start:end + 1]
    for attempt in range(20):
        try:
            return json.loads(body), attempt > 0
        except json.JSONDecodeError as exc:
            pos = exc.pos
            # the offending bracket is at the error position or just before it
            for i in (pos, pos - 1):
                if 0 <= i < len(body) and body[i] in "]}":
                    body = body[:i] + body[i + 1:]
                    break
            else:
                # trailing junk after a complete object
                if "Extra data" in exc.msg:
                    body = body[:pos]
                    continue
                return None, False
    return None, False


def read_verdict(rec: dict):
    """(status, verdict dict or None) for one saved result."""
    if rec.get("error"):
        return "api_error", None
    resp = rec.get("response") or {}
    if resp.get("parsed") is not None:
        return "ok", resp["parsed"]
    if resp.get("finish_reason") == "length":
        return "incomplete", None
    obj, repaired = repair_json(resp.get("text") or "")
    if obj is not None:
        return ("repaired" if repaired else "ok"), obj
    return "unparsed", None


# --------------------------------------------------------------------------- #
# Matching a finding against the key
# --------------------------------------------------------------------------- #

def _norm_ref(r) -> str:
    return str(r).strip().upper()


def _norm_net(n) -> str:
    return str(n).strip().lstrip("/").upper()


def finding_parts(a: dict) -> set:
    refs = {_norm_ref(c) for c in a.get("components") or []}
    refs |= {_norm_ref(str(p).split(".", 1)[0]) for p in a.get("pins") or []}
    return {r for r in refs if r}


def matches_fault(a: dict, key: dict) -> bool:
    """Whether one finding has the expected category and names the fault."""
    if a.get("category") != key["category"]:
        return False
    parts = finding_parts(a)
    target = {_norm_ref(c) for c in key.get("net_components") or key.get("components") or []}
    if parts & target:
        return True
    if key["category"] in COMPONENT_FAULTS:
        return False  # a passive's nets are shared with many parts: name the part
    # shorts / bridges: naming the affected signal net also counts (not GND / rails)
    nets = {_norm_net(n) for n in a.get("nets") or []}
    want = {_norm_net(n) for n in key.get("nets") or [] if not _RAIL_RE.match(str(n).lstrip("/"))}
    return bool(nets & want)


# --------------------------------------------------------------------------- #
# Grading
# --------------------------------------------------------------------------- #

def grade(root: str, models_filter=None) -> list:
    with open(os.path.join(root, "answer_key.jsonl")) as f:
        key = {r["id"]: r for r in map(json.loads, f)}

    raw = []  # (model, pid, rec)
    for path in sorted(glob.glob(os.path.join(root, "*", "*", "results", "*.json"))):
        pid = os.path.relpath(os.path.dirname(os.path.dirname(path)), root)
        if pid not in key:
            continue
        with open(path) as f:
            rec = json.load(f)
        if models_filter and rec.get("model") not in models_filter:
            continue
        raw.append((rec.get("model"), pid, rec))

    # what each model flags on each board's clean control (its standing complaints)
    baseline = defaultdict(set)
    for model, pid, rec in raw:
        if key[pid]["anomaly"] is False:
            _, v = read_verdict(rec)
            for a in (v or {}).get("anomalies") or []:
                baseline[(model, key[pid]["board"])] |= finding_parts(a)

    rows = []
    for model, pid, rec in raw:
        k = key[pid]
        status, v = read_verdict(rec)
        answered = v is not None
        findings = (v or {}).get("anomalies") or []
        detected = (v or {}).get("anomaly_detected") is True
        base = baseline.get((model, k["board"]), set())
        non_baseline = [a for a in findings if not (finding_parts(a) and finding_parts(a) <= base)]
        u = rec.get("usage") or {}
        row = {
            "model": model, "id": pid, "board": k["board"], "scenario": k["scenario"],
            "variant": k["variant"], "expected_anomaly": k["anomaly"],
            "expected_category": k["category"], "status": status,
            "anomaly_detected": (v or {}).get("anomaly_detected") if answered else None,
            "confidence": (v or {}).get("confidence") if answered else None,
            "verdict_correct": answered and detected == k["anomaly"],
            "categories": ";".join(str(a.get("category")) for a in findings),
            "components": ";".join(sorted({c for a in findings for c in finding_parts(a)})),
            "n_findings": len(findings),
            "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": u.get("reasoning_tokens"), "cost_usd": u.get("cost_usd"),
            "latency_s": (rec.get("timing") or {}).get("latency_s"),
        }
        if k["anomaly"]:
            row.update({
                "category_hit": any(a.get("category") == k["category"] for a in findings),
                "localised": any(matches_fault(a, k) for a in findings),
                "localised_top1": bool(findings) and matches_fault(findings[0], k),
                "baseline_only": detected and bool(findings) and not non_baseline,
                "detected_beyond_baseline": detected and bool(non_baseline),
            })
        else:
            row.update({"category_hit": None, "localised": None, "localised_top1": None,
                        "baseline_only": None, "detected_beyond_baseline": None})
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #

def _rate(n, d):
    return round(n / d, 3) if d else None


def summarise(rows: list) -> dict:
    faulty = [r for r in rows if r["expected_anomaly"]]
    ctrl = [r for r in rows if not r["expected_anomaly"]]
    statuses = defaultdict(int)
    for r in rows:
        statuses[r["status"]] += 1
    nf = len(faulty)
    return {
        "results": len(rows), "faulty": nf, "controls": len(ctrl),
        "status": dict(statuses),
        "detection_rate": _rate(sum(r["anomaly_detected"] is True for r in faulty), nf),
        "detection_beyond_baseline": _rate(sum(bool(r["detected_beyond_baseline"]) for r in faulty), nf),
        "baseline_only_rate": _rate(sum(bool(r["baseline_only"]) for r in faulty), nf),
        "category_rate": _rate(sum(bool(r["category_hit"]) for r in faulty), nf),
        "localisation_rate": _rate(sum(bool(r["localised"]) for r in faulty), nf),
        "localisation_top1_rate": _rate(sum(bool(r["localised_top1"]) for r in faulty), nf),
        "false_alarm_rate": _rate(sum(r["anomaly_detected"] is True for r in ctrl), len(ctrl)),
        "controls_unanswered": sum(r["anomaly_detected"] is None for r in ctrl),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 4),
        "completion_tokens": sum(r["completion_tokens"] or 0 for r in rows),
    }


def group(rows: list, field: str) -> dict:
    out = defaultdict(list)
    for r in rows:
        out[r[field]].append(r)
    return out


def _pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def to_markdown(summary: dict) -> str:
    lines = ["# Anomaly-detection grades", "",
             "Localisation = one finding with the expected category that names the fault "
             "(for shorts/bridges any part on the affected net, or the net itself). "
             "Unanswered results (incomplete, unparsed, API error) count as wrong.", "",
             "## By model", "",
             "| Model | Results | Not answered | Detection | Beyond baseline | Category | "
             "**Localisation** | Top-1 | False alarms | Cost |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for m, s in summary["by_model"].items():
        bad = sum(v for k, v in s["status"].items() if k not in ("ok", "repaired"))
        lines.append(f"| {m} | {s['results']} | {bad} | {_pct(s['detection_rate'])} | "
                     f"{_pct(s['detection_beyond_baseline'])} | {_pct(s['category_rate'])} | "
                     f"**{_pct(s['localisation_rate'])}** | {_pct(s['localisation_top1_rate'])} | "
                     f"{_pct(s['false_alarm_rate'])} ({s['controls']}) | ${s['cost_usd']:.3f} |")
    for title, field in (("By scenario (localisation)", "by_model_scenario"),
                         ("By board (localisation)", "by_model_board")):
        cols = sorted({c for per in summary[field].values() for c in per})
        lines += ["", f"## {title}", "", "| Model | " + " | ".join(cols) + " |",
                  "|---|" + "---|" * len(cols)]
        for m, per in summary[field].items():
            cells = []
            for c in cols:
                s = per.get(c)
                if not s or not s["faulty"]:
                    cells.append("–")
                else:
                    n = round((s["localisation_rate"] or 0) * s["faulty"])
                    cells.append(f"{n}/{s['faulty']}")
            lines.append(f"| {m} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", default=DEFAULT_OUT, help=f"Prompts root (default: {DEFAULT_OUT})")
    p.add_argument("--models", help="Comma list of models to grade (default: all with results)")
    args = p.parse_args(argv)
    os.chdir(REPO_ROOT)

    rows = grade(args.root, set(args.models.split(",")) if args.models else None)
    if not rows:
        print("no results to grade")
        return 1

    with open(os.path.join(args.root, "grades.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    by_model = group(rows, "model")
    summary = {
        "by_model": {m: summarise(rs) for m, rs in sorted(by_model.items())},
        "by_model_scenario": {m: {sc: summarise(x) for sc, x in sorted(group(rs, "scenario").items())
                                  if sc != "Control"} for m, rs in sorted(by_model.items())},
        "by_model_board": {m: {b: summarise(x) for b, x in sorted(group(rs, "board").items())}
                           for m, rs in sorted(by_model.items())},
    }
    with open(os.path.join(args.root, "grade_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    md = to_markdown(summary)
    with open(os.path.join(args.root, "grade_summary.md"), "w") as f:
        f.write(md)
    print(md)
    print(f"{len(rows)} result(s) graded -> grades.csv, grade_summary.json, grade_summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
