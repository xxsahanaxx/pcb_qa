You are an expert PCB design reviewer. You will be given the design specification for the hardware project **fan_controller**, and the design files for one build of that board. Your job is to decide whether the design files contain an **anomaly**: a deviation from the intended design that would make the board behave differently from what was intended. It could come from a design error, an assembly or sourcing mistake, or deliberate tampering.

The design files may be completely correct. Do not assume an anomaly exists. Report one only if the files support it.

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

- **KiCad netlist (`.net`):** the authoritative connectivity. Every component, with its reference, value, footprint, library part and fields, and every net, with the pins on it. Net names of the form `Net-(<ref>-<pin>)` are generated automatically from a pin on that net.
- **SPICE deck (`.cir`):** a simulation deck derived from the same schematic. Only resistors, capacitors, inductors, diodes and sources are modelled. ICs, connectors and transistors are left out, and ground is node `0`. Treat this file as a secondary view; the netlist takes precedence.
- **Circuit JSON (`.json`), if present:** the same netlist as hierarchical JSON.

<design_files>
#### KiCad netlist: `fan_controller.net`

````
(export (version "E")
  (design
    (source "fan_controller.kicad_sch")
    (date "")
    (tool "Eeschema 9.0.6")
    (sheet (number "1") (name "/") (tstamps "/")
      (title_block
        (title)
        (company)
        (rev)
        (date)
        (source "fan_controller.kicad_sch")
        (comment (number "1") (value ""))
        (comment (number "2") (value ""))
        (comment (number "3") (value ""))
        (comment (number "4") (value ""))
        (comment (number "5") (value ""))
        (comment (number "6") (value ""))
        (comment (number "7") (value ""))
        (comment (number "8") (value ""))
        (comment (number "9") (value "")))))
  (components
    (comp (ref "C1")
      (value "100nF")
      (footprint "Capacitor_SMD:C_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Tolerance") "20%")
        (field (name "Footprint") "Capacitor_SMD:C_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Tolerance") (value "20%"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615a4cd5"))
    (comp (ref "C2")
      (value "100nF")
      (footprint "Capacitor_SMD:C_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-000061593f2c"))
    (comp (ref "D1")
      (value "5V1")
      (footprint "Diode_SMD:D_SOD-123")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Diode_SMD:D_SOD-123")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "D_Zener_Small") (description "Zener diode, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "diode"))
      (property (name "ki_fp_filters") (value "TO-???* *_Diode_* *SingleDiode* D_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615abaa1"))
    (comp (ref "H1")
      (value "MountingHole")
      (footprint "MountingHole:MountingHole_2.1mm")
      (datasheet "~")
      (fields
        (field (name "Footprint") "MountingHole:MountingHole_2.1mm")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Mechanical") (part "MountingHole") (description "Mounting Hole without connection"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "mounting hole"))
      (property (name "ki_fp_filters") (value "MountingHole*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615c773f"))
    (comp (ref "H2")
      (value "MountingHole")
      (footprint "MountingHole:MountingHole_2.1mm")
      (datasheet "~")
      (fields
        (field (name "Footprint") "MountingHole:MountingHole_2.1mm")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Mechanical") (part "MountingHole") (description "Mounting Hole without connection"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "mounting hole"))
      (property (name "ki_fp_filters") (value "MountingHole*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615c788a"))
    (comp (ref "H3")
      (value "MountingHole")
      (footprint "MountingHole:MountingHole_2.1mm")
      (datasheet "~")
      (fields
        (field (name "Footprint") "MountingHole:MountingHole_2.1mm")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Mechanical") (part "MountingHole") (description "Mounting Hole without connection"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "mounting hole"))
      (property (name "ki_fp_filters") (value "MountingHole*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615c7a86"))
    (comp (ref "H4")
      (value "MountingHole")
      (footprint "MountingHole:MountingHole_2.1mm")
      (datasheet "~")
      (fields
        (field (name "Footprint") "MountingHole:MountingHole_2.1mm")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Mechanical") (part "MountingHole") (description "Mounting Hole without connection"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "mounting hole"))
      (property (name "ki_fp_filters") (value "MountingHole*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615c7bdf"))
    (comp (ref "J1")
      (value "I2C")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Connector_Generic") (part "Conn_01x05") (description "Generic connector, single row, 01x05, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "connector"))
      (property (name "ki_fp_filters") (value "Connector*:*_1x??_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615fdd9b"))
    (comp (ref "J2")
      (value "FAN")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Connector_Generic") (part "Conn_01x04") (description "Generic connector, single row, 01x04, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "connector"))
      (property (name "ki_fp_filters") (value "Connector*:*_1x??_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615921ae"))
    (comp (ref "J3")
      (value "POT")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Connector_Generic") (part "Conn_01x03") (description "Generic connector, single row, 01x03, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "connector"))
      (property (name "ki_fp_filters") (value "Connector*:*_1x??_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-000061592b5d"))
    (comp (ref "J4")
      (value "AVR-ISP-6")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical")
      (datasheet " ~")
      (fields
        (field (name "Footprint") "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical")
        (field (name "Datasheet") " ~")
        (field (name "Description")))
      (libsource (lib "Connector") (part "AVR-ISP-6") (description "Atmel 6-pin ISP connector"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "AVR ISP Connector"))
      (property (name "ki_fp_filters") (value "IDC?Header*2x03* Pin?Header*2x03*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615e619d"))
    (comp (ref "J5")
      (value "PWR")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Connector_Generic") (part "Conn_01x02") (description "Generic connector, single row, 01x02, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "connector"))
      (property (name "ki_fp_filters") (value "Connector*:*_1x??_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-000061629a09"))
    (comp (ref "J6")
      (value "I2C_PWR")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Connector_Generic") (part "Conn_01x02") (description "Generic connector, single row, 01x02, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "connector"))
      (property (name "ki_fp_filters") (value "Connector*:*_1x??_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-00006158eb66"))
    (comp (ref "JP1")
      (value "VCC_STABLE")
      (footprint "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Jumper") (part "Jumper_2_Open") (description "Jumper, 2-pole, open"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "Jumper SPST"))
      (property (name "ki_fp_filters") (value "Jumper* TestPoint*2Pads* TestPoint*Bridge*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615c7c74"))
    (comp (ref "Q1")
      (value "Q_PMOS_GSD")
      (footprint "Package_TO_SOT_SMD:SOT-23")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Package_TO_SOT_SMD:SOT-23")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "Q_PMOS_GSD") (description "P-MOSFET transistor, gate/source/drain"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "transistor PMOS P-MOS P-MOSFET"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615c8358"))
    (comp (ref "Q2")
      (value "BC817")
      (footprint "Package_TO_SOT_SMD:SOT-23")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Package_TO_SOT_SMD:SOT-23")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "Q_NPN_BEC") (description "NPN transistor, base/emitter/collector"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "transistor NPN"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000616f7fa8"))
    (comp (ref "R1")
      (value "10K")
      (footprint "Resistor_SMD:R_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615df3db"))
    (comp (ref "R2")
      (value "1K")
      (footprint "Resistor_SMD:R_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615e0afc"))
    (comp (ref "R3")
      (value "10K")
      (footprint "Resistor_SMD:R_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-00006159399c"))
    (comp (ref "R4")
      (value "1K")
      (footprint "Resistor_SMD:R_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615a8701"))
    (comp (ref "R5")
      (value "1K")
      (footprint "Resistor_SMD:R_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615af729"))
    (comp (ref "R6")
      (value "10K")
      (footprint "Resistor_SMD:R_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000616e6e98"))
    (comp (ref "U1")
      (value "LM1117-5.0")
      (footprint "Package_TO_SOT_SMD:SOT-223-3_TabPin2")
      (datasheet "http://www.ti.com/lit/ds/symlink/lm1117.pdf")
      (fields
        (field (name "Footprint") "Package_TO_SOT_SMD:SOT-223-3_TabPin2")
        (field (name "Datasheet") "http://www.ti.com/lit/ds/symlink/lm1117.pdf")
        (field (name "Description")))
      (libsource (lib "fan_controller-rescue") (part "LM1117-5.0-Regulator_Linear") (description ""))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_fp_filters") (value "SOT?223* TO?263* TO?252* TO?220*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615afe6e"))
    (comp (ref "U2")
      (value "ATtiny45-20P")
      (footprint "Package_DIP:DIP-8_W7.62mm")
      (datasheet "http://ww1.microchip.com/downloads/en/DeviceDoc/atmel-2586-avr-8-bit-microcontroller-attiny25-attiny45-attiny85_datasheet.pdf")
      (fields
        (field (name "Footprint") "Package_DIP:DIP-8_W7.62mm")
        (field (name "Datasheet") "http://ww1.microchip.com/downloads/en/DeviceDoc/atmel-2586-avr-8-bit-microcontroller-attiny25-attiny45-attiny85_datasheet.pdf")
        (field (name "Description")))
      (libsource (lib "fan_controller-rescue") (part "ATtiny45-20P-MCU_Microchip_ATtiny-fan_controller-rescue") (description ""))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_fp_filters") (value "DIP*W7.62mm*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615963d2"))
    (comp (ref "U3")
      (value "ATtiny13V-10S")
      (footprint "Package_SO:SOIC-8W_5.3x5.3mm_P1.27mm")
      (datasheet "http://ww1.microchip.com/downloads/en/DeviceDoc/doc2535.pdf")
      (fields
        (field (name "Footprint") "Package_SO:SOIC-8W_5.3x5.3mm_P1.27mm")
        (field (name "Datasheet") "http://ww1.microchip.com/downloads/en/DeviceDoc/doc2535.pdf")
        (field (name "Description")))
      (libsource (lib "fan_controller-rescue") (part "ATtiny13V-10S-MCU_Microchip_ATtiny-fan_controller-rescue") (description ""))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "fan_controller.kicad_sch"))
      (property (name "ki_fp_filters") (value "SOIC*5.3x5.3mm*P1.27mm*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "00000000-0000-0000-0000-0000615959af")))
  (libparts
    (libpart (lib "Connector") (part "AVR-ISP-6")
      (description "Atmel 6-pin ISP connector")
      (docs "~")
      (footprints
        (fp "IDC?Header*2x03*")
        (fp "Pin?Header*2x03*"))
      (fields
        (field (name "Reference") "J")
        (field (name "Value") "AVR-ISP-6")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Atmel 6-pin ISP connector"))
      (pins
        (pin (num "1") (name "MISO") (type "passive"))
        (pin (num "2") (name "VCC") (type "passive"))
        (pin (num "3") (name "SCK") (type "passive"))
        (pin (num "4") (name "MOSI") (type "passive"))
        (pin (num "5") (name "~{RST}") (type "passive"))
        (pin (num "6") (name "GND") (type "passive"))))
    (libpart (lib "Connector_Generic") (part "Conn_01x02")
      (description "Generic connector, single row, 01x02, script generated (kicad-library-utils/schlib/autogen/connector/)")
      (docs "~")
      (footprints
        (fp "Connector*:*_1x??_*"))
      (fields
        (field (name "Reference") "J")
        (field (name "Value") "Conn_01x02")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Generic connector, single row, 01x02, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (pins
        (pin (num "1") (name "Pin_1") (type "passive"))
        (pin (num "2") (name "Pin_2") (type "passive"))))
    (libpart (lib "Connector_Generic") (part "Conn_01x03")
      (description "Generic connector, single row, 01x03, script generated (kicad-library-utils/schlib/autogen/connector/)")
      (docs "~")
      (footprints
        (fp "Connector*:*_1x??_*"))
      (fields
        (field (name "Reference") "J")
        (field (name "Value") "Conn_01x03")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Generic connector, single row, 01x03, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (pins
        (pin (num "1") (name "Pin_1") (type "passive"))
        (pin (num "2") (name "Pin_2") (type "passive"))
        (pin (num "3") (name "Pin_3") (type "passive"))))
    (libpart (lib "Connector_Generic") (part "Conn_01x04")
      (description "Generic connector, single row, 01x04, script generated (kicad-library-utils/schlib/autogen/connector/)")
      (docs "~")
      (footprints
        (fp "Connector*:*_1x??_*"))
      (fields
        (field (name "Reference") "J")
        (field (name "Value") "Conn_01x04")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Generic connector, single row, 01x04, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (pins
        (pin (num "1") (name "Pin_1") (type "passive"))
        (pin (num "2") (name "Pin_2") (type "passive"))
        (pin (num "3") (name "Pin_3") (type "passive"))
        (pin (num "4") (name "Pin_4") (type "passive"))))
    (libpart (lib "Connector_Generic") (part "Conn_01x05")
      (description "Generic connector, single row, 01x05, script generated (kicad-library-utils/schlib/autogen/connector/)")
      (docs "~")
      (footprints
        (fp "Connector*:*_1x??_*"))
      (fields
        (field (name "Reference") "J")
        (field (name "Value") "Conn_01x05")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Generic connector, single row, 01x05, script generated (kicad-library-utils/schlib/autogen/connector/)"))
      (pins
        (pin (num "1") (name "Pin_1") (type "passive"))
        (pin (num "2") (name "Pin_2") (type "passive"))
        (pin (num "3") (name "Pin_3") (type "passive"))
        (pin (num "4") (name "Pin_4") (type "passive"))
        (pin (num "5") (name "Pin_5") (type "passive"))))
    (libpart (lib "Device") (part "C_Small")
      (description "Unpolarized capacitor, small symbol")
      (docs "~")
      (footprints
        (fp "C_*"))
      (fields
        (field (name "Reference") "C")
        (field (name "Value") "C_Small")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Unpolarized capacitor, small symbol"))
      (pins
        (pin (num "1") (name "") (type "passive"))
        (pin (num "2") (name "") (type "passive"))))
    (libpart (lib "Device") (part "D_Zener_Small")
      (description "Zener diode, small symbol")
      (docs "~")
      (footprints
        (fp "TO-???*")
        (fp "*_Diode_*")
        (fp "*SingleDiode*")
        (fp "D_*"))
      (fields
        (field (name "Reference") "D")
        (field (name "Value") "D_Zener_Small")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Zener diode, small symbol"))
      (pins
        (pin (num "1") (name "K") (type "passive"))
        (pin (num "2") (name "A") (type "passive"))))
    (libpart (lib "Device") (part "Q_NPN_BEC")
      (description "NPN transistor, base/emitter/collector")
      (docs "~")
      (fields
        (field (name "Reference") "Q")
        (field (name "Value") "Q_NPN_BEC")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "NPN transistor, base/emitter/collector"))
      (pins
        (pin (num "1") (name "B") (type "input"))
        (pin (num "2") (name "E") (type "passive"))
        (pin (num "3") (name "C") (type "passive"))))
    (libpart (lib "Device") (part "Q_PMOS_GSD")
      (description "P-MOSFET transistor, gate/source/drain")
      (docs "~")
      (fields
        (field (name "Reference") "Q")
        (field (name "Value") "Q_PMOS_GSD")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "P-MOSFET transistor, gate/source/drain"))
      (pins
        (pin (num "1") (name "G") (type "input"))
        (pin (num "2") (name "S") (type "passive"))
        (pin (num "3") (name "D") (type "passive"))))
    (libpart (lib "Device") (part "R_Small")
      (description "Resistor, small symbol")
      (docs "~")
      (footprints
        (fp "R_*"))
      (fields
        (field (name "Reference") "R")
        (field (name "Value") "R_Small")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Resistor, small symbol"))
      (pins
        (pin (num "1") (name "") (type "passive"))
        (pin (num "2") (name "") (type "passive"))))
    (libpart (lib "Jumper") (part "Jumper_2_Open")
      (description "Jumper, 2-pole, open")
      (docs "~")
      (footprints
        (fp "Jumper*")
        (fp "TestPoint*2Pads*")
        (fp "TestPoint*Bridge*"))
      (fields
        (field (name "Reference") "JP")
        (field (name "Value") "Jumper_2_Open")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Jumper, 2-pole, open"))
      (pins
        (pin (num "1") (name "A") (type "passive"))
        (pin (num "2") (name "B") (type "passive"))))
    (libpart (lib "Mechanical") (part "MountingHole")
      (description "Mounting Hole without connection")
      (docs "~")
      (footprints
        (fp "MountingHole*"))
      (fields
        (field (name "Reference") "H")
        (field (name "Value") "MountingHole")
        (field (name "Footprint"))
        (field (name "Datasheet") "~")
        (field (name "Description") "Mounting Hole without connection")))
    (libpart (lib "fan_controller-rescue") (part "ATtiny13V-10S-MCU_Microchip_ATtiny-fan_controller-rescue")
      (footprints
        (fp "SOIC*5.3x5.3mm*P1.27mm*"))
      (fields
        (field (name "Reference") "U")
        (field (name "Value") "fan_controller-rescue_ATtiny13V-10S-MCU_Microchip_ATtiny")
        (field (name "Footprint") "Package_SO:SOIC-8W_5.3x5.3mm_P1.27mm")
        (field (name "Datasheet"))
        (field (name "Description")))
      (pins
        (pin (num "1") (name "~{RESET}/PB5") (type "bidirectional"))
        (pin (num "2") (name "PB3") (type "bidirectional"))
        (pin (num "3") (name "PB4") (type "bidirectional"))
        (pin (num "4") (name "GND") (type "power_in"))
        (pin (num "5") (name "PB0") (type "bidirectional"))
        (pin (num "6") (name "PB1") (type "bidirectional"))
        (pin (num "7") (name "PB2") (type "bidirectional"))
        (pin (num "8") (name "VCC") (type "power_in"))))
    (libpart (lib "fan_controller-rescue") (part "ATtiny45-20P-MCU_Microchip_ATtiny-fan_controller-rescue")
      (footprints
        (fp "DIP*W7.62mm*"))
      (fields
        (field (name "Reference") "U")
        (field (name "Value") "fan_controller-rescue_ATtiny45-20P-MCU_Microchip_ATtiny")
        (field (name "Footprint") "Package_DIP:DIP-8_W7.62mm")
        (field (name "Datasheet"))
        (field (name "Description")))
      (pins
        (pin (num "1") (name "~{RESET}/PB5") (type "bidirectional"))
        (pin (num "2") (name "XTAL1/PB3") (type "bidirectional"))
        (pin (num "3") (name "XTAL2/PB4") (type "bidirectional"))
        (pin (num "4") (name "GND") (type "power_in"))
        (pin (num "5") (name "AREF/PB0") (type "bidirectional"))
        (pin (num "6") (name "PB1") (type "bidirectional"))
        (pin (num "7") (name "PB2") (type "bidirectional"))
        (pin (num "8") (name "VCC") (type "power_in"))))
    (libpart (lib "fan_controller-rescue") (part "LM1117-5.0-Regulator_Linear")
      (footprints
        (fp "SOT?223*")
        (fp "TO?263*")
        (fp "TO?252*")
        (fp "TO?220*"))
      (fields
        (field (name "Reference") "U")
        (field (name "Value") "Regulator_Linear_LM1117-5.0")
        (field (name "Footprint"))
        (field (name "Datasheet"))
        (field (name "Description")))
      (pins
        (pin (num "1") (name "GND") (type "power_in"))
        (pin (num "2") (name "VO") (type "power_out"))
        (pin (num "3") (name "VI") (type "power_in")))))
  (libraries
    (library (logical "Connector")
      (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols//Connector.kicad_sym"))
    (library (logical "Connector_Generic")
      (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols//Connector_Generic.kicad_sym"))
    (library (logical "Device")
      (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols//Device.kicad_sym"))
    (library (logical "Jumper")
      (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols//Jumper.kicad_sym"))
    (library (logical "Mechanical")
      (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols//Mechanical.kicad_sym"))
    (library (logical "fan_controller-rescue")
      (uri "${KIPRJMOD}/fan_controller-rescue.kicad_sym")))
  (nets
    (net (code "1") (name "+5V") (class "Default")
      (node (ref "C2") (pin "1") (pintype "passive"))
      (node (ref "J3") (pin "1") (pinfunction "Pin_1") (pintype "passive"))
      (node (ref "J4") (pin "2") (pinfunction "VCC") (pintype "passive"))
      (node (ref "J6") (pin "2") (pinfunction "Pin_2") (pintype "passive"))
      (node (ref "R3") (pin "1") (pintype "passive"))
      (node (ref "U1") (pin "2") (pinfunction "VO") (pintype "power_out"))
      (node (ref "U2") (pin "8") (pinfunction "VCC") (pintype "power_in"))
      (node (ref "U3") (pin "8") (pinfunction "VCC") (pintype "power_in")))
    (net (code "2") (name "/PWM_OUT") (class "Default")
      (node (ref "J2") (pin "4") (pinfunction "Pin_4") (pintype "passive"))
      (node (ref "R5") (pin "1") (pintype "passive")))
    (net (code "3") (name "/TACH_IN") (class "Default")
      (node (ref "J2") (pin "3") (pinfunction "Pin_3") (pintype "passive"))
      (node (ref "R4") (pin "2") (pintype "passive")))
    (net (code "4") (name "/VCC_OUT") (class "Default")
      (node (ref "J2") (pin "2") (pinfunction "Pin_2") (pintype "passive"))
      (node (ref "JP1") (pin "1") (pinfunction "A") (pintype "passive"))
      (node (ref "Q1") (pin "3") (pinfunction "D") (pintype "passive")))
    (net (code "5") (name "GND") (class "Default")
      (node (ref "C1") (pin "2") (pintype "passive"))
      (node (ref "C2") (pin "2") (pintype "passive"))
      (node (ref "D1") (pin "2") (pinfunction "A") (pintype "passive"))
      (node (ref "J1") (pin "5") (pinfunction "Pin_5") (pintype "passive"))
      (node (ref "J2") (pin "1") (pinfunction "Pin_1") (pintype "passive"))
      (node (ref "J3") (pin "3") (pinfunction "Pin_3") (pintype "passive"))
      (node (ref "J4") (pin "6") (pinfunction "GND") (pintype "passive"))
      (node (ref "J5") (pin "1") (pinfunction "Pin_1") (pintype "passive"))
      (node (ref "Q2") (pin "2") (pinfunction "E") (pintype "passive"))
      (node (ref "U1") (pin "1") (pinfunction "GND") (pintype "power_in"))
      (node (ref "U2") (pin "4") (pinfunction "GND") (pintype "power_in"))
      (node (ref "U3") (pin "4") (pinfunction "GND") (pintype "power_in")))
    (net (code "6") (name "Net-(J1-Pin_1)") (class "Default")
      (node (ref "J1") (pin "1") (pinfunction "Pin_1") (pintype "passive"))
      (node (ref "J6") (pin "1") (pinfunction "Pin_1") (pintype "passive")))
    (net (code "7") (name "Net-(Q1-G)") (class "Default")
      (node (ref "Q1") (pin "1") (pinfunction "G") (pintype "input"))
      (node (ref "Q2") (pin "3") (pinfunction "C") (pintype "passive"))
      (node (ref "R1") (pin "2") (pintype "passive")))
    (net (code "8") (name "Net-(Q2-B)") (class "Default")
      (node (ref "Q2") (pin "1") (pinfunction "B") (pintype "input"))
      (node (ref "R2") (pin "2") (pintype "passive")))
    (net (code "9") (name "POT") (class "Default")
      (node (ref "J3") (pin "2") (pinfunction "Pin_2") (pintype "passive"))
      (node (ref "U2") (pin "2") (pinfunction "XTAL1/PB3") (pintype "bidirectional"))
      (node (ref "U3") (pin "2") (pinfunction "PB3") (pintype "bidirectional")))
    (net (code "10") (name "PWM") (class "Default")
      (node (ref "J4") (pin "1") (pinfunction "MISO") (pintype "passive"))
      (node (ref "R2") (pin "1") (pintype "passive"))
      (node (ref "R5") (pin "2") (pintype "passive"))
      (node (ref "U2") (pin "6") (pinfunction "PB1") (pintype "bidirectional"))
      (node (ref "U3") (pin "6") (pinfunction "PB1") (pintype "bidirectional")))
    (net (code "11") (name "RST") (class "Default")
      (node (ref "J1") (pin "4") (pinfunction "Pin_4") (pintype "passive"))
      (node (ref "J4") (pin "5") (pinfunction "~{RST}") (pintype "passive"))
      (node (ref "R3") (pin "2") (pintype "passive"))
      (node (ref "U2") (pin "1") (pinfunction "~{RESET}/PB5") (pintype "bidirectional"))
      (node (ref "U3") (pin "1") (pinfunction "~{RESET}/PB5") (pintype "bidirectional")))
    (net (code "12") (name "SCK") (class "Default")
      (node (ref "J1") (pin "3") (pinfunction "Pin_3") (pintype "passive"))
      (node (ref "J4") (pin "3") (pinfunction "SCK") (pintype "passive"))
      (node (ref "U2") (pin "7") (pinfunction "PB2") (pintype "bidirectional"))
      (node (ref "U3") (pin "7") (pinfunction "PB2") (pintype "bidirectional")))
    (net (code "13") (name "SDA") (class "Default")
      (node (ref "J1") (pin "2") (pinfunction "Pin_2") (pintype "passive"))
      (node (ref "J4") (pin "4") (pinfunction "MOSI") (pintype "passive"))
      (node (ref "U2") (pin "5") (pinfunction "AREF/PB0") (pintype "bidirectional"))
      (node (ref "U3") (pin "5") (pinfunction "PB0") (pintype "bidirectional")))
    (net (code "14") (name "TACH") (class "Default")
      (node (ref "D1") (pin "1") (pinfunction "K") (pintype "passive"))
      (node (ref "R4") (pin "1") (pintype "passive"))
      (node (ref "R6") (pin "2") (pintype "passive"))
      (node (ref "U2") (pin "3") (pinfunction "XTAL2/PB4") (pintype "bidirectional"))
      (node (ref "U3") (pin "3") (pinfunction "PB4") (pintype "bidirectional")))
    (net (code "15") (name "VCC") (class "Default")
      (node (ref "C1") (pin "1") (pintype "passive"))
      (node (ref "J5") (pin "2") (pinfunction "Pin_2") (pintype "passive"))
      (node (ref "JP1") (pin "2") (pinfunction "B") (pintype "passive"))
      (node (ref "Q1") (pin "2") (pinfunction "S") (pintype "passive"))
      (node (ref "R1") (pin "1") (pintype "passive"))
      (node (ref "R6") (pin "1") (pintype "passive"))
      (node (ref "U1") (pin "3") (pinfunction "VI") (pintype "power_in")))))
````

#### SPICE deck: `fan_controller.cir`

````
.title KiCad schematic


R2 PWM Net-_Q2-B_ 1k
R1 VCC Net-_Q1-G_ 10k
R3 +5V RST 10k
R6 VCC TACH 10k
C1 VCC 0 100n
C2 +5V 0 100n
R5 /PWM_OUT PWM 1k
R4 TACH /TACH_IN 1k


V_5V +5V 0 DC 5.0
V_VCC VCC 0 DC 5.0


.control
tran 100u 10m
set filetype=ascii
write fan_controller_raw.raw all
.endc

.end
````
</design_files>

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
        {"source": "netlist" | "spice" | "circuit_json" | "spec", "quote": "short verbatim excerpt"}
      ],
      "impact": "the likely effect on the board's behaviour",
      "confidence": a number from 0 to 1
    }
  ],
  "summary": "one or two sentences stating your verdict and the main reason for it"
}

If `anomaly_detected` is `false`, `anomalies` must be an empty list.
