# HADES Flight Control System — Hardware Design Specification

**Source project:** `OSHP_files/Clean/HadesFCS` (submodule), by Philip Salmony (philsal.co.uk), BSD-3-Clause.
**Scope of this document:** primary board `Hardware/Hades`, with shorter companion sections for `HadesNT`, `HadesMicro` / `HadesMicroJLCPCB`, and `HadesGPSDongle`.

> **Grounding note:** every "why" statement below is either quoted/paraphrased from a project source (README, the author's own hardware presentation PDF, schematic text notes, or `HADES V1 Bugs.txt`) or explicitly marked **Inferred**. Where only the *what* could be confirmed from the schematic/netlist, that is stated as fact without a rationale attached.

---

## 1. TL;DR

HADES is a from-scratch autopilot for **fixed-wing autonomous drones** (take-off, landing, waypoint navigation, payload delivery), built around **FreeRTOS** on **STM32** MCUs with custom **Kalman-filter** state estimation — per the project README (`OSHP_files/Clean/HadesFCS/README.md`).

The flagship `Hades` board implements the architecture laid out in the author's own design deck, `Documentation/HadesHardwarePresentation.pdf` ("Flight Control System Design: Hardware", 9 Dec 2019): a **two-MCU split**,

- **Navigation Computer (NAVC)** — gathers IMU, magnetometer, pressure sensor and GPS receiver data, backed by its own EEPROM;
- **Flight Control Computer (FCC)** — receives the navigation solution from NAVC, drives a PWM servo driver, reads a current/voltage sensor, and owns its own EEPROM + FLASH,

connected by a shared link (confirmed in `Hades.sch`: NAVC↔FCC run UART2 + I2C + GPIO between the two MCUs). The deck's own slide 4 states the hardware requirements driving this design: *"Standard set of sensors (IMU, magnetometer, barometer…), expansion/interface IOs, power distribution for servos, processing power, affordability."* Slide 5's block diagram gives the power envelope: **6 V < Vin < 26 V**, **5 V @ 9 A max**, **3V3 @ 2 A max**, plus connectors for additional sensors/servos/GPS antenna and programming/debug via SWD, USB DFU, and UART-to-USB.

In the as-built schematic, the FCC is populated with an **STM32H753VITx** (Cortex-M7) and the NAVC with an **STM32F405RGTx** (Cortex-M4) — i.e. the "F4 and H7" dual-MCU combination described in `Hardware/README.md`. (The file `STM32F7 PINOUT.PNG` sits in the same folder as a leftover artifact — filename only noted here, not opened — and does not match the F4/H7 parts actually instantiated in `FCC.sch`/`NAVC.sch`.)

---

## 2. Component Table (Hades)

| Function | Reference | Part | Source |
|---|---|---|---|
| Flight Control Computer MCU | FCC1 | STM32H753VITx (Cortex-M7, 400 MHz, 2 MB flash, LQFP-100) | `FCC.sch` / `Hades.net` |
| Navigation Computer MCU | NAVC1 | STM32F405RGTx (Cortex-M4, 168 MHz, 1 MB flash, LQFP-64) | `NAVC.sch` / `Hades.net` |
| IMU (accel + gyro) | NAVCPeripherals | Bosch BMI088, I2C addr 0x19 (acc) / 0x69 (gyr) | `NAVCPeripherals.sch` note "Inertial Measurement Unit (Accelerometer + Gyroscope)" |
| Magnetometer | NAVCPeripherals | ST IIS2MDCTR, I2C addr 0x1E | `NAVCPeripherals.sch` note "Magnetometer" |
| Absolute pressure sensor (barometer) | NAVCPeripherals | Honeywell MPRLS0025PA00001A, I2C addr 0x18 | `NAVCPeripherals.sch` note "Absolute Pressure Sensor" |
| Temperature sensor | NAVCPeripherals | TMP100, I2C addr 0x4E | `NAVCPeripherals.sch` note "Temperature Sensor" |
| GPS receiver | NAVCPeripherals | u-blox MAX-8Q (schematic label) / netlist footprint `MODULE-GPS-SMD-MAX-7Q` (see §3 note) | `NAVCPeripherals.sch`, `Hades.net` |
| NAVC-side EEPROM | NAVCPeripherals | 24CW1280T-I_OT, I2C addr 0x50 | `NAVCPeripherals.sch` note "EEPROM" |
| PWM/servo driver | FCCPeripherals | NXP PCA9685PW (I2C 16-ch PWM), I2C addr 0x40 | `FCCPeripherals.sch` note "PWM Driver" |
| FCC-side FLASH | FCCPeripherals | Winbond W25N01GVZEIG_TR (1 Gb NAND) | `FCCPeripherals.sch` note "FLASH Memory" |
| FCC-side EEPROM | FCCPeripherals | 24CW1280T-I_OT | `FCCPeripherals.sch` note "EEPROM" |
| Current/voltage sensor | Hades (top sheet) | TI INA219AIDCNR, I2C addr 0x40, across R1 = 10 mΩ shunt | `Hades.sch` notes "Voltage/Current/Power Sense IC", "(Vin+ - Vin-)max = 320mV" |
| Main buck regulator (5 V rail) | Hades (top sheet) | Microchip MIC26903YJL-TR | `Hades.sch` — populates the "Power" block; notes "L = 15uH for 5% ripple current", "Vout=0.8*(1+R5/R6)" |
| 3.3 V LDO (MCUs + sensors) | Hades (top sheet) | ST LD39200PU33R | `Hades.sch` note "3.3V 2A Regulator (MCUs and Sensors)" |
| Battery input connector | Hades (top sheet) | XT60-M | `Hades.sch` |
| USB-UART bridges (programming/debug) | Connections | otter_CH330 ×2 | `Connections.sch` note "CH330 UART to USB Converters" |
| ESD/boot-select switch | FCC / NAVC | TDD01H0SB1R (SPDT) | `FCC.sch` note "TDD01H0SB1R = SPDT" |
| HSE crystal (both MCUs) | FCC / NAVC | ABM8G-25.000MHZ-4Y-T3 | `FCC.sch`, `NAVC.sch` notes "High Speed External Crystal" |

Note: `Sensors.sch`, listed among the Hades schematic sheets, is **empty** (no components — confirmed by direct inspection: it contains only the KiCad sheet header, zero symbols). All sensor ICs actually live in `NAVCPeripherals.sch`; `Sensors.sch` appears to be an unused/placeholder sheet rather than the real sensor section.

---

## 3. Hardware Revision History

### Logged bugs (`Hardware/Hades/HADES V1 Bugs.txt`)

The file contains one logged entry:

> *"Barometer reset and EOC pins (and pull-up resistor) mixed up (fixable in software however)"*

This is corroborated directly in the schematic: `NAVCPeripherals.sch` carries an explicit, emphatic annotation right next to the "Absolute Pressure Sensor" (MPRLS0025PA00001A) block:

> *"RESET AND INTERRUPT PINS ARE MIXED UP!!!!!"*

The MPRLS family uses dedicated RESET and EOC (end-of-conversion/interrupt) pins, consistent with this being the barometer referenced in the bug log. The bug was logged as software-workaroundable, so it is not clear from the repo whether a V2 of the Hades board itself (vs. HadesNT) ever corrected the pin assignment — no second revision of `Hardware/Hades/*.sch` exists in the repo to confirm a hardware fix at that board level.

### Confirmed differences vs. `HadesNT` (dated 2020-05-20, ~5 months after the Dec 2019 Hades presentation)

Directly confirmed by comparing `Hades.sch`/`FCC.sch`/`NAVC.sch` against `HadesNT.sch`:

- **MCU count/split:** Hades uses the two-MCU FCC/NAVC architecture (STM32H753VITx + STM32F405RGTx, as hierarchical sheets). HadesNT is a **single flat schematic sheet** (`grep -c '$Sheet'` returns 0 sub-sheets) built around **one** STM32H750VBT6 (Cortex-M7, confirmed via `stm32h750vbt6.pdf` datasheet link embedded in the schematic). The FCC/NAVC split present in Hades does not appear in HadesNT's part list or structure.
- **IMU:** Hades uses discrete BMI088 (accel+gyro) + IIS2MDCTR (magnetometer). HadesNT uses a single combined 9-axis part, **BMX055**.
- **Barometer:** Hades uses Honeywell MPRLS0025PA00001A. HadesNT uses a **BMP280**.
- **Flash:** Hades (FCC side) uses Winbond W25N01GVZEIG_TR (1 Gb NAND). HadesNT uses **W25Q128JVS** (128 Mb NOR).
- **Power stage:** Hades uses a MIC26903YJL-TR buck (5 V) + LD39200PU33R LDO (3V3). HadesNT uses an **MP2451DT-LF-Z** buck regulator and an AO3401A load switch instead.
- **Protection:** HadesNT adds an **SRV05-4** ESD-protection array on the USB port, not present in Hades' `Connections.sch` USB section.
- Both boards keep the same current/voltage sense IC, **INA219AIDCNR**.

Rationale for these specific substitutions (e.g. why BMX055 over the discrete BMI088+IIS2MDCTR pairing, or why STM32H750 over keeping the F4/H7 split) is **not stated anywhere** in the HadesNT files — no text notes exist in `HadesNT.sch` (confirmed: zero `Text Notes` entries, unlike Hades' heavily annotated sheets). **Inferred:** consolidating to a single H7-class MCU and single-package IMU/baro parts plausibly reduces BOM count and board area versus the dual-MCU Hades design, but this is not asserted anywhere in the repo and should be treated as speculation only.

---

## 4. Power Section (traced from `Hades.net` / `Hades.sch`)

Per the block diagram (`HadesHardwarePresentation.pdf`, slide 5) and corroborating schematic notes on the Hades top sheet:

1. **Input:** Battery connects via an **XT60-M** connector. Schematic note: *"Maximum input voltage: 26V"*; combined with the block diagram's stated range this gives the documented **6 V–26 V** input window.
2. **Current/voltage sensing:** Battery current passes through shunt **R1 = 10 mΩ (1 W, 2512 package)**, sensed differentially by **INA219AIDCNR** (I2C addr 0x40). Schematic note: *"(Vin+ - Vin-)max = 320mV"* bounds the sensor's usable current range for that shunt value.
3. **5 V rail:** A **MIC26903YJL-TR** synchronous buck regulator steps the battery input down to 5 V. Design notes on this section: inductor *"L = 15uH for 5% ripple current"*; feedback divider relation *"Vout=0.8*(1+R5/R6)"*; input bulk capacitors *"C1, C2 rated at >= 35V"* (headroom for the 26 V max input). Block diagram caption: *"9A @ 5V max."* — this rail supplies servo power and the board's 5 V distribution.
4. **3.3 V rail:** An **LD39200PU33R** LDO, fed from the 5 V rail, produces 3V3 for "MCUs and Sensors" (schematic note verbatim). Block diagram caption: 3V3 rail rated **2 A max**.
5. **Layout note (grounded rationale):** *"Keep SGND and PGND separate - connect only at one location!"* — an explicit single-point star-ground instruction on the power sheet, i.e. the author's stated reason for splitting signal and power ground in layout.
6. **Distribution:** From these two regulated rails, 3V3 feeds both MCUs (FCC, NAVC) and all I2C sensor ICs; 5 V feeds the servo/PWM connector bank (via PCA9685PW), the GPS module, and the CH330 USB-UART bridges.

---

## 5. Companion Boards

**HadesNT** — A single-board, single-MCU (STM32H750VBT6) redesign of the Hades concept: it replaces the FCC+NAVC dual-processor split with one Cortex-M7 handling both roles, and swaps the discrete BMI088+IIS2MDCTR+MPRLS sensor set for a combined BMX055 IMU and BMP280 barometer, plus a different buck regulator (MP2451) and added USB ESD protection (SRV05-4). It keeps the same INA219 current/voltage sensor as Hades. No in-repo documentation states the motivation for this consolidation (see §3); it is presented here purely as an observed hardware difference.

**HadesMicro / HadesMicroJLCPCB** — Per `Hardware/README.md`: *"Hades Micro: 5cmx5cm flight control board with a single STM32F4. No GPS receiver and limited power distribution."* Schematic confirms a single STM32F405RGT6 with BMI088 IMU, LD39200PU33R regulator, PCA9685BS PWM driver, W25N01GVZEIG_TR flash, and a CH330 USB-UART bridge — effectively a cut-down, GPS-less single-MCU variant of the Hades NAVC+FCC feature set. **HadesMicroJLCPCB** is, per the same README, *"Nearly identical to Hades Micro, however uses SPI instead of I2C for sensor communication. Additionally, nearly all parts are available through LCSC/JLCPCB for assembly."* This is corroborated by the ground-truth BOM (`HadesMicroJLCPCB-FullBOM.csv`, 41 line items) and by a direct schematic comparison: the JLCPCB variant's schematic contains 19 MOSI/MISO/SCK references versus 6 in the original HadesMicro, and fewer I2C/SCL/SDA references (19 vs. 29) — consistent with the sensor interface having moved from I2C to SPI. The BOM also shows an MPRLS0015PA0000SA barometer (lower full-scale-pressure variant than Hades' 0025PA part), a CAT24C256 EEPROM, an AP2112K-3.3 LDO, and USBLC6-2SC6 USB ESD protection — all swapped for parts available via LCSC/JLCPCB, consistent with the stated cost-reduction/assembly goal.

**HadesGPSDongle** — A standalone GPS/GNSS module, distinct from the u-blox GPS footprint used on the main Hades board: its schematic is built around an **STMicroelectronics Teseo-LIV3R** GNSS module with a **MAX2674EWT+T** LNA front-end, SMA and U.FL antenna connector options (CONSMA002, CONUFL001-SMD-T), and status LEDs — i.e. a self-contained GPS receiver "dongle" rather than a flight controller, presumably (Inferred — not stated in-repo) for bench-testing or evaluating an alternative GNSS receiver independent of the main board's integrated u-blox part.
