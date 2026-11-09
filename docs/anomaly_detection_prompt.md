# Anomaly-Detection Prompt (Design Spec vs. Design Files)

This prompt asks an LLM whether a board's design files contain an anomaly,
using that project's design specification (`docs/design_specs/`) as the
statement of intent. It is run once per board version under
`outputs/Infected/Scenarios/` (one injected fault each), and once per clean
board as a control, so that a model which always answers "anomaly" can be
told apart from one that actually detects faults.

The template below is the single source of truth: `netlist_modifications/scripts/build_anomaly_prompts.py`
reads the text between the `TEMPLATE START` / `TEMPLATE END` markers. It fills
the first two placeholders when building, and leaves the design-file
placeholders for the caller to fill at run time.

| Placeholder | Filled by | With |
|---|---|---|
| `{{PROJECT_NAME}}` | the builder | The board name, e.g. `CF-Chef` |
| `{{DESIGN_SPEC}}` | the builder | The full Markdown of that project's design specification |
| `{{NETLIST}}` | the caller | The contents of the prompt's scrubbed KiCad netlist (`.net`) |
| `{{SPICE_CIRCUIT}}` | the caller | The contents of the prompt's scrubbed SPICE deck (`.cir`) |

## Design rules

- **No answer leakage.** The prompt never names the fault types that were
  injected, and never says the board is faulty. Its checklist is a generic
  design-review list that includes classes no scenario injects (opens,
  polarity, footprint mismatches, missing parts), so a model can't pick the
  answer off the list. The builder also scrubs file metadata that would give
  the answer away. Each faulty netlist's `(source …)` header and library
  `(uri …)` paths held the temporary build folder named after the modified
  part, and each SPICE deck's `write` line held the scenario path. All are
  normalised in faulty and clean files alike, and so is the export
  `(date …)`, so clean and faulty files can't be told apart by their headers.
  Fill `{{NETLIST}}` / `{{SPICE_CIRCUIT}}` from the scrubbed copies the
  builder writes, never from the raw files under `outputs/Infected/Scenarios/`.
- **The spec is intent, not ground truth.** The specs mark some claims
  "Inferred", and list real, pre-existing quirks of the boards ("Known
  limitations", logged bugs). The prompt tells the model that anything the
  spec documents as how the board actually is does not count as an anomaly.
- **Structured, gradable output.** The answer is one JSON object, with a fixed
  `category` vocabulary and the refs, pins and nets involved, so it can be
  scored automatically against `answer_key.jsonl` (see the builder).

## Template

<!-- TEMPLATE START -->
You are an expert PCB design reviewer. You will be given the design specification for the hardware project **{{PROJECT_NAME}}**, and the design files for one build of that board. Your job is to decide whether the design files contain an **anomaly**: a deviation from the intended design that would make the board behave differently from what was intended. It could come from a design error, an assembly or sourcing mistake, or deliberate tampering.

The design files may be completely correct. Do not assume an anomaly exists. Report one only if the files support it.

## Inputs

### 1. Design specification

The specification describes the intended design: its purpose, architecture, key components and their values, power rails and interfaces. It was written by examining the reference design. Statements marked **Inferred** are the author's reasoning, not confirmed fact. Sections such as "Known limitations", "Known issues" or "logged bugs" describe real properties of the reference design. Those are **not** anomalies, and must not be reported.

The specification may not mention every component. Where it is silent, judge the design with standard electrical-engineering practice and with the component's own metadata (its library part, description, footprint and datasheet fields).

<design_specification>
{{DESIGN_SPEC}}
</design_specification>

### 2. Design files

- **KiCad netlist:** the authoritative connectivity. Every component, with its reference, value, footprint, library part and fields, and every net, with the pins on it. Net names of the form `Net-(<ref>-<pin>)` are generated automatically from a pin on that net.
- **SPICE deck:** a simulation deck derived from the same schematic. Only resistors, capacitors, inductors, diodes and sources are modelled. ICs, connectors and transistors are left out, and ground is node `0`. Treat this file as a secondary view; the netlist takes precedence.

<netlist>
{{NETLIST}}
</netlist>

<spice_circuit>
{{SPICE_CIRCUIT}}
</spice_circuit>

## How to review

Work through the design systematically before answering:

1. **Power and ground.** For each supply rail and for `GND`, check which pins sit on it. Look for signal, enable, reset, data or sense pins tied directly to `GND` or to a supply rail where the spec or the part's function says they should not be. Look for two different rails joined together.
2. **Connectivity.** For each important interface the spec describes (buses, enables, resets, feedback networks, sensing paths, connectors), check that the expected pins share a net, and that no net merges signals that should be separate, such as two unrelated buses or a data line joined to a power or control line.
3. **Component identity.** For every two-terminal passive, check that its reference prefix (`R`, `C`, `L`), library part, description, footprint and value all agree with each other and with its role in the circuit. Examples: a pull-up or current-limit position occupied by a capacitor, or a decoupling position occupied by a resistor.
4. **Values.** Check each passive's value against the spec where the spec states it, and otherwise against its role. Examples: a pull-up three orders of magnitude off, a decoupling capacitor in millifarads in a small chip footprint, or a feedback or timing part inconsistent with the stated output or timing.
5. **Tolerances and ratings.** Check stated tolerance, voltage rating and dielectric fields against the part's description and its role (precision divider, current sense, reference, timing).
6. **Anything else.** Polarity, missing or extra components, open connections, footprint mismatches.

Rules:
- Base every finding on specific evidence quoted from the files: references, pin numbers, net names and values. Where the finding contradicts the spec, quote the relevant spec text too.
- Report only real deviations. Do not report pre-existing properties the spec documents, style issues, automatically generated net names, component ordering, or parts the SPICE deck leaves out by design.
- If you find several candidate issues, rank them by confidence, most likely first, and report at most 3.

## Output format

Respond with a **single JSON object** and nothing else: no prose before or after it, and no Markdown code fence.

{
  "anomaly_detected": true or false,
  "confidence": a number from 0 to 1 for your overall verdict,
  "anomalies": [
    {
      "category": one of "short_to_ground", "short_to_supply", "bridged_nets", "open_connection", "wrong_component_type", "wrong_value", "wrong_tolerance", "wrong_rating", "polarity", "footprint_mismatch", "missing_component", "extra_component", "other",
      "components": ["references involved, e.g. \"R5\""],
      "pins": ["pins involved, e.g. \"U1.8\""],
      "nets": ["nets involved, exactly as named in the netlist"],
      "observed": "what the design files show",
      "expected": "what the specification or sound design practice requires instead",
      "evidence": [
        {"source": "netlist" | "spice" | "spec", "quote": "short verbatim excerpt"}
      ],
      "impact": "the likely effect on the board's behaviour",
      "confidence": a number from 0 to 1
    }
  ],
  "summary": "one or two sentences stating your verdict and the main reason for it"
}

If `anomaly_detected` is `false`, `anomalies` must be an empty list.
<!-- TEMPLATE END -->

## Building

```bash
.venv/bin/python netlist_modifications/scripts/build_anomaly_prompts.py                 # all scenarios + clean controls
.venv/bin/python netlist_modifications/scripts/build_anomaly_prompts.py --scenarios GndShortRandom,BridgeRandom --no-controls
```

Output (default `outputs/Infected/Prompts/AnomalyDetection/`):

One folder per project, one subfolder per anomaly, plus each project's clean
control:

```
<Board>/                              # 8 project folders
  <Scenario>_<Variant>/               # one per anomaly, e.g. GndShortRandom_Wire1
    prompt.md                         # spec filled, {{NETLIST}} / {{SPICE_CIRCUIT}} left open
    netlist.net                       # scrubbed netlist for this prompt
    spice.cir                         # scrubbed SPICE deck for this prompt
    results/<model>.json              # one per model, written by the runner
  Control/                            # the clean board: same four items
prompts.jsonl                         # one line per prompt: {"id", "prompt", "netlist", "spice_circuit"}; no ground truth
answer_key.jsonl                      # one line per prompt: expected verdict, category, refs and nets
run_summary.json                      # per-model totals, written by the runner
```

A prompt's `id` is its folder path under the root: `<Board>/<Scenario>_<Variant>`
(e.g. `CF-Chef/GndShortRandom_Wire1`) or `<Board>/Control`. The clean
controls' SPICE decks are built in a temporary folder with the same pipeline as
the scenarios; only the scrubbed `spice.cir` is kept.

To run a prompt, substitute the two files' contents into the placeholders:

```python
from netlist_modifications.scripts.build_anomaly_prompts import render
text = render("outputs/Infected/Prompts/AnomalyDetection/CF-Chef/GndShortRandom_Wire1")  # folder or its prompt.md
# or by hand: prompt.replace("{{NETLIST}}", net).replace("{{SPICE_CIRCUIT}}", cir)
```

`render()` reads the folder's `netlist.net` / `spice.cir` and refuses to
return a prompt with an unfilled placeholder. A runner can iterate over
`prompts.jsonl` without ever opening `answer_key.jsonl`. Records in both
files share the same `id`.

## Running

`netlist_modifications/scripts/run_anomaly_prompts.py` renders each prompt and sends it to OpenRouter
models as a single user message. It saves every response together with the
run's metadata.

```bash
.venv/bin/python netlist_modifications/scripts/run_anomaly_prompts.py --dry-run          # token / cost estimate, no calls
.venv/bin/python netlist_modifications/scripts/run_anomaly_prompts.py \
    [--models a/x,b/y] [--boards CF-Chef,stack-chan] [--limit 10] [--jobs 4] \
    [--max-tokens 8000] [--reasoning-effort medium]
```

Each call may take up to `--timeout` seconds (default 1800) and is not retried
automatically (`--max-retries 0`). Reasoning models can take 5–10 minutes per
answer here. Under the client's own defaults (a 600 s timeout and 2 automatic
retries), a slow answer was abandoned and regenerated from scratch, possibly
billed each time. A real failure is saved as an error. Re-run those
deliberately with `--retry-errors`.

Without `--models`, the runner uses its `DEFAULT_MODELS`: eight fast, low-cost
models, closed and open weights, all with enough context for the largest
prompt (AcornRobot, about 151k tokens).

| Model | Weights |
|---|---|
| `openai/gpt-6-luna` | closed |
| `anthropic/claude-haiku-5.5` | closed |
| `qwen/qwen3.8-flash` | closed (Alibaba API model) |
| `deepseek/deepseek-v4.1-flash` | open |
| `z-ai/glm-5.3-flash` | open |
| `meta-llama/llama-4-scout` | open |
| `google/gemma-4-31b-it` | open |
| `minimax/minimax-m3.1-flash` | open |

The open / closed labels follow each family's usual release practice. Check
the model card where licensing matters.

Results go into each prompt's own folder, at `<Board>/<anomaly>/results/<model>.json`,
with the `/` in the model name written as `__` (e.g. `openai__gpt-6-luna.json`).
Each holds:

| Key | Holds |
|---|---|
| `response` | `text` (raw model output), `parsed` (the JSON verdict), `parse_error`, `finish_reason`, and `reasoning` if the model returned any |
| `usage` | `prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `cached_tokens`, `total_tokens`, `cost_usd`, `cost_details`, as reported on the response (requested with OpenRouter's `usage: {include: true}`) |
| `generation` | OpenRouter's `/generation` record for the call: provider, native (provider-tokenizer) token counts, `total_cost`, `latency` and `generation_time` (ms), cache discount, finish reasons |
| `timing` | `started_at`, `ended_at` (UTC) and wall-clock `latency_s` |
| `request` | model, temperature, max tokens, reasoning effort |
| `prompt` | paths to the prompt and its netlist and SPICE files, character count, and SHA-256 of the exact rendered prompt |
| `raw_response` | the complete, unfiltered response dump |
| `error` | set instead of `response` / `usage` when the API call failed |

`run_summary.json` at the root holds, for each model, totals of results,
errors, parse errors, every token count, cost and latency over all of that
model's saved results. It's recomputed after each run, so it stays correct
when a run is resumed.
Prompts that already have a result are skipped. `--retry-errors` re-runs only
the ones whose saved result is an API error, and `--overwrite` re-runs
everything. The runner never reads `answer_key.jsonl`.

## Grading

```bash
.venv/bin/python netlist_modifications/scripts/grade_anomaly_results.py [--models a/x,b/y]
```

The grader scores every saved result against `answer_key.jsonl` and writes
three files at the prompts root:
- `grades.csv`: one row per model and prompt;
- `grade_summary.json`: per-model totals, plus per model × scenario and model × board;
- `grade_summary.md`: the same as Markdown tables.

| Measure | Meaning |
|---|---|
| Detection | Share of faulty prompts answered `anomaly_detected: true` |
| Beyond baseline | The same, counting only findings that aren't repeats of what the model flagged on that board's clean control |
| Category | Some finding has the expected category |
| **Localisation** (headline) | A single finding has the expected category and names the fault (rules below) |
| Top-1 | The same, for the model's first finding only |
| False alarms | Share of clean controls answered `anomaly_detected: true` |

Each result gets a `status`:
- `ok`, or `repaired` when stray closing brackets had to be removed before the JSON would parse;
- `incomplete` when the answer was cut off at the output limit;
- `unparsed` when the JSON couldn't be recovered;
- `api_error` when the call failed.

The last three count as wrong answers. They stay in every denominator rather
than being dropped, so a model can't improve its score by failing to answer.
If a board's control has no result for a model yet, there is no baseline for
that board, and "beyond baseline" equals detection.

Each `answer_key.jsonl` line carries `prompt`, `scenario`, `variant`, `board`,
`anomaly` (`true` / `false`), the expected `category`, and the `components` and
`nets` the injected fault touched. A response counts as a correct detection if
`anomaly_detected` matches. It counts as a correct localisation if one of its
`anomalies` has the expected `category` and shares at least one component or
net with the answer key.

For shorts and bridges, match components against `net_components`: every part
on the net(s) the fault pulled together. The pin a short was placed on is
arbitrary, so naming any part on that net counts. For example, for the CF-Chef
GND short placed on C7.1, naming U1 (whose enable pin is on that net) or R5 is
correct. For the swaps, value faults and tolerance faults, `net_components` is
just the modified part(s).

The set is heavily imbalanced: 256 faulty prompts against 8 clean controls
(one per board). Report detection as per-class rates (true-positive rate on
faulty prompts, true-negative rate on controls) rather than plain accuracy,
or run each control several times (different seeds or models) to balance the
classes.

Scenario → expected `category`:

| Scenario | category |
|---|---|
| GndShortRandom | `short_to_ground` |
| VccShortRandom | `short_to_supply` |
| BridgeRandom | `bridged_nets` |
| ResistorToCapacitorRandom, CapacitorToResistorRandom | `wrong_component_type` |
| ResistorMagnitudeUpRandom, ResistorMagnitudeDownRandom, CapacitorMagnitudeUpRandom, CapacitorMagnitudeDownRandom | `wrong_value` |
| ResistorToleranceUpRandom, CapacitorToleranceUpRandom, ResistorToleranceDownRandom, CapacitorToleranceDownRandom | `wrong_tolerance` |
| PolarityFlipRandom | `polarity` |

Spec mapping: `AcornRobotElectronics` → `acorn-robot-electronics.md`,
`OPNhydro-r2` → `OPNhydro.md`, `PortalHardware` → `portal-hardware.md`, and
`fan_controller` → `MyKiCad.md`, which is the overview of the monorepo the fan
controller comes from. It does not describe that board specifically, so
fan_controller prompts lean on general design practice. The other boards'
specs share the board's name.

Prompt size: once filled, the netlist dominates. AcornRobot's is about
500 KB (very roughly 150k tokens), while CF-Chef's, Meshinger's and the
smaller boards' are 36–100 KB.
