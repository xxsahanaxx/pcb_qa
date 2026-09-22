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
  insert_trojan/
    core.py       # engine: parse / render / extract_spec / apply_spec (the library)
    snip.py       # "snip" Trojan  — split one net (SDA, SCL, MISO, MOSI, ...)
    swap.py       # "swap" Trojan  — cross an RX/TX pair (UART, ...)
    tolerance.py  # "tolerance" Trojan — re-grade one R/C/L passive
    value.py      # "value" Trojan — shift one R/C/L passive's SI-prefix magnitude
    cli.py        # command-line front end (argparse)
  conversions/
    convert_circuits.py  # infected .net -> hierarchical circuit JSON (needs pcb_qa)
    convert_spice.py     # infected .net -> infected SPICE .cir (needs pcb_qa)
    run_spice.py         # batch-run ngspice over generated .cir files
  gen_trojan_questions.py  # Trojan-detection question banks from batch manifests
  __main__.py              # enables `python -m netlist_trojans`
  specs/                   # example Trojan spec(s): uart.json
```

---

## Which Trojan do I want?

| Trojan | What it does | Command | Spec file? |
|---|---|---|---|
| **snip** | Split one bus net into `Troj_<SIGNAL>0` / `Troj_<SIGNAL>1` (cut a trace) | `snip`, `snip-batch` | no — rule-based |
| **swap** | Cross a matched RX/TX pair → `Troj_RX` / `Troj_TX` | `swap`, `swap-batch` | no — rule-based |
| **tolerance** | Re-grade one R/C/L passive to a different tolerance (%) | `tolerance`, `tolerance-batch` | no — rule-based |
| **value** | Shift one R/C/L passive's value to a different SI decade | `value`, `value-batch` | no — rule-based |
| **spec replay** | Reproduce/retarget an *exact* recorded Trojan | `extract`, `apply` | yes — `specs/*.json` |

**Rule-based** Trojans (snip, swap, tolerance, value) compute what to change
from whatever nets/components a board actually has — nothing is stored.
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

### tolerance — re-grade a passive (R/C/L) to a different tolerance

Models a supply-chain substitution: a resistor/capacitor/inductor is swapped
for a same-value, same-footprint part sourced to a **different tolerance
grade**. Value, footprint and every net stay untouched — the only change is a
single `Tolerance` property in the component's own `(comp ...)` block, so the
diff is one line. The new grade is picked deterministically (hash of board +
ref), never equal to the component's current grade.

"Current grade" is read with this precedence: an explicit `Tolerance`
property already in the block > a grade mined from the vendor part/description
text when the library states one (e.g. `"RES 10kΩ ±1% 1/8W 0805 Yageo"`) > a
generic per-family default (5% for R, 10% for C/L) when the netlist states
neither — so the *value that gets tampered* is always the board's real
declared tolerance where one exists, and after the swap it visibly disagrees
with any untouched vendor description sitting right next to it.

```bash
# one file
.venv/bin/python -m netlist_trojans tolerance board.net --list           # show candidates + current grade
.venv/bin/python -m netlist_trojans tolerance board.net --ref R5 -o out.net

# every R/C/L passive across a tree of clean netlists (one output per part)
.venv/bin/python -m netlist_trojans tolerance-batch
.venv/bin/python -m netlist_trojans tolerance-batch --families R,C       # skip inductors
```

Only two-terminal passives with a meaningful ±% rating qualify: Device-library
`R`/`R_Small`/`R_US`/`C`/`C_Small`/`C_Polarized`/`L`, plus any part whose
libsource `part` text starts with `RES`/`CAP`/`IND` (vendor-exported
libraries). LEDs, diodes, transistors, crystals and fuses are excluded — they
aren't rated by a simple tolerance percentage.

### value — shift a passive's magnitude (same unit, different decade)

Tampers with the component's actual nominal value instead of a bolted-on
property: it shifts the SI-prefix magnitude (p, n, u, m, k, M) while leaving
every digit, the decimal point, and the base unit (ohms/farads/henries)
untouched. A `10k` pull-up silently becomes `10M`; a `100n` decoupling cap
becomes `100u`; a bare `47` (ohm) resistor becomes `47k`. Same-family,
same-footprint, same-digits — only the decade is wrong, which is exactly the
kind of misread (k vs M, m vs M) that slips past a schematic review.

```bash
# one file
.venv/bin/python -m netlist_trojans value board.net --list           # show candidates + current value
.venv/bin/python -m netlist_trojans value board.net --ref C5 -o out.net

# every R/C/L passive across a tree of clean netlists (one output per part)
.venv/bin/python -m netlist_trojans value-batch
.venv/bin/python -m netlist_trojans value-batch --families R          # resistors only
```

Handles every value shape seen in this corpus: plain SI shorthand (`10k`,
`3.9uH`), KiCad's decimal-in-letter form (`4k7` = 4.7k, `2u2` = 2.2u), and
bare/no-prefix numbers with or without a spelled-out unit (`47`, `100R`,
`0.47ohm`, `100Ω`). A trailing rating/tolerance/description (`47uF 63V
solid`, `1nF 2kV`, `2.2k 1%`, `0.1uF/16V`) is split off first and left
alone, so a prefix letter inside a voltage rating (the `k` in `2kV`) is
never mistaken for the component's own magnitude. A value with no
meaningful magnitude to shift — a 0-ohm link, or a placeholder like `??` —
is skipped rather than corrupted.

### Batch output layout

`snip-batch`, `swap-batch`, `tolerance-batch` and `value-batch` write **one
output file per net / per pair / per part**, so each output's diff is a
single change:

```
<out-root>/<board>/<net-or-pair-or-ref>/<original filename>
<out-root>/manifest.json          # board, target(s), output path, what changed
```

Defaults: `--clean-glob 'outputs/Clean/*/*.net'`, `--out-root
outputs/Infected/<SIGNAL>` (snip/swap), `outputs/Infected/Tolerance`
(tolerance-batch), or `outputs/Infected/Value` (value-batch). Override either
for use outside this repo.

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

## Conversions (`netlist_trojans/conversions/`)

Three separate scripts, meant to run in sequence after generating infected
netlists. **Note:** unlike the rest of this package (which only needs
`simp_sexp`), all three depend on the **pcb_qa** project package (`convert_spice`
directly; the others import it lazily) — run them with the project venv, from
the repo root.

### convert_circuits — infected `.net` → hierarchical circuit JSON

Convert each infected netlist to hierarchical circuit JSON, written
`<source>.json` next to every `.net`:

```bash
.venv/bin/python -m netlist_trojans.conversions.convert_circuits                       # whole Infected tree
.venv/bin/python -m netlist_trojans.conversions.convert_circuits --root outputs/Infected/SDA
.venv/bin/python -m netlist_trojans.conversions.convert_circuits --verbose             # show parser logs
```

Re-run it any time you regenerate netlists.

### convert_spice — infected `.net` → infected SPICE `.cir`

For every infected `.net` under
`outputs/Infected/ComponentSubstitution/{Value,Tolerance}/<board>/<ref>/`,
writes a sibling `.cir`, derived from that board's Clean `.cir` template
(`outputs/Clean/<board>/*.cir`) with the same substitution applied — **without**
re-running KiCad's schematic → SPICE export (the infected netlists have no
schematic to export from):

- **Value** substitutions rewrite just the SI-magnitude prefix of the matching
  `.cir` line (`10k` → `10M` in the `.net` becomes `10k` → `10Meg` in the `.cir`,
  since bare SPICE `M` means milli, not mega), reusing the Clean line's own
  already-correct mantissa.
- **Tolerance** substitutions never touch a component's `value`, and KiCad's
  SPICE exporter has no notion of tolerance at all, so the `.cir` is a copy of
  the Clean template — only its `write` output path is retargeted (see below).
- A ref the Clean board's SPICE export excludes (KiCad doesn't model every
  schematic component) is written out unchanged.
- Every variant's own `.control` block is rewritten to `write` its `.raw` dump
  next to its own `.cir`, instead of the Clean template's single shared path —
  otherwise every variant of a board would clobber the same `.raw` file.
- `stack-chan`'s Clean `.cir` was checked in at KiCad's raw, pre-conversion
  export stage (no `.control`/`tran`/`write`/DC sources at all, unlike every
  other board). `convert_spice` finishes it into a runnable deck **in memory**
  before using it as that board's template — it is never written to
  `outputs/Clean/`.

```bash
.venv/bin/python -m netlist_trojans.conversions.convert_spice                       # whole ComponentSubstitution tree
.venv/bin/python -m netlist_trojans.conversions.convert_spice --root outputs/Infected/ComponentSubstitution/Value
.venv/bin/python -m netlist_trojans.conversions.convert_spice --dry-run             # report only, write nothing
```

Writes a manifest to `<root>/spice_manifest.json` (per-file board/ref/status/detail).
Never reads a Clean `.net`/`.cir` for anything other than as an unmodified
template, and never writes under `outputs/Clean/`.

### run_spice — batch-run ngspice over generated `.cir` files

Runs `ngspice -b` against every `.cir` under a root (in parallel), writing an
ngspice log next to each one:

```bash
.venv/bin/python -m netlist_trojans.conversions.run_spice                       # whole ComponentSubstitution tree
.venv/bin/python -m netlist_trojans.conversions.run_spice --root outputs/Infected/ComponentSubstitution/Value
.venv/bin/python -m netlist_trojans.conversions.run_spice --jobs 8              # parallel ngspice processes
```

Only needs the `ngspice` binary on `PATH` (no pcb_qa/venv dependency). Writes a
manifest to `<root>/spice_run_manifest.json` (per-file ok/fail + first error
line). A circuit that doesn't converge under ngspice's default `tran` solver
(e.g. an extreme Value-substitution magnitude shift next to a near-zero-ohm
net tie, which can blow the linear solver's condition number past
double-precision range) needs solver-level fixes by hand — relaxed
`.options` tolerances/`gmin` stepping/`rshunt`, or, if the matrix stays
singular, nudging an adjacent near-zero-value passive slightly off zero — not
something this script attempts automatically.

## Trojan-detection question banks

Generate a detection question bank next to each infected netlist, driven by the
batch `manifest.json` files:

```bash
.venv/bin/python -m netlist_trojans.gen_trojan_questions                 # whole Infected tree
.venv/bin/python -m netlist_trojans.gen_trojan_questions --root outputs/Infected/SDA
```

For each infected variant it writes `<stem>_trojan_questions.json` into that
folder (schema `{category, question, answer, clean_answer}`, `category =
"trojan_detection"`). Each `answer` is the ground truth **on the infected
netlist**, computed from the parsed files, and questions are kept only when the
clean and infected answers differ — so every question is guaranteed to
discriminate. Question kinds:

- a named signal net is now missing (renamed/removed),
- a `Troj_*` net has appeared (canary),
- a signal endpoint moved to the wrong net (RX/TX swap),
- two components that shared a bus net are no longer on a common net (snip),
- a pin now sits on a one-pin (floating) net — dangling pin (snip),
- a pin's function contradicts its net's role, e.g. a `UART_TXD` pin on a
  receive-named net (swap; emitted only when pin functions denote a role).

The last two are reference-free — they flag the tamper from the infected file
alone, even if the `Troj_*` nets were renamed to something innocent.

`clean_answer` is stored alongside so the bank supports single-file scoring or
clean-vs-infected differential scoring. Only manifest-listed variants are
covered (the hand-made `outputs/Infected/UART/Meshinger/Meshinger.net` sample is
not in a manifest, so it is skipped).

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

passives = t.parse_passives(clean)
sub = t.build_substitution(passives[0], clean, board="board")
infected = t.tolerance.apply_tolerance(clean, passives[0], sub["substituted_tolerance"])

candidates = t.parse_candidates(clean)
vsub = t.value.build_substitution(candidates[0], board="board")
infected = t.value.apply_value(clean, candidates[0], vsub["new_value"])

# spec-based
spec = t.extract_spec("clean.net", "infected.net", label="UART")
infected, log = t.apply_spec(clean, spec)

# batch runners
t.snip.run_batch("SDA")
t.swap.run_batch("UART")
t.tolerance.run_batch()
t.value.run_batch()
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
