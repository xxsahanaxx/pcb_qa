#!/usr/bin/env python3
"""
Confusion matrix and binary-classification metrics for the anomaly-detection
results graded by netlist_modifications/scripts/grade_anomaly_results.py.

Reads ``grades.csv`` at the prompts root and treats each (model, prompt) row as
one binary decision:

- **actual positive**  - the prompt's board really carries an injected fault
  (``expected_anomaly``); the clean controls are the actual negatives.
- **predicted positive** - what counts as the model "saying yes", chosen with
  ``--positive-rule``:

  - ``detected`` (default): the model reported an anomaly at all
    (``anomaly_detected``). This is the literal yes/no question the prompt asks.
  - ``localised``: the model named the right fault (``localised``). Stricter -
    a vague "something looks wrong" scores as a negative. Note this can only
    ever be true for faulty prompts, so on the controls it is identical to
    ``detected``.

Unanswered results (``incomplete``, ``unparsed``, ``api_error``) are *not*
dropped: they are counted as a predicted negative, matching the grader, which
keeps them in every denominator. ``--drop-unanswered`` excludes them instead,
which measures the model on the answers it managed to return.

Outputs one tidy CSV, one row per model plus a ``POOLED`` row over all of them:
tp/fp/fn/tn, then accuracy, precision, recall (sensitivity), specificity, npv,
f1, balanced accuracy, mcc and prevalence. A readable matrix goes to stdout.

Metrics whose denominator is zero are written as empty cells, never 0.

Run from the repo root:
    .venv/bin/python netlist_modifications/scripts/binary_metrics.py
        [--root DIR] [--board fan_controller] [--models a/x,b/y]
        [--positive-rule detected|localised] [--drop-unanswered] [--out FILE]
"""

import argparse
import csv
import math
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = "outputs/Infected/Prompts/AnomalyDetection"
ANSWERED = {"ok", "repaired"}
FIELDS = ["model", "n", "tp", "fp", "fn", "tn", "unanswered", "prevalence",
          "accuracy", "precision", "recall", "specificity", "npv", "f1",
          "balanced_accuracy", "mcc"]


def truthy(v: str) -> bool:
    return (v or "").strip().lower() in ("true", "1", "yes")


def div(num: float, den: float):
    """Metric value, or None when undefined (zero denominator)."""
    return None if den == 0 else num / den


def mcc(tp: int, fp: int, fn: int, tn: int):
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return None if den == 0 else ((tp * tn) - (fp * fn)) / den


def metrics(tp: int, fp: int, fn: int, tn: int, unanswered: int) -> dict:
    n = tp + fp + fn + tn
    recall = div(tp, tp + fn)
    spec = div(tn, tn + fp)
    prec = div(tp, tp + fp)
    f1 = None
    if prec is not None and recall is not None and (prec + recall) > 0:
        f1 = 2 * prec * recall / (prec + recall)
    bal = None
    if recall is not None and spec is not None:
        bal = (recall + spec) / 2
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "unanswered": unanswered,
        "prevalence": div(tp + fn, n),
        "accuracy": div(tp + tn, n),
        "precision": prec, "recall": recall, "specificity": spec,
        "npv": div(tn, tn + fn), "f1": f1,
        "balanced_accuracy": bal, "mcc": mcc(tp, fp, fn, tn),
    }


def fmt(v, places=4) -> str:
    if v is None:
        return ""
    return f"{v:.{places}f}"


def tally(rows, rule: str, drop_unanswered: bool):
    tp = fp = fn = tn = unanswered = 0
    for r in rows:
        answered = r["status"] in ANSWERED
        if not answered:
            unanswered += 1
            if drop_unanswered:
                continue
        actual = truthy(r["expected_anomaly"])
        # An unanswered result predicts nothing; score it as a negative.
        if not answered:
            pred = False
        elif rule == "localised" and actual:
            pred = truthy(r["localised"])
        else:
            pred = truthy(r["anomaly_detected"])
        if actual and pred:
            tp += 1
        elif actual and not pred:
            fn += 1
        elif not actual and pred:
            fp += 1
        else:
            tn += 1
    return tp, fp, fn, tn, unanswered


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", default=DEFAULT_OUT, help=f"Prompts root (default: {DEFAULT_OUT})")
    p.add_argument("--board", help="Keep only this board (default: all)")
    p.add_argument("--models", help="Comma list of models (default: all in grades.csv)")
    p.add_argument("--positive-rule", choices=["detected", "localised"], default="detected",
                   help="What counts as a positive prediction (default: detected)")
    p.add_argument("--drop-unanswered", action="store_true",
                   help="Exclude unanswered results instead of scoring them as negatives")
    p.add_argument("--out", help="Output CSV (default: <root>/binary_metrics[_<board>].csv)")
    args = p.parse_args(argv)

    os.chdir(REPO_ROOT)
    grades = os.path.join(args.root, "grades.csv")
    if not os.path.exists(grades):
        print(f"No grades.csv at {grades}; run grade_anomaly_results.py first.", file=sys.stderr)
        return 1

    with open(grades) as f:
        rows = list(csv.DictReader(f))
    if args.board:
        rows = [r for r in rows if r["board"] == args.board]
    if args.models:
        keep = set(args.models.split(","))
        rows = [r for r in rows if r["model"] in keep]
    if not rows:
        print("No rows matched --board/--models.", file=sys.stderr)
        return 1

    models = sorted({r["model"] for r in rows})
    out_rows = []
    for m in models:
        tp, fp, fn, tn, un = tally([r for r in rows if r["model"] == m],
                                   args.positive_rule, args.drop_unanswered)
        out_rows.append({"model": m, **metrics(tp, fp, fn, tn, un)})
    tp, fp, fn, tn, un = tally(rows, args.positive_rule, args.drop_unanswered)
    out_rows.append({"model": "POOLED", **metrics(tp, fp, fn, tn, un)})

    out = args.out or os.path.join(
        args.root, f"binary_metrics{'_' + args.board if args.board else ''}.csv")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in out_rows:
            w.writerow({k: (r[k] if k in ("model", "n", "tp", "fp", "fn", "tn", "unanswered")
                            else fmt(r[k])) for k in FIELDS})

    scope = args.board or "all boards"
    print(f"Binary classification - {scope}, positive = {args.positive_rule}"
          f"{', unanswered dropped' if args.drop_unanswered else ', unanswered = negative'}\n")
    for r in out_rows:
        print(f"{r['model']}  (n={r['n']}, unanswered={r['unanswered']})")
        print(f"                 pred +   pred -")
        print(f"   actual +      {r['tp']:>6}   {r['fn']:>6}")
        print(f"   actual -      {r['fp']:>6}   {r['tn']:>6}")
        print(f"   acc={fmt(r['accuracy'],3)}  prec={fmt(r['precision'],3)}  "
              f"recall={fmt(r['recall'],3)}  spec={fmt(r['specificity'],3)}  "
              f"f1={fmt(r['f1'],3)}  bal_acc={fmt(r['balanced_accuracy'],3)}  "
              f"mcc={fmt(r['mcc'],3)}\n")

    neg = out_rows[-1]["tn"] + out_rows[-1]["fp"]
    per = neg / len(models) if models else 0
    if per < 5:
        print(f"WARNING: only {per:.0f} actual negative(s) (clean control) per model. "
              "Precision, specificity, NPV, F1, balanced accuracy and MCC all depend on "
              "the negative class and are not meaningful at this sample size. Recall is "
              "the only robust figure here. Build more controls to fix this.", file=sys.stderr)
    print(f"{len(out_rows)} row(s) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
