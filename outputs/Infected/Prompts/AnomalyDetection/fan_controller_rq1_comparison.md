# fan_controller — RQ1 anomaly-detection model comparison

Generated 2026-11-09 from `grades.csv`, filtered to **board = fan_controller**.
Separate from `grade_summary.md`, which mixes boards and uneven samples.

## Design

- **Board:** fan_controller (1 of 8), 35 faulty variants + 1 clean control.
- **Scenarios:** all **14** RQ1_SimpleMods fault types. Variants per type are 1-3, capped by the board (only 2 capacitors, 1 polarised part).
- **Models:** 4, each run on **all 36 prompts** - a fully levelled matrix (144/144 cells).
- **Input:** raw KiCad `.net` S-expression + ngspice `.cir` deck, ~17.5k prompt tokens each. Temperature 0.
- **Localisation** (headline): one finding with the expected category that names the fault. Unanswered counts as wrong.

## Results

| Model | Localised | Top-1 | Detection | Beyond baseline | Category | Unanswered | False alarm | Cost | $/correct |
|---|---|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | **16/35 (46%)** | 16/35 | 25/35 | 21/35 | 16/35 | 0 | 1/1 | $0.168 | $0.0105 |
| `qwen/qwen3.8-flash` | **14/35 (40%)** | 14/35 | 33/35 | 33/35 | 14/35 | 0 | 0/1 | $0.533 | $0.0380 |
| `deepseek/deepseek-v4.1-flash` | **13/35 (37%)** | 11/35 | 22/35 | 14/35 | 14/35 | 12 | 1/1 | $1.671 | $0.1285 |
| `openai/gpt-6-luna` | **8/35 (23%)** | 7/35 | 35/35 | 10/35 | 9/35 | 0 | 1/1 | $0.114 | $0.0142 |

## Cost and latency

| Model | Cost | $/result | Prompt tok | Completion tok | Latency |
|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | $0.168 | $0.0047 | 815,241 | 173,025 | 13 min |
| `qwen/qwen3.8-flash` | $0.533 | $0.0148 | 629,889 | 1,013,244 | 181 min |
| `deepseek/deepseek-v4.1-flash` | $1.671 | $0.0464 | 596,237 | 2,167,370 | 126 min |
| `openai/gpt-6-luna` | $0.114 | $0.0032 | 570,455 | 85,032 | 15 min |

Total: **$2.486** over 144 calls.

## Localisation by scenario

| Scenario | claude-haiku-5.5 | qwen3.8-flash | deepseek-v4.1-flash | gpt-6-luna | Total |
|---|---|---|---|---|---|
| BridgeRandom | 2/3 | 2/3 | 3/3 | 1/3 | **8/12** |
| CapacitorMagnitudeDownRandom | 2/2 | 1/2 | 2/2 | 1/2 | **6/8** |
| CapacitorMagnitudeUpRandom | 2/2 | 0/2 | 0/2 | 0/2 | **2/8** |
| CapacitorToResistorRandom | 0/2 | 0/2 | 0/2 | 0/2 | **0/8** |
| CapacitorToleranceDownRandom | 0/2 | 0/2 | 0/2 | 0/2 | **0/8** |
| CapacitorToleranceUpRandom | 0/2 | 0/2 | 0/2 | 0/2 | **0/8** |
| GndShortRandom | 2/3 | 1/3 | 3/3 | 2/3 | **8/12** |
| PolarityFlipRandom | 1/1 | 1/1 | 1/1 | 0/1 | **3/4** |
| ResistorMagnitudeDownRandom | 3/3 | 3/3 | 2/3 | 1/3 | **9/12** |
| ResistorMagnitudeUpRandom | 3/3 | 2/3 | 1/3 | 1/3 | **7/12** |
| ResistorToCapacitorRandom | 1/3 | 2/3 | 1/3 | 1/3 | **5/12** |
| ResistorToleranceDownRandom | 0/3 | 0/3 | 0/3 | 0/3 | **0/12** |
| ResistorToleranceUpRandom | 0/3 | 0/3 | 0/3 | 0/3 | **0/12** |
| VccShortRandom | 0/3 | 2/3 | 0/3 | 1/3 | **3/12** |

## Observations

**1. Accuracy does not track cost.** `claude-haiku-5.5` leads on localisation (46%) at $0.168, while `deepseek-v4.1-flash` scores lowest-but-one (37%) at $1.671 - **10x the cost for fewer correct answers**. Per correct localisation: haiku $0.011, gpt-6-luna $0.014, qwen $0.038, deepseek $0.129.

**2. DeepSeek's score is depressed by truncation, not only by reasoning.** 12 of its 36 results have status `incomplete` - cut off at the output limit mid-answer. It emitted 2.76M tokens, ~3x haiku. Those 12 are scored wrong, so its 37% is a floor, not a clean measurement. Re-running with a higher `--max-tokens` would be needed before treating this number as a model property.

**3. All 4 tolerance scenarios scored 0/40 across every model.** This is a benchmark artefact, not a blind spot. The clean netlist contains *no* `Tolerance` field, so the injected 'fault' is the **appearance of a metadata field that was previously absent**. With no clean reference in the prompt, a resistor marked 20% is not identifiably defective. These 10 variants (~29% of the board's set) are arguably unanswerable as posed and should be reconsidered before being reported as detection failures.

**4. Detection and localisation are close to uncorrelated.** `gpt-6-luna` detected 35/35 but localised 8/35 - it flags something almost always, with only 10/35 beyond its own clean-control baseline. `qwen3.8-flash` detected 33/35 with 33/35 beyond baseline. Headline 'detection' rates are near-meaningless here; beyond-baseline and localisation carry the signal.

**5. Shorts and value faults are tractable; swaps and tolerance are not.** Across models: ResistorMagnitudeDown 9/12, Bridge 8/12, GndShort 8/12 versus CapacitorToResistor 0/8 and all tolerance 0/40. VccShort (3/12) is notably harder than GndShort (8/12) despite being structurally symmetric.

## Caveats

- **n is small.** Per-scenario cells are 1-3 variants per model; a single flip moves a scenario rate by 33pp. Treat per-scenario figures as directional only.
- **One board.** fan_controller is the smallest design (~17.5k prompt tokens). Results may not transfer to boards like AcornRobotElectronics (~145k tokens).
- **One control.** False-alarm rate rests on a single clean prompt per model - 3 of 4 flagged it, but n=1.
- **Unanswered counted wrong** by design, which penalises verbose reasoners (deepseek) relative to concise ones.

