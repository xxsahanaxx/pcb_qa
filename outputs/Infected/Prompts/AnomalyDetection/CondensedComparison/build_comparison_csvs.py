#!/usr/bin/env python3
"""
Build the derived CSVs for the condensed-vs-raw netlist comparison.

Consumes, from the RQ1 prompts root (``../RQ1_SimpleMods`` by default):
  - ``grades.csv``            the base arm, graded
  - ``grades_condensed.csv``  the condensed arm, graded
  - ``csv/arm_comparison_*.csv``      from compare_arms.py
  - ``csv/binary_<board>_<arm>_<rule>.csv``  from binary_metrics.py

Writes, into ``csv/``:
  - ``binary_metrics_combined.csv``       tidy master: board x arm x rule x model
  - ``confusion_deltas.csv``              base vs condensed, side by side + deltas
  - ``mcnemar_paired_flips.csv``          won/lost/tied + exact McNemar p
  - ``scenario_family_localisation.csv``  per fault family
  - ``flip_ledger.csv``                   every pair that changed between arms
  - ``cost_tokens.csv``                   tokens, cost, latency, unanswered
  - ``representation_size.csv``           netlist bytes, prompt tokens, validation

The upstream ``binary_*`` and ``arm_comparison_*`` CSVs are *not* regenerated
here; run the two scripts in README.md "Reproducing" first. This only builds
what is derived from them.

Run from this directory, or anywhere with --root:
    .venv/bin/python outputs/Infected/Prompts/AnomalyDetection/CondensedComparison/build_comparison_csvs.py
"""

import argparse
import collections
import csv
import glob
import importlib.util
import os
import re
import statistics
import sys
from math import comb

RQ1_DIR = "RQ1_SimpleMods"
BOARDS = ["AcornRobotElectronics", "fan_controller"]
ARMS = ["base", "condensed"]
RULES = ["detected", "localised"]
MET = ["n", "tp", "fp", "fn", "tn", "unanswered", "prevalence", "accuracy",
       "precision", "recall", "specificity", "npv", "f1", "balanced_accuracy", "mcc"]
COUNTS = ["tp", "fp", "fn", "tn", "unanswered"]
RATES = ["accuracy", "precision", "recall", "specificity", "npv", "f1",
         "balanced_accuracy", "mcc"]
# The tokenizer used for the single-model prompt-size figures in the write-up.
SIZE_MODEL = "openai/gpt-6-luna"


def truthy(v) -> bool:
    return (v or "").strip().lower() in ("true", "1", "yes")


def mcnemar_exact(won: int, lost: int) -> float:
    """Two-sided exact McNemar (sign test on the discordant pairs)."""
    n = won + lost
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(won, lost) + 1))
    return min(1.0, 2 * tail / 2 ** n)


def write(path, rows, order=None):
    if not rows:
        print(f"  skip {os.path.basename(path)} (no rows)", file=sys.stderr)
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=order or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  {os.path.basename(path):<36}{len(rows):>4} rows")


def load_pairs(root):
    """{(model, id): row} for each arm, restricted to the two boards."""
    def one(name):
        path = os.path.join(root, name)
        if not os.path.exists(path):
            sys.exit(f"missing {path}; grade that arm first")
        return {(r["model"], r["id"]): r for r in csv.DictReader(open(path))
                if r["board"] in BOARDS}
    base, cond = one("grades.csv"), one("grades_condensed.csv")
    keys = sorted(set(base) & set(cond))
    if not keys:
        sys.exit("no (model, prompt) pairs present in both arms")
    only = len(set(base) ^ set(cond))
    if only:
        print(f"note: {only} pair(s) in one arm only; using the "
              f"{len(keys)} matched pairs.", file=sys.stderr)
    return base, cond, keys


# --------------------------------------------------------------------------- #

def binary_tables(csvdir):
    """binary_metrics_combined.csv + confusion_deltas.csv"""
    store, rows = {}, []
    for b in BOARDS:
        for a in ARMS:
            for r in RULES:
                p = os.path.join(csvdir, f"binary_{b}_{a}_{r}.csv")
                if not os.path.exists(p):
                    sys.exit(f"missing {p}; run binary_metrics.py first "
                             f"(see README.md 'Reproducing')")
                for x in csv.DictReader(open(p)):
                    store[(b, a, r, x["model"])] = x
                    rows.append({"board": b, "arm": a, "positive_rule": r,
                                 "model": x["model"], **{k: x[k] for k in MET}})
    write(os.path.join(csvdir, "binary_metrics_combined.csv"), rows,
          ["board", "arm", "positive_rule", "model"] + MET)

    drows = []
    for b in BOARDS:
        for r in RULES:
            models = sorted({k[3] for k in store if k[0] == b and k[2] == r},
                            key=lambda s: (s == "POOLED", s))
            for m in models:
                x, y = store[(b, "base", r, m)], store[(b, "condensed", r, m)]
                rec = {"board": b, "positive_rule": r, "model": m, "n": x["n"]}
                for k in COUNTS:
                    rec[f"{k}_base"], rec[f"{k}_condensed"] = x[k], y[k]
                    rec[f"{k}_delta"] = int(y[k]) - int(x[k])
                for k in RATES:
                    rec[f"{k}_base"], rec[f"{k}_condensed"] = x[k], y[k]
                    rec[f"{k}_delta"] = (f"{float(y[k]) - float(x[k]):.4f}"
                                         if x[k] and y[k] else "")
                drows.append(rec)
    write(os.path.join(csvdir, "confusion_deltas.csv"), drows)


def mcnemar_table(csvdir, base, cond, keys):
    groups = collections.defaultdict(list)
    for k in keys:
        b = base[k]["board"]
        for g in ((b, k[0]), (b, "POOLED"), ("BOTH", k[0]), ("BOTH", "POOLED")):
            groups[g].append(k)
        # deepseek truncates on 23-42% of prompts and those score as negatives,
        # so report the pooled rates without it as a sensitivity check.
        if "deepseek" not in k[0]:
            groups[(b, "POOLED_EXCL_DEEPSEEK")].append(k)
            groups[("BOTH", "POOLED_EXCL_DEEPSEEK")].append(k)
    rows = []
    for (b, m), ks in sorted(groups.items()):
        n = len(ks)
        for field, label in (("localised", "localised"),
                             ("anomaly_detected", "detected")):
            won = sum(1 for k in ks if truthy(cond[k][field]) and not truthy(base[k][field]))
            lost = sum(1 for k in ks if truthy(base[k][field]) and not truthy(cond[k][field]))
            rb = sum(truthy(base[k][field]) for k in ks)
            rc = sum(truthy(cond[k][field]) for k in ks)
            rows.append({"board": b, "model": m, "metric": label, "pairs": n,
                         "won": won, "lost": lost, "tied": n - won - lost,
                         "rate_base": f"{rb / n:.4f}",
                         "rate_condensed": f"{rc / n:.4f}",
                         "delta_pp": f"{(rc - rb) / n * 100:+.1f}",
                         "flip_rate": f"{(won + lost) / n:.4f}",
                         "mcnemar_exact_p": f"{mcnemar_exact(won, lost):.4f}"})
    write(os.path.join(csvdir, "mcnemar_paired_flips.csv"), rows)


def scenario_table(csvdir, base, cond, keys):
    fam = collections.defaultdict(collections.Counter)
    for k in keys:
        b = base[k]["board"]
        # Strip the per-instance suffix: GndShortRandom_Wire2 -> GndShortRandom
        s = re.sub(r"(Random)?_(Wire|Value|Swap|Tolerance|Flip)\d+$", "",
                   base[k]["scenario"])
        d = fam[(b, s)]
        d["n"] += 1
        lb, lc = truthy(base[k]["localised"]), truthy(cond[k]["localised"])
        d["lb"] += lb
        d["lc"] += lc
        d["db"] += truthy(base[k]["anomaly_detected"])
        d["dc"] += truthy(cond[k]["anomaly_detected"])
        d["won"] += lc and not lb
        d["lost"] += lb and not lc
        d["flips"] += lb != lc
    rows = []
    for (b, s), d in sorted(fam.items()):
        n = d["n"]
        rows.append({"board": b, "scenario_family": s, "pairs": n,
                     "localised_base": f"{d['lb'] / n:.4f}",
                     "localised_condensed": f"{d['lc'] / n:.4f}",
                     "localised_delta_pp": f"{(d['lc'] - d['lb']) / n * 100:+.1f}",
                     "detected_base": f"{d['db'] / n:.4f}",
                     "detected_condensed": f"{d['dc'] / n:.4f}",
                     "won": d["won"], "lost": d["lost"], "flips": d["flips"],
                     "flip_rate": f"{d['flips'] / n:.4f}"})
    write(os.path.join(csvdir, "scenario_family_localisation.csv"), rows)


def flip_ledger(csvdir, base, cond, keys):
    rows = []
    for k in keys:
        lb, lc = truthy(base[k]["localised"]), truthy(cond[k]["localised"])
        db, dc = truthy(base[k]["anomaly_detected"]), truthy(cond[k]["anomaly_detected"])
        if lb == lc and db == dc and base[k]["status"] == cond[k]["status"]:
            continue
        rows.append({"board": base[k]["board"], "model": k[0], "id": k[1],
                     "scenario": base[k]["scenario"],
                     "localised_base": lb, "localised_condensed": lc,
                     "localisation_change": "won" if (lc and not lb)
                                            else ("lost" if (lb and not lc) else ""),
                     "detected_base": db, "detected_condensed": dc,
                     "status_base": base[k]["status"],
                     "status_condensed": cond[k]["status"]})
    write(os.path.join(csvdir, "flip_ledger.csv"), rows)


def cost_table(csvdir):
    src = [("AcornRobotElectronics", "arm_comparison_AcornRobotElectronics.csv"),
           ("fan_controller", "arm_comparison_fan_controller.csv"),
           ("BOTH", "arm_comparison_both_boards.csv")]
    rows = []
    for b, f in src:
        p = os.path.join(csvdir, f)
        if not os.path.exists(p):
            sys.exit(f"missing {p}; run compare_arms.py first "
                     f"(see README.md 'Reproducing')")
        for x in csv.DictReader(open(p)):
            ob, oa = float(x["out_tokens_base"]), float(x["out_tokens_arm"])
            rows.append({
                "board": b, "model": x["model"], "pairs": x["pairs"],
                "in_tokens_base": int(float(x["in_tokens_base"])),
                "in_tokens_condensed": int(float(x["in_tokens_arm"])),
                "in_tokens_delta_pct": f'{float(x["in_tokens_delta_pct"]) * 100:+.1f}',
                "out_tokens_base": int(ob), "out_tokens_condensed": int(oa),
                "out_tokens_delta_pct": f"{(oa - ob) / ob * 100:+.1f}" if ob else "",
                "cost_usd_base": f'{float(x["cost_base"]):.4f}',
                "cost_usd_condensed": f'{float(x["cost_arm"]):.4f}',
                "cost_delta_pct": f'{float(x["cost_delta_pct"]) * 100:+.1f}',
                "latency_s_base": f'{float(x["latency_base"]):.0f}',
                "latency_s_condensed": f'{float(x["latency_arm"]):.0f}',
                "unanswered_base": x["unanswered_base"],
                "unanswered_condensed": x["unanswered_arm"]})
    write(os.path.join(csvdir, "cost_tokens.csv"), rows)


REL_CONDENSER = os.path.join("netlist_modifications", "scripts", "condense_netlist.py")


def _load_condenser(root):
    """The condense_netlist module, for its S-expression parser.

    Walks up from `root` looking for the repo, rather than counting a fixed
    number of ``dirname`` calls, so moving the prompts tree deeper or shallower
    (as the RQ1_SimpleMods/RQ2_ComplexMods split did) does not break this.
    """
    d = os.path.abspath(root)
    while True:
        cand = os.path.join(d, REL_CONDENSER)
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("condense_netlist", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _raw_facts(cn, path):
    """{ref: (value, footprint)}, {net: {(ref, pin)}} from the S-expression netlist."""
    text = open(path, encoding="utf-8").read()
    roots = [c for c in cn.parse(text)
             if isinstance(c, list) and c and c[0] == "export"]
    root = roots[0] if roots else cn.parse(text)[0]
    comps = {cn.one(c, "ref"): (cn.one(c, "value"), cn.one(c, "footprint"))
             for blk in cn.tagged(root, "components") for c in cn.tagged(blk, "comp")}
    nets = {}
    for blk in cn.tagged(root, "nets"):
        for n in cn.tagged(blk, "net"):
            nets[cn.one(n, "name")] = {(cn.one(nd, "ref"), cn.one(nd, "pin"))
                                       for nd in cn.tagged(n, "node")}
    return comps, nets


def _cond_facts(path):
    """The same two structures, re-read out of the condensed flat form."""
    comps, nets, sec = {}, {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("COMPONENTS"):
            sec = "c"; continue
        if line.startswith("LIBRARY PARTS"):
            sec = "l"; continue
        if line.startswith("NETS"):
            sec = "n"; continue
        if not line.strip() or line.startswith("#"):
            continue
        if sec == "c":
            p = [x.strip() for x in line.split("|")]
            comps[p[0]] = (p[1] if len(p) > 1 else "", p[2] if len(p) > 2 else "")
        elif sec == "n" and " : " in line:
            head, rest = line.split(" : ", 1)
            nodes = set()
            for tok in rest.split():
                m = re.match(r"^([^.]+)\.([^(]+)", tok)
                if m:
                    nodes.add((m.group(1), m.group(2)))
            nets[re.sub(r"\s*\[.*\]$", "", head).strip()] = nodes
    return comps, nets


def validate(root, board, cn):
    """(faults_with_zero_diff, semantic_noloss_mismatches) for one board.

    The first is the number of faulty scenarios whose condensed netlist is
    identical to the condensed clean control - i.e. faults condensing destroyed.
    The second counts netlists where a component or net failed to survive the
    transformation with identical value, footprint and membership.
    Both should be 0. Returns ("", "") if the check cannot be run.
    """
    ctrl = os.path.join(root, board, "Control", "netlist.condensed.net")
    if not os.path.exists(ctrl) or cn is None:
        return "", ""
    ctrl_text = open(ctrl, encoding="utf-8").read()
    zero = mismatches = 0
    for raw in sorted(glob.glob(os.path.join(root, board, "*", "netlist.net"))):
        con = raw[: -len("netlist.net")] + "netlist.condensed.net"
        if not os.path.exists(con):
            continue
        scen = os.path.basename(os.path.dirname(raw))
        text = open(con, encoding="utf-8").read()
        if scen != "Control" and text == ctrl_text:
            zero += 1
        rc, rn = _raw_facts(cn, raw)
        cc, nn = _cond_facts(con)
        if rc != cc or rn != nn:
            mismatches += 1
    return zero, mismatches


def size_table(root, csvdir):
    gb = list(csv.DictReader(open(os.path.join(root, "grades.csv"))))
    gc = list(csv.DictReader(open(os.path.join(root, "grades_condensed.csv"))))

    def mean_tokens(rows, board):
        v = [float(r["prompt_tokens"]) for r in rows
             if r["board"] == board and r["model"] == SIZE_MODEL]
        return statistics.mean(v) if v else 0.0

    cn = _load_condenser(root)
    if cn is None:
        print("note: condense_netlist.py not found; skipping the validation "
              "columns.", file=sys.stderr)

    rows = []
    for b in BOARDS:
        raw = glob.glob(os.path.join(root, b, "*", "netlist.net"))
        con = glob.glob(os.path.join(root, b, "*", "netlist.condensed.net"))
        o = sum(os.path.getsize(p) for p in raw)
        c = sum(os.path.getsize(p) for p in con)
        n = len(raw) or 1
        mt, mtc = mean_tokens(gb, b), mean_tokens(gc, b)
        zero, mism = validate(root, b, cn)
        rows.append({"board": b, "prompts": len(raw),
                     "netlist_bytes_base": o, "netlist_bytes_condensed": c,
                     "netlist_bytes_delta_pct": f"{(c - o) / o * 100:+.1f}" if o else "",
                     "netlist_bytes_mean_base": f"{o / n:.0f}",
                     "netlist_bytes_mean_condensed": f"{c / n:.0f}",
                     "mean_prompt_tokens_base": f"{mt:.0f}",
                     "mean_prompt_tokens_condensed": f"{mtc:.0f}",
                     "mean_prompt_tokens_delta_pct":
                         f"{(mtc - mt) / mt * 100:+.1f}" if mt else "",
                     "tokenizer_model": SIZE_MODEL,
                     "faults_with_zero_diff": zero,
                     "semantic_noloss_mismatches": mism})
    write(os.path.join(csvdir, "representation_size.csv"), rows)


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    # The graded arms live in the RQ1 prompts tree, a sibling of this directory.
    default_root = os.path.join(os.path.dirname(here), RQ1_DIR)
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", default=default_root,
                   help=f"RQ1 prompts root holding grades.csv "
                        f"(default: ../{RQ1_DIR})")
    p.add_argument("--csvdir", default=os.path.join(here, "csv"),
                   help="Where the CSVs live (default: ./csv)")
    args = p.parse_args(argv)
    os.makedirs(args.csvdir, exist_ok=True)

    base, cond, keys = load_pairs(args.root)
    print(f"{len(keys)} matched pair(s) over {', '.join(BOARDS)}\n")
    binary_tables(args.csvdir)
    mcnemar_table(args.csvdir, base, cond, keys)
    scenario_table(args.csvdir, base, cond, keys)
    flip_ledger(args.csvdir, base, cond, keys)
    cost_table(args.csvdir)
    size_table(args.root, args.csvdir)
    print(f"\n-> {args.csvdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
