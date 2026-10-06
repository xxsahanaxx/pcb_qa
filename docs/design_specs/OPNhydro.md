# OPNhydro — ESP32-C6 Hydroponics Controller: Design Specification

*Derived independently from `OPNhydro_r2` schematic/netlist/BOM, `OPNhydro_r1` BOM/schematic, the top-level `README.md`, TF-Luna datasheets, and `esphome/hydroponics-controller.yaml`. The human-written files `hardware/ARCHITECTURE.md`, `SCHEMATIC_DESIGN.md`, `BOARD_LAYOUT.md`, and `PUMPS.md` were deliberately not consulted.*

## 1. TL;DR

OPNhydro is an ESP32-C6-based controller for an NFT (Nutrient Film Technique) hydroponics system (20–80 plants, per `README.md`'s Hardware Overview table). Per the README's own feature list, it automates:

- **Water quality control**: pH and EC/TDS closed-loop dosing against user setpoints (pH target 6.0 ± 0.3, EC target 1500 ± 200 µS/cm), using Atlas Scientific EZO-pH, EZO-EC, and EZO-RTD (temperature) circuits.
- **Automatic Top-Off (ATO)**: water-level sensing with a user-approval gate before filling, plus float-switch interlocks for low-level pump cutoff and high-level overflow protection.
- **Environmental monitoring**: air temperature/humidity (BME280) and light intensity/PPFD (BH1750), used to compute VPD.
- **Standalone operation**: local pH/EC control logic continues to run without Home Assistant.

**Main hardware decisions confirmed by the r2 netlist/BOM** (not from narrative docs):
- A single ESP32-C6-DevKitC-1-N8 (M1) is the sole controller, docked onto the custom PCB via two card-edge/header rows (`J1`, `J3` in the netlist).
- Two Atlas Scientific EZO circuits (pH, EC) each sit behind a dedicated 2.5 kV galvanically-isolated I2C bridge (ADM3260, U3/U4); the EZO-RTD (M4) does not — it shares the main, non-isolated I2C bus. This is a direct schematic observation; the EZO/Atlas datasheets confirm ADM3260 is a 2-channel isolated-I2C IC but do not themselves explain *why* RTD was left unisolated — **Inferred**: RTD/PT-1000 signals are less susceptible to the ground-loop/noise issues that motivate isolating the two wet-chemistry (pH, EC) probes, which sit in the nutrient solution and can couple PE/earth paths through the liquid.
- Nutrient/pH-Down dosing is implemented with three TMC2209 stepper-motor driver ICs (U5, U6, U7) rather than simple on/off MOSFET pump drivers, each with its own current-sense resistors and a shared single-wire UART bus (`STEP_BUS`). This is new in r2 (see §5) and is not reflected in the top-level README's actuator table, which still describes dosing pumps generically as "GPIO → MOSFET."
- A Benewake TF-Luna LiDAR module (PR1) is present in the r2 schematic/BOM with datasheets for both standard and underwater variants, but — per the netlist — its pins are "free" and it is marked `on_board: no` / excluded from the board; it is not wired into any net. The water-level sensing that is actually wired and actually used by firmware is an HC-SR04-style ultrasonic sensor read on two ESP32 GPIOs (see §4).

## 2. Component Table

| Part | Selected | Reason |
|---|---|---|
| M1 — ESP32-C6-DevKitC-1-N8 | MCU | README's Hardware Overview table states "WiFi 6, Thread, USB-C" as the selection criteria; no further rationale is given in-repo. |
| M2 — Atlas Scientific EZO-pH | pH sensor interface | README Sensor Suite table: "Water pH monitoring," I2C interface. |
| M3 — Atlas Scientific EZO-EC | EC/TDS sensor interface | README: "Nutrient concentration (EC/TDS)," I2C. |
| M4 — Atlas Scientific EZO-RTD | Temperature sensor interface (PT-1000 probe, PR4/PB4) | README: "Water temperature (PT-1000 probe)." |
| U3, U4 — ADM3260 (Analog Devices) | 2.5 kV isolated dual-channel I2C bridge, one per EZO-pH and EZO-EC | Netlist shows each EZO circuit (M2, M3) wired to its own isolated-domain I2C pair (`/SDA_pH`/`/SCL_pH` via U3; `/SDA_EC`/`/SCL_EC` via U4), each with a dedicated isolated supply (`/V_pH`, `/V_EC`) and isolated ground (`/GNDISO_pH`, `/GNDISO_EC`). **Inferred**: used to break ground loops between the ESP32/digital domain and the wet pH/EC probes; no in-repo text states this rationale explicitly. |
| U5, U6, U7 — TMC2209 (28-VFQFN, stallGuard) | Stepper-motor drivers for the pH-Down, Nutrient-A, and Nutrient-B peristaltic pumps | Netlist: each drives a 2-phase coil output (`/A_xx+/-`, `/B_xx+/-`) to connectors H7/H8/H9, with its own current-sense resistor pair (R30–R35, 110 mΩ) and a shared single-wire UART (`STEP_BUS`) plus individual STEP lines. The BOM/footprint explicitly names the "stallGuard" feature. **Inferred**: stallGuard-capable drivers suggest an intent to detect pump stall/jam (e.g., tubing blockage) via back-EMF sensing, but no code or note in this repo exercises that feature — the ESPHome YAML drives these pumps as plain GPIO on/off switches (see §4), not via UART/TMC2209 register control. |
| U1 — TPS62933 (TI) | 24 V → 5 V synchronous buck regulator, 3 A | Netlist: BST/RT/SS/FB pin names match the TPS62933 application circuit; SW node feeds inductor L1 into the board's main `+5V` rail, which powers the ESP32 DevKit's 5V0 pin and the downstream LDO. |
| U2 — AZ1117-3.3 (Diodes Inc.) | 5 V → 3.3 V LDO, 1 A | Netlist: VI tied to `+5V`, VO feeds `+3V3`, which powers the I2C pull-ups, isolator primary sides, and TMC2209 logic (`VCC_IO`). |
| T2 — IRLR2905 (DPAK N-MOSFET) | Main circulation-pump low-side switch | Netlist: drives `PUMP_MAIN` net to the 24 V main pump load; gate driven through R1 (100 Ω) from the ESP32 pin, pre-driven via T1 (BT3904 NPN level shifter). |
| T3 — AON6407 (8-DFN N-MOSFET) | ATO solenoid-valve low-side switch | Netlist: drives `ATO_VALVE` net; gate driven through R10 (100 Ω), pre-driven via T4 (BT3904). |
| D2 — SMBJ28A TVS | Input surge/overvoltage protection on the 24 V rail | BOM footprint/value ("28V," DO-214AA TVS) matches a 24 V-rail clamp; README states the board has "TVS diodes" among its protection features. |
| F1 — 7 A resettable/fuse element (NANO 451) | Input overcurrent protection | README states the PCB includes "reverse polarity protection, TVS diodes, proper isolation"; F1 sits on the 24 V input path per the netlist (`/+24V_FB` net). |
| D1, D4 — SS34 Schottky | Flyback/reverse-current protection across inductive loads (pump/valve) | Standard Schottky flyback placement inferred from net adjacency to `PUMP_MAIN`/`ATO_VALVE`-driven loads; not explicitly annotated in the netlist text. **Inferred**. |

## 3. Power Architecture (from `OPNhydro_r2.cir` and the r2 netlist)

```
24V external supply (V1, "DIGITEN-24V", excluded from board)
   │
   ├─► F1 (fuse) ─► D2 (TVS clamp) ─► /+24V_FB  ──► +24V bulk rail
   │                                                 (C6 1000µF, C9 47µF,
   │                                                  C2/C58/C59/C60 220µF
   │                                                  distributed near loads)
   │
   ├─► +24V rail directly powers:
   │     • Main circulation pump (via T2/T1 switch, PUMP_MAIN net)
   │     • ATO solenoid valve (via T3/T4 switch, ATO_VALVE net)
   │     • TMC2209 motor-supply pins (U5/U6/U7 pin "VS") for the 3
   │       stepper-driven dosing pumps
   │     • U1 (TPS62933) buck input (VIN)
   │
   ├─► U1 TPS62933 bucks +24V → +5V (SW→L1→+5V, feedback via R13/R14/R15,
   │    BST cap C12, soft-start cap C10, as named by the /BST_BK, /RT_BK,
   │    /SS_BK, /0V8_BK nets) ─► +5V rail
   │       • Powers ESP32-C6 DevKit (5V0 pin)
   │       • Feeds U2 (AZ1117-3.3 LDO)
   │
   └─► U2 AZ1117-3.3 LDO: +5V → +3V3 ─► +3V3 rail
          • I2C pull-ups (R3, R4, 2.2 kΩ) for the main (non-isolated) I2C bus
          • Primary (non-isolated) side of U3/U4 ADM3260 isolators
          • TMC2209 logic supply (VCC_IO on U5/U6/U7)

Each TMC2209 (U5/U6/U7) also has an internal 5V linear regulator output
("5VOUT") that is NOT tied to the board's main +5V rail — it is used
locally to bias each driver's own current-reference divider
(/5V_pH, /5V_NA, /5V_NB nets feeding VREF-setting resistors R24–R29),
i.e. a per-driver reference rail, not a shared supply.

Each isolated EZO channel (U3 for pH, U4 for EC) derives its own isolated
+5V (/V_pH, /V_EC) and isolated ground (/GNDISO_pH, /GNDISO_EC) internally
from the ADM3260's isoPower feature, galvanically separate from the main
+3V3/+5V/+24V domains.
```

The `.cir` SPICE netlist confirms the same topology by component value (e.g. `C6 +24V GND 1000μ`, `U1`/`U2` value fields, `R3/R4 I2C_SDA/I2C_SCL +3V3 2.2k` pull-ups), and lists an external DC source `V1 ... DC DIGITEN-24V` as the board's 24 V supply, matching the BOM's `V1` entry (value "DIGITEN-24V", excluded from board).

## 4. Sensor-Interface Section

### 4.1 Main (non-isolated) I2C bus
Netlist: ESP32-C6 pin `IO4/I2C_SDA` → `I2C_SDA` net; pin `IO5/I2C_SCL` → `I2C_SCL` net, each pulled up to `+3V3` via 2.2 kΩ resistors (R3, R4). This bus fans out to:
- M4 (EZO-RTD) — directly, unisolated.
- H5, H6 (4-pin JST-PH headers) — each breaks out `+3V3`, `GND`, `I2C_SCL`, `I2C_SDA`. These are the wired connection points for the environmental sensors (BME280, BH1750) that the firmware expects (see below), and/or H1 (6-pin PicoBlade, also carrying `+5V`/`GND`/`I2C_SCL`/`I2C_SDA`).
- Primary (non-isolated) side of U3 and U4 (ADM3260 isolators), which bridge through to the isolated pH/EC domains.

### 4.2 Isolated pH/EC channels
U3 (pH) and U4 (EC) each present a secondary isolated I2C pair (`/SDA_pH`/`/SCL_pH`, `/SDA_EC`/`/SCL_EC`) that connects directly to M2 (EZO-pH) and M3 (EZO-EC) respectively, each with its own isolated supply/ground domain generated on-chip. An `EZO_PDIS` net ties both U3 pin 8 and U4 pin 8 (PDIS = power-disable) to a single ESP32 pin (`IO6/SPI_CLK`), i.e. firmware can power down both isolators from one GPIO.

### 4.3 TF-Luna LiDAR (PR1) — present in schematic but not wired
The BOM/datasheets folder lists both a standard and an "underwater" TF-Luna variant (Benewake, 5V UART/I2C interface, used for distance ranging). Its presence alongside ATO/water-level logic in the README (and the "underwater" variant specifically) supports the inference that it was intended for **reservoir level sensing** — a LiDAR rangefinder mounted above the tank, measuring distance to the water surface. However, the r2 netlist shows PR1 with `on_board: no`, `in_bom: yes`, and all four pins (`VCC`, `SDA`, `SCL`, `GND`) typed `free` — i.e., it is not connected to any net in this design. It also does not appear anywhere in `esphome/hydroponics-controller.yaml` (no `uart:` bus, no distance/TF-Luna sensor block). **This sensor is documented in the schematic/BOM but not implemented in either the r2 PCB wiring or the current firmware.**

### 4.4 Water level — what is actually wired and used
The firmware (`hydroponics-controller.yaml`) defines an `ultrasonic` platform sensor ("Water Level Distance") on `trigger_pin: GPIO4`, `echo_pin: GPIO5`, consistent with the README's Sensor Suite entry "HC-SR04 | GPIO | Water level (ultrasonic)." Two float switches are read as `binary_sensor` GPIO inputs (`GPIO11` "Water Level Low", `GPIO12` "Water Level High"), matching the README's float-switch safety feature and the netlist's `FLOAT_LOW`/`FLOAT_HIGH` nets (with 10 kΩ/4.7 kΩ pull resistors visible in the `.cir` file: `R6 FLOAT_LOW +3V3 10k`, `R9 GND FLOAT_HIGH 10k`, `R2 FLOAT_LOW /BPUMP 4.7k`, `R11 FLOAT_HIGH /BATO 4.7k`).

**Cross-check finding (directly observed, not resolved in-repo):** the ESP32-C6 pin numbers used in the firmware do not match the pin functions wired in the r2 netlist for *any* of the actuator/sensor nets checked:

| Net (schematic) | Schematic pin | Firmware GPIO (YAML) | Firmware's stated use |
|---|---|---|---|
| `I2C_SDA` / `I2C_SCL` | IO4 / IO5 | GPIO1 / GPIO2 | `i2c: sda/scl` |
| `FLOAT_LOW` / `FLOAT_HIGH` | IO0 / IO1 | GPIO11 / GPIO12 | float-switch binary sensors |
| `PUMP_MAIN` | IO10 | GPIO6 | main pump switch |
| `STEP_NUT_A` | IO15 | GPIO9 | "Pump Nutrient A" switch |
| `STEP_NUT_B` | IO19 | GPIO10 | "Pump Nutrient B" switch |
| `STEP_PH_DN` | IO11 | GPIO21 | "Pump pH Down" switch (comment: "Moved from GPIO8") |
| `ATO_VALVE` | IO2 | GPIO20 | ATO valve switch |
| `STEP_BUS` (shared UART) | IO21/IO22 | *(no `uart:` bus declared)* | n/a — pumps driven as plain GPIO on/off, not via TMC2209 UART registers |
| *(no net found)* | — | GPIO3 | `one_wire:` bus (no DS18B20 net exists in the r2 schematic) |

No note, comment, or revision history in either file explains this mismatch; it is reported here as an observed discrepancy between the firmware's declared pin map and the r2 schematic's actual wiring, not as a resolved fact about which is correct.

### 4.5 Environmental sensors — DNP in r2
The r2 BOM marks `PR5` ("LIGHT", BH1750) and `PR6` ("BME280") as **DNP** (Do Not Populate), even though the firmware defines working `bme280_i2c` and `bh1750` sensor blocks (air temp/humidity, lux, and a derived VPD/PPFD calculation) and the board has I2C headers (H5/H6) available to wire them. This is a direct observation from the BOM; no note in the BOM or schematic explains why these were left unpopulated in r2.

## 5. r1 → r2 Revision Differences (directly observed from BOM/schematic comparison)

- **Dosing-pump actuation changed**: r1's BOM lists general-purpose switching transistors only (`T1` SI2301 P-MOSFET, `T2`/`T6` BT3904, `T3`/`T5`/`T7`/`T8` AO3400A ×4, `T4` IRLR2905) and no stepper-driver ICs. r2 drops to a smaller discrete-switch set (`T1`/`T4` BT3904 ×2, `T2` IRLR2905, `T3` AON6407, `T5` AO3400A ×1) and adds **three TMC2209 stepper-motor-driver ICs** (`U5`, `U6`, `U7`) with associated current-sense resistors (`R30`–`R35`, 110 mΩ) and stepper connectors (`H7`, `H8`, `H9`, JST-XH 4-pin). No note in either revision's files states the reason for this change.
- **Isolator reference numbering shifted but count unchanged**: r1 uses `U2`/`U3` for the two ADM3260 isolators; r2 uses `U3`/`U4` (r2's `U1`/`U2` are now the TPS62933 buck and AZ1117 LDO). Both revisions use exactly 2× ADM3260.
- **Explicit pump/probe BOM line items added in r2**: r1's BOM has no `PUMP*` or `PR*` (probe) reference entries at all. r2's BOM adds `PUMP1` (DC40F-2460, 24V brushless main pump), `PUMP2`/`PUMP3`/`PUMP4` (ANKO_A200SX peristaltic pumps, ×3 — consistent with 3 TMC2209 drivers for pH-Down/Nutrient-A/Nutrient-B), and `PR1`–`PR6` (LiDAR, pH probe, EC probe, RTD probe, LIGHT [DNP], BME280 [DNP]), all marked "Excluded from Board."
- **External power-source placeholder renamed**: r1's BOM has a generic `V1` labeled "ATO"; r2's `V1` is labeled "DIGITEN-24V" — a named 24 V supply part.
- **Connector/part substitutions observed**: r1 uses `H3`/`H4` as 2-pos (`MC_0.2"`) headers; r2's `H3`/`H4` differ in count/position (r2 has `H2` as a single `MSTBA_0.2"` and `H3`/`H4` as `MC_0.2"` pairs) — footprints shifted between revisions but the underlying connector families (JST-PH, JST-XH, Phoenix MC/MSTB terminal blocks, BNC) are consistent across both.
- Both revisions' top-level `README.md` files are byte-identical — the project-level framing/feature list has not changed between r1 and r2.

No stated rationale was found in either revision's BOM, schematic text, or README for *why* the stepper-driver approach was adopted in r2; it is reported here purely as an observed BOM/schematic delta.

## 6. Known Limitations (only items directly evidenced in-repo)

- **TF-Luna LiDAR is unwired**: present in the r2 schematic/BOM with full datasheets (including an underwater variant), but its pins are typed `free`, it is marked `on_board: no`, and it has no corresponding firmware code. It is schematic documentation only, not a built or driven part of this revision.
- **Firmware GPIO map does not match the r2 schematic's wiring** for every actuator/sensor net checked (I2C, float switches, main pump, all three dosing-pump step lines, ATO valve) — see table in §4.4. There is no `uart:` bus or TMC2209 component in the firmware despite the r2 schematic wiring three dosing pumps through TMC2209 drivers on a shared single-wire UART bus; the firmware instead toggles them as plain GPIO switches.
- **Environmental sensors (BME280, BH1750) are DNP in the r2 BOM** even though firmware code exists to read them and I2C headers (H5/H6) are present to wire them in.
- **DS18B20/one-wire reference in firmware has no corresponding hardware net**: the YAML's Quick-Start instructions mention updating a "DS18B20 address" and configure a `one_wire:` bus on GPIO3, but no DS18B20 part or one-wire net appears anywhere in the r2 BOM, schematic, or netlist. Water temperature in this design is read through the EZO-RTD/PT-1000 probe (M4/PR4) instead.
- No in-repo note documents the rationale for isolating pH/EC but not RTD, for the TMC2209 adoption in r2, or for leaving BME280/BH1750/LiDAR unpopulated — these are reported above as direct observations, with any causal explanation explicitly marked "Inferred" rather than stated as fact.
