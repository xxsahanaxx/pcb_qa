# Condensed-netlist arm — fan_controller, RQ1

A paired A/B on the design-file representation. Both arms use the same 36
prompts, the same `prompt.md` (instructions, specification and output schema
byte-identical), the same 4 models and `temperature=0.0`. The only difference
is that the condensed arm substitutes `netlist.condensed.net` in place of
`netlist.net`. The SPICE deck is byte-identical in both arms.

- Base arm: `fan_controller/*/results/*.json` → `grades.csv`
- Condensed arm: `fan_controller/*/results/condensed/*.json` → `grades_condensed.csv`
- 144 matched (model, prompt) pairs; no prompt is in one arm only.

## What was condensed

`netlist_modifications/scripts/condense_netlist.py` flattens the KiCad
S-expression netlist into three sections (components, library parts, nets). It
is a whitelist of what to keep, not a blacklist of what to drop, so a fault
injected into an unrecognised field still surfaces in the `extra` column.

**Kept:** component ref, value, footprint, `libsource` lib:part and its
description, every non-boilerplate field/property (this is what carries the
injected `Tolerance` faults), each library part's description and full pin
inventory with pin names and electrical types, and every net with each node's
ref, pin number, pinfunction and pintype.

**Dropped:** the `design` block, the `libraries` block, per-component `tstamps`
and `sheetpath`, `datasheet` URLs, `fields` entries duplicating
footprint/datasheet/description, the `Sheetname`/`Sheetfile`/`ki_*`
properties, and `libpart` `docs`/`footprints` globs.

Netlist bytes: **1,300,694 → 261,984 (−79.9%)** over the 36 prompts.
Rendered prompt: 52,296 → 23,451 chars (−55.2%) — the specification, unchanged,
is now ~68% of the prompt, so on this board the netlist is no longer the
dominant cost.

### Pre-run validation (no API calls)

- All 35 faults remain visible after condensing (2–6 changed lines each vs the
  condensed clean board; no scenario produced a zero diff).
- Semantic no-loss check over all 36 netlists: **0 mismatches** — every
  component, net and node preserved with identical values, footprints and net
  membership.

## Result 1 — accuracy is unchanged

Localisation, paired over 144 (model, prompt) pairs:

| Model | base | condensed | delta | won | lost | tied |
|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 44.4% | 41.7% | −2.8pp | 3 | 4 | 29 |
| deepseek/deepseek-v4.1-flash | 36.1% | 33.3% | −2.8pp | 3 | 4 | 29 |
| openai/gpt-6-luna | 22.2% | 27.8% | **+5.6pp** | 4 | 2 | 30 |
| qwen/qwen3.8-flash | 38.9% | 36.1% | −2.8pp | 3 | 4 | 29 |
| **POOLED** | **35.4%** | **34.7%** | **−0.7pp** | **13** | **14** | **117** |

−2.8pp is exactly one prompt out of 36. Three models each moved by one prompt
in the same direction and one moved by two in the other; pooled, 13 pairs
improved and 14 regressed. **Removing 56% of the input tokens did not change
what these models find.** That is the main result, and it is consistent with
the pre-run finding that no engineering content was removed.

The stability is a *net* effect, not per-prompt stability: **27 of 144 pairs
flipped (19%)** while the pooled rate moved 0.7pp. At `temperature=0.0`, that
churn is worth treating as a floor on this benchmark's measurement noise — any
future claim smaller than roughly ±5pp on 36 prompts is not separable from it.

## Result 2 — it did not save money; overall it cost more

| Model | input tokens | output tokens | cost base | cost condensed | change |
|---|---|---|---|---|---|
| openai/gpt-6-luna | 570,455 → 248,436 | 85,032 → 95,111 | $0.114 | $0.079 | **−31%** |
| anthropic/claude-haiku-5.5 | 815,241 → 373,034 | 173,025 → 148,626 | $0.168 | $0.112 | **−34%** |
| qwen/qwen3.8-flash | 629,889 → 265,649 | 1,013,244 → 1,346,230 | $0.533 | $0.652 | **+22%** |
| deepseek/deepseek-v4.1-flash | 596,237 → 259,837 | 2,167,370 → 2,605,658 | $1.671 | $1.998 | **+20%** |
| **POOLED** | **2,611,822 → 1,146,956 (−56%)** | **3,438,671 → 4,195,625 (+22%)** | **$2.486** | **$2.839** | **+14%** |

Input fell 56% consistently across all four tokenizers. But **output rose 22%**,
and output is the more expensive side, so the arm came out 14% *more* expensive
in total. Savings materialise only where input dominated the bill:

- **Input-dominated (gpt-6-luna, haiku):** 31–34% cheaper.
- **Output-dominated (qwen, deepseek):** 20–22% dearer, because their output
  grew by 333k and 438k tokens respectively.

Why output grew on a shorter input is not established here. It is reproducible
across both reasoning models and worth a dedicated test before being explained.

## Result 3 — deepseek's truncation is an output-side failure

deepseek returned **no answer at all** on 15 of 36 prompts (base arm: 12 of 36).
Each such result shows `finish_reason: "length"` with
`completion_tokens == reasoning_tokens == 131072` — its entire output ceiling
spent on hidden reasoning, `text` empty, so the verdict is unparseable.

Condensing the input did not help, and the two rates (42% vs 33%, n=36) are not
separable. The trigger is a genuine ambiguity: fan_controller carries two MCUs
(U2 ATtiny45-20P, U3 ATtiny13V-10S) on the same nets — an alternative-footprint
board — and neither the netlist nor the specification states that populating one
is intended. Truncated runs mention "attiny" 109–1,273 times, re-litigating
whether a second MCU is an extra component. Truncations concentrate in the value
and tolerance scenarios, where the injected fault offers no strong signal to
settle on instead.

In the condensed arm this also consumed the **clean control**, which truncated
where it had been answered in the base arm.

Fixes, in order of directness: cap *reasoning* rather than output
(`reasoning: {max_tokens: N}`, leaving budget for the answer — lowering
`--max-tokens` makes this worse, not better); state the dual-footprint intent
in the specification so the attractor disappears for every model. Note
`--retry-errors` does **not** recover these: they are successful HTTP responses
with empty text, not API errors.

## Caveat — the binary metrics remain unusable

Under `--positive-rule localised`, with 35 faulty prompts and **1** control per
model:

| Model | tp | fp | fn | tn | recall | specificity | MCC |
|---|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 15 | 0 | 20 | 1 | 0.429 | 1.000 | 0.143 |
| qwen/qwen3.8-flash | 13 | 1 | 22 | 0 | 0.371 | 0.000 | −0.212 |
| deepseek/deepseek-v4.1-flash | 12 | 0 | 23 | 1 | 0.343 | 1.000 | 0.120 |
| openai/gpt-6-luna | 10 | 1 | 25 | 0 | 0.286 | 0.000 | −0.255 |

Specificity is 0.000 or 1.000 purely because it rests on a single sample, and
the negative MCCs follow from that one control. **Recall is the only defensible
figure in this table.** Precision, specificity, NPV, F1, balanced accuracy and
MCC all need a real negative class before they mean anything.

## Reading this together

Condensing is a **token and context win, not a cost win**: 56% fewer input
tokens for no measurable accuracy change. That matters most where context is
the binding constraint rather than price — AcornRobotElectronics' netlist is
508 KB (~145k tokens) and condenses to roughly 17k, which is the difference
between a prompt that strains a context window and one that does not.

It is not a reason to expect a cheaper full sweep. On these four models the
sweep would get *dearer* unless deepseek's unbounded reasoning is capped first.

## Reproducing

```sh
# condense (writes netlist.condensed.net + spice.condensed.cir beside the originals)
.venv/bin/python netlist_modifications/scripts/condense_netlist.py \
    --root outputs/Infected/Prompts/AnomalyDetection --boards fan_controller --variant condensed

# run the arm (results -> results/condensed/, summary -> run_summary_condensed.json)
.venv/bin/python netlist_modifications/scripts/run_anomaly_prompts.py \
    --models openai/gpt-6-luna,anthropic/claude-haiku-5.5,deepseek/deepseek-v4.1-flash,qwen/qwen3.8-flash \
    --boards fan_controller --variant condensed --jobs 6 --temperature 0.0

# grade, compare, score
.venv/bin/python netlist_modifications/scripts/grade_anomaly_results.py --variant condensed
.venv/bin/python netlist_modifications/scripts/compare_arms.py --board fan_controller --arm condensed
.venv/bin/python netlist_modifications/scripts/binary_metrics.py \
    --board fan_controller --variant condensed --positive-rule localised
```
