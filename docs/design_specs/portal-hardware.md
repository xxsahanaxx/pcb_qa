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
