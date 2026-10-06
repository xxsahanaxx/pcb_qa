# LLM Prompts for Generating Design Specifications (Clean OSHP Projects)

These prompts generate human-readable **design specification** documents
(architecture rationale, component-selection tables, power budgets,
subsystem walkthroughs) for the open-source hardware projects vendored
under `OSHP_files/Clean/`. They are patterned on `OPNhydro`'s own
hand-written docs (`hardware/ARCHITECTURE.md`, `SCHEMATIC_DESIGN.md`,
`BOARD_LAYOUT.md`, `PUMPS.md`), which already exist and serve as the target
shape for the rest.

`OSHP_files/*` entries are git submodules (see root `.gitmodules`) — do not
write generated docs into those directories. Save generated output under
this repo's own tree (e.g. alongside this file, or in `outputs/<project>/`).

---

## Shared contract (applies to every prompt below)

Each prompt asks the LLM to produce Markdown document(s) shaped like
OPNhydro's: a **TL;DR** (3–5 bullets of major decisions + the "why"), a
**component-selection table** (Part | Selected | Reason), numbered
**subsystem sections**, a **power budget**, and an **interface/bus
rationale** section.

**Grounding rule (critical):** Only state a design rationale ("why X was
chosen") if it is directly supported by something in the repo — a code
comment, a `notes.txt`/`TODO`/bug-log entry, a datasheet of a part actually
used, or an explicit statement in a README/doc. Where the *what* is clear
from the schematic/netlist but the *why* is not stated anywhere, write
"Inferred: …" and flag it as inferred, don't present it as fact. Never
invent a rationale to fill a section.

---

## 1. CF-Chef (oven controller, KiCad + Rust firmware)

```
You are a hardware design-documentation assistant. Using the CF-Chef repository
(https://github.com/reilleya/CF-Chef, vendored at OSHP_files/Clean/CF-Chef),
write an ARCHITECTURE.md that explains the design of this composite-curing
oven controller.

Primary sources to read:
- readme.md (one-line project description)
- hardware/controller/controller.kicad_sch (top sheet), power.kicad_sch,
  thermocouples.kicad_sch, mcu.kicad_sch
- hardware/controller/controller.net and controller.cir (ground truth for
  every net/component actually present)
- hardware/controller/components/ — datasheets/symbols for
  MPM3606AGQV-P (buck converter), TPS1H200AQDGNRQ1 (smart high-side switch),
  LM73100RPWR (ideal diode / reverse-current protection), TPS2121RUXR
  (autoswitching power mux) — these four parts are the main "why" signal:
  explain what each is actually protecting or switching in this design
- firmware/src/ — only to confirm which peripherals (thermocouple interface,
  heater control signals) the firmware actually drives; don't invent firmware
  behaviour beyond what's there

Produce:
1. TL;DR — what the board controls (oven heating elements + thermocouple
   sensing) and the main protection/power decisions
2. Component table (Part | Selected | Reason) for the four ICs above plus the
   MCU
3. Power architecture section: trace power.kicad_sch rail-by-rail
4. Thermocouple sensing section: trace thermocouples.kicad_sch
5. Known limitations: cite anything found in commit history / code comments
   indicating unresolved issues — do not fabricate any if none exist

Follow the grounding rule: mark anything not directly supported by a file in
this repo as "Inferred", not fact.
```

---

## 2. acorn-robot-electronics (CM4 farming-robot motherboard + aux boards)

```
You are a hardware design-documentation assistant. Using the
acorn-robot-electronics repository
(https://github.com/Twisted-Fields/acorn-robot-electronics, vendored at
OSHP_files/Clean/acorn-robot-electronics), write ARCHITECTURE.md for the
cm4_robot_board (the main motherboard) plus a one-paragraph summary each for
the gps_adapter, supercap, mag_sensor, and soft_start auxiliary boards.

Primary sources to read:
- README.md (project context: Acorn precision farming rover, CM4-based)
- cm4_robot_board/cm4-robot.kicad_sch, cm4-robot.net
- notes.txt and board_TODO.txt — these are the single richest source of
  *actual engineer-stated rationale and known issues* in this repo (e.g. CAN
  crystal frequency correction, CAN TX/RX LED polarity inversion for
  fast-cutoff, e-stop-on-disconnect behaviour, USB ideal-diode /
  reverse-current-protection via LTC4412, GLOBAL_EN power-sequencing
  uncertainty). Quote or closely paraphrase these, don't restate generically.
- doc/motherboard_2023.jpg, doc/motherboard_all.jpg — only for physical
  layout description, not for inventing electrical rationale

Produce:
1. TL;DR — what the CM4 motherboard does for the rover (compute carrier,
   power distribution, motor/actuator interfaces, safety/e-stop)
2. Component table for anything notes.txt/board_TODO.txt gives a stated
   reason for (CAN transceiver + crystal, e-stop circuit, USB protection
   diode, GLOBAL_EN sequencing)
3. A "Known issues / open TODOs" section that is a faithful summary of
   board_TODO.txt and notes.txt — do not resolve or guess fixes for items
   left open there
4. One paragraph each for gps_adapter, supercap, mag_sensor, soft_start,
   stating only what their schematic/net files show plus any related
   notes.txt mentions

Follow the grounding rule.
```

---

## 3. portal-hardware (Bitcoin signer / NFC hardware wallet, TwentyTwoHW)

```
You are a hardware design-documentation assistant. Using the portal-hardware
repository (https://github.com/TwentyTwoHW/portal-hardware, vendored at
OSHP_files/Clean/portal-hardware), write ARCHITECTURE.md for the Portal board.

Primary sources to read:
- README.md (one-line description + front/back SVGs)
- PCB.kicad_sch (top sheet), nfc_ic.kicad_sch, display.kicad_sch
- PCB.net and PCB.cir — ground truth for every net; note the NFC_SDA/NFC_SCL/
  NFC_INT pull-ups, the DISP_RES/DISP_SCL/DISP_SDA display interface, the
  TSC_G2_IO2/IO4 touch-sense-controller pins, and the charge-pump capacitor
  network (C7/C11/C12/C13) feeding the display driver
- 3D_Models/NT3H21111.step and OLED.step — identify the actual parts (NXP
  NT3H2111 NFC tag IC; confirm OLED driver part from display.kicad_sch
  symbol, don't assume a part number not present in the files)
- case/ — only for physical form-factor context

Produce:
1. TL;DR — this is a tap-to-sign Bitcoin hardware wallet: NFC for
   air-gapped PSBT transfer, OLED for transaction review, capacitive touch
   for input, no wired connector required for normal use (confirm this last
   claim against the schematics before stating it as fact — don't assert
   "no wired connector" unless you've confirmed no USB/UART connector exists)
2. Component table: NFC IC, display driver, touch-sense controller, any
   MCU/secure element found in PCB.kicad_sch
3. Interface rationale section: why I2C for NFC+display (if that's what the
   nets show), how touch sensing is wired
4. Power section: trace VCC/GND decoupling network from PCB.cir

Follow the grounding rule — the NFC/no-wires UX story is a strong external
claim; verify it against the actual connector list in PCB.net before writing
it as settled fact.
```

---

## 4. HadesFCS (flight control system — multi-board)

```
You are a hardware design-documentation assistant. Using the HadesFCS
repository (vendored at OSHP_files/Clean/HadesFCS), write ARCHITECTURE.md
for the flagship flight-controller board (Hardware/Hades), with shorter
companion sections for the other boards in Hardware/ (HadesNT, HadesMicro /
HadesMicroJLCPCB, HadesGPSDongle).

Primary sources to read:
- README.md (top-level project framing: fixed-wing autonomous FCS, FreeRTOS,
  STM32, Kalman filtering, from-scratch design)
- Documentation/HadesBlockDiagram.svg and
  Documentation/HadesHardwarePresentation.pdf — these are the author's OWN
  design-rationale documents; treat them as the primary "why" source and
  reconcile against the schematics, rather than reverse-engineering rationale
  from the netlist alone
- Hardware/Hades/Hades.sch (top), FCC.sch, FCCPeripherals.sch, NAVC.sch,
  NAVCPeripherals.sch, Sensors.sch, Connections.sch, Hades.net
- Hardware/Hades/HADES V1 Bugs.txt — real, author-logged hardware bugs; this
  is a second strong rationale source (what changed between V1 and later
  boards, and why)
- Hardware/HadesNT/HadesNT.sch, .net, stm32h750vbt6.pdf — identify what
  changed vs. the original Hades board (newer MCU: STM32H750 vs the STM32F7
  referenced in Hades/STM32F7 PINOUT.PNG)
- Hardware/HadesMicro and HadesMicroJLCPCB — smaller/cost-reduced variant;
  use HadesMicroJLCPCB-FullBOM.csv as ground truth for its BOM
- Hardware/HadesGPSDongle/HadesGPSDongle.sch, .net

Produce, for Hades (the main board):
1. TL;DR — FCC (flight control computer) + NAVC (navigation computer)
   split, sensor suite, from HadesBlockDiagram.svg / the presentation PDF
2. Component table for the MCU(s), IMU/sensor ICs found in Sensors.sch,
   any regulators
3. A "Hardware revision history" section built from "HADES V1 Bugs.txt"
   plus any differences you can confirm against HadesNT's schematic
4. Power section tracing Hades.net rails

Then one short paragraph each for HadesNT, HadesMicro, HadesGPSDongle,
stating their role (from folder naming + schematic contents) and how they
differ from the main Hades board.

Follow the grounding rule — prefer the author's own
HadesHardwarePresentation.pdf / block diagram as the "why" source over
inferring rationale yourself, but don't state anything the schematics
contradict.
```

---

## 5. stack-chan (M5Stack-based robot)

```
You are a hardware design-documentation assistant. Using the stack-chan
repository (https://github.com/stack-chan/stack-chan, vendored at
OSHP_files/Clean/stack-chan), write ARCHITECTURE.md for the pan-tilt servo
carrier board described in schematics/.

Primary sources to read:
- README.md (M5Stack-embedded robot, features list)
- schematics/README.md — this already contains real design rationale: the
  PWM-servo (SG90) vs serial-servo (RS304MD) trade-off (cost vs. inrush
  current / smoke risk vs. closed-loop angle feedback and torque control),
  M5Unit PortB/PortC usage, external 5V supply vs. battery-through-M5Stack
  charging, optional power switch. Reuse this rationale directly rather than
  re-deriving it.
- schematics/ KiCad schematic/PCB files (confirm actual file names present
  in that folder) for the servo-driver and power-switch circuitry
- case/README.md only for mechanical/physical context, not electrical
  rationale

Produce:
1. TL;DR — pan-tilt head carrier for an M5Stack core, two servo channels
   (PWM or serial), battery + external 5V options
2. Component table: servo connector(s)/driver, power-switch circuit, any
   regulator present in the schematic
3. "Servo interface trade-off" section: reproduce the PWM-vs-serial
   rationale from schematics/README.md, tied to the actual connector pins in
   the schematic
4. Power section: battery charge-through-M5Stack path vs. external 5V input,
   as shown in the schematic

Follow the grounding rule.
```

---

## 6. Meshinger (e-paper mesh messenger)

```
You are a hardware design-documentation assistant. Using the Meshinger
repository (vendored at OSHP_files/Clean/Meshinger), write ARCHITECTURE.md
for the Meshinger board.

Primary sources to read:
- Meshinger/Meshinger.kicad_sch (top sheet), SkylabModule.kicad_sch,
  EthernetAndPower.kicad_sch, EPD_Driver.kicad_sch
- Meshinger/Meshinger.net and Meshinger.cir — ground truth for every net
- SKW92A files/SkyLab_SKW92A_V1.04_datasheet.pdf and
  "SKW92 Reference Schematic.pdf" — identify exactly what the SkylabModule
  sheet is: SKW92A is a SKYLAB WiFi/OpenWRT-capable module (confirm from the
  datasheet and GPIO-multiplexing spreadsheet rather than assuming); explain
  why a Linux-capable module was chosen as the main compute element instead
  of a bare MCU, if the repo gives any evidence for that, otherwise mark it
  Inferred
- 3rdparty/EPD-driving-circuit-of-Pervasive-Displays-rev.01.pdf and
  CAD/Waveshare213rev.* — the e-paper display driver circuit
- 3rdparty/FAN53610-D-1805279.pdf — buck regulator, trace its use in
  EthernetAndPower.kicad_sch
- 3rdparty/BBQ10KBD — physical keyboard module, CAD/BBQ10KBD.step for
  mechanical integration only
- CAD/18650_Refrence_Cell.stl — confirms single-cell 18650 battery power

Produce:
1. TL;DR — SKW92A-based mesh messenger with e-paper display and physical
   keyboard, 18650-powered
2. Component table: SKW92A module, EPD driver, FAN53610 regulator, keyboard
   interface
3. Power section tracing EthernetAndPower.kicad_sch rails from battery/USB
   input to the regulated rails feeding the module and display
4. Display-interface section tracing EPD_Driver.kicad_sch against the
   Pervasive Displays driving-circuit reference doc

Follow the grounding rule — the "why a WiFi/OpenWRT module instead of an
MCU" claim is speculative unless the repo states it; mark it Inferred if so.
```

---

## 7. MyKiCad (personal monorepo of ~dozens of independent boards)

This one is structurally different from the rest — it's not a single
project, so a single ARCHITECTURE.md doesn't apply. Use this **per-board**
template, substituting one board's path each run:

```
You are a hardware design-documentation assistant. MyKiCad is a personal
monorepo of many independent, unrelated PCB designs
(OSHP_files/Clean/MyKiCad), each in its own subfolder under categories like
Raspberry Pi stuff/, ESP32/, Breakouts/, Power stuff/, etc. Do NOT attempt to
write one architecture document for the whole repo.

For THIS run, write a short design note for exactly one board:
  Board path: {BOARD_PATH}   e.g. "Raspberry Pi stuff/pi_spiflash_shim"

Primary sources to read:
- {BOARD_PATH}/README.md if present — about half the boards have one
  following TEMPLATE.md's structure (Notes / Info: software version, PCB
  size, layer count, thickness). If no README exists for this board, say so
  explicitly rather than inventing its contents.
- {BOARD_PATH}/*.kicad_sch and *.net (or legacy .sch/.pro) — the schematic
  is the real ground truth here since many boards lack a README
- MyKiCad/TEMPLATE.md — the house style this repo's own READMEs follow;
  match its level of detail (this repo deliberately keeps per-board docs
  short — a few bullets, not a multi-section architecture doc)

Produce a short note (not a full ARCHITECTURE.md): one-paragraph purpose
(what this specific board plugs into / is for), a component list, and the
physical parameters (board size, layer count) if findable in the KiCad
project file.

Follow the grounding rule — this repo has no narrative "why" documentation
by design; don't manufacture rationale beyond what TEMPLATE.md-style notes
would state.
```

---

## 8. OPNhydro — calibration check, not a new prompt

OPNhydro already has `hardware/ARCHITECTURE.md`, `SCHEMATIC_DESIGN.md`,
`BOARD_LAYOUT.md`, and `PUMPS.md` — this is the real, human-written example
the prompts above are patterned on. Before trusting the above prompts on the
other 7 projects, it's worth running the same prompt shape against
OPNhydro's own source files (its `hardware/` schematics + `README.md`,
deliberately *not* reading its existing `.md` docs) and diffing the output
against the real `ARCHITECTURE.md`. That tells you whether the prompt
reliably surfaces real rationale or just produces plausible-sounding filler
— a cheap sanity check since ground truth already exists for this one
project.
