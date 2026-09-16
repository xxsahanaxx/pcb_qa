# netlist_trojans

Insert hardware Trojans into KiCad S-expression netlists (`.net`). Self-contained
and dependency-light so it can be reused from other projects: copy the folder,
install `simp_sexp`, and `import netlist_trojans`.

- **Minimal, single-change diffs.** Every Trojan touches only the nets it must,
  leaving the rest of the file (formatting, quoting, header) byte-for-byte intact.
  So a clean-vs-infected diff shows exactly the Trojan and nothing else.
- **Two layers.** A generic engine that records/replays Trojans as JSON *specs*,
  and ready-made rule-based Trojans (snip, swap) built on top of it.

---

## Requirements & how to run

Depends on [`simp_sexp`](https://pypi.org/project/simp-sexp/) for value parsing.
In this repo it lives in `.venv`. Run the CLI **as a module** (the package uses
relative imports, so a loose-file invocation won't work):

```bash
.venv/bin/python -m netlist_trojans <subcommand> ...
.venv/bin/python -m netlist_trojans --help
```

---

## Layout

```
netlist_trojans/
  core.py     # engine: parse / render / extract_spec / apply_spec (the library)
  snip.py     # "snip" Trojan  — split one net (SDA, SCL, MISO, MOSI, ...)
  swap.py     # "swap" Trojan  — cross an RX/TX pair (UART, ...)
  cli.py      # command-line front end (argparse)
  __main__.py # enables `python -m netlist_trojans`
  specs/      # example Trojan spec(s): uart.json
```

---

## Which Trojan do I want?

| Trojan | What it does | Command | Spec file? |
|---|---|---|---|
| **snip** | Split one bus net into `Troj_<SIGNAL>0` / `Troj_<SIGNAL>1` (cut a trace) | `snip`, `snip-batch` | no — rule-based |
| **swap** | Cross a matched RX/TX pair → `Troj_RX` / `Troj_TX` | `swap`, `swap-batch` | no — rule-based |
| **spec replay** | Reproduce/retarget an *exact* recorded Trojan | `extract`, `apply` | yes — `specs/*.json` |

**Rule-based** Trojans (snip, swap) compute what to change from whatever nets a
board actually has — you just give a `--signal` keyword, nothing is stored.
**Spec-based** Trojans capture a specific hand-made example once (via `extract`)
and replay it (via `apply`); that recipe *is* the JSON in `specs/`.

---

## Rule-based Trojans

### snip — cut one bus net in two

Splits a signal net into two nets: the first node is isolated on
`Troj_<SIGNAL>0`, the rest go on `Troj_<SIGNAL>1`.

```bash
# one file
.venv/bin/python -m netlist_trojans snip board.net --signal SDA
.venv/bin/python -m netlist_trojans snip board.net --signal SDA --list        # show candidates
.venv/bin/python -m netlist_trojans snip board.net --signal SDA --net NFC_SDA -o out.net

# every matching net across a tree of clean netlists (one output per net)
.venv/bin/python -m netlist_trojans snip-batch --signal SCL
```

`--signal` is any keyword found in a net name: `SDA`, `SCL`, `MISO`, `MOSI`,
`SCK`, ... A net qualifies if it contains the keyword and has ≥ 2 nodes.

### swap — cross an RX/TX pair (UART)

Swaps the node lists of a matched RX/TX pair and renames them `Troj_RX` /
`Troj_TX`. Pairs are matched by base name, so `UART_RX`↔`UART_TX` and
`UART1_RX_FCC`↔`UART1_TX_FCC` pair up.

```bash
# one file
.venv/bin/python -m netlist_trojans swap board.net --signal UART --list
.venv/bin/python -m netlist_trojans swap board.net --signal UART --net UART_RX -o out.net

# every RX/TX pair across a tree (one output per pair)
.venv/bin/python -m netlist_trojans swap-batch --signal UART
```

Works for any RX/TX-named bus (e.g. `--signal RS485`), not just UART.

### Batch output layout

`snip-batch` and `swap-batch` write **one output file per net / per pair**, so
each output's diff is a single change:

```
<out-root>/<board>/<net-or-pair>/<original filename>
<out-root>/manifest.json          # board, net(s), output path, resulting nodes
```

Defaults: `--clean-glob 'outputs/Clean/*/*.net'`, `--out-root outputs/Infected/<SIGNAL>`.
Override either for use outside this repo.

---

## Spec-based Trojans

A **spec** is a JSON list of net-level operations (`modify_net`, `split_net`,
`add_net`, `remove_net`). Use this path when you have a concrete infected example
you want to reproduce exactly, or retarget across boards.

### extract — record a Trojan from a clean/infected pair

```bash
.venv/bin/python -m netlist_trojans extract \
    outputs/Clean/Meshinger/Meshinger.net \
    outputs/Infected/UART/Meshinger/Meshinger.net \
    --label UART --param J7=CONN --param U5=MCU \
    -o netlist_trojans/specs/uart.json
```

`--param OLDREF=VAR` turns a component ref into a `${VAR}` placeholder whose
default is that ref, so the spec stays retargetable. Omit `-o` to print to stdout.

### apply — replay a spec onto a clean netlist

```bash
.venv/bin/python -m netlist_trojans apply \
    outputs/Clean/Meshinger/Meshinger.net \
    netlist_trojans/specs/uart.json \
    -o outputs/Infected/UART/Meshinger/Meshinger.net
```

- `--set NAME=VALUE` overrides a `${VAR}` placeholder (e.g. `--set CONN=J3`). An
  unresolved placeholder is an error, not a silent `${CONN}` in the file.
- `--strict` makes a missing target net (or a node list that doesn't match the
  spec's `expect_nodes`) a hard error instead of a skip.

The bundled `specs/uart.json` reproduces the Meshinger UART sample byte-for-byte
(RX/TX rename + rewire **and** the `+3V3`/`GND`/`Display_Power_Switch` class
downgrades). It's kept as the worked example for this workflow.

---

## Library use

```python
import netlist_trojans as t

clean = t.read("board.net")

# rule-based, in memory (no spec file needed)
nets = t.parse_nets(clean)
sda  = t.bus_nets(nets, "SDA")[0]
infected, log = t.apply_spec(clean, t.build_split(sda, "SDA"))

rx, tx = t.uart_pairs(nets, "UART")[0]
infected, log = t.apply_spec(clean, t.build_swap(rx, tx))

# spec-based
spec = t.extract_spec("clean.net", "infected.net", label="UART")
infected, log = t.apply_spec(clean, spec)

# batch runners
t.snip.run_batch("SDA")
t.swap.run_batch("UART")
```

---

## How it works (and why)

- **Join by code, key by name.** `extract` matches clean↔infected nets by KiCad
  *code* (stable between two exports of one schematic), but every op is keyed by
  net *name*, so a spec applies to a freshly regenerated netlist even if codes move.
- **Surgical edits.** `apply` does string-level edits (a rename/class change is
  one header swap; only rewired/split nets have their node block rebuilt). A full
  `simp_sexp` round-trip would reformat the whole file — that's deliberately avoided.
- **Header left alone.** The `(source ...)`/`(date ...)` header is environment
  metadata, not part of the Trojan, so it is never touched.

---

## Notes & limitations

- **Which side of a cut?** A netlist has no trace topology, so "which node goes on
  which side" of a snip is a *choice*. The rule (isolate the first node) lives in
  `snip.build_split`; edit it for a different cut.
- **`swap` ≠ the exact Meshinger sample.** The generalized swap does only the
  RX/TX cross; it omits the class downgrades and uses `Troj_RX` (not the sample's
  uppercase `TROJ_RX`). Use `apply specs/uart.json` for the exact sample.
- **`--set` / `--param` don't validate.** They substitute the ref *string* only;
  they don't check the ref exists on the board. `pin`/`pinfunction` values in a
  spec are literal — parameterise them too, or extract a board-specific spec, if a
  target board's wiring differs.
- **Run with `-m`.** Package-relative imports mean `python -m netlist_trojans ...`,
  not `python netlist_trojans/cli.py`.

---

## Reusing elsewhere

Copy `netlist_trojans/` next to your code (or onto `PYTHONPATH`) and
`pip install simp_sexp`. The snip/swap path defaults are just CLI defaults —
override with `--clean-glob` / `--out-root`, or call `snip.run_batch(...)` /
`swap.run_batch(...)` / `run_single(...)` with your own paths.
