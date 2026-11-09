# LLM Prompts for Generating PCB Design Questions

Based on analysis of the question files in `outputs/` folder, there are **3 distinct categories** of questions. Below are recommended prompts for generating questions in each category.

---

## Category 1: `component_datasheet`

### Purpose
Questions that verify component specifications, characteristics, and capabilities by referencing component datasheets.

### Key Observations from Existing Questions
- Focuses on IC/component properties: temperature ratings, voltage limits, communication interfaces (I2C, SPI, UART, CAN, USB, Ethernet, WiFi, Bluetooth)
- Tests for component capabilities: flash, memory, PWM module, magnetic sensor, motion sensor
- Uses component references (U1, U2, U3, U6, U8, U9, U12, U25, U32, U33, REG1, REG2, SW2, SW3, D1, etc.)
- Format: `"Does the component {REF} have {PROPERTY} according to its datasheet?"`
- Expected answers: YES or NO

### LLM Prompt for Generating `component_datasheet` Questions

```
You are a PCB design verification assistant. Generate questions that test whether a component has specific characteristics or capabilities based on its datasheet.

**Input Context:**
- A KiCad schematic JSON file containing component references, values, and properties
- Component datasheets in PDF format for integrated circuits (ICs)
- Available properties from component descriptions include: temperature ratings, voltage ratings, current ratings, communication interfaces, special capabilities

**Rules for Question Generation:**
1. Select a component reference (e.g., U1, U2, U3, U6, U8, U9, U12, REG1, REG2, etc.)
2. Formulate a question about ONE specific property or capability
3. Use clear, verifiable properties from the datasheet such as:
   - Temperature specifications (max/min operating/junction temperature, °C)
   - Voltage specifications (max/min supply voltage, V)
   - Current specifications (max current, quiescent current, µA/A)
   - Communication interfaces (I2C, SPI, UART, CAN, USB, Ethernet, WiFi, Bluetooth)
   - Special capabilities (flash, memory, PWM, ADC, DAC, sensor types)
   - Physical characteristics (output voltage, dropout voltage, dielectric strength)

**Question Format:**
"Does the component {COMPONENT_REF} have {PROPERTY} according to its datasheet?"

**Examples:**
- "Does the component U3 have a maximum operating temperature of 125°C according to its datasheet?"
- "Does the component U6 have I2C capabilities according to its datasheet?"
- "Does the component U12 have a minimum operating ambient temperature of -30°C according to its datasheet?"
- "Does the component REG2 have a maximum current of 1.5A according to its datasheet?"

Generate 20 unique questions of this format. Vary the components, properties, and values. Provide only the question text and indicate the answer should be YES or NO.
```

---

## Category 2: `spice_behaviour`

### Purpose
Questions that verify SPICE circuit simulation results - checking if signals maintain specific voltage levels throughout the simulation.

### Key Observations from Existing Questions
- Focuses on nets and signals in the circuit
- Tests voltage levels: 0V, 3.3V, 5V, 12V, ~25V
- Uses net names like: `serial_can_pwr_3.3v`, `net-_q9-g_`, `scl0_gpio45`, `+12v`, `+3v3`, `vbus`, `bat+`, etc.
- Format variants:
  - "Does the net {NET_NAME} maintain a voltage of X V during the entire simulation?"
  - "Does the {SIGNAL_NAME} signal maintain a voltage of ~X V during the entire simulation?"
  - "Does the net {NET_NAME} obtain a steady state of ~X V after the entire simulation?"
- Expected answers: YES or NO

### LLM Prompt for Generating `spice_behaviour` Questions

```
You are a PCB circuit simulation verification assistant. Generate questions that test SPICE simulation results by verifying signal voltage levels throughout the simulation.

**Input Context:**
- A SPICE circuit netlist file (.cir)
- A SPICE simulation results JSON file containing time-series voltage data for each net
- Power rails typically identified: +3.3V, +5V, +12V, VBUS, BAT+, etc.
- Signal nets have names like: net-*, signal names with underscores

**Rules for Question Generation:**
1. Select a net or signal name from the circuit
2. Choose a target voltage level (typically 0V, 3.3V, 5V, or 12V)
3. Formulate YES/NO questions about voltage stability or steady state

**Question Formats:**
- "Does the net {NET_NAME} maintain a voltage of {VOLTAGE}V during the entire simulation?"
- "Does the {SIGNAL_NAME} signal maintain a voltage of ~{VOLTAGE}V during the entire simulation?"
- "Does the net {NET_NAME} obtain a steady state of ~{VOLTAGE}V after the entire simulation?"
- "Is the {SIGNAL_NAME} signal at {VOLTAGE}V for the entire simulation?"
- "Is the {POWER_RAIL} power rail stable at approximately {VOLTAGE}V throughout the simulation?"

**Voltage Levels to Use:**
- 0V (ground/reference signals)
- 3.3V (logic level signals)
- 5V (legacy logic/IO signals)
- 12V (power rails)
- ~1.2V (special cases like feedback nets)

Generate 20 unique questions. Mix different net names and voltage levels to cover both true and false cases.
```

---

## Category 3: `theory_layout`

### Purpose
Questions that verify physical connections between components and nets in the PCB layout.

### Key Observations from Existing Questions
- Focuses on component-to-net connectivity
- Uses component references (J1, J2, J3, R1, R2, R3, C1, C2, U1, U4, Q1, Q2, Y1, Y2, TR1, etc.)
- Tests connections to specific nets/signals like: GND, _p_5V, _p_3V3, RX4, USBC_VBUS_IN, etc.
- Format: `"Is the component {COMPONENT} connected to {NET_NAME}?"`
- Expected answers: YES or NO

### LLM Prompt for Generating `theory_layout` Questions

```
You are a PCB layout verification assistant. Generate questions that verify whether components are physically connected to specific nets in the circuit schematic.

**Input Context:**
- A KiCad schematic JSON file with component references and net connections
- Nets are identified by names like: GND, _p_5V, _p_3V3, RX4, USBC_VBUS_IN, WS2812, etc.
- Components have pins connected to various nets in the design

**Rules for Question Generation:**
1. Select a component reference (e.g., J1, J2, J3, R1, R2, R3, C1, C2, U1, U6, Q1, Q2, Y1, Y2, TR1, etc.)
2. Select a net name that exists in the circuit
3. Formulate YES/NO questions about connectivity

**Question Format:**
"Is the component {COMPONENT_REF} connected to {NET_NAME}?"

**Component Types to Include:**
- Connectors (J1, J2, J3, etc.)
- Resistors (R1, R2, R3, etc.)
- Capacitors (C1, C2, C3, etc.)
- Integrated circuits (U1, U2, U3, etc.)
- Transistors (Q1, Q2, etc.)
- Crystals (Y1, Y2, etc.)
- Test points (TP1, TP2, TP3)
- Switches (SW1, SW2, SW3)
- LEDs (LED1, LED2, LED3)
- Modules/Feedback components (FB1, FB, Module1)

**Net Types to Include:**
- Power nets: GND, _p_5V, _p_3V3, +3V3, +5V, +12V
- Signal nets: RX, TX, SCK, CS, SDA, SCL (with specific bus designations)
- Interface nets: USB_DM, USB_DP, I2C_SCL, SPI_MISO, UART_RX
- Special function nets: HEATER, PWM, RESET, BOOT, ENABLE

Generate 20 unique questions. Ensure questions test real connections that exist in the circuit to create meaningful YES/NO answers.
```

---

## Category 4: `component_value_anomaly`

### Purpose

Questions that test whether a passive component's (R/C/L) **value** is
plausible for its role in the circuit — designed to catch the
`ComponentSubstitution/Value` Trojan family in `netlist_trojans` (see
`netlist_trojans/insert_trojan/value.py`), which shifts one component's
SI-magnitude prefix (`10k` → `10M`, `100n` → `100u`, a bare `47` → `47k`)
while leaving every digit, the decimal point, and the base unit untouched.
That mechanism — and only that mechanism — is the ground truth this category
checks for; it is not a general "is this a sensible resistor value" oracle.

### Design rationale (from two worked examples)

Generating this category means picking between **four independent signals**,
because no single one catches every case:

1. **HadesFCS, ref R6** (feedback-divider bottom resistor for regulator
   `REG1`, a MIC26903): shifting `1.3k` → `1.3m` is directly SPICE-visible —
   `V(REG_FB)` collapses from `1.531V` (Clean) to `0.0021V` (Infected). A
   *simulated-voltage* question catches this immediately.
2. **fan_controller, ref R1** (nominal gate pull-up for Q1, fed through Q2):
   shifting `10k` → `10` produces **zero** simulated difference — `Net-_Q1-G_`
   reads exactly `5V` in both Clean and Infected, because Q1/Q2 aren't
   SPICE-modeled (this pipeline's `.cir` export only carries passives it can
   model — see `netlist_trojans/README.md`'s Conversions section), so no
   current ever flows through R1 either way. A simulated-voltage question is
   **blind** to this Trojan. Only a magnitude-plausibility or outlier check
   (formats 2–3 below) can catch it.

So: always generate a mix of simulation-grounded (format 1) and
simulation-free (formats 2–4) questions per project — never only format 1, or
the bank will silently miss every Trojan sitting on an unmodeled node.

### LLM Prompt for Generating `component_value_anomaly` Questions

```
You are a PCB anomaly-detection assistant. Generate questions that test
whether a resistor/capacitor/inductor's value is plausible for its role in
this specific circuit, or whether it looks like a magnitude-substitution
error (e.g. a pull-up misread as 10M instead of 10k).

**Input Context (per project):**
- The project's circuit JSON (component refs, values, footprints, connected
  net names) — e.g. `outputs/Clean/<board>/<board>.json`, or, for a specific
  infected variant, `outputs/Infected/ComponentSubstitution/Value/<board>/<ref>/<board>.json`
- The project's SPICE circuit JSON with simulated node voltages —
  `outputs/Clean/<board>/<board>_SPICE_circuit.json`, or for an infected
  variant, the sibling JSON next to its `.raw` file (parse with
  `KiCadSPICECircuitProcesser.parse_spice_simulated_data`)
- `outputs/Infected/ComponentSubstitution/Value/manifest.json` — which
  ref/board pairs actually carry this Trojan, and their `old_value`/`new_value`
- `outputs/Infected/ComponentSubstitution/spice_manifest.json` — whether that
  ref's line was even present in the Clean `.cir` (`status: "unchanged"` with
  detail `"... not present in Clean .cir"` means the ref is NOT SPICE-modeled;
  skip format 1 for it, use formats 2–4 instead)
- Component datasheets via FAISS-embedded chunks
  (`<project>/embeddings/<REF>_chunks.json`), for regulator/reference ICs

**Rules for Question Generation — four formats, mix all of them:**

1. **Simulated voltage vs. expected** (needs the ref to be SPICE-modeled —
   check the spice_manifest first). Pick a net driven by the component under
   test. Ground truth: average the last 10 transient sample points for that
   net's `v(...)` trace (same "steady-state average" convention as
   `KiCadSPICECircuitProcesser.check_steady_state_average_matches_expected_voltage`)
   and compare to the target voltage in the question, rounded to 2 decimal
   places.
   Format: "Does the net {NET_NAME} settle to approximately {VOLTAGE}V by
   the end of the transient simulation?"

2. **Magnitude plausibility for inferred role.** Infer the component's role
   from the net name(s) it touches (keyword heuristics: `SDA`/`SCL`/`RST`/`EN`/
   a bus name → pull-up/pull-down, typical 1k–100k; a cap directly bridging a
   power-rail net to `GND`/`0` → decoupling, typical 1nF–10uF; a resistor on a
   net named `*FB*`/`*_FB` → feedback divider, typical 100Ω–1MΩ; a resistor
   in series with a crystal/oscillator net → timing, typical 1–100Ω). Ground
   truth: does the component's actual value fall inside that role's typical
   decade range?
   Format: "Is {REF}'s value ({VALUE}) within the typical range for a
   {ROLE} in this position?"

3. **Cross-component outlier.** Within the same board, gather every other
   component of the same family (R/C/L) and same inferred role (or same
   footprint, if role can't be inferred). Ground truth: does {REF}'s
   log10-magnitude deviate from the sibling group's median by more than 2
   decades?
   Format: "Compared to its {N} same-role sibling components ({REFLIST}),
   is {REF}'s value a multi-decade outlier?"

4. **Datasheet-grounded formula check.** For a feedback-divider pair
   (top/bottom resistor into a regulator's FB pin), look up the regulator's
   reference voltage from its datasheet chunks, compute
   `Vout = Vref * (1 + Rtop/Rbottom)` (or the part-specific formula stated in
   the datasheet — do not assume this generic one applies to every regulator),
   and compare against the nominal voltage implied by the output net's own
   name (e.g. `+3V3` implies 3.3V).
   Format: "Given {REF_TOP} and {REF_BOTTOM} and {IC_REF}'s datasheet feedback
   reference, does the computed output voltage match the nominal value implied
   by the net name '{NET_NAME}'?"

**Examples:**
- "Does the net REG_FB settle to approximately 1.53V by the end of the
  transient simulation?" (format 1)
- "Is R6's value (1.3mΩ) within the typical range for a feedback-divider
  resistor in this position?" (format 2 — answer NO)
- "Compared to its 4 same-role sibling decoupling capacitors (C1, C3, C4,
  C5), is C2's value a multi-decade outlier?" (format 3)
- "Given R5 and R6 and REG1's datasheet feedback reference, does the
  computed output voltage match the nominal value implied by the net name
  '+5V'?" (format 4)

Generate 20 unique questions, drawing from ALL FOUR formats (not just one),
and note next to each which format it uses. Provide only the question text
and indicate the answer should be YES or NO.
```

### Notes specific to this category

- **This category is single-file scoring, like the other three** — a bank
  generated against a Clean project should score entirely YES (no anomalies);
  a bank generated against one `ComponentSubstitution/Value/<board>/<ref>/`
  variant should have its questions about *that* ref trend NO, while every
  other component in the same variant still scores YES. Don't conflate this
  with `netlist_trojans.gen_trojan_questions`'s separate `clean_answer` /
  differential scoring convention — that's a different pipeline.
- **Tolerance substitutions are out of scope here.** `ComponentSubstitution/Tolerance`
  never touches a component's `value` field (see `netlist_trojans/insert_trojan/tolerance.py`),
  so none of these four formats can detect it — see Category 5 below.

---

## Category 5: `component_tolerance_anomaly`

### Purpose

Questions that test whether a passive component's declared `Tolerance`
property is plausible — designed to catch the `ComponentSubstitution/Tolerance`
Trojan family (see `netlist_trojans/insert_trojan/tolerance.py`), which
inserts or overwrites a `(property (name "Tolerance") (value "..."))` on one
R/C/L component while leaving `value`, footprint, and every net
byte-for-byte untouched. Because nothing else changes, **none of this
Trojan's effect is visible in simulation** — `spice_behaviour` and
`component_value_anomaly` questions score identically on Clean and Infected
variants of a Tolerance substitution (confirmed directly:
`outputs/Infected/ComponentSubstitution/spice_manifest.json` records every
Tolerance-category `.cir` as `"tolerance-only change ... simulated values ==
Clean template"`). Detection here has to come entirely from the *text* of the
netlist and, where available, the part's real specification — not from
electrical behavior.

### Design rationale (from two worked examples, two different signals)

1. **AcornRobotElectronics, ref C1** (a real sourced part — LCSC `C2887234`,
   NJCON 47µF polymer aluminum cap): its own `description`/`field` text
   already states `"63V 47uF ±20% Plugin..."`. The Trojan adds
   `(property (name "Tolerance") (value "10%"))` — which directly contradicts
   the ±20% the part's own printed description states, on the *same*
   component block. This is checkable from the netlist text alone, no
   datasheet lookup needed — the strongest possible signal, but only
   available where a vendor-sourced part with declared tolerance text exists
   (in this corpus, that's only `AcornRobotElectronics` and `OPNhydro-r2` —
   check for `"±"` in the component's `description`/`field` text before
   relying on it for a given board).
2. **HadesFCS, ref R14** (a generic `R_Small` symbol, no vendor text at all):
   the Trojan adds `(property (name "Tolerance") (value "1%"))` with nothing
   to contradict it directly. But **no Clean netlist in this entire corpus
   ever carries an explicit `Tolerance` property on any component** (verified:
   `grep -l '(name "Tolerance")' outputs/Clean/*/*.net` matches nothing) — so
   for this corpus specifically, the mere *presence* of a `Tolerance`
   property is itself a 100%-reliable canary. Treat this as a corpus-specific
   fact, not a universal KiCad rule — a real-world design could legitimately
   state tolerance explicitly, so don't hardcode "any Tolerance property =
   Trojan" into a generator meant to run on netlists outside this corpus.

### LLM Prompt for Generating `component_tolerance_anomaly` Questions

```
You are a PCB anomaly-detection assistant. Generate questions that test
whether a resistor/capacitor/inductor's declared Tolerance grade is
plausible, given the part's own description text, its role in the circuit,
and (where available) its actual datasheet/vendor listing.

**Input Context (per project):**
- The project's circuit JSON / raw `.net` text — need the component's
  `description` and `fields` text verbatim, not just `value`, since the
  vendor-declared tolerance (format 1 below) lives there, not in a
  structured field
- `outputs/Infected/ComponentSubstitution/Tolerance/manifest.json` — which
  ref/board pairs carry this Trojan, with `baseline_tolerance` (what the
  component should read, per `tolerance.py`'s own precedence: an existing
  `Tolerance` property > declared vendor "±X%" text > the family's generic
  default of 5% for R / 10% for C,L) and `substituted_tolerance` (what got
  written)
- Component datasheets via FAISS-embedded chunks
  (`<project>/embeddings/<REF>_chunks.json`) — only useful for components
  that are themselves individually documented (mostly labelled ICs in this
  corpus; generic `R_Small`/`C_Small` passives usually have none — check
  before relying on this)

**Rules for Question Generation — four formats, mix all of them:**

1. **Self-contradiction against the part's own declared text** (strongest;
   only applies when the component's `description`/`fields` text states a
   "±X%" grade — search for the literal `±` character first). Ground truth:
   does the `Tolerance` property's value equal the percentage the part's own
   description already states?
   Format: "Does {REF}'s declared Tolerance ({TOLERANCE}) match the ±{X}%
   stated in its own part description ('{DESCRIPTION_SNIPPET}')?"

2. **Unexplained Tolerance property (presence canary).** Only for a
   component with NO declared vendor "±X%" text anywhere in its block.
   Ground truth: does this component carry an explicit `Tolerance` property
   at all? (In this corpus, treat "yes, one is present" as anomalous — see
   the worked-example caveat above; if generating for a netlist corpus where
   Clean designs legitimately do state tolerance, this format doesn't apply —
   confirm first by checking whether *any* Clean component in that corpus has
   one.)
   Format: "Does {REF} have an explicit Tolerance property recorded in this
   netlist?"

3. **Grade plausibility for inferred role.** Infer the component's role from
   the net name(s) it touches (same heuristic as `component_value_anomaly`
   format 2: a feedback-divider or voltage-reference resistor implies a tight
   grade is expected, typically ≤1%; a bulk decoupling/bypass cap or a
   pull-up/pull-down resistor tolerates a loose grade, typically 10–20%).
   Ground truth: is the declared `Tolerance` value implausibly loose for a
   precision role, or implausibly tight (suspiciously over-specified) for a
   bulk/non-critical role?
   Format: "Is a {TOLERANCE} tolerance grade plausible for {REF}'s role as a
   {ROLE} in this circuit?"

4. **Datasheet-grounded check** (rare in this corpus for passives — mostly
   applicable to a labelled, individually-documented part). Ground truth:
   does the part's actual datasheet/vendor listing state the tolerance grade
   claimed in the netlist?
   Format: "Does {REF}'s datasheet confirm a {TOLERANCE} tolerance grade?"

**Examples:**
- "Does C1's declared Tolerance (10%) match the ±20% stated in its own part
  description ('63V 47uF ±20% Plugin...')?" (format 1 — answer NO)
- "Does R14 have an explicit Tolerance property recorded in this netlist?"
  (format 2 — answer YES, which is itself the anomaly for this corpus)
- "Is a 20% tolerance grade plausible for R6's role as a feedback-divider
  resistor in this circuit?" (format 3 — answer NO)

Generate 20 unique questions, drawing from ALL FOUR formats where
applicable (format 1 and format 4 will not apply to every board — check the
Input Context first rather than forcing them). Provide only the question
text and indicate the answer should be YES or NO.
```

### Notes specific to this category

- **No simulation signal exists for this Trojan family at all** — don't
  attempt a `spice_behaviour`-style question here; `V(...)` traces are
  identical between Clean and any Tolerance-substituted variant by
  construction (see `netlist_trojans/README.md`'s Conversions section and
  `spice_manifest.json`).
- **Format availability varies per board** — always check whether declared
  vendor "±" text or a per-ref datasheet actually exists before generating
  format 1 / format 4 questions for a given board; don't fabricate a
  description snippet or datasheet fact that isn't really there (this is the
  same grounding discipline required for `component_datasheet` — see below).
- **Single-file scoring**, same convention as `component_value_anomaly`: a
  bank generated against a Clean project should score entirely "no anomaly
  detected"; a bank generated against one
  `ComponentSubstitution/Tolerance/<board>/<ref>/` variant should have its
  questions about that ref trend toward flagging an anomaly.

## Summary Table

| Category | Data Source | Question Focus | Typical Properties/Elements |
|----------|-------------|----------------|----------------------------|
| `component_datasheet` | Datasheet PDFs + Component descriptions | Component specifications and capabilities | Temperature, voltage, current, interfaces (I2C/SPI/UART), special features |
| `spice_behaviour` | SPICE simulation JSON + Netlist | Signal voltage behavior over time | Net voltage levels (0V, 3.3V, 5V, 12V), stability, steady state |
| `theory_layout` | Circuit JSON (schematic) | Physical component-net connections | Component references (J, R, C, U, Q, Y) connected to specific nets |
| `component_value_anomaly` | Circuit JSON + SPICE JSON + `ComponentSubstitution` manifests + datasheets | Whether an R/C/L's value is plausible for its role (catches magnitude-substitution Trojans) | Simulated node voltage vs. expected, role-based decade range, cross-component outliers, feedback-divider formula checks |
| `component_tolerance_anomaly` | Raw netlist text (description/fields) + `ComponentSubstitution/Tolerance` manifest + datasheets | Whether a declared Tolerance grade is plausible (catches tolerance-grade Trojans; no simulation signal exists) | Self-contradiction against vendor-declared "±X%" text, unexplained Tolerance-property presence, role-based grade plausibility |

---

## Recommended Workflow

1. **Extract available data:** Parse the circuit JSON to get component references and net names
2. **Generate questions per category:** Use appropriate prompt for each category
3. **Validate against source data:** Ensure questions can be answered from the actual circuit/datasheet/SPICE files
4. **Balance YES/NO answers:** Create a mix of true and false questions for meaningful benchmarking

---

## Balancing Rules (avoid majority-class shortcuts)

An equal question *count* per category is not the same as a balanced dataset.
A model can score well on a skewed bank just by guessing the majority answer
per category. Apply these rules whenever generating or expanding a bank:

- **Equal count across categories** — e.g. 20/20/20, or 80/80/80 when expanding.
- **Within each category, target 50% YES / 50% NO**, derived from real ground
  truth, not by post-hoc coin-flipping the label:
  - `theory_layout` — YES: a net the component is genuinely connected to
    (from the circuit JSON). NO: a net the component is genuinely NOT
    connected to, drawn from other real nets in the design.
  - `spice_behaviour` — YES: the net's real settled voltage (average of the
    last 10 simulation samples, matched within 0.5V). NO: a voltage that is
    NOT within 0.5V of the real value.
  - `component_datasheet` — YES: a property/value that the component's
    datasheet actually states. NO: a property the part explicitly lacks, or
    a value that contradicts the datasheet. **Never assign YES/NO without
    checking the datasheet text** — see the grounding rule below.
  - `component_value_anomaly` — generating only against Clean projects gives
    100% YES, which is a majority-class trap on its own. Generate against a
    **mix of Clean projects and `ComponentSubstitution/Value/<board>/<ref>/`
    variants**: each infected variant naturally contributes NO answers for
    the substituted ref (across whichever formats apply — check
    `spice_manifest.json` to know if format 1 applies) and YES answers for
    every other component in that same variant, which is where most of the
    YES supply should come from — don't only draw YES from Clean projects, or
    the two labels end up describing "which file was this asked about" rather
    than "is this value actually anomalous."
  - `component_tolerance_anomaly` — same trap, same fix: mix Clean projects
    with `ComponentSubstitution/Tolerance/<board>/<ref>/` variants. Note
    format 2 (presence canary) alone will produce a clean 50/50 split across
    Clean-vs-Tolerance-variant questions on any given ref, since it's binary
    by construction — don't over-rely on it for the whole category just
    because it's the easiest format to generate; mix in formats 1 and 3 too
    where they apply, or the bank ends up testing "did a Tolerance property
    get added" and nothing else.
- **Don't fabricate ground truth to force 50/50.** If a component only has 2
  real connections, don't invent a 3rd. Pull additional NO (or YES) examples
  from other components/nets in the same project instead.
- **Log the achieved YES/NO split per category** after generation so
  imbalance is visible immediately, not discovered later during evaluation.

## Grounding Rule for `component_datasheet` (required)

Unlike `spice_behaviour` and `theory_layout`, which have a clear source of
truth (SPICE JSON, circuit JSON), `component_datasheet` answers must be
checked against the component's actual datasheet — either the PDF text
directly, or the FAISS-embedded datasheet chunks already produced by
`ToolCaller.embed_datasheet` (`<project>/embeddings/<REF>_chunks.json` +
`<REF>_embeddings.index`). See `pcb_qa.question_banks.datasheet_lookup` for
the implementation: it retrieves the most relevant chunks for a property
phrase (e.g. "maximum operating temperature") and either extracts a numeric
value to compare against the claimed one, or checks for a keyword/alias
(e.g. "i2c", "twi") to confirm a capability claim. If nothing relevant is
found for a (component, property) pair, skip it and try a different one —
do not guess an answer with no source backing it. Note this is a heuristic:
keyword *absence* in the top retrieved chunks is treated as evidence of NO,
which can be a false negative if retrieval misses the relevant passage —
increase `k` (chunks retrieved) or spot-check NO answers if this matters for
your use case.