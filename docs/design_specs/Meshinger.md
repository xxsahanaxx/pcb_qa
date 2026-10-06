# Meshinger — Design Specification

Source: `OSHP_files/Clean/Meshinger` (KiCad project `Meshinger/Meshinger.kicad_pro`, submodule history `174a142` … `af0d263`).

## 1. TL;DR

Meshinger is a handheld mesh-messenger built around a **SKYLAB SKW92A** 802.11b/g/n 2×2 MIMO WiFi AP/Router module (MediaTek MT7628N, 580 MHz MIPS CPU, DDR2, SPI flash — confirmed in `SKW92A files/SkyLab_SKW92A_V1.04_datasheet.pdf`), driving a reflective **e-paper display** through a dedicated boost/charge-pump driver circuit, with a physical **BBQ10KBD**-style QWERTY keyboard matrix, and powered from a single **18650 Li-ion cell** (`CAD/18650_Refrence_Cell.stl`, Keystone 1043 TH battery holder in the netlist) or USB/DC-barrel input. The top sheet `Meshinger.kicad_sch` instantiates exactly three hierarchical sheets: `SkylabModule.kicad_sch`, `EthernetAndPower.kicad_sch`, and `EPD_Driver.kicad_sch`.

The repository filename `SKW92A files/SKYLAB-uptate_firmware_openwrt.pdf` directly evidences OpenWRT-class firmware support for this module, so the TL;DR's "WiFi/OpenWRT-capable module" characterization is directly sourced. However, **the rationale for choosing a Linux/OpenWRT-capable WiFi SoC module over a bare MCU for this project is not stated anywhere in the repo** (no design notes, README, or schematic comment makes this tradeoff explicit) — that specific design decision is **Inferred** only, based on the fact that a full WAN/LAN WiFi router SoC is a very unusual and powerful choice for a simple messenger unless mesh/Linux networking stack and 5-port Ethernet switch capability were specifically wanted.

## 2. Component Table

| Ref | Part | Role | Evidence |
|---|---|---|---|
| U5 | SKYLAB SKW92A (`SKW92A:SKW92A`) | Main compute / WiFi radio / 5-port Ethernet switch | `SkylabModule.kicad_sch`; datasheet confirms MT7628N, 802.11b/g/n, 1 WAN + 4 LAN 10/100 ports, I2C/SD/SPI-slave/UART/GPIO interfaces, requires external 3.3 V |
| J1 | FH34SRJ-24S-0.5SH(99) 24-pin 0.5 mm FPC connector | EPD panel interface | `EPD_Driver.kicad_sch`; matches PDI reference doc's specified "HRS FH34SRJ 24S" golden-finger connector exactly |
| Q1 | MCH3478-TL-W (N-channel MOSFET, SOT-23, 30 V/2 A) | EPD boost-converter switch | `EPD_Driver.kicad_sch`; exact part named in PDI `EPD-driving-circuit-of-Pervasive-Displays-rev.01.pdf` BOM (item 8) |
| U1/U2/U3 | SS2040FL Schottky diodes (SOD-123FL) | EPD charge-pump/multiplier rectifiers | `EPD_Driver.kicad_sch`; PDI doc specifies 3× SS2040FL diodes for this exact circuit |
| L1 | 10 µH inductor | EPD boost-converter inductor | `EPD_Driver.kicad_sch`; matches PDI "G1 group" default (10 µH) for small panel sizes |
| R1 | 0.47 Ω current-sense resistor | EPD booster current-limit sense | `EPD_Driver.kicad_sch`; matches PDI "G1, G2" default (0.47 Ω) |
| Q2 | NTR2101P (P-channel MOSFET, SOT-23, −3.7 A/−8 V) | High-side load switch for EPD VDD/VDDIO rail ("Display Power MOSFET") | `SkylabModule.kicad_sch`; BOM row explicitly describes it as "P-Channel MOSFET"; commit `b3a898a` "Display Power MOSFET heats up while off..." names this exact function |
| U4 | Keyboard:BBQ10KBD (24/28-pad FPC footprint `BM14B(0.8)-24DS-0.4V(53)`) | Physical QWERTY keyboard interface | `SkylabModule.kicad_sch`; netlist shows 5 column + 7 row lines wired directly to SKW92A GPIO pins (matrix scanned by the module itself, not via an onboard keyboard controller) |
| IC1 | FAN53610AUC33X (fixed 3.3 V, 1 A synchronous buck) | Main 3.3 V rail regulator | `EthernetAndPower.kicad_sch`; `3rdparty/FAN53610-D-1805279.pdf` |
| L2 | LQM2MPN1R0MGHL (1.0 µH) | Buck regulator output inductor | `EthernetAndPower.kicad_sch`; matches FAN53610 datasheet Table 2 recommended part ("utilized to generate graphs" in the datasheet itself) |
| U7 | Keystone 1043 (18650 TH battery holder) | Single-cell Li-ion battery holder | SamacSys lib description: "BATTERY HOLDER, 18650, TH"; corroborated by `CAD/18650_Refrence_Cell.stl` |
| S1 | TE Connectivity 1825232-1 (SPDT slide switch) | — wired as **HW_RESET** switch, not a power switch (see §3) | SamacSys lib description: "SLIDE SWITCH, SPDT"; netlist: pin1→GND, pin2→`HW_RESET` (SKW92A pin 45) |
| J4 | SamacSys PJ-079BH, value `Barrel_Jack_Switch` | DC power jack with integrated switch contact — battery disconnect when adapter is plugged in | `EthernetAndPower.kicad_sch`; see §3 |
| U6 | SS2040FL (Schottky diode) | Battery-feed isolation diode | netlist: anode on battery (via U7), cathode on `BAT+` |
| J5 | RJ45 Amphenol RJMG1BD3B8K1ANR | Ethernet jack | `EthernetAndPower.kicad_sch` — see open item in §3 |
| J3 | USB_A | USB power/data | `EthernetAndPower.kicad_sch` |
| J7 | Conn_01x03 | Debug UART header | netlist: pin1→GND, pin2→`UART_TX` (SKW92A pin 26), pin3→`UART_RX` (SKW92A pin 25) |
| J2 | Micro_SD_Card | microSD storage | `SkylabModule.kicad_sch`; wired to SKW92A's shared SD_CLK/CMD/D0–D3 pins (21/22/16/15/24/23), matching the datasheet's SD pin-share table exactly |

## 3. Power Section — `EthernetAndPower.kicad_sch`

**Input sources, all summed onto the `BAT+` net:**
- **Battery (U7, 18650 holder)** → pin 1 → `Net-(U6-A)` → **U6 (SS2040FL) anode→cathode** → `BAT+`. The battery is the only source routed through a series diode; USB (`J3.1`, VBUS) and the DC barrel jack (`J4.1`, center pin) tie directly onto `BAT+` with no diode. **Inferred:** the diode's evident function is to prevent USB/adapter 5 V from back-feeding current into the raw, uncontrolled 18650 cell when both are present — this is standard diode-OR practice, but the repo does not state this reasoning explicitly.
- **DC barrel jack (J4, "Barrel_Jack_Switch")**: a schematic text note in `EthernetAndPower.kicad_sch` directly states *"2 and 3 are shorted with no plug / 1 is center, center is positive."* Netlist: `J4.1→BAT+` (center/positive), `J4.2→GND` (sleeve), `J4.3→BAT-`. Since pins 2 and 3 are normally shorted (per the note) and `BAT-` only otherwise reaches `U7.2` (battery negative) and `J6.1`, this means the jack's internal switch keeps the battery's return path connected to `GND` by default, and inserting a DC plug breaks that short — disconnecting the battery. This directly explains the commit history: `a1d9676` *"Meshinger 1.0 rev B WARNING THE DC PLUG PINS ARE WRONG, SHORTS BATTERY!"* followed by `af0d263` *"Meshinger 1.0 rev D, now with power switch and squiggles"* — the "power switch" referred to in that commit is this jack's internal battery-disconnect contact, not S1.
- **S1 (SPDT slide switch)** is, per the netlist, wired as a **reset** button (`S1.1→GND`, `S1.2→HW_RESET`→SKW92A pin 45 `HW_RESET`), not an on/off power switch, despite its physical form factor.

**Regulation (IC1, FAN53610AUC33X):**
- `VIN` (pins A2/B2) → `BAT+`. The B2 pin is the part's `EN` pin per the FAN53610 datasheet pinout table, and it is tied to the same `BAT+` node as `VIN` — i.e. **EN is hard-wired to VIN**, so the regulator is always enabled whenever input power is present.
- `MODE` (pin A1) → `GND` — per the datasheet, Logic 0 on MODE allows the IC to auto-switch into PFM (power-save) mode under light load, i.e. the board is configured for Auto PFM/PWM operation.
- `SW` (pin B1) → **L2 (1.0 µH, Murata LQM2MPN1R0MGHL)** → `+3V3` output rail.
- `FB` (pin C1) → `+3V3` directly (fixed-output part; this is the standard connection for a fixed-voltage FAN53610 variant).
- `C12` (2.2 µF) on `BAT+`→GND is the input cap; `C13` (10 µF) on `+3V3`→GND is the output cap — these exactly match the FAN53610 datasheet's recommended 2.2 µF `CIN` / 10 µF `COUT` values, and L2's 1.0 µH value matches the datasheet's "Utilized to generate graphs" recommended inductor. This is a close-to-reference-design implementation of the FAN53610 typical application circuit (Figure 1 of the datasheet).

**`+3V3` rail destinations:** SKW92A module power pins (`U5.28`, `U5.29` — matching the datasheet's two dedicated `3.3VD` pins), keyboard `U4.2`, microSD `J2.4`, the gate pull-up `R2` (10 kΩ, pulling Q2's gate high/off by default), and the EPD power-switch MOSFET `Q2`'s source.

**Open item (directly observed, not interpreted):** the RJ45 jack `J5`'s data pads (TD+/TD-/RD+/RD-, center-taps, shield) all appear in the netlist as individually unconnected (`unconnected-(J5-...)`), while the `LAN1_RX+/-`, `LAN1_TX+/-` global labels used elsewhere resolve to single-node nets containing only `U5` (SKW92A) pins. In this netlist export, the Ethernet jack is not wired to the SKW92A's Ethernet PHY nets. Whether this is a routing gap in this revision or an artifact of the export was not possible to determine from the files examined.

## 4. Display-Interface Section — `EPD_Driver.kicad_sch` vs. the Pervasive Displays Reference

The `EPD_Driver.kicad_sch` sheet is a near-exact implementation of the circuit in `3rdparty/EPD-driving-circuit-of-Pervasive-Displays-rev.01.pdf` ("EPD Driving Circuit", Rev. 01, Dec 2020):

| PDI reference circuit | Meshinger schematic | Match |
|---|---|---|
| 24-pin, 0.5 mm FPC, "HRS FH34SRJ 24S" | J1 = `FH34SRJ-24S-0.5SH(99)` | Exact part |
| Boost MOSFET: "MCH3478 SOT-23 N-Channel 30V/2A ON-Semi" | Q1 = `MCH3478-TL-W` | Exact part |
| Diode: "SS2040FL SOD-123FL", qty 3 | U1, U2, U3 = `SS2040FL` ×3 | Exact part, exact quantity |
| L1 default (G1/G2 group): 10 µH | L1 = 10 µH | Matches G1 default |
| R1 default (G1/G2 group): 0.47 Ω | R1 = 0.47 Ω | Matches G1 default |
| C1 (G1 group only): 1 µF/6.3 V | C2 = 1 µF/6.3 V | Matches G1-specific value |
| C2 default: 1 µF/25 V | C1/C5/C7/C8/C9/C10 = 1 µF/25 V | Matches default |

Since the "G1" EPD group in the PDI doc covers the 1.54", 2.13", 2.66", 2.71", 2.87", and 2.90" panel sizes, and the component values here match the **G1-specific** 1 µF/6.3 V option rather than the G2/G3 default, this is consistent with the CAD files `Waveshare213rev.gltf` / `"Waveshare 2.13 (D) E-ink - Reverse Mount.stp"` — i.e. the panel is a **Waveshare 2.13" e-paper display**, directly evidenced by those filenames.

**Signal mapping** (netlist, `J1` pin → function per PDI's 24-pin table, cross-checked against SKW92A datasheet pins):
- `J1.9` (BUSY_N) ↔ `EINK_DISPLAY_BUSY` ↔ `U5.43`
- `J1.10` (RST_N) ↔ `EINK_DISPLAY_RESET` ↔ `U5.44`
- `J1.11` (DC) ↔ `EINK_DATA_COMMAND` ↔ `U5.42`
- `J1.12` (CSB) ↔ `EINK_CHIP_SELECT` ↔ `U5.41`
- `J1.13` (SCL) ↔ `SPI_CLK` ↔ `U5.11`
- `J1.14` (SDA) ↔ `SPI_MOSI` ↔ `U5.12`

**Flagged inconsistency (Inferred):** the net labels `SPI_CLK`/`SPI_MOSI` suggest the module's hardware SPI peripheral, but per the SKW92A datasheet's own pin-share tables, module pins 11/12 are documented as `UART2_TXD/PWM_CH2/SD_D5` and `UART2_RXD/PWM_CH3/SD_D4` respectively — **not** among the module's dedicated SPI-slave pins (which the datasheet lists as pins 5–8). This suggests the EPD's SPI-style command interface is most likely bit-banged over general-purpose GPIO rather than driven by SKW92A's native SPI-slave hardware block, but the repo does not document this choice explicitly, so it is marked Inferred.

**Display power-switch / leakage prevention:** The PDI reference diagram carries the annotations *"Connect to Power Switch"* and *"Connect to a Transistor Switch to prevent leakage current."* In this design that transistor is **Q2** (NTR2101P, P-channel): netlist shows `Net-(Q2-G)` = `Q2.1` (gate), `R2.1`→`R2.2`→`+3V3` (10 kΩ pull-up, gate defaults high/off), and `U5.31` (SKW92A GPIO, datasheet pin 31 = `P4_LED`/`GPIO#39`, repurposed here as a general output). `Q2.2` (source) ties to `+3V3`; `Q2.3` (drain) ties to the `Display_Power_Switch` net, which feeds `J1.15`/`J1.16` — the EPD panel's `VDDIO`/`VDD` pins per the PDI pin table — plus the EPD boost converter's `L1`, `C1`, `C2`. So Q2 is a high-side load switch gating the EPD panel's own power rail under SKW92A GPIO control, matching the PDI doc's stated purpose for that transistor. The commit `b3a898a` *"Meshinger 1.0 rev C, Display Power MOSFET heats up while off..."* documents a known thermal issue with this exact switch in an earlier board revision.

**Boost converter operation:** `Q1`'s gate (`Net-(Q1-G)`) is driven from `J1.2` — the EPD panel's own `GDR` pin ("Power MOSFET driver control" per the PDI pin table) — meaning the EPD COG driver IC itself generates the boost-converter switching signal; Q1's source (`Net-(Q1-S)`) returns through `R1` (0.47 Ω) to GND and also feeds back to `J1.3` (`RESE`, the panel's current-sense/booster-control input), closing the control loop entirely within the EPD module and external power stage — the SKW92A only issues SPI commands and toggles the Q2 power-switch GPIO; it does not directly control the boost converter's switching.

## Summary of Inferred vs. Directly Sourced Claims

**Directly sourced** (schematic/netlist connectivity, datasheets, BOM descriptions, git commit messages, CAD filenames, or an in-schematic text note):
- SKW92A identity and capability (datasheet)
- FAN53610 regulator topology, values, EN/MODE/FB wiring (datasheet + netlist)
- EPD driver circuit component matching to the PDI reference doc, including exact part numbers/quantities and G1-group value selection
- Barrel jack battery-disconnect behavior (explicit schematic text note)
- Q2 as the PDI-recommended "leakage prevention" transistor switch, GPIO-controlled (netlist + BOM + PDI doc + commit log)
- S1 wired as HW_RESET, not a power switch (netlist)
- 18650 single-cell battery power (CAD STL filename + Keystone 1043 lib description)
- Waveshare 2.13" panel identity (CAD filenames + G1-group value match)
- RJ45 data pins unconnected in this netlist (netlist observation)

**Marked Inferred** (plausible but not explicitly stated in the repo):
- Rationale for choosing a Linux/OpenWRT-capable WiFi SoC module over a bare MCU
- Purpose of the battery-isolation diode U6 (standard diode-OR reasoning, not documented)
- Whether SPI_CLK/SPI_MOSI to the EPD are bit-banged GPIO vs. hardware SPI, given the pin-share table mismatch
