# RQ1 anomaly detection — pooled model comparison (AcornRobotElectronics + fan_controller)

Generated 2026-11-10 from `grades.csv`, filtered to **board ∈ {AcornRobotElectronics,
fan_controller}**. Companion to `fan_controller_rq1_comparison.md`, which covers one board;
this document pools both so trends can be read independently of any single project.

## Design

- **Boards:** 2 of 8, chosen as the size extremes available — fan_controller is the
  smallest design in the set and AcornRobotElectronics the largest.
- **Prompts:** 79 — 77 faulty variants (35 + 42) and 2 clean controls (1 per board).
- **Scenarios:** all **14** RQ1_SimpleMods fault types on both boards. Variants per type
  are 1–3, capped by what each board carries.
- **Models:** 4, each run on all 79 prompts — a fully levelled matrix (**316/316 cells**).
- **Input:** raw KiCad `.net` S-expression + ngspice `.cir` deck, the non-condensed
  representation. Temperature 0.
- **Localisation** (headline): one finding with the expected category that names the
  fault. Unanswered counts as wrong and stays in the denominator.

The two boards differ by roughly an order of magnitude in input size, which is what makes
pooling informative rather than merely additive:

| | fan_controller | AcornRobotElectronics |
|---|---|---|
| netlist | 52 KB | 508 KB |
| input tokens / prompt | ~15–18k | 182k–255k (varies by tokenizer) |
| faulty prompts | 35 | 42 |

## Results — pooled over both boards

| Model | Localised | Top-1 | Detection | Beyond baseline | Baseline-only | Category | Unanswered | False alarm | Cost | $/correct |
|---|---|---|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | **35/77 (45%)** | 30/77 | 67/77 | 63/77 | 4/77 | 37/77 | 0 | 2/2 | $8.450 | $0.241 |
| `deepseek/deepseek-v4.1-flash` | **25/77 (32%)** | 18/77 | 55/77 | 47/77 | 8/77 | 28/77 | 21 | 1/2 | $4.710 | $0.188 |
| `qwen/qwen3.8-flash` | **25/77 (32%)** | 21/77 | 74/77 | 70/77 | 4/77 | 27/77 | 1 | 1/2 | $2.388 | $0.096 |
| `openai/gpt-6-luna` | **17/77 (22%)** | 14/77 | 76/77 | 45/77 | 31/77 | 21/77 | 0 | 2/2 | $1.178 | $0.069 |
| **POOLED** | **102/308 (33%)** | 83/308 | 272/308 | 225/308 | 47/308 | 113/308 | 22 | 6/8 | **$16.727** | $0.164 |

## Cost and latency

| Model | Cost | $/result | Prompt tok | Completion tok | Latency |
|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | $8.450 | $0.1070 | 11,802,420 | 1,288,362 | 95 min |
| `deepseek/deepseek-v4.1-flash` | $4.710 | $0.0596 | 8,680,415 | 4,570,090 | 293 min |
| `qwen/qwen3.8-flash` | $2.388 | $0.0302 | 9,496,398 | 3,075,927 | 481 min |
| `openai/gpt-6-luna` | $1.178 | $0.0149 | 8,420,251 | 251,193 | 42 min |

Total: **$16.727** over 316 calls, 38.4M input and 9.2M output tokens.

## Localisation by board

| Model | fan_controller | Acorn | pooled | change |
|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 16/35 (46%) | 19/42 (45%) | 35/77 (45%) | −1pp |
| `openai/gpt-6-luna` | 8/35 (23%) | 9/42 (21%) | 17/77 (22%) | −2pp |
| `deepseek/deepseek-v4.1-flash` | 13/35 (37%) | 12/42 (29%) | 25/77 (32%) | −8pp |
| `qwen/qwen3.8-flash` | 14/35 (40%) | 11/42 (26%) | 25/77 (32%) | −14pp |
| **POOLED** | **51/140 (36%)** | **51/168 (30%)** | **102/308 (33%)** | **−6pp** |

## Localisation by scenario (pooled)

| Scenario | haiku-5.5 | deepseek-v4.1 | gpt-6-luna | qwen3.8 | Total |
|---|---|---|---|---|---|
| ResistorMagnitudeDownRandom | 6/6 | 3/6 | 3/6 | 5/6 | **17/24 (71%)** |
| ResistorMagnitudeUpRandom | 6/6 | 4/6 | 3/6 | 4/6 | **17/24 (71%)** |
| GndShortRandom | 4/6 | 6/6 | 4/6 | 2/6 | **16/24 (67%)** |
| BridgeRandom | 4/6 | 5/6 | 2/6 | 4/6 | **15/24 (63%)** |
| CapacitorMagnitudeDownRandom | 5/5 | 4/5 | 3/5 | 3/5 | **15/20 (75%)** |
| CapacitorMagnitudeUpRandom | 4/5 | 1/5 | 0/5 | 1/5 | **6/20 (30%)** |
| ResistorToCapacitorRandom | 1/6 | 1/6 | 1/6 | 2/6 | **5/24 (21%)** |
| VccShortRandom | 1/6 | 0/6 | 1/6 | 3/6 | **5/24 (21%)** |
| PolarityFlipRandom | 2/4 | 1/4 | 0/4 | 1/4 | **4/16 (25%)** |
| CapacitorToleranceUpRandom | 1/5 | 0/5 | 0/5 | 0/5 | **1/20 (5%)** |
| ResistorToleranceUpRandom | 1/6 | 0/6 | 0/6 | 0/6 | **1/24 (4%)** |
| CapacitorToResistorRandom | 0/5 | 0/5 | 0/5 | 0/5 | **0/20** |
| CapacitorToleranceDownRandom | 0/5 | 0/5 | 0/5 | 0/5 | **0/20** |
| ResistorToleranceDownRandom | 0/6 | 0/6 | 0/6 | 0/6 | **0/24** |

## Localisation by fault category (pooled)

| Category | Localised | n | Localised % | Detection % | Category % |
|---|---|---|---|---|---|
| `short_to_ground` | 16 | 24 | **66.7%** | 95.8% | 66.7% |
| `bridged_nets` | 15 | 24 | **62.5%** | 95.8% | 75.0% |
| `wrong_value` | 55 | 88 | **62.5%** | 94.3% | 69.3% |
| `polarity` | 4 | 16 | 25.0% | 100.0% | 31.2% |
| `short_to_supply` | 5 | 24 | 20.8% | 87.5% | 20.8% |
| `wrong_component_type` | 5 | 44 | 11.4% | 90.9% | 13.6% |
| `wrong_tolerance` | 2 | 88 | **2.3%** | 75.0% | 2.3% |

Per model, by category:

| Category | haiku-5.5 | deepseek-v4.1 | gpt-6-luna | qwen3.8 |
|---|---|---|---|---|
| `wrong_value` | 21/22 | 12/22 | 9/22 | 13/22 |
| `short_to_ground` | 4/6 | 6/6 | 4/6 | 2/6 |
| `bridged_nets` | 4/6 | 5/6 | 2/6 | 4/6 |
| `short_to_supply` | 1/6 | 0/6 | 1/6 | 3/6 |
| `polarity` | 2/4 | 1/4 | 0/4 | 1/4 |
| `wrong_component_type` | 1/11 | 1/11 | 1/11 | 2/11 |
| `wrong_tolerance` | 2/22 | 0/22 | 0/22 | 0/22 |

## Observations

**1. The cost-effectiveness ranking from fan_controller reverses on two boards.** This is
the single most important change from the one-board document. There, haiku was both the
most accurate *and* the cheapest per correct answer ($0.0105), and deepseek the most
expensive ($0.1285) — the tidy conclusion being "the cheap model is also the best". Pooled,
haiku is still the most accurate but becomes the **most expensive per correct answer**
($0.241), while gpt-6-luna, the *least* accurate model, is the cheapest ($0.069):

| Model | $/correct on fan_controller | $/correct on Acorn | pooled |
|---|---|---|---|
| `anthropic/claude-haiku-5.5` | $0.011 (best) | $0.436 (worst) | $0.241 |
| `openai/gpt-6-luna` | $0.014 | $0.118 (best) | $0.069 |
| `qwen/qwen3.8-flash` | $0.038 | $0.169 | $0.096 |
| `deepseek/deepseek-v4.1-flash` | $0.129 (worst) | $0.253 | $0.188 |

The cause is not accuracy, which barely moved (46% → 45%), but billing. On Acorn haiku's
prompts exceed 200k input tokens and are billed at **5× OpenRouter's list price on both
input and output**, verified by solving the marginal rate from pairs of calls differing
only in output length. Its own tokenizer puts it over that threshold where the other three
models stay under it: 255k tokens for the same netlist that gpt-6-luna counts as 182k. Any
cost-per-correct claim is therefore a statement about board size, not about the model, and
must not be generalised from one board.

**2. Accuracy is stable across a 10× change in input size; two of four models are not.**
Pooled localisation falls only 36% → 30% between the small and large board, so sheer design
size costs about six points. But the per-model picture splits: haiku (−1pp) and gpt-6-luna
(−2pp) are essentially flat, while qwen (−14pp) and deepseek (−8pp) degrade. The rank order
is also only partly preserved — haiku stays first and gpt-6-luna last on both boards, but
qwen falls from second to third. With 35–42 prompts per board a single flip is ~2.5pp, so
haiku's and gpt-6-luna's changes are noise; qwen's is not.

**3. The category ladder is the real result, and it is consistent across both boards.**
Topology faults are found and parameter faults are not. `short_to_ground` (66.7%),
`bridged_nets` (62.5%) and `wrong_value` (62.5%) sit far above `wrong_component_type`
(11.4%) and `wrong_tolerance` (2.3%). The ordering is the same on each board separately,
which is what makes it a property of the fault type rather than of a particular design.

**4. All four tolerance scenarios remain near-zero: 2 of 88.** Both successes are haiku's.
This is a benchmark artefact rather than a blind spot, for the reason given in the
one-board document: the clean netlist has no `Tolerance` field at all, so the injected
"fault" is the *appearance* of a metadata field that was previously absent, and with no
clean reference in the prompt a resistor marked 20% is not identifiably defective. These 22
prompts are 29% of the faulty set and are arguably unanswerable as posed. They drag the
pooled 33% down by roughly 9 points and should be fixed or excluded before any headline
number is published.

**5. Detection remains uninformative; beyond-baseline carries the signal.** Prevalence is
77/79, so a model that always answers "yes" scores 97% detection. gpt-6-luna does almost
exactly that — **76/77 detection against 17/77 localisation** — and the beyond-baseline
column explains why: only 45/77 of its detections mentioned any part it had not already
flagged on the clean control, with **31/77 baseline-only**, four times any other model's
rate. It has a standing list of complaints about each board and recites it. qwen is the
opposite, 74/77 detected and 70/77 beyond baseline, so its findings respond to the specific
file even when wrong. Report localisation and beyond-baseline; do not report detection
alone.

**6. `category` adds little over `localised`.** Pooled the two differ by 11 cells out of
308 (113 vs 102), and for haiku and qwen the gap is 2 cells. When a model assigns the right
category it nearly always names the right part in the same finding, so the binding
constraint is *classifying* the fault, not locating it. The column could be dropped from
future reports without losing information.

**7. `VccShort` is three times harder than `GndShort` despite being structurally
symmetric** — 5/24 against 16/24, and the asymmetry holds on both boards. Worth
investigating directly: the plausible explanation is that a signal pin sitting on a named
supply rail reads as intentional (many pins legitimately do), whereas the same pin on `GND`
does not.

**8. deepseek's score is a floor, not a measurement.** 21 of its 77 faulty results (27%)
are unanswered — cut off at the output ceiling with `finish_reason: length`, the entire
budget spent on hidden reasoning and an empty `text`. Those score as wrong. On the 56 it
did answer it localised 25, or 45%, which would place it level with haiku rather than tied
with qwen. It also emitted 4.57M output tokens, 3.5× haiku's, and that output is what its
bill is made of. A reasoning cap (`reasoning: {max_tokens: N}`) is needed before its number
means anything; lowering `--max-tokens` makes this worse, not better.

## Caveats

- **Two boards of eight.** 79 of the eventual 324 RQ1 prompts, 24%. These are the size
  extremes, which is the best case for detecting scale effects but says nothing about the
  six mid-size boards.
- **n is small per cell.** Per-scenario cells are 4–6 variants per model pooled across both
  boards; one flip moves a scenario rate by 17–25pp. Per-scenario figures are directional
  only. The per-category rows (16–88) are firmer.
- **Two controls.** The false-alarm rate rests on one clean prompt per board — 6 of 8
  flagged. This is also why `binary_metrics_*.csv` reports specificity of exactly 0.000 or
  1.000 and negative MCCs: with prevalence 0.97 only **recall** is defensible. A real
  negative class is needed before precision, specificity, NPV, F1, balanced accuracy or MCC
  mean anything.
- **Unanswered counted wrong** by design, which penalises verbose reasoners (deepseek)
  relative to concise ones.
- **Non-condensed input only.** A paired condensed arm exists for both boards; on
  fan_controller it changed pooled localisation by −0.7pp, and 27 of 144 pairs flipped at
  temperature 0, which is a useful noise floor: **claims below roughly ±5pp on this sample
  size are not separable from run-to-run churn.**

## Reproducing

```sh
.venv/bin/python netlist_modifications/scripts/grade_anomaly_results.py
.venv/bin/python netlist_modifications/scripts/binary_metrics.py \
    --board AcornRobotElectronics --positive-rule localised
# this document's figures: grades.csv filtered to the two boards
```
