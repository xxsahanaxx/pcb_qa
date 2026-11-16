You are an expert PCB design reviewer. You will be given the design specification for the hardware project **fan_controller**, and the schematic drawing for one build of that board. Your job is to decide whether the design files contain an **anomaly**: a deviation from the intended design that would make the board behave differently from what was intended. It could come from a design error, an assembly or sourcing mistake, or deliberate tampering.

The schematic may be completely correct. Do not assume an anomaly exists. Report one only if the drawing supports it.

## Inputs

### 1. Design specification

The specification describes the intended design: its purpose, architecture, key components and their values, power rails and interfaces. It was written by examining the reference design. Statements marked **Inferred** are the author's reasoning, not confirmed fact. Sections such as "Known limitations", "Known issues" or "logged bugs" describe real properties of the reference design. Those are **not** anomalies, and must not be reported.

The specification may not mention every component. Where it is silent, judge the design with standard electrical-engineering practice and with the component's own metadata (its library part, description, footprint and datasheet fields).

<design_specification>
# MyKiCad — Repository Overview

## Why this isn't a single ARCHITECTURE.md

`MyKiCad` is a personal monorepo, not one project. Its own `README.md` states it is
"a repository where I upload [almost] everything that I design in KiCad," and that
"About 50% of all of the PCBs have a README describing what they're meant for and
the PCB's physical parameters." The repo is organized as dozens of independent,
unrelated board designs grouped into loose category folders (`Raspberry Pi stuff/`,
`ESP32/`, `Breakouts/`, `Power stuff/`, etc.), each board living in its own
subdirectory with its own KiCad project files and (sometimes) its own short README.

There is no shared schematic hierarchy, no shared bus, no single system that the
boards plug into — a USB-C level-shifter breakout and a laptop keyboard controller
have nothing architecturally in common beyond both being KiCad PCBs maintained by
the same author. Consequently, a single architecture narrative describing "the
system" would misrepresent the repo. Instead, this document gives (1) a map of what
each category folder contains, based on actually listing and spot-checking their
contents, and (2) short notes on three individual boards that have substantive
READMEs following the repo's own `TEMPLATE.md` convention.

The repo's `TEMPLATE.md` defines the expected shape of a per-board README: an
optional `## Notes` section (free-form caveats — untested status, stencil
recommendation, silkscreen conventions, third-party sourcing) and an `## Info`
section with `Software` (KiCad version used), `Version`, `PCB size`, `Layer count`,
and `Recommended thickness`. The repo's own README confirms only about half the
boards have been given a README at all, and documentation is added "as I go" — so
most boards are undocumented beyond their KiCad project files, and per-board
sections are deliberately short, matching the template.

## Category folder overview

Descriptions below are based on actually listing each category's subfolders and
spot-checking several README files/board names per category (not inferred from the
folder name alone).

| Category | What's actually in there (spot-checked) |
|---|---|
| `Raspberry Pi stuff/` | Pi-specific add-on boards: an I2C-to-5V level shifter (`pi_i2c_shifter`), a GPIO breakout, an SPI-flash shim, a WiFi adapter, a "ZPN devboard" (marked work-in-progress), and a business-card-sized ZPUI device. |
| `ESP32/` | Present but empty apart from a `.gitignore` — no boards currently checked into this folder in this copy of the repo. |
| `ESP8266/` | Small ESP8266 breakout/prototyping boards, e.g. `esp12_ss_breakout`, `esp12_spi_i2c_breakout`, `esp8266_simple_breakout`, `protoesp`. |
| `Breakouts/` | The largest category — single-chip or single-connector breakout boards for a wide range of parts: display drivers (`0.69_i2c_display_breakout`), connectors/FPC adapters (`10p_fpc_breakout`, `50p_0.5_fpc`, `microusb_breakout`), relay drivers (`0jss148hm_relay_breakout`, 24V/5V relay boards), logic ICs (`4051_breakout_smd/tht`, `6n137_breakout`, `74hc125_breakout`), and misc parts like `max3232_breakout` (RS-232 level shifter) and `ttp229bsf_breakout` (touch sensor). |
| `Power stuff/` | Power-management boards: battery/charging (`18650_pcb`, `axp209_breakout`), power-path/FET switching (`simple_fet_powerpath`, `usb_power_switcher`), regulator/converter breakouts (`pam2306_breakout`, `traco_tsr05sm_breakout`), and a solenoid driver (`piano_solenoid_controller`). |
| `Logic stuff/` | Small logic-glue boards: a 74HC245 breakout, a simple latch, an LED adapter for a logic probe, and `spi_1v8_level_shifter` (a GTL2002-based SPI level shifter, per its README). |
| `Wearables/` | Just one board, `hapticbelt_driver`: a WS2818B/P-FET vibromotor PWM driver board for a DIY haptic belt, per its README. |
| `Atmel/` | AVR/ATtiny-centric boards: chip-footprint adapters (`attiny_x02-x5_adapter`, `attiny_x4-x5_adapter`), a UART injector, an ATtiny-driven fan controller, and `nrf_tiny_mega` (README is just a link to an external Hackaday.io project page, "saferspace"). |
| `Ecosystems/` | One board, `nep_hackerboard`: described in its README as "a hacker board for a pre-determined pinout" with I2C/SPI-flash footprints and QWIIC connectors. |
| `Peripherals/` | Breakouts for peripheral/IO chips: GPIO expanders (`mcp23017_breakout`, `pcf8574_dip_breakout`), a USB hub (`gl850a_small_hub`), RTC breakouts, a camera adapter, and USB-C alt-mode/NeoPixel-to-RS485 adapter boards. |
| `Reverse-engineering/` | Tools/boards for probing or reverse-engineering other hardware: a USB-C signal finder (`usbc_debug_finder`), a parallel EEPROM reader, an RS-232 sniffer, keyboard-matrix and display debug boards, and FPC breakouts for specific laptop panels (`lenovo_flex_2_14_lcd_fpc`, `sony_vaio_p_re`). |
| `Third-party/` | Boards the author rebuilt/modified from other designers' work, explicitly credited in the README, e.g. `arduino-micro-usb-mod` (USB-B to Micro-USB adapter, "Original description from Scott Alfter"). |
| `Repairs/` | Small adapter boards made to repair/rework existing hardware: USB-A/USB-B to USB-C adapters, a `pinecil_24v_enjoyer` mod, and an `xserve_sata_adapter`. |
| `Laptop mods/` | The most complex boards in the repo: Framework laptop input-cover/keyboard controllers (`framework_input_controller`, `framework_mobo_lefthalf`), NVMe/M.2 adapters (`nvme_bm_to_m`, `nvme_to_dual_ssd`), an SPI flash interposer, and a fan-PWM disconnecter. |
| `Fluff/` | Non-functional/decorative items: outline/fiducial test PCBs, SVG logo files (credited to OpenMoji, CC BY-SA 4.0 per its README), and a touch-PCB test board — not real product designs. |
| `Libs/` | A single shared KiCad symbol library file, `rtl2832u.kicad_sym`. |

## Representative per-board notes

Three boards were chosen because each has a substantive README that follows the
`TEMPLATE.md` structure (purpose text + `## Notes` + `## Info` with physical
parameters), rather than being blank, a placeholder, or a bare external link —
and because together they span three different category folders (`Power stuff/`,
`Laptop mods/`, `Ecosystems/`).

### 1. 18650 board — `Power stuff/18650_pcb/README.md`

**Purpose (from README):** A LiIon battery management board built around two
18650 cells wired in parallel, combining cell holders, charging, protection,
power-path switching, and indicator functions on one board, described as having
"a bunch of stuff for very simple but very sufficient LiIon management."

**Component list (from README's numbered feature list):** two 18650 cell holder
footprints (SMD and THT compatible, wired in parallel); JST-PH 2-pin connector
(SMD/THT compatible); TP4056 protection-included charger module footprint;
DC-DC step-up footprint (FET-switchable VIN, NPN-driven); a 1117-like 3.3V
regulator footprint (FET-switchable VIN, NPN-driven); power-path circuitry for a
VSW output; polarity-indicator LEDs; crowbar-protection diode footprint (SMD/THT)
against reverse 18650 insertion; fuses on both 18650 positive pins; THT power-rail
test points; strain-relief holes; a side/top-press button footprint; silkscreen
polarity markings; and an onboard USB-C connector for charging.

**Physical parameters (from README `## Info`):** Software: KiCad 7; Version: 3;
PCB size: 47.2×88 mm; Layer count: 2; Recommended thickness: "not thin" (verbatim
from README — no numeric value given).

### 2. Framework input cover controller — `Laptop mods/framework_input_controller/README.md`

**Purpose (from README):** An RP2040-based controller for a Framework laptop's
palmrest, connecting to the keyboard matrix, touchpad, power button, fingerprint
sensor LEDs, keyboard backlight, and CAPS LOCK LED — intended for building the
Framework keyboard into an external keyboard or for prototyping alternate
motherboards for the laptop chassis. The README notes a detachable USB-C
connector, an optional SL2.1 USB hub exposing the fingerprint sensor plus two
extra USB ports (rewireable to 3.3V power), and a 74HC595 shift register used to
drive the CAPS lock LED and fingerprint sensor RGB LEDs. QMK firmware and
"rudimentary MicroPython code" are mentioned as existing for this board.

**Component list (from the board's `bom.csv`, which lists real part values):**
RP2040 microcontroller (U4, RP2040-QFN-56 footprint); SL2.1A USB hub IC (U1);
AP1117-33 3.3V linear regulator (U2); W25Q32JVSS SPI flash (U3); 74HC595 shift
register (U5); BC817 NPN transistor (Q1); CJ2305 P-FET (Q2); Amphenol 10156000
mobo input connector (J1); USB-C receptacle, USB2.0 (J2); three 12 MHz crystals
(Y1–Y3); plus passive arrays (0603/0805/0402 resistors, 0603 capacitors including
16× 100 nF and 2× 1 µF decoupling, a 4.7 kΩ resistor array).

**Physical parameters (from README, under `## Info` — note this board's README
omits "Software"/"Recommended thickness" from the listed `## Info` header in the
file but still states the values inline):** Software: KiCad 7; Version: 1; PCB
size: 35×38.25 mm; Layer count: 2. (No "Recommended thickness" value is given in
this README.)

### 3. NEP hacker board — `Ecosystems/nep_hackerboard/README.md`

**Purpose (from README):** Described as "a hacker board for a pre-determined
pinout," intended for embedded-device hacking. The README states it has I2C and
SPI flash footprints, 3.3V and 5V backflow/overcurrent protection, two QWIIC
connectors, and UART/I2C/SPI/PCM audio pin headers, with series resistors on SPI
and I2C/SPI-flash auxiliary pins "carefully pulled to their best levels."

**Component list (from README description; no bom.csv present in this board's
folder):** I2C footprint; SPI flash footprint; two QWIIC connectors; UART, I2C,
SPI, and PCM audio pin headers; backflow/overcurrent protection circuitry for
3.3V and 5V rails; series resistors on the SPI lines.

**Physical parameters (from README `## Info`):** Software: KiCad 7; Version: 1;
PCB size: 28×47 mm; Layer count: 2; Recommended thickness: "none" (verbatim from
README).

## Notes on sourcing

All statements above are drawn directly from `README.md`/`TEMPLATE.md` text,
directory listings, or (for board 2) the board's own `bom.csv`. No rationale,
intended-use beyond what's stated, or missing physical parameter was invented —
where a README omits a field (e.g. board 2's thickness, board 1's numeric
thickness), this is called out explicitly rather than filled in. Nothing in this
document required marking as "Inferred" beyond what is noted inline, since all
category and board descriptions are backed by directory listings or verbatim
README content read directly from the repository.
</design_specification>

### 2. Design files

The board's **schematic drawing** is attached to this message, and is the only design file you are given. There is no netlist and no SPICE deck.

- **Pages.** One page per schematic sheet, in hierarchy order with the root sheet first. A sheet too large to stay legible at full-page scale is supplied as several overlapping tiles instead, in reading order (top-left first); tiles overlap, so a symbol cut by one tile's edge appears whole in its neighbour.
- **What is drawn.** Symbols with their reference, value and part name; wires, junctions and no-connect markers; power and ground symbols; local, global and hierarchical labels; and, in a hierarchical design, sheet symbols with the pins that join them to their parent.
- **Connectivity is not given to you precomputed.** There is no net list. Two pins share a net because a wire runs between them, because a junction joins their wires, or because they carry the same label name, on the same sheet or across sheets. Trace the wires and read the labels before judging the connectivity.

## How to review

Work through the design systematically before answering:

1. **Power and ground.** For each supply rail and for `GND`, check which pins sit on it. Look for signal, enable, reset, data or sense pins tied directly to `GND` or to a supply rail where the spec or the part's function says they should not be. Look for two different rails joined together.
2. **Connectivity.** For each important interface the spec describes (buses, enables, resets, feedback networks, sensing paths, connectors), check that the expected pins share a net, and that no net merges signals that should be separate, such as two unrelated buses or a data line joined to a power or control line.
3. **Component identity.** For every two-terminal passive, check that its reference prefix (`R`, `C`, `L`), library part, description, footprint and value all agree with each other and with its role in the circuit. Examples: a pull-up or current-limit position occupied by a capacitor, or a decoupling position occupied by a resistor.
4. **Values.** Check each passive's value against the spec where the spec states it, and otherwise against its role. Examples: a pull-up three orders of magnitude off, a decoupling capacitor in millifarads in a small chip footprint, or a feedback or timing part inconsistent with the stated output or timing.
5. **Tolerances and ratings.** Check stated tolerance, voltage rating and dielectric fields against the part's description and its role (precision divider, current sense, reference, timing).
6. **Anything else.** Polarity, missing or extra components, open connections, footprint mismatches.

Rules:
- Base every finding on specific evidence read off the drawing: references, pin numbers, label or net names and values. Where the finding contradicts the spec, quote the relevant spec text too.
- Report only real deviations. Do not report pre-existing properties the spec documents, style issues, automatically generated net names, component ordering, or drawing conventions such as sheet frames, title blocks, grid references and symbol graphics.
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
      "nets": ["nets involved, named by their schematic label where one exists, otherwise by the pins on them"],
      "observed": "what the schematic shows",
      "expected": "what the specification or sound design practice requires instead",
      "evidence": [
        {"source": "schematic" | "spec", "quote": "short verbatim excerpt, with the sheet and page it is on"}
      ],
      "impact": "the likely effect on the board's behaviour",
      "confidence": a number from 0 to 1
    }
  ],
  "summary": "one or two sentences stating your verdict and the main reason for it"
}

If `anomaly_detected` is `false`, `anomalies` must be an empty list.
