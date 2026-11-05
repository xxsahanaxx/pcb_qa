You are an expert PCB design reviewer. You will be given the design specification for the hardware project **PortalHardware**, and the design files for one build of that board. Your job is to decide whether the design files contain an **anomaly**: a deviation from the intended design that would make the board behave differently from what was intended. It could come from a design error, an assembly or sourcing mistake, or deliberate tampering.

The design files may be completely correct. Do not assume an anomaly exists. Report one only if the files support it.

## Inputs

### 1. Design specification

The specification describes the intended design: its purpose, architecture, key components and their values, power rails and interfaces. It was written by examining the reference design. Statements marked **Inferred** are the author's reasoning, not confirmed fact. Sections such as "Known limitations", "Known issues" or "logged bugs" describe real properties of the reference design. Those are **not** anomalies, and must not be reported.

The specification may not mention every component. Where it is silent, judge the design with standard electrical-engineering practice and with the component's own metadata (its library part, description, footprint and datasheet fields).

<design_specification>
# Portal — Design Specification

Source: `OSHP_files/Clean/portal-hardware` (vendored submodule of https://github.com/TwentyTwoHW/portal-hardware), KiCad project `PCB.kicad_sch` (top sheet) with two hierarchical sub-sheets `nfc_ic.kicad_sch` and `display.kicad_sch`, netlist `PCB.net`, and SPICE deck `PCB.cir`.

## 1. TL;DR

Per the repository README, this is "a Kicad project containing the Portal board design" — no further description is given in-repo. Based on the schematic contents, Portal is a single-PCB embedded controller built around an STM32L476RGT6 (ARM Cortex-M4) MCU with three user-facing peripherals:

- **NFC** (NXP NT3H2111 "NTAG I2C plus" tag IC, U3) wired to the MCU over I2C, for contactless data transfer with an external reader (e.g. a phone). This matches the "tap-to-sign" / air-gapped PSBT-transfer usage described for this board outside this repo; that *purpose* is not itself stated anywhere in the files reviewed, so treat it as context, not a grounded claim from this repo.
- **OLED display** (SSD1306 driver, on a module valued `ER-OLED0.96-1W`, U4) wired to the MCU over a 2-wire interface, for showing information to the user.
- **Capacitive touch button** (STM32 built-in Touch Sensing Controller peripheral, driven through electrode A2) for user input.

**Connector situation (verified against `PCB.net`'s component list):** the netlist contains exactly **one** connector-class part, `J1`, a 6-pin Tag-Connect `TC2030` pogo-pin SWD/JTAG programming header (footprint `Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical` — "NL" = no mounted legs, i.e. pads only, no plugged connector body lives on the board permanently). Its pins are VCC, GND, ~{RESET}, SWCLK, SWDIO, SWO — a standard ARM debug/programming interface, not a user I/O or power cable. No other `J`-prefixed (or any other explicitly connector-typed) component exists anywhere in `PCB.net`. There is no separate connector for NFC, display, touch, or battery/USB power — those subsystems are each realized as on-board chips/antennas wired directly into the PCB copper, and the schematic does not show where board VCC is normally sourced from (no battery, regulator, or USB part appears anywhere in the three `.kicad_sch` files or `PCB.net`/`PCB.cir` — confirmed by a text search for "battery", "regulat", "boost", "buck", "lipo" across all schematic/netlist files, which returned no matches, and by the absence of any `U1` reference).

## 2. Component table

| Ref | Part / value (from `PCB.net`) | Role | Source |
|---|---|---|---|
| U2 | `STM32L476RGT6`, LQFP-64 (symbol lib `MCU_ST_STM32L4`) | Main MCU — ARM Cortex-M4, 1024 KB flash / 128 KB RAM / 80 MHz (per symbol's own `Description` field), drives NFC, display, and touch | `PCB.kicad_sch`, `PCB.net` |
| U3 | `NT3H2111W0FT1X` (symbol `Symbols:NT3H2X11`, footprint `SOT96-1`) | NFC tag IC — NXP "NTAG I2C plus": NFC Forum Type-2-Tag with I2C interface, password protection, energy harvesting (symbol's own `Description` field) | `nfc_ic.kicad_sch`, `PCB.net`; identity corroborated by `3D_Models/NT3H21111.step` filename |
| U4 | `ER-OLED0.96-1W`, footprint `OLED-128O064D-WITH-FP` | OLED display module. The schematic symbol used for it is literally named `Symbols:SSD1306` in `display.kicad_sch`, with pins named per the SSD1306 datasheet (BS0–BS2, CS#, D/C#, E/RD#, R/W#, D0–D7, C1P/C1N/C2P/C2N, IREF, VCOMH, VBAT, VDD) — so the driver IC is the Solomon Systech SSD1306 | `display.kicad_sch`, `PCB.net`; corroborated by `3D_Models/OLED.step` |
| A2 | `TSC` (symbol `Symbols:TSC`, footprint `TSC-Rectangle-25x16mm`) | Capacitive-touch electrode/pad (pins `BTN`, `SHLD`). Not a chip — it is the sense pad wired into the MCU's built-in Touch Sensing Controller (TSC) peripheral | `PCB.kicad_sch`, `PCB.net` |
| A1 | `Antenna`, footprint `Antenna-Round-13.8MHz-53pF-Class3-50mm` | NFC loop antenna (PCB trace coil) coupled to U3 | `nfc_ic.kicad_sch`, `PCB.net` |
| J1 | `Conn_ARM_SWD_TagConnect_TC2030` | SWD/JTAG programming/debug connector (see §1) | `PCB.kicad_sch`, `PCB.net` |

No separate secure-element IC is present anywhere in the design files; the NT3H2111 provides on-chip password protection but there is no additional discrete secure element. No MCU other than U2 appears.

## 3. Interface rationale

### NFC and display both use 2-wire buses — why I2C, and how firmly is that grounded

**NFC (I2C — directly confirmed, by part choice and pin names):** U3 is the NXP NT3H2111, whose only digital interface (per its own symbol pin list) is I2C (`SDA` pin 5, `SCL` pin 3). There is no alternative interface on this part, so I2C here is simply what the chosen IC supports — not a separate design decision documented anywhere.
- `NFC_SDA` net: U2 pin 62 (`PB9`) — R1 (10 kΩ) to VCC — U3 pin 5 (`SDA`)
- `NFC_SCL` net: U2 pin 61 (`PB8`) — R2 (10 kΩ) to VCC — U3 pin 3 (`SCL`)
- `NFC_INT` net: U2 pin 22 (`PA6`) — R3 (10 kΩ) to VCC — U3 pin 4 (`FD`, field-detect output)

R1/R2/R3 are classic I2C-bus / open-drain pull-ups (SDA, SCL, and the NTAG's open-drain `FD` field-detect line all need an external pull-up to be read as a digital high) — this is a direct, unambiguous reading of the netlist topology, not an inference.

Separately, U3's `VOUT` (energy-harvesting output, pin 7) is tied to the same `VCC` net as its own `VCC` pin (pin 6) and the board's main VCC rail. The part's own `Description` field says the NT3H2111 supports "energy harvesting," so VOUT→VCC is consistent with that capability, but nothing in the repo states this was done so the board could run off harvested NFC field energy — **Inferred**: likely intent is to let the harvested rail assist/supplement VCC, but the actual reason is not documented.

**Display (confirmed to be I2C by BS-pin strapping, read directly from the netlist):** the SSD1306's own interface-select pins are hard-wired in `PCB.net`:
- `BS0` (pin 10) → GND
- `BS1` (pin 11) → VCC
- `BS2` (pin 12) → GND

That BS2,BS1,BS0 = 0,1,0 strapping, together with `D0`→`DISP_SCL` and `D1`+`D2` tied together →`DISP_SDA`, is the SSD1306's documented I2C-mode pin configuration (SCLK on D0, SDA on D1/D2 tied). This is a direct, repeatable reading of the netlist. **Inferred** (flagged, not asserted as fact): *why* I2C was picked over the SSD1306's alternative SPI/parallel modes is not stated anywhere in the repo (the `SSD1306` schematic symbol's own `Datasheet` property is empty, and no text note in `display.kicad_sch` explains the choice) — a reasonable guess is pin-count/MCU-GPIO economy (I2C shares the same two MCU pin pads class as the NFC bus) or because it is the module manufacturer's default soldered configuration (`ER-OLED0.96-1W` modules are typically fixed to I2C), but neither is confirmed in-repo.
- `DISP_SCL`: U2 pin 34 (`PB13`) — R6 (10 kΩ) to VCC — U4 pin 18 (`D0`)
- `DISP_SDA`: U2 pin 35 (`PB14`) — R7 (10 kΩ) to VCC — U4 pins 19/20 (`D1`/`D2`)
- `DISP_RES`: U2 pin 33 (`PB12`) — R4 (10 kΩ) to VCC — U4 pin 14 (`RES#`), active-low reset held high by R4's pull-up, asserted low by the MCU

Whether `PB8/PB9` and `PB13/PB14` are driven by the MCU's dedicated hardware I2C peripherals or bit-banged in firmware is **not stated** in the schematic — the KiCad symbol only labels these as generic bidirectional GPIO (`PB8`, `PB9`, `PB13`, `PB14`), with no alternate-function annotation. This is flagged as **Inferred** if assumed to be hardware I2C1/I2C2.

### Capacitive touch — how it is wired

The top-sheet text label "Capacitive Touch Button (TSC)" (the only section header for this block in `PCB.kicad_sch`) and the net names `TSC_G2_IO2` / `TSC_G2_IO4` are both literal, directly-sourced evidence that this uses the STM32's on-chip Touch Sensing Controller (TSC) peripheral, Group 2:
- `TSC_G2_IO2`: U2 pin 57 (`PB5`) — R8 (1 kΩ series resistor) — A2 pin "BTN" (the touch electrode)
- `TSC_G2_IO4`: U2 pin 59 (`PB7`) — C14 (22 nF to GND) — this is the TSC sampling capacitor for the group
- A2 pin "SHLD" (shield) ties to GND

This exactly matches ST's standard TSC application topology (one sampling-capacitor IO per group, with other group IOs carrying a series resistor out to the sense electrode), but no comment in the repo states this explicitly — the resistor/capacitor *function* (series-Rs vs. sampling-Cs) is **Inferred** from the well-known TSC circuit pattern and the component values (1 kΩ series resistor, 22 nF sampling cap are typical TSC values), not from an in-repo note.

## 4. Power section (from `PCB.cir`)

`PCB.cir` is a flat SPICE netlist with two global rails, `VCC` and `GND`; no voltage value or source element is defined in it (no `.param`, no voltage source, no battery/regulator part anywhere in the project — confirmed by grep across all `.kicad_sch`/`.net`/`.cir` files). The schematic does not show where VCC is generated; it is only consumed.

Decoupling / bulk capacitance directly on VCC–GND (all generic bypass, cannot be tied to a specific pin from the netlist alone since they only attach to the shared rails):
- C1, C9 — 4.7 µF each, VCC–GND (bulk)
- C2, C3, C4, C5, C6, C8 — 100 nF each, VCC–GND (local bypass)
- C10, C17 — 1 µF each, VCC–GND

Reset line: R10 (10 kΩ) ties `NRST` to VCC, holding the MCU's `NRST` pin high at idle; `NRST` is also wired to J1 pin 3 (`~{RESET}`) so the Tag-Connect programmer can pull it low.

OLED charge-pump / bias network (SSD1306, U4), read directly from `PCB.cir`/`PCB.net`:
- `C7` (2.2 µF) — U4 `VCC` (digital-logic supply pin) to GND
- `C12` (1 µF) — across U4 `C1P`/`C1N` (charge-pump stage 1 flying capacitor)
- `C13` (1 µF) — across U4 `C2P`/`C2N` (charge-pump stage 2 flying capacitor)
- `C11` (4.7 µF) — U4 `VCOMH` (charge-pump output) to GND, the output reservoir/filter cap
- `R5` (390 kΩ) — U4 `IREF` to GND

U4's `VBAT` pin (its high-voltage supply input) is tied directly to the board's main `VCC` net (same net as the MCU and NFC IC) rather than to a separate boosted rail — meaning the SSD1306's internal charge pump (via C12/C13, output-filtered by C11) is relied on to step VBAT up to the panel drive voltage. This is a direct reading of the netlist; no comment in the repo states this was a deliberate choice versus an external boost converter, so the "why" is **Inferred** (standard SSD1306 app-circuit practice, using the chip's own internal DC-DC rather than an extra external regulator) rather than confirmed.

NFC antenna matching: the design note in `nfc_ic.kicad_sch` (the only non-trivial rationale comment in the whole repo) explicitly documents the inductance target calculation: assuming 3 pF parasitic capacitance and a 13.6 MHz target resonant frequency against the antenna footprint's rated 53 pF, it solves for a target inductance and states the realized 50 mm/5-turn/520 µm-track coil (`A1`, footprint `Antenna-Round-13.8MHz-53pF-Class3-50mm`) has an "Eq. inductance = 2.581 µH." The tuning/matching capacitor `C18` across the antenna terminals is still left with an unresolved value in the netlist (`PCB.net` lists `C18` value as literally `"??"`), meaning the resonance tuning had not been finalized at the time this schematic was captured — stated directly, not inferred.
</design_specification>

### 2. Design files

- **KiCad netlist (`.net`):** the authoritative connectivity. Every component, with its reference, value, footprint, library part and fields, and every net, with the pins on it. Net names of the form `Net-(<ref>-<pin>)` are generated automatically from a pin on that net.
- **SPICE deck (`.cir`):** a simulation deck derived from the same schematic. Only resistors, capacitors, inductors, diodes and sources are modelled. ICs, connectors and transistors are left out, and ground is node `0`. Treat this file as a secondary view; the netlist takes precedence.
- **Circuit JSON (`.json`), if present:** the same netlist as hierarchical JSON.

<design_files>
#### KiCad netlist: `PCB.net`

````
(export (version "E")
  (design
    (source "PCB.kicad_sch")
    (date "")
    (tool "Eeschema 9.0.6")
    (sheet (number "1") (name "/") (tstamps "/")
      (title_block
        (title)
        (company)
        (rev)
        (date)
        (source "PCB.kicad_sch")
        (comment (number "1") (value ""))
        (comment (number "2") (value ""))
        (comment (number "3") (value ""))
        (comment (number "4") (value ""))
        (comment (number "5") (value ""))
        (comment (number "6") (value ""))
        (comment (number "7") (value ""))
        (comment (number "8") (value ""))
        (comment (number "9") (value ""))))
    (sheet (number "2") (name "/NFC_IC/") (tstamps "/66315e85-01d7-4de8-9fd4-832315f91890/")
      (title_block
        (title)
        (company)
        (rev)
        (date)
        (source "nfc_ic.kicad_sch")
        (comment (number "1") (value ""))
        (comment (number "2") (value ""))
        (comment (number "3") (value ""))
        (comment (number "4") (value ""))
        (comment (number "5") (value ""))
        (comment (number "6") (value ""))
        (comment (number "7") (value ""))
        (comment (number "8") (value ""))
        (comment (number "9") (value ""))))
    (sheet (number "3") (name "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/")
      (title_block
        (title)
        (company)
        (rev)
        (date)
        (source "display.kicad_sch")
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
    (comp (ref "A2")
      (value "TSC")
      (footprint "Footprints:TSC-Rectangle-25x16mm")
      (fields
        (field (name "Footprint") "Footprints:TSC-Rectangle-25x16mm")
        (field (name "Datasheet"))
        (field (name "Description")))
      (libsource (lib "Symbols") (part "TSC") (description ""))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "exclude_from_bom"))
      (property (name "ki_fp_filters") (value "TSC-*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "4754f59b-5211-4ff3-9b98-38c756a2261b"))
    (comp (ref "C1")
      (value "4.7u")
      (footprint "Capacitor_SMD:C_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "4426a6ac-deab-4ba4-a9a1-cff04998eb68"))
    (comp (ref "C2")
      (value "100n")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "4e282c2f-dc8a-464d-8d46-9cb5245199c6"))
    (comp (ref "C3")
      (value "100n")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "55bd8d7b-82b7-4a5c-a0ae-7f24986e84af"))
    (comp (ref "C4")
      (value "100n")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "7f12b300-127c-4934-a4e0-a17cd1ade43a"))
    (comp (ref "C5")
      (value "100n")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "eea7b2d8-635f-4a2e-b423-40e9d90e5626"))
    (comp (ref "C6")
      (value "100n")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "5c2fc8b2-c33e-47ef-be14-83846ae7c7d5"))
    (comp (ref "C9")
      (value "4.7u")
      (footprint "Capacitor_SMD:C_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "164580b9-8db0-47d7-b1a7-acb0b6644a59"))
    (comp (ref "C14")
      (value "22n")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "855667a8-cea1-4703-9eda-6eba4a3cf557"))
    (comp (ref "J1")
      (value "Conn_ARM_SWD_TagConnect_TC2030")
      (footprint "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical")
      (datasheet "https://www.tag-connect.com/wp-content/uploads/bsk-pdf-manager/TC2030-CTX_1.pdf")
      (fields
        (field (name "Footprint") "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical")
        (field (name "Datasheet") "https://www.tag-connect.com/wp-content/uploads/bsk-pdf-manager/TC2030-CTX_1.pdf")
        (field (name "Description")))
      (libsource (lib "Connector") (part "Conn_ARM_SWD_TagConnect_TC2030") (description "Tag-Connect ARM Cortex SWD JTAG connector, 6 pin"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "exclude_from_bom"))
      (property (name "ki_keywords") (value "Cortex Debug Connector ARM SWD JTAG"))
      (property (name "ki_fp_filters") (value "*TC2030*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "5d13cc3c-090a-4732-8d15-f1bbc4a216ae"))
    (comp (ref "R8")
      (value "1k")
      (footprint "Resistor_SMD:R_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "8da44583-b02a-44ad-b511-6b47b0f49ffd"))
    (comp (ref "R10")
      (value "10k")
      (footprint "Resistor_SMD:R_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "b0a1df78-34ed-455f-9117-bd2beca93fbf"))
    (comp (ref "U2")
      (value "STM32L476RGT6")
      (footprint "Package_QFP:LQFP-64_10x10mm_P0.5mm")
      (datasheet "http://www.st.com/st-web-ui/static/active/en/resource/technical/document/datasheet/DM00108832.pdf")
      (fields
        (field (name "Footprint") "Package_QFP:LQFP-64_10x10mm_P0.5mm")
        (field (name "Datasheet") "http://www.st.com/st-web-ui/static/active/en/resource/technical/document/datasheet/DM00108832.pdf")
        (field (name "Description")))
      (libsource (lib "MCU_ST_STM32L4") (part "STM32L476RGTx") (description "ARM Cortex-M4 MCU, 1024KB flash, 128KB RAM, 80MHz, 1.71-3.6V, 51 GPIO, LQFP-64"))
      (property (name "Sheetname") (value ""))
      (property (name "Sheetfile") (value "PCB.kicad_sch"))
      (property (name "ki_keywords") (value "ARM Cortex-M4 STM32L4 STM32L4x6"))
      (property (name "ki_fp_filters") (value "LQFP*10x10mm*P0.5mm*"))
      (sheetpath (names "/") (tstamps "/"))
      (tstamps "dfe1377e-31e4-4713-b75a-d9fba377f756"))
    (comp (ref "A1")
      (value "Antenna")
      (footprint "Footprints:Antenna-Round-13.8MHz-53pF-Class3-50mm")
      (fields
        (field (name "Footprint") "Footprints:Antenna-Round-13.8MHz-53pF-Class3-50mm")
        (field (name "Datasheet"))
        (field (name "Description")))
      (libsource (lib "Symbols") (part "Antenna") (description ""))
      (property (name "Sheetname") (value "NFC_IC"))
      (property (name "Sheetfile") (value "nfc_ic.kicad_sch"))
      (property (name "exclude_from_bom"))
      (property (name "ki_fp_filters") (value "Antenna-*"))
      (sheetpath (names "/NFC_IC/") (tstamps "/66315e85-01d7-4de8-9fd4-832315f91890/"))
      (tstamps "87a0081e-2809-4b93-a5e6-a3d25fb30205"))
    (comp (ref "C8")
      (value "100n")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "NFC_IC"))
      (property (name "Sheetfile") (value "nfc_ic.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/NFC_IC/") (tstamps "/66315e85-01d7-4de8-9fd4-832315f91890/"))
      (tstamps "11dd6fb4-0f24-4441-bd16-c50c9fc87118"))
    (comp (ref "C18")
      (value "??")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "NFC_IC"))
      (property (name "Sheetfile") (value "nfc_ic.kicad_sch"))
      (property (name "exclude_from_bom"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/NFC_IC/") (tstamps "/66315e85-01d7-4de8-9fd4-832315f91890/"))
      (tstamps "d3ffcb79-26a2-4a04-82aa-c9811ebfc8ce"))
    (comp (ref "R1")
      (value "10k")
      (footprint "Resistor_SMD:R_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value "NFC_IC"))
      (property (name "Sheetfile") (value "nfc_ic.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/NFC_IC/") (tstamps "/66315e85-01d7-4de8-9fd4-832315f91890/"))
      (tstamps "f137fb8c-5119-4044-a4cf-fb5454f858f5"))
    (comp (ref "R2")
      (value "10k")
      (footprint "Resistor_SMD:R_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value "NFC_IC"))
      (property (name "Sheetfile") (value "nfc_ic.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/NFC_IC/") (tstamps "/66315e85-01d7-4de8-9fd4-832315f91890/"))
      (tstamps "773557db-8528-4ddc-b545-2333ac14d08c"))
    (comp (ref "R3")
      (value "10k")
      (footprint "Resistor_SMD:R_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value "NFC_IC"))
      (property (name "Sheetfile") (value "nfc_ic.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/NFC_IC/") (tstamps "/66315e85-01d7-4de8-9fd4-832315f91890/"))
      (tstamps "ca49aff2-562f-42d2-9b85-cac6bbb3618b"))
    (comp (ref "U3")
      (value "NT3H2111W0FT1X")
      (footprint "Footprints:SOT96-1")
      (fields
        (field (name "Footprint") "Footprints:SOT96-1")
        (field (name "Datasheet"))
        (field (name "Description")))
      (libsource (lib "Symbols") (part "NT3H2X11") (description "NTAG I2C plus: NFC Forum T2T with I2C interface, password protection and energy harvesting"))
      (property (name "Sheetname") (value "NFC_IC"))
      (property (name "Sheetfile") (value "nfc_ic.kicad_sch"))
      (property (name "ki_keywords") (value "NT3H2211 NT3H2111"))
      (property (name "ki_fp_filters") (value "XQFN-8_1.6x1.6_Pitch0.5mm SOT96-1"))
      (sheetpath (names "/NFC_IC/") (tstamps "/66315e85-01d7-4de8-9fd4-832315f91890/"))
      (tstamps "c233d657-5051-4759-b124-f24ddd9c1073"))
    (comp (ref "C7")
      (value "2.2u")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "034b1185-a428-41ca-aea1-968e47f71eed"))
    (comp (ref "C10")
      (value "1u")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "1479ea74-964a-4fdc-b6e6-56736721bc68"))
    (comp (ref "C11")
      (value "4.7u")
      (footprint "Capacitor_SMD:C_0805_2012Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0805_2012Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "c7332dcf-992f-473b-8dd7-ae09463d2855"))
    (comp (ref "C12")
      (value "1u")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "9a524035-35b5-4dd1-a141-6c957d049a04"))
    (comp (ref "C13")
      (value "1u")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "6ccc6c71-8e20-4c74-9d71-feb50be9414c"))
    (comp (ref "C17")
      (value "1u")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "ef0820ac-fe01-4680-8f17-49f62d180914"))
    (comp (ref "C19")
      (value "100n")
      (footprint "Capacitor_SMD:C_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Capacitor_SMD:C_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "C_Small") (description "Unpolarized capacitor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "capacitor cap"))
      (property (name "ki_fp_filters") (value "C_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "0ec32fcf-8b7f-4e1b-b601-ae8333f8e633"))
    (comp (ref "R4")
      (value "10k")
      (footprint "Resistor_SMD:R_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "f5df7a63-e0ef-4ec2-a028-83a9517aef6c"))
    (comp (ref "R6")
      (value "10k")
      (footprint "Resistor_SMD:R_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "6f0145b2-ca6d-4ec3-93a9-fcdc564203c7"))
    (comp (ref "R7")
      (value "10k")
      (footprint "Resistor_SMD:R_0603_1608Metric")
      (datasheet "~")
      (fields
        (field (name "Footprint") "Resistor_SMD:R_0603_1608Metric")
        (field (name "Datasheet") "~")
        (field (name "Description")))
      (libsource (lib "Device") (part "R_Small") (description "Resistor, small symbol"))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (property (name "ki_keywords") (value "R resistor"))
      (property (name "ki_fp_filters") (value "R_*"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "1f5f1e87-9c81-4762-826e-2524b8b2a08c"))
    (comp (ref "U4")
      (value "ER-OLED0.96-1W")
      (footprint "Footprints:OLED-128O064D-WITH-FP")
      (fields
        (field (name "Footprint") "Footprints:OLED-128O064D-WITH-FP")
        (field (name "Datasheet"))
        (field (name "Description")))
      (libsource (lib "Symbols") (part "SSD1306") (description ""))
      (property (name "Sheetname") (value "DISPLAY"))
      (property (name "Sheetfile") (value "display.kicad_sch"))
      (sheetpath (names "/DISPLAY/") (tstamps "/d44f1684-d5b1-4ed8-a67b-a9b4d50feb0f/"))
      (tstamps "d021d40a-bad3-4f14-a849-ec2ffb31d17a")))
  (libparts
    (libpart (lib "Connector") (part "Conn_ARM_SWD_TagConnect_TC2030")
      (description "Tag-Connect ARM Cortex SWD JTAG connector, 6 pin")
      (docs "https://www.tag-connect.com/wp-content/uploads/bsk-pdf-manager/TC2030-CTX_1.pdf")
      (footprints
        (fp "*TC2030*"))
      (fields
        (field (name "Reference") "J")
        (field (name "Value") "Conn_ARM_SWD_TagConnect_TC2030")
        (field (name "Footprint") "Connector:Tag-Connect_TC2030-IDC-FP_2x03_P1.27mm_Vertical")
        (field (name "Datasheet") "https://www.tag-connect.com/wp-content/uploads/bsk-pdf-manager/TC2030-CTX_1.pdf")
        (field (name "Description") "Tag-Connect ARM Cortex SWD JTAG connector, 6 pin"))
      (pins
        (pin (num "1") (name "VCC") (type "power_in"))
        (pin (num "2") (name "SWDIO") (type "bidirectional"))
        (pin (num "3") (name "~{RESET}") (type "open_collector"))
        (pin (num "4") (name "SWCLK") (type "output"))
        (pin (num "5") (name "GND") (type "power_in"))
        (pin (num "6") (name "SWO") (type "input"))))
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
    (libpart (lib "MCU_ST_STM32L4") (part "STM32L476RGTx")
      (description "ARM Cortex-M4 MCU, 1024KB flash, 128KB RAM, 80MHz, 1.71-3.6V, 51 GPIO, LQFP-64")
      (docs "http://www.st.com/st-web-ui/static/active/en/resource/technical/document/datasheet/DM00108832.pdf")
      (footprints
        (fp "LQFP*10x10mm*P0.5mm*"))
      (fields
        (field (name "Reference") "U")
        (field (name "Value") "STM32L476RGTx")
        (field (name "Footprint") "Package_QFP:LQFP-64_10x10mm_P0.5mm")
        (field (name "Datasheet") "http://www.st.com/st-web-ui/static/active/en/resource/technical/document/datasheet/DM00108832.pdf")
        (field (name "Description") "ARM Cortex-M4 MCU, 1024KB flash, 128KB RAM, 80MHz, 1.71-3.6V, 51 GPIO, LQFP-64"))
      (pins
        (pin (num "1") (name "VBAT") (type "power_in"))
        (pin (num "2") (name "PC13") (type "bidirectional"))
        (pin (num "3") (name "PC14") (type "bidirectional"))
        (pin (num "4") (name "PC15") (type "bidirectional"))
        (pin (num "5") (name "PH0") (type "input"))
        (pin (num "6") (name "PH1") (type "input"))
        (pin (num "7") (name "NRST") (type "input"))
        (pin (num "8") (name "PC0") (type "bidirectional"))
        (pin (num "9") (name "PC1") (type "bidirectional"))
        (pin (num "10") (name "PC2") (type "bidirectional"))
        (pin (num "11") (name "PC3") (type "bidirectional"))
        (pin (num "12") (name "VSSA") (type "power_in"))
        (pin (num "13") (name "VDDA") (type "power_in"))
        (pin (num "14") (name "PA0") (type "bidirectional"))
        (pin (num "15") (name "PA1") (type "bidirectional"))
        (pin (num "16") (name "PA2") (type "bidirectional"))
        (pin (num "17") (name "PA3") (type "bidirectional"))
        (pin (num "18") (name "VSS") (type "power_in"))
        (pin (num "19") (name "VDD") (type "power_in"))
        (pin (num "20") (name "PA4") (type "bidirectional"))
        (pin (num "21") (name "PA5") (type "bidirectional"))
        (pin (num "22") (name "PA6") (type "bidirectional"))
        (pin (num "23") (name "PA7") (type "bidirectional"))
        (pin (num "24") (name "PC4") (type "bidirectional"))
        (pin (num "25") (name "PC5") (type "bidirectional"))
        (pin (num "26") (name "PB0") (type "bidirectional"))
        (pin (num "27") (name "PB1") (type "bidirectional"))
        (pin (num "28") (name "PB2") (type "bidirectional"))
        (pin (num "29") (name "PB10") (type "bidirectional"))
        (pin (num "30") (name "PB11") (type "bidirectional"))
        (pin (num "31") (name "VSS") (type "power_in"))
        (pin (num "32") (name "VDD") (type "power_in"))
        (pin (num "33") (name "PB12") (type "bidirectional"))
        (pin (num "34") (name "PB13") (type "bidirectional"))
        (pin (num "35") (name "PB14") (type "bidirectional"))
        (pin (num "36") (name "PB15") (type "bidirectional"))
        (pin (num "37") (name "PC6") (type "bidirectional"))
        (pin (num "38") (name "PC7") (type "bidirectional"))
        (pin (num "39") (name "PC8") (type "bidirectional"))
        (pin (num "40") (name "PC9") (type "bidirectional"))
        (pin (num "41") (name "PA8") (type "bidirectional"))
        (pin (num "42") (name "PA9") (type "bidirectional"))
        (pin (num "43") (name "PA10") (type "bidirectional"))
        (pin (num "44") (name "PA11") (type "bidirectional"))
        (pin (num "45") (name "PA12") (type "bidirectional"))
        (pin (num "46") (name "PA13") (type "bidirectional"))
        (pin (num "47") (name "VSS") (type "power_in"))
        (pin (num "48") (name "VDDUSB") (type "power_in"))
        (pin (num "49") (name "PA14") (type "bidirectional"))
        (pin (num "50") (name "PA15") (type "bidirectional"))
        (pin (num "51") (name "PC10") (type "bidirectional"))
        (pin (num "52") (name "PC11") (type "bidirectional"))
        (pin (num "53") (name "PC12") (type "bidirectional"))
        (pin (num "54") (name "PD2") (type "bidirectional"))
        (pin (num "55") (name "PB3") (type "bidirectional"))
        (pin (num "56") (name "PB4") (type "bidirectional"))
        (pin (num "57") (name "PB5") (type "bidirectional"))
        (pin (num "58") (name "PB6") (type "bidirectional"))
        (pin (num "59") (name "PB7") (type "bidirectional"))
        (pin (num "60") (name "BOOT0") (type "input"))
        (pin (num "61") (name "PB8") (type "bidirectional"))
        (pin (num "62") (name "PB9") (type "bidirectional"))
        (pin (num "63") (name "VSS") (type "power_in"))
        (pin (num "64") (name "VDD") (type "power_in"))))
    (libpart (lib "Symbols") (part "Antenna")
      (footprints
        (fp "Antenna-*"))
      (fields
        (field (name "Reference") "A")
        (field (name "Value") "Antenna")
        (field (name "Footprint"))
        (field (name "Datasheet"))
        (field (name "Description")))
      (pins
        (pin (num "1") (name "A") (type "passive"))
        (pin (num "2") (name "B") (type "passive"))))
    (libpart (lib "Symbols") (part "NT3H2X11")
      (description "NTAG I2C plus: NFC Forum T2T with I2C interface, password protection and energy harvesting")
      (footprints
        (fp "XQFN-8_1.6x1.6_Pitch0.5mm")
        (fp "SOT96-1"))
      (fields
        (field (name "Reference") "U")
        (field (name "Value") "NT3H2X11")
        (field (name "Footprint"))
        (field (name "Datasheet"))
        (field (name "Description") "NTAG I2C plus: NFC Forum T2T with I2C interface, password protection and energy harvesting"))
      (pins
        (pin (num "1") (name "LA") (type "passive"))
        (pin (num "2") (name "VSS") (type "power_in"))
        (pin (num "3") (name "SCL") (type "input"))
        (pin (num "4") (name "FD") (type "output"))
        (pin (num "5") (name "SDA") (type "bidirectional"))
        (pin (num "6") (name "VCC") (type "power_in"))
        (pin (num "7") (name "VOUT") (type "power_out"))
        (pin (num "8") (name "LB") (type "passive"))))
    (libpart (lib "Symbols") (part "SSD1306")
      (fields
        (field (name "Reference") "U")
        (field (name "Value") "SSD1306")
        (field (name "Footprint") "Footprints:OLED-30")
        (field (name "Datasheet"))
        (field (name "Description")))
      (pins
        (pin (num "1") (name "N.C.(GND)") (type "power_in"))
        (pin (num "2") (name "C2P") (type "input"))
        (pin (num "3") (name "C2N") (type "input"))
        (pin (num "4") (name "C1P") (type "input"))
        (pin (num "5") (name "C1N") (type "input"))
        (pin (num "6") (name "VBAT") (type "power_in"))
        (pin (num "7") (name "N.C.") (type "no_connect"))
        (pin (num "8") (name "VSS") (type "power_in"))
        (pin (num "9") (name "VDD") (type "power_in"))
        (pin (num "10") (name "BS0") (type "input"))
        (pin (num "11") (name "BS1") (type "input"))
        (pin (num "12") (name "BS2") (type "input"))
        (pin (num "13") (name "CS#") (type "input"))
        (pin (num "14") (name "RES#") (type "input"))
        (pin (num "15") (name "D/C#") (type "input"))
        (pin (num "16") (name "R/W#") (type "input"))
        (pin (num "17") (name "E/RD#") (type "input"))
        (pin (num "18") (name "D0") (type "bidirectional"))
        (pin (num "19") (name "D1") (type "bidirectional"))
        (pin (num "20") (name "D2") (type "bidirectional"))
        (pin (num "21") (name "D3") (type "bidirectional"))
        (pin (num "22") (name "D4") (type "bidirectional"))
        (pin (num "23") (name "D5") (type "bidirectional"))
        (pin (num "24") (name "D6") (type "bidirectional"))
        (pin (num "25") (name "D7") (type "bidirectional"))
        (pin (num "26") (name "IREF") (type "input"))
        (pin (num "27") (name "VCOMH") (type "output"))
        (pin (num "28") (name "VCC") (type "power_in"))
        (pin (num "29") (name "VLSS") (type "power_in"))
        (pin (num "30") (name "N.C.(GND)") (type "power_in"))))
    (libpart (lib "Symbols") (part "TSC")
      (footprints
        (fp "TSC-*"))
      (fields
        (field (name "Reference") "A")
        (field (name "Value") "TSC")
        (field (name "Footprint"))
        (field (name "Datasheet"))
        (field (name "Description")))
      (pins
        (pin (num "1") (name "BTN") (type "passive"))
        (pin (num "2") (name "SHLD") (type "passive")))))
  (libraries
    (library (logical "Connector")
      (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols//Connector.kicad_sym"))
    (library (logical "Device")
      (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols//Device.kicad_sym"))
    (library (logical "MCU_ST_STM32L4")
      (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols//MCU_ST_STM32L4.kicad_sym"))
    (library (logical "Symbols")
      (uri "${KIPRJMOD}/Symbols.kicad_sym")))
  (nets
    (net (code "1") (name "DISP_RES") (class "Default")
      (node (ref "R4") (pin "1") (pintype "passive"))
      (node (ref "U2") (pin "33") (pinfunction "PB12") (pintype "bidirectional"))
      (node (ref "U4") (pin "14") (pinfunction "RES#") (pintype "input")))
    (net (code "2") (name "DISP_SCL") (class "Default")
      (node (ref "R6") (pin "1") (pintype "passive"))
      (node (ref "U2") (pin "34") (pinfunction "PB13") (pintype "bidirectional"))
      (node (ref "U4") (pin "18") (pinfunction "D0") (pintype "bidirectional")))
    (net (code "3") (name "DISP_SDA") (class "Default")
      (node (ref "R7") (pin "1") (pintype "passive"))
      (node (ref "U2") (pin "35") (pinfunction "PB14") (pintype "bidirectional"))
      (node (ref "U4") (pin "19") (pinfunction "D1") (pintype "bidirectional"))
      (node (ref "U4") (pin "20") (pinfunction "D2") (pintype "bidirectional")))
    (net (code "4") (name "GND") (class "Default")
      (node (ref "A2") (pin "2") (pinfunction "SHLD") (pintype "passive"))
      (node (ref "C1") (pin "2") (pintype "passive"))
      (node (ref "C10") (pin "2") (pintype "passive"))
      (node (ref "C11") (pin "2") (pintype "passive"))
      (node (ref "C14") (pin "1") (pintype "passive"))
      (node (ref "C17") (pin "2") (pintype "passive"))
      (node (ref "C19") (pin "1") (pintype "passive"))
      (node (ref "C2") (pin "2") (pintype "passive"))
      (node (ref "C3") (pin "2") (pintype "passive"))
      (node (ref "C4") (pin "2") (pintype "passive"))
      (node (ref "C5") (pin "2") (pintype "passive"))
      (node (ref "C6") (pin "2") (pintype "passive"))
      (node (ref "C7") (pin "2") (pintype "passive"))
      (node (ref "C8") (pin "2") (pintype "passive"))
      (node (ref "C9") (pin "2") (pintype "passive"))
      (node (ref "J1") (pin "5") (pinfunction "GND") (pintype "power_in"))
      (node (ref "U2") (pin "12") (pinfunction "VSSA") (pintype "power_in"))
      (node (ref "U2") (pin "18") (pinfunction "VSS") (pintype "power_in"))
      (node (ref "U2") (pin "31") (pinfunction "VSS") (pintype "power_in"))
      (node (ref "U2") (pin "47") (pinfunction "VSS") (pintype "power_in"))
      (node (ref "U2") (pin "60") (pinfunction "BOOT0") (pintype "input"))
      (node (ref "U2") (pin "63") (pinfunction "VSS") (pintype "power_in"))
      (node (ref "U3") (pin "2") (pinfunction "VSS") (pintype "power_in"))
      (node (ref "U4") (pin "1") (pinfunction "N.C.(GND)") (pintype "power_in"))
      (node (ref "U4") (pin "10") (pinfunction "BS0") (pintype "input"))
      (node (ref "U4") (pin "12") (pinfunction "BS2") (pintype "input"))
      (node (ref "U4") (pin "13") (pinfunction "CS#") (pintype "input"))
      (node (ref "U4") (pin "15") (pinfunction "D/C#") (pintype "input"))
      (node (ref "U4") (pin "16") (pinfunction "R/W#") (pintype "input"))
      (node (ref "U4") (pin "17") (pinfunction "E/RD#") (pintype "input"))
      (node (ref "U4") (pin "21") (pinfunction "D3") (pintype "bidirectional"))
      (node (ref "U4") (pin "22") (pinfunction "D4") (pintype "bidirectional"))
      (node (ref "U4") (pin "23") (pinfunction "D5") (pintype "bidirectional"))
      (node (ref "U4") (pin "24") (pinfunction "D6") (pintype "bidirectional"))
      (node (ref "U4") (pin "25") (pinfunction "D7") (pintype "bidirectional"))
      (node (ref "U4") (pin "29") (pinfunction "VLSS") (pintype "power_in"))
      (node (ref "U4") (pin "30") (pinfunction "N.C.(GND)") (pintype "power_in"))
      (node (ref "U4") (pin "8") (pinfunction "VSS") (pintype "power_in")))
    (net (code "5") (name "NFC_INT") (class "Default")
      (node (ref "R3") (pin "1") (pintype "passive"))
      (node (ref "U2") (pin "22") (pinfunction "PA6") (pintype "bidirectional"))
      (node (ref "U3") (pin "4") (pinfunction "FD") (pintype "output")))
    (net (code "6") (name "NFC_SCL") (class "Default")
      (node (ref "R2") (pin "1") (pintype "passive"))
      (node (ref "U2") (pin "61") (pinfunction "PB8") (pintype "bidirectional"))
      (node (ref "U3") (pin "3") (pinfunction "SCL") (pintype "input")))
    (net (code "7") (name "NFC_SDA") (class "Default")
      (node (ref "R1") (pin "1") (pintype "passive"))
      (node (ref "U2") (pin "62") (pinfunction "PB9") (pintype "bidirectional"))
      (node (ref "U3") (pin "5") (pinfunction "SDA") (pintype "bidirectional")))
    (net (code "8") (name "NRST") (class "Default")
      (node (ref "J1") (pin "3") (pinfunction "~{RESET}") (pintype "open_collector"))
      (node (ref "R10") (pin "2") (pintype "passive"))
      (node (ref "U2") (pin "7") (pinfunction "NRST") (pintype "input")))
    (net (code "9") (name "Net-(A1-A)") (class "Default")
      (node (ref "A1") (pin "1") (pinfunction "A") (pintype "passive"))
      (node (ref "C18") (pin "2") (pintype "passive"))
      (node (ref "U3") (pin "8") (pinfunction "LB") (pintype "passive")))
    (net (code "10") (name "Net-(A1-B)") (class "Default")
      (node (ref "A1") (pin "2") (pinfunction "B") (pintype "passive"))
      (node (ref "C18") (pin "1") (pintype "passive"))
      (node (ref "U3") (pin "1") (pinfunction "LA") (pintype "passive")))
    (net (code "11") (name "Net-(A2-BTN)") (class "Default")
      (node (ref "A2") (pin "1") (pinfunction "BTN") (pintype "passive"))
      (node (ref "R8") (pin "2") (pintype "passive")))
    (net (code "12") (name "Net-(U4-C1N)") (class "Default")
      (node (ref "C12") (pin "1") (pintype "passive"))
      (node (ref "U4") (pin "5") (pinfunction "C1N") (pintype "input")))
    (net (code "13") (name "Net-(U4-C1P)") (class "Default")
      (node (ref "C12") (pin "2") (pintype "passive"))
      (node (ref "U4") (pin "4") (pinfunction "C1P") (pintype "input")))
    (net (code "14") (name "Net-(U4-C2N)") (class "Default")
      (node (ref "C13") (pin "1") (pintype "passive"))
      (node (ref "U4") (pin "3") (pinfunction "C2N") (pintype "input")))
    (net (code "15") (name "Net-(U4-C2P)") (class "Default")
      (node (ref "C13") (pin "2") (pintype "passive"))
      (node (ref "U4") (pin "2") (pinfunction "C2P") (pintype "input")))
    (net (code "16") (name "Net-(U4-IREF)") (class "Default")
      (node (ref "C19") (pin "2") (pintype "passive"))
      (node (ref "U4") (pin "26") (pinfunction "IREF") (pintype "input")))
    (net (code "17") (name "Net-(U4-VCC)") (class "Default")
      (node (ref "C7") (pin "1") (pintype "passive"))
      (node (ref "U4") (pin "28") (pinfunction "VCC") (pintype "power_in")))
    (net (code "18") (name "Net-(U4-VCOMH)") (class "Default")
      (node (ref "C11") (pin "1") (pintype "passive"))
      (node (ref "U4") (pin "27") (pinfunction "VCOMH") (pintype "output")))
    (net (code "19") (name "SWCLK") (class "Default")
      (node (ref "J1") (pin "4") (pinfunction "SWCLK") (pintype "output"))
      (node (ref "U2") (pin "49") (pinfunction "PA14") (pintype "bidirectional")))
    (net (code "20") (name "SWDIO") (class "Default")
      (node (ref "J1") (pin "2") (pinfunction "SWDIO") (pintype "bidirectional"))
      (node (ref "U2") (pin "46") (pinfunction "PA13") (pintype "bidirectional")))
    (net (code "21") (name "SWO") (class "Default")
      (node (ref "J1") (pin "6") (pinfunction "SWO") (pintype "input"))
      (node (ref "U2") (pin "55") (pinfunction "PB3") (pintype "bidirectional")))
    (net (code "22") (name "TSC_G2_IO2") (class "Default")
      (node (ref "R8") (pin "1") (pintype "passive"))
      (node (ref "U2") (pin "57") (pinfunction "PB5") (pintype "bidirectional")))
    (net (code "23") (name "TSC_G2_IO4") (class "Default")
      (node (ref "C14") (pin "2") (pintype "passive"))
      (node (ref "U2") (pin "59") (pinfunction "PB7") (pintype "bidirectional")))
    (net (code "24") (name "VCC") (class "Default")
      (node (ref "C1") (pin "1") (pintype "passive"))
      (node (ref "C10") (pin "1") (pintype "passive"))
      (node (ref "C17") (pin "1") (pintype "passive"))
      (node (ref "C2") (pin "1") (pintype "passive"))
      (node (ref "C3") (pin "1") (pintype "passive"))
      (node (ref "C4") (pin "1") (pintype "passive"))
      (node (ref "C5") (pin "1") (pintype "passive"))
      (node (ref "C6") (pin "1") (pintype "passive"))
      (node (ref "C8") (pin "1") (pintype "passive"))
      (node (ref "C9") (pin "1") (pintype "passive"))
      (node (ref "J1") (pin "1") (pinfunction "VCC") (pintype "power_in"))
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "R10") (pin "1") (pintype "passive"))
      (node (ref "R2") (pin "2") (pintype "passive"))
      (node (ref "R3") (pin "2") (pintype "passive"))
      (node (ref "R4") (pin "2") (pintype "passive"))
      (node (ref "R6") (pin "2") (pintype "passive"))
      (node (ref "R7") (pin "2") (pintype "passive"))
      (node (ref "U2") (pin "13") (pinfunction "VDDA") (pintype "power_in"))
      (node (ref "U2") (pin "19") (pinfunction "VDD") (pintype "power_in"))
      (node (ref "U2") (pin "32") (pinfunction "VDD") (pintype "power_in"))
      (node (ref "U2") (pin "48") (pinfunction "VDDUSB") (pintype "power_in"))
      (node (ref "U2") (pin "64") (pinfunction "VDD") (pintype "power_in"))
      (node (ref "U3") (pin "6") (pinfunction "VCC") (pintype "power_in"))
      (node (ref "U3") (pin "7") (pinfunction "VOUT") (pintype "power_out"))
      (node (ref "U4") (pin "11") (pinfunction "BS1") (pintype "input"))
      (node (ref "U4") (pin "6") (pinfunction "VBAT") (pintype "power_in"))
      (node (ref "U4") (pin "9") (pinfunction "VDD") (pintype "power_in")))
    (net (code "25") (name "unconnected-(U2-PA0-Pad14)") (class "Default")
      (node (ref "U2") (pin "14") (pinfunction "PA0") (pintype "bidirectional")))
    (net (code "26") (name "unconnected-(U2-PA1-Pad15)") (class "Default")
      (node (ref "U2") (pin "15") (pinfunction "PA1") (pintype "bidirectional")))
    (net (code "27") (name "unconnected-(U2-PA2-Pad16)") (class "Default")
      (node (ref "U2") (pin "16") (pinfunction "PA2") (pintype "bidirectional")))
    (net (code "28") (name "unconnected-(U2-PA3-Pad17)") (class "Default")
      (node (ref "U2") (pin "17") (pinfunction "PA3") (pintype "bidirectional")))
    (net (code "29") (name "unconnected-(U2-PA4-Pad20)") (class "Default")
      (node (ref "U2") (pin "20") (pinfunction "PA4") (pintype "bidirectional")))
    (net (code "30") (name "unconnected-(U2-PA5-Pad21)") (class "Default")
      (node (ref "U2") (pin "21") (pinfunction "PA5") (pintype "bidirectional")))
    (net (code "31") (name "unconnected-(U2-PA7-Pad23)") (class "Default")
      (node (ref "U2") (pin "23") (pinfunction "PA7") (pintype "bidirectional")))
    (net (code "32") (name "unconnected-(U2-PA8-Pad41)") (class "Default")
      (node (ref "U2") (pin "41") (pinfunction "PA8") (pintype "bidirectional")))
    (net (code "33") (name "unconnected-(U2-PA9-Pad42)") (class "Default")
      (node (ref "U2") (pin "42") (pinfunction "PA9") (pintype "bidirectional")))
    (net (code "34") (name "unconnected-(U2-PA10-Pad43)") (class "Default")
      (node (ref "U2") (pin "43") (pinfunction "PA10") (pintype "bidirectional")))
    (net (code "35") (name "unconnected-(U2-PA11-Pad44)") (class "Default")
      (node (ref "U2") (pin "44") (pinfunction "PA11") (pintype "bidirectional")))
    (net (code "36") (name "unconnected-(U2-PA12-Pad45)") (class "Default")
      (node (ref "U2") (pin "45") (pinfunction "PA12") (pintype "bidirectional")))
    (net (code "37") (name "unconnected-(U2-PA15-Pad50)") (class "Default")
      (node (ref "U2") (pin "50") (pinfunction "PA15") (pintype "bidirectional")))
    (net (code "38") (name "unconnected-(U2-PB0-Pad26)") (class "Default")
      (node (ref "U2") (pin "26") (pinfunction "PB0") (pintype "bidirectional")))
    (net (code "39") (name "unconnected-(U2-PB1-Pad27)") (class "Default")
      (node (ref "U2") (pin "27") (pinfunction "PB1") (pintype "bidirectional")))
    (net (code "40") (name "unconnected-(U2-PB2-Pad28)") (class "Default")
      (node (ref "U2") (pin "28") (pinfunction "PB2") (pintype "bidirectional")))
    (net (code "41") (name "unconnected-(U2-PB4-Pad56)") (class "Default")
      (node (ref "U2") (pin "56") (pinfunction "PB4") (pintype "bidirectional")))
    (net (code "42") (name "unconnected-(U2-PB6-Pad58)") (class "Default")
      (node (ref "U2") (pin "58") (pinfunction "PB6") (pintype "bidirectional")))
    (net (code "43") (name "unconnected-(U2-PB10-Pad29)") (class "Default")
      (node (ref "U2") (pin "29") (pinfunction "PB10") (pintype "bidirectional")))
    (net (code "44") (name "unconnected-(U2-PB11-Pad30)") (class "Default")
      (node (ref "U2") (pin "30") (pinfunction "PB11") (pintype "bidirectional")))
    (net (code "45") (name "unconnected-(U2-PB15-Pad36)") (class "Default")
      (node (ref "U2") (pin "36") (pinfunction "PB15") (pintype "bidirectional")))
    (net (code "46") (name "unconnected-(U2-PC0-Pad8)") (class "Default")
      (node (ref "U2") (pin "8") (pinfunction "PC0") (pintype "bidirectional")))
    (net (code "47") (name "unconnected-(U2-PC1-Pad9)") (class "Default")
      (node (ref "U2") (pin "9") (pinfunction "PC1") (pintype "bidirectional")))
    (net (code "48") (name "unconnected-(U2-PC2-Pad10)") (class "Default")
      (node (ref "U2") (pin "10") (pinfunction "PC2") (pintype "bidirectional")))
    (net (code "49") (name "unconnected-(U2-PC3-Pad11)") (class "Default")
      (node (ref "U2") (pin "11") (pinfunction "PC3") (pintype "bidirectional")))
    (net (code "50") (name "unconnected-(U2-PC4-Pad24)") (class "Default")
      (node (ref "U2") (pin "24") (pinfunction "PC4") (pintype "bidirectional")))
    (net (code "51") (name "unconnected-(U2-PC5-Pad25)") (class "Default")
      (node (ref "U2") (pin "25") (pinfunction "PC5") (pintype "bidirectional")))
    (net (code "52") (name "unconnected-(U2-PC6-Pad37)") (class "Default")
      (node (ref "U2") (pin "37") (pinfunction "PC6") (pintype "bidirectional")))
    (net (code "53") (name "unconnected-(U2-PC7-Pad38)") (class "Default")
      (node (ref "U2") (pin "38") (pinfunction "PC7") (pintype "bidirectional")))
    (net (code "54") (name "unconnected-(U2-PC8-Pad39)") (class "Default")
      (node (ref "U2") (pin "39") (pinfunction "PC8") (pintype "bidirectional")))
    (net (code "55") (name "unconnected-(U2-PC9-Pad40)") (class "Default")
      (node (ref "U2") (pin "40") (pinfunction "PC9") (pintype "bidirectional")))
    (net (code "56") (name "unconnected-(U2-PC10-Pad51)") (class "Default")
      (node (ref "U2") (pin "51") (pinfunction "PC10") (pintype "bidirectional")))
    (net (code "57") (name "unconnected-(U2-PC11-Pad52)") (class "Default")
      (node (ref "U2") (pin "52") (pinfunction "PC11") (pintype "bidirectional")))
    (net (code "58") (name "unconnected-(U2-PC12-Pad53)") (class "Default")
      (node (ref "U2") (pin "53") (pinfunction "PC12") (pintype "bidirectional")))
    (net (code "59") (name "unconnected-(U2-PC13-Pad2)") (class "Default")
      (node (ref "U2") (pin "2") (pinfunction "PC13") (pintype "bidirectional")))
    (net (code "60") (name "unconnected-(U2-PC14-Pad3)") (class "Default")
      (node (ref "U2") (pin "3") (pinfunction "PC14") (pintype "bidirectional")))
    (net (code "61") (name "unconnected-(U2-PC15-Pad4)") (class "Default")
      (node (ref "U2") (pin "4") (pinfunction "PC15") (pintype "bidirectional")))
    (net (code "62") (name "unconnected-(U2-PD2-Pad54)") (class "Default")
      (node (ref "U2") (pin "54") (pinfunction "PD2") (pintype "bidirectional")))
    (net (code "63") (name "unconnected-(U2-PH0-Pad5)") (class "Default")
      (node (ref "U2") (pin "5") (pinfunction "PH0") (pintype "input")))
    (net (code "64") (name "unconnected-(U2-PH1-Pad6)") (class "Default")
      (node (ref "U2") (pin "6") (pinfunction "PH1") (pintype "input")))
    (net (code "65") (name "unconnected-(U2-VBAT-Pad1)") (class "Default")
      (node (ref "U2") (pin "1") (pinfunction "VBAT") (pintype "power_in+no_connect")))
    (net (code "66") (name "unconnected-(U4-N.C.-Pad7)") (class "Default")
      (node (ref "U4") (pin "7") (pinfunction "N.C.") (pintype "no_connect")))))
````

#### SPICE deck: `PCB.cir`

````
.title KiCad schematic


C9 VCC 0 4.7u
C1 VCC 0 4.7u
R10 VCC NRST 10k
R8 TSC_G2_IO2 Net-_A2-BTN_ 1k
C14 0 TSC_G2_IO4 22n
C5 VCC 0 100n
C4 VCC 0 100n
C6 VCC 0 100n
C2 VCC 0 100n
C3 VCC 0 100n
C8 VCC 0 100n
R1 NFC_SDA VCC 10k
R2 NFC_SCL VCC 10k
R3 NFC_INT VCC 10k
R4 DISP_RES VCC 10k
R6 DISP_SCL VCC 10k
R7 DISP_SDA VCC 10k
C13 Net-_U4-C2N_ Net-_U4-C2P_ 1u
C12 Net-_U4-C1N_ Net-_U4-C1P_ 1u
C11 Net-_U4-VCOMH_ 0 4.7u
C7 Net-_U4-VCC_ 0 2.2u
C19 0 Net-_U4-IREF_ 100n
C17 VCC 0 1u
C10 VCC 0 1u


V_VCC VCC 0 DC 3.3


.control
tran 1m 10m
set filetype=ascii
write PCB_raw.raw all
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
