# Condensed vs. raw netlist — AcornRobotElectronics and fan_controller

A paired A/B on the **design-file representation only**. Both arms use the same
prompts, the same `prompt.md` (instructions, specification and output schema
byte-identical), the same 4 models and `temperature=0.0`. The only difference is
that the condensed arm substitutes `netlist.condensed.net` for `netlist.net`.
The SPICE deck is byte-identical in both arms.

| | AcornRobotElectronics | fan_controller |
|---|---|---|
| Board scale | 262 components, 370 nets, 1,139 nodes | 25 components, 15 nets, 67 nodes |
| Prompts (1 clean control + faults) | 43 | 36 |
| Models | 4 | 4 |
| Matched (model, prompt) pairs | **172** | **144** |

316 matched pairs in total; no prompt is in one arm only. The two extra base-arm
rows in `RQ1_SimpleMods/grades.csv` are a different board (`CF-Chef`) and are excluded.

Both arms live in the RQ1 prompts tree, `../RQ1_SimpleMods/` (a sibling of this
directory):

- Base arm: `RQ1_SimpleMods/<board>/*/results/*.json` → `RQ1_SimpleMods/grades.csv`
- Condensed arm: `RQ1_SimpleMods/<board>/*/results/condensed/*.json` →
  `RQ1_SimpleMods/grades_condensed.csv`

---

## Headline

**Condensing removed 73% of the input tokens and changed nothing measurable
about what these models find.** Pooled over both boards, localisation went
32.3% → 32.0% (−0.3pp, McNemar exact p = 1.000).

The boards disagree sharply on *cost*, and that is the finding worth carrying
forward:

| Board | Input tokens | Localisation | Total cost | Verdict |
|---|---|---|---|---|
| AcornRobotElectronics | −74% | 29.7% → 29.7% (+0.0pp) | $14.24 → **$5.42 (−62%)** | large saving |
| fan_controller | −56% | 35.4% → 34.7% (−0.7pp) | $2.49 → **$2.84 (+14%)** | costs more |

Same transformation, opposite economics. Condensing pays on the large board and
loses on the small one, because the saving is on the input side and only the
large board's bill is input-dominated.

---

## 1. The transformation is lossless

`netlist_modifications/scripts/condense_netlist.py` flattens the KiCad
S-expression netlist into three sections (components, library parts, nets). It
is a **whitelist of what to keep**, not a blacklist of what to drop, so a fault
injected into an unrecognised field still surfaces in the `extra` column rather
than being silently deleted.

**Kept:** component ref, value, footprint, `libsource` lib:part and its
description, every non-boilerplate field/property (this is what carries the
injected `Tolerance` faults), each library part's description and full pin
inventory with pin names and electrical types, and every net with each node's
ref, pin number, pinfunction and pintype.

**Dropped:** the `design` block, the `libraries` block, per-component `tstamps`
and `sheetpath`, `datasheet` URLs, `fields` entries duplicating
footprint/datasheet/description, the `Sheetname`/`Sheetfile`/`ki_*` properties,
and `libpart` `docs`/`footprints` globs.

### Size

| Board | Netlist bytes | Mean netlist | Mean prompt tokens |
|---|---|---|---|
| AcornRobotElectronics | 21,848,419 → 4,082,194 (**−81.3%**) | 508,103 → 94,935 | **182,553 → 46,960 (−74.3%)** |
| fan_controller | 1,300,694 → 261,984 (**−79.9%**) | 36,130 → 7,277 | 15,846 → 6,901 (−56.4%) |

(Prompt tokens on the gpt-6-luna tokenizer; the other three agree within a
point or two.)

The Acorn figure is the one that matters structurally: **the raw prompt is
182,553 tokens, which does not fit a 128k context window at all.** Condensed, it
is 46,960 — comfortably inside one, with room for the response. On that board
condensing is not an optimisation, it is what makes the prompt admissible.

### Pre-run validation (no API calls)

Both checks pass on every netlist in both boards:

- **Fault visibility** — all 77 faulty scenarios (42 Acorn + 35 fan_controller)
  still differ from their condensed clean control. **0 scenarios produced a zero
  diff**, so no injected fault was condensed away.
- **Semantic no-loss** — parsing both forms and comparing component sets
  (ref → value, footprint) and net sets (name → {(ref, pin)}) over all 79
  netlists: **0 mismatches**. Every component, net and node is preserved with
  identical values, footprints and net membership.

This is what licenses reading the accuracy result as an effect of
*representation* rather than of information loss.

---

## 2. Accuracy: unchanged on both boards

Localisation, paired over every (model, prompt):

### AcornRobotElectronics — 172 pairs

| Model | base | condensed | delta | won | lost | tied | McNemar p |
|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 44.2% | 37.2% | −7.0pp | 3 | 6 | 34 | 0.508 |
| deepseek/deepseek-v4.1-flash | 27.9% | 23.3% | −4.7pp | 5 | 7 | 31 | 0.774 |
| openai/gpt-6-luna | 20.9% | 23.3% | +2.3pp | 3 | 2 | 38 | 1.000 |
| qwen/qwen3.8-flash | 25.6% | 34.9% | **+9.3pp** | 5 | 1 | 37 | 0.219 |
| **POOLED** | **29.7%** | **29.7%** | **+0.0pp** | **16** | **16** | **140** | **1.000** |

### fan_controller — 144 pairs

| Model | base | condensed | delta | won | lost | tied | McNemar p |
|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 44.4% | 41.7% | −2.8pp | 3 | 4 | 29 | 1.000 |
| deepseek/deepseek-v4.1-flash | 36.1% | 33.3% | −2.8pp | 3 | 4 | 29 | 1.000 |
| openai/gpt-6-luna | 22.2% | 27.8% | +5.6pp | 4 | 2 | 30 | 0.688 |
| qwen/qwen3.8-flash | 38.9% | 36.1% | −2.8pp | 3 | 4 | 29 | 1.000 |
| **POOLED** | **35.4%** | **34.7%** | **−0.7pp** | **13** | **14** | **117** | **1.000** |

**No model on either board moved by a statistically separable amount** — every
exact McNemar p is ≥ 0.219. The pooled Acorn result is an exact tie (16 won,
16 lost). The two largest per-model swings, qwen +9.3pp on Acorn and haiku
−7.0pp, are 4 and 3 prompts respectively out of 43, and point in opposite
directions, which is the signature of noise rather than of an effect.

### The stability is a net effect, not per-prompt stability

| Board | Pairs | Flipped | Flip rate |
|---|---|---|---|
| AcornRobotElectronics | 172 | 32 | **18.6%** |
| fan_controller | 144 | 27 | **18.8%** |
| **Both** | **316** | **59** | **18.7%** |

Roughly **one pair in five changes answer** while the pooled rate moves 0.3pp.
The two boards land on the same flip rate independently, despite a 20×
difference in board size — so at `temperature=0.0`, treat ~19% churn as this
benchmark's measurement floor. **Any future claim smaller than about ±5pp on a
40-prompt board is not separable from it.** Per-pair detail is in
`csv/flip_ledger.csv` (100 rows: every pair whose localisation, detection or
status changed).

### Where the faults are hard in both arms

From `csv/scenario_family_localisation.csv` — the **tolerance** families sit at
0% in *both* arms on *both* boards:

| Scenario family | Acorn base → cond | fan base → cond |
|---|---|---|
| ResistorToleranceUpRandom | 8% → 0% | 0% → 0% |
| ResistorToleranceDownRandom | 0% → 0% | 0% → 0% |
| CapacitorToleranceDownRandom | 0% → 0% | 0% → 0% |
| CapacitorToleranceUpRandom | 8% → 0% | 0% → 12% |
| ResistorToCapacitorRandom | 0% → 8% | 42% → 42% |

That floor is a property of the fault class and the prompt, not of the
representation — condensing explicitly preserves the `Tolerance` field, and the
no-loss check confirms it. Models simply do not treat a tolerance change as an
anomaly. Conversely the magnitude and short/bridge families localise at 42–92%
in both arms. **Fixing tolerance detection is a prompt/specification problem and
is independent of this experiment.**

---

## 3. Cost: the result splits on board size

| Model | Board | Input tokens | Output tokens | Cost base → cond | Change |
|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | Acorn | 10,987,179 → 2,986,399 | 1,115,337 → 1,115,958 | $8.282 → $0.857 | **−90%** |
| openai/gpt-6-luna | Acorn | 7,849,796 → 2,019,298 | 166,161 → 159,976 | $1.064 → $0.332 | **−69%** |
| qwen/qwen3.8-flash | Acorn | 8,866,509 → 2,289,513 | 2,062,683 → 2,717,540 | $1.856 → $1.517 | −18% |
| deepseek/deepseek-v4.1-flash | Acorn | 8,084,178 → 2,092,806 | 2,402,720 → 2,752,095 | $3.039 → $2.716 | −11% |
| **POOLED** | **Acorn** | **35,787,662 → 9,388,016 (−74%)** | **5,746,901 → 6,745,569 (+17%)** | **$14.241 → $5.422** | **−62%** |
| anthropic/claude-haiku-5.5 | fan | 815,241 → 373,034 | 173,025 → 148,626 | $0.168 → $0.112 | −34% |
| openai/gpt-6-luna | fan | 570,455 → 248,436 | 85,032 → 95,111 | $0.114 → $0.079 | −31% |
| qwen/qwen3.8-flash | fan | 629,889 → 265,649 | 1,013,244 → 1,346,230 | $0.533 → $0.652 | **+22%** |
| deepseek/deepseek-v4.1-flash | fan | 596,237 → 259,837 | 2,167,370 → 2,605,658 | $1.671 → $1.998 | **+20%** |
| **POOLED** | **fan** | **2,611,822 → 1,146,956 (−56%)** | **3,438,671 → 4,195,625 (+22%)** | **$2.486 → $2.839** | **+14%** |

Two mechanisms, pulling against each other:

**Input falls consistently** — 73% pooled, across all four tokenizers, on both
boards. This is the direct, predictable effect.

**Output *rises*** — +17% on Acorn, +22% on fan_controller. Output is the more
expensive side, so whether condensing saves money comes down to which side
dominated the bill to begin with:

- **Input-dominated** (Acorn, where the raw netlist is 508 KB): the input cut
  swamps the output growth. haiku drops 90%, from $8.28 to $0.86.
- **Output-dominated** (the reasoning models on the small board, where the
  netlist was only 36 KB to begin with): output growth wins and the arm comes
  out 20–22% dearer.

Note that haiku's output is flat on Acorn (+0.05%) while qwen's and deepseek's
grow by 655k and 349k tokens. **The output growth is specific to the reasoning
models**, and it is the single thing standing between this transformation and an
unambiguous win. Why a shorter input produces more reasoning is not established
here; it reproduces across two reasoning models and two boards, which makes it
worth a dedicated test rather than an explanation.

Latency pooled: Acorn 34,539s → 49,183s, fan_controller 20,160s → 25,157s —
both up, tracking the output growth, not the input cut.

---

## 4. deepseek's truncation is an output-side failure, and condensing makes it worse

Every unanswered result in either arm on either board is deepseek, status
`incomplete`:

| Board | base | condensed |
|---|---|---|
| AcornRobotElectronics | 10 / 43 | **12 / 43** |
| fan_controller | 12 / 36 | **15 / 36** |

(The one Acorn base-arm qwen `unparsed` result resolved in the condensed arm.)

Every one of these 49 results has `finish_reason: "length"`, empty `text`, and
`completion_tokens` pegged at exactly **131,072** — the entire output ceiling
spent on hidden reasoning, with nothing left for the answer. `reasoning_tokens`
is at or near the same ceiling.

Condensing the input **did not help, and slightly worsened it on both boards**
(+2 and +3 prompts). This is consistent with §3: the failure is on the output
side, so cutting input cannot fix it, and the same pressure that grows output
tokens pushes more runs over the ceiling. On fan_controller the condensed arm
lost the **clean control** this way — it truncated where the base arm answered.

Fixes, in order of directness:

1. **Cap reasoning, not output** — `reasoning: {max_tokens: N}`, leaving budget
   for the answer. Lowering `--max-tokens` makes this *worse*, not better.
2. **Remove the attractor.** On fan_controller the trigger is a genuine
   ambiguity: two MCUs (U2 ATtiny45-20P, U3 ATtiny13V-10S) on the same nets — an
   alternative-footprint board — and neither the netlist nor the specification
   says populating one is intended. Truncated runs mention "attiny" 109–1,273
   times. Stating the dual-footprint intent in the specification would remove it
   for every model.

`--retry-errors` does **not** recover these: they are successful HTTP responses
with empty text, not API errors.

---

## 5. Binary classification matrices — and why most columns are unusable

Full matrices are in `csv/`. The headline caveat first, because it governs how
the tables should be read.

> **There is 1 clean control per board per model — 4 actual negatives pooled per
> board.** Specificity, precision, NPV, F1, balanced accuracy and MCC all rest
> on that single sample. They swing between 0.000 and 1.000 on one prompt
> changing, and the negative MCCs are artefacts of it, not findings.
> **Recall is the only defensible figure in these tables.** Building a real
> negative class is the prerequisite for any of the rest.

The sensitivity to that one control is visible directly. On fan_controller,
specificity under `localised` goes 0.000 → 1.000 for haiku and deepseek, and
1.000 → 0.000 for qwen, because their single control flipped; MCC follows it
from −0.178 to +0.143. None of that is about condensing.

### `--positive-rule detected` (the literal yes/no the prompt asks)

| Board | Model | tp/fp/fn/tn base | tp/fp/fn/tn cond | recall base → cond |
|---|---|---|---|---|
| Acorn | anthropic/claude-haiku-5.5 | 42/1/0/0 | 42/1/0/0 | 1.000 → 1.000 |
| Acorn | deepseek/deepseek-v4.1-flash | 33/0/9/1 | 30/1/12/0 | 0.785 → 0.714 |
| Acorn | openai/gpt-6-luna | 41/1/1/0 | 41/1/1/0 | 0.976 → 0.976 |
| Acorn | qwen/qwen3.8-flash | 41/1/1/0 | 42/1/0/0 | 0.976 → 1.000 |
| Acorn | **POOLED** | **157/3/11/1** | **155/4/13/0** | **0.934 → 0.922** |
| fan | anthropic/claude-haiku-5.5 | 25/1/10/0 | 25/0/10/1 | 0.714 → 0.714 |
| fan | deepseek/deepseek-v4.1-flash | 22/1/13/0 | 21/0/14/1 | 0.628 → 0.600 |
| fan | openai/gpt-6-luna | 35/1/0/0 | 35/1/0/0 | 1.000 → 1.000 |
| fan | qwen/qwen3.8-flash | 33/0/2/1 | 31/1/4/0 | 0.942 → 0.885 |
| fan | **POOLED** | **115/3/25/1** | **112/2/28/2** | **0.821 → 0.800** |

### `--positive-rule localised` (stricter: the right fault, named)

| Board | Model | tp/fp/fn/tn base | tp/fp/fn/tn cond | recall base → cond |
|---|---|---|---|---|
| Acorn | anthropic/claude-haiku-5.5 | 19/1/23/0 | 16/1/26/0 | 0.452 → 0.381 |
| Acorn | deepseek/deepseek-v4.1-flash | 12/0/30/1 | 10/1/32/0 | 0.285 → 0.238 |
| Acorn | openai/gpt-6-luna | 9/1/33/0 | 10/1/32/0 | 0.214 → 0.238 |
| Acorn | qwen/qwen3.8-flash | 11/1/31/0 | 15/1/27/0 | 0.261 → 0.357 |
| Acorn | **POOLED** | **51/3/117/1** | **51/4/117/0** | **0.303 → 0.303** |
| fan | anthropic/claude-haiku-5.5 | 16/1/19/0 | 15/0/20/1 | 0.457 → 0.428 |
| fan | deepseek/deepseek-v4.1-flash | 13/1/22/0 | 12/0/23/1 | 0.371 → 0.342 |
| fan | openai/gpt-6-luna | 8/1/27/0 | 10/1/25/0 | 0.228 → 0.285 |
| fan | qwen/qwen3.8-flash | 14/0/21/1 | 13/1/22/0 | 0.400 → 0.371 |
| fan | **POOLED** | **51/3/89/1** | **50/2/90/2** | **0.364 → 0.357** |

Reading the recall column — the one trustworthy column — the detection rate is
essentially flat (−1.2pp and −2.1pp pooled under `detected`; −0.0pp and −0.7pp
under `localised`).

Most of the small `detected` decline is deepseek's extra truncations (§4),
which the grader scores as predicted negatives. Removing deepseek entirely:

| Scope | detected, all 4 models | detected, excl. deepseek | localised, all 4 | localised, excl. deepseek |
|---|---|---|---|---|
| AcornRobotElectronics | 93.0% → 92.4% (−0.6pp) | 98.4% → 99.2% (**+0.8pp**) | 29.7% → 29.7% (+0.0pp) | 30.2% → 31.8% (+1.6pp) |
| fan_controller | 81.9% → 79.2% (−2.8pp) | 88.0% → 86.1% (−1.9pp) | 35.4% → 34.7% (−0.7pp) | 35.2% → 35.2% (+0.0pp) |
| **Both** | **88.0% → 86.4% (−1.6pp)** | **93.7% → 93.2% (−0.4pp)** | **32.3% → 32.0% (−0.3pp)** | **32.5% → 33.3% (+0.8pp)** |

On Acorn, deepseek accounts for the whole decline and then some — without it
the condensed arm is slightly *ahead* on both metrics. Pooled, the detected gap
shrinks from −1.6pp to −0.4pp. On fan_controller, though, −1.9pp remains after
deepseek is removed, so **deepseek is the main but not the only contributor.**
That residual is a net 2 prompts across 108 pairs (4 won, 6 lost,
McNemar p = 0.754), well inside the ~19% churn floor of §2, and the
localisation column for the same subset is an exact tie (10 won, 10 lost).
Every one of these deepseek-free subsets has p ≥ 0.75 — removing deepseek does
not turn up an effect that the full set was hiding. These rows are in
`csv/mcnemar_paired_flips.csv` as `POOLED_EXCL_DEEPSEEK`.

Note also the gap between the two rules: under `detected`, pooled recall is
0.92 (Acorn) and 0.82 (fan); under `localised` it falls to 0.30 and 0.36. The
models say "something is wrong" far more often than they name the right thing —
which, with 42 of 43 prompts carrying a fault, is close to what a constant
"yes" would score. That gap, not the condensing effect, is the substantive
weakness these runs expose.

---

## 6. What to conclude

1. **Condensing is safe.** Verified lossless two ways, and accuracy is
   statistically unchanged across 316 paired prompts, 4 models and a 20× range
   of board size. Use it.
2. **It is a context win everywhere, and a cost win only on large boards.**
   On AcornRobotElectronics it cuts the bill 62% *and* brings a 182k-token
   prompt inside a 128k window. On fan_controller it costs 14% more. Decide per
   board, by which side of the bill dominates — not by a blanket policy.
3. **Do not expect a cheaper full sweep until reasoning is capped.** Output grew
   17–22% on both boards, driven entirely by qwen and deepseek. On a sweep
   weighted toward small boards, condensing would make the bill *larger*.
4. **deepseek is not usable on this benchmark as configured** — 23–42% of its
   prompts return nothing, and condensing worsens it. Cap reasoning tokens
   before running it again.
5. **The benchmark's measurement floor is ~19% per-pair churn** at
   `temperature=0.0`, replicated independently on both boards. Size future
   experiments against that, or run repeats.
6. **Two blockers are independent of representation and worth more than further
   condensing work:** tolerance faults localise at ~0% in every arm, and only 1
   clean control per board makes six of the eight standard binary metrics
   meaningless.

---

## Files

All paths relative to this directory.

| File | Contents |
|---|---|
| `csv/binary_metrics_combined.csv` | **Tidy master.** 40 rows — every board × arm × positive-rule × model, with tp/fp/fn/tn and all 9 metrics. |
| `csv/confusion_deltas.csv` | Base vs condensed side by side, 20 rows, with a `_delta` column per cell and per metric. |
| `csv/binary_<board>_<arm>_<rule>.csv` | The 8 raw `binary_metrics.py` outputs, unmodified. |
| `csv/arm_comparison_<board>.csv` | Paired `compare_arms.py` output per board. |
| `csv/arm_comparison_both_boards.csv` | Same, pooled over all 316 pairs. |
| `csv/mcnemar_paired_flips.csv` | Won/lost/tied and exact McNemar p per board × model, for localisation and detection. Includes `POOLED` and `POOLED_EXCL_DEEPSEEK` scopes. |
| `csv/scenario_family_localisation.csv` | Localisation and flips per fault family per board. |
| `csv/flip_ledger.csv` | Every pair (100) whose localisation, detection or status changed between arms. |
| `csv/cost_tokens.csv` | Input/output tokens, cost, latency and unanswered counts per board × model. |
| `csv/representation_size.csv` | Netlist bytes, prompt tokens, and the two §1 validation checks (both re-run, both 0). |
| `build_comparison_csvs.py` | Builds the seven derived CSVs above, and re-runs the §1 validation. |

## Reproducing

From the repo root:

```sh
BOARDS=AcornRobotElectronics,fan_controller
MODELS=openai/gpt-6-luna,anthropic/claude-haiku-5.5,deepseek/deepseek-v4.1-flash,qwen/qwen3.8-flash
AD=outputs/Infected/Prompts/AnomalyDetection
OUT=$AD/CondensedComparison/csv

# condense (writes netlist.condensed.net + spice.condensed.cir beside the originals)
.venv/bin/python netlist_modifications/scripts/condense_netlist.py \
    --root $AD/RQ1_SimpleMods --boards $BOARDS --variant condensed

# run the arm (results -> results/condensed/, summary -> run_summary_condensed.json)
.venv/bin/python netlist_modifications/scripts/run_anomaly_prompts.py \
    --models $MODELS --boards $BOARDS --variant condensed --jobs 6 --temperature 0.0

# grade
.venv/bin/python netlist_modifications/scripts/grade_anomaly_results.py --variant condensed

# paired comparison, per board and pooled
for b in AcornRobotElectronics fan_controller; do
  .venv/bin/python netlist_modifications/scripts/compare_arms.py \
      --board $b --arm condensed --out $OUT/arm_comparison_$b.csv
done
.venv/bin/python netlist_modifications/scripts/compare_arms.py \
    --arm condensed --out $OUT/arm_comparison_both_boards.csv

# binary metrics: 2 boards x 2 arms x 2 rules
for b in AcornRobotElectronics fan_controller; do
  for rule in detected localised; do
    .venv/bin/python netlist_modifications/scripts/binary_metrics.py \
        --board $b --positive-rule $rule --out $OUT/binary_${b}_base_${rule}.csv
    .venv/bin/python netlist_modifications/scripts/binary_metrics.py \
        --board $b --positive-rule $rule --variant condensed \
        --out $OUT/binary_${b}_condensed_${rule}.csv
  done
done
```

Then build the seven derived CSVs from `RQ1_SimpleMods/grades.csv`,
`RQ1_SimpleMods/grades_condensed.csv` and
the files above. This step also re-runs both §1 validation checks (fault
visibility and semantic no-loss) and writes their results into
`representation_size.csv`, so the lossless claim is verified rather than
asserted:

```sh
.venv/bin/python outputs/Infected/Prompts/AnomalyDetection/CondensedComparison/build_comparison_csvs.py
```

It is read-only with respect to the runs — it only reads the graded CSVs and the
netlists, and writes into `csv/`. Re-running it is safe and idempotent.
