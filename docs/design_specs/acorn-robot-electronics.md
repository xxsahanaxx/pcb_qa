# Design Specification — Acorn Robot Electronics

Source: `OSHP_files/Clean/acorn-robot-electronics` (git submodule, upstream: Twisted-Fields/acorn-robot-electronics). KiCad PCB sources for Acorn, a precision farming rover from Twisted Fields, designed by Taylor Alexander (per project `README.md`). This document covers the `cm4_robot_board` motherboard in detail, plus one paragraph each for the `gps_adapter`, `supercap`, `mag_sensor`, and `soft_start` auxiliary boards.

Grounding note: rationale is stated only where the repo says so (notes.txt, board_TODO.txt, TODO.txt, issues.txt, docs/twistedfields-notes.txt, or a datasheet of a part actually used). Where the schematic/netlist shows *what* was built but no stated *why*, the text is marked "Inferred:" rather than presented as settled fact.

---

## 1. TL;DR — what the CM4 motherboard does

Per `cm4_robot_board/README.md`: "This board provides motor control communication to four Odrive motor controllers via RS-485, e-stop control, motor power control, and more." It is the central carrier/compute board of the rover, built around a Raspberry Pi Compute Module 4 (`Module1` in the netlist, referred to as "CM4" throughout the repo's notes).

From the schematic/netlist, the board actually implements:
- **Compute carrier**: hosts the CM4 (`Module1`), breaking out GPIO, Ethernet, USB, camera connectors, and an RTC (datasheet link in `cm4_robot_board/docs` points to a `PCF85063ATAAZ` RTC — see `new_notes.txt`).
- **Power distribution**: DC-DC conversion, a CM4 power-enable path (`GLOBAL_EN`), and USB input "OR-ing"/protection circuitry (LTC4412 ideal-diode controller, `U6`).
- **Motor/actuator interfaces**: two isolated CAN buses (`CAN0`, `CAN1`), each driven by its own MCP2515 SPI CAN controller (`U8`, `U9`) through an isolated CAN transceiver (`U11`/companion), broken out on M12 circular connectors `J2` ("CAN Interface A") and `J13` ("CAN Interface B"). This is the hardware actually present for talking to the Odrive motor controllers the README describes — **note the discrepancy**: the README text says "RS-485" but no RS-485 transceiver part (e.g. THVD1451/ISL8348x, both discussed in `docs/twistedfields-notes.txt`) was found in `cm4-robot.net`; the netlist shows CAN hardware instead. This is reported as observed, not resolved — it may reflect the README describing an earlier design intent/other board revision.
- **Safety/e-stop**: an e-stop loop with multiple sink points (`ESTOP_SINK1`, `ESTOP_SINK2`, `ESTOP_SINK_LOCAL`) gated through single non-inverting buffers (`SN74LVC1G07`, parts `U15`, `U22`, `U35`, `U36`) wired as `/OE`-controlled sinks, feeding an `ESTOP_OUT` signal shared with the CAN connectors `J2`/`J13`.
- Addressable status LEDs (WS2812B, `D5`-`D7`, `D18`-`D21`) and an analog switch (`ISL54222AIUZ`, `U5`) for LED/signal routing.

---

## 2. Component table — items with a stated reason in the repo notes

| Component(s) | Role (from schematic/netlist) | Stated rationale / note (source) |
|---|---|---|
| `U8`, `U9` — MCP2515-xSO CAN controllers; `Y1`, `Y2` — 16MHz crystals | SPI CAN controllers for CAN0/CAN1, each with its own oscillator crystal | `board_TODO.txt`: "make CAN controller crystal value more clear - 16mhz not 12mhz!" — i.e. the engineer flagged that the correct/required crystal is 16MHz, not 12MHz, implying a past labeling/BOM ambiguity. The netlist's current `Y1`/`Y2` value is **16MHz**, consistent with the corrected value the note calls for. |
| `U11` (and its CAN1 counterpart) — isolated CAN transceiver; `U18`, `U19` (`SN74LVC1G07`) driving `TXLED`/`RXLED` nets from `U8` TXCAN/RXCAN | CAN TX/RX activity indicator LEDs, buffered off the CAN controller's TXCAN/RXCAN lines | `board_TODO.txt`: "invert CAN TX/RX LED polarity either by using inverting buffer part number or by rewiring input - maybe inverted is best for fast cut-off?" — engineer is unresolved/considering whether inverted LED logic better signals a fast cut-off condition. Left as an open question in the source, not resolved here. |
| `U15`, `U22`, `U35`, `U36` (`SN74LVC1G07`) wired as `/OE` gates on `ESTOP_SINK1`/`ESTOP_SINK2`/`ESTOP_SINK_LOCAL` | E-stop sink/buffer circuit feeding `ESTOP_OUT`, shared with CAN connectors `J2`/`J13` | `board_TODO.txt`: "e-stop should activate if a cable is disconnected. - nevermind, it does this" — i.e. the engineer initially flagged a concern, then confirmed the existing circuit already satisfies cable-disconnect-triggers-e-stop behavior. |
| `U6` — LTC4412xS6 ("ideal-diode or-ing" per its own `ki_keywords` field) | USB power-path controller intended to OR/protect a USB power input | `new_notes.txt` / `notes.txt` (motherboard section): "USB diode doesn't work, I guess need ideal diode to handle more power? LTC4412 controller and p-ch mosfet. need reverse current protection mostly" with a cited TI app note (`https://www.ti.com/lit/an/slvae57b/slvae57b.pdf`). This documents the stated reason for choosing an ideal-diode (LTC4412 + P-ch MOSFET) topology over a simple diode: handling more power while providing reverse-current protection. The note itself says the (then-current) USB diode arrangement "doesn't work," so this is a documented open/partially-resolved issue, not a confirmed-working design. |
| `Module1` pin 99 (`Global_EN`) — `GLOBAL_EN` net, tied directly to `SW1` pin 2 | CM4 power-enable signal, driven by a simple switch with no sequencing component in between | `notes.txt`: "add something to the design to hold CM4 in reset until power is stabilized? why does it not always boot at power on?" and "consider a power on delay chip attached to GLOBAL_EN, or debug inconsistent power on condition. or is that due to incorrectly seated CM4?" — the engineer explicitly flags GLOBAL_EN sequencing as unresolved/uncertain; the netlist confirms there is currently no delay/sequencing IC on this net, only a direct switch connection. |
| `D9`, `D10` — `CDSOT23-SM712` TVS diode arrays on `CAN0_P/N`, `CAN1_P/N` | CAN bus transient/ESD protection | `docs/twistedfields-notes.txt` lists "TVS Diodes: SM712-TP or SM712-02HTG" as the intended part family for this role; the netlist's `CDSOT23-SM712` matches this documented choice. |

Items named in `board_TODO.txt` but not resolvable from schematic alone (left as-is, per the grounding rule): the exact silkscreen/polarity marking fix for `U5`, `D19`, `D5`, `D6`, `D20`, `D7`, `D21`, `D18` (all WS2812B LEDs plus the `ISL54222AIUZ` analog switch) is only described as a to-do ("Make clear the polarity for U5、D19、D5、D6、D20、D7、D21、D18"), with no stated root cause.

---

## 3. Known issues / open TODOs

This section is a faithful summary of `board_TODO.txt`, `notes.txt`, `cm4_robot_board/TODO.txt`, and `cm4_robot_board/new_notes.txt`. None of these are resolved or re-diagnosed here — they are reproduced as the engineer left them.

**From `board_TODO.txt` ("TODO RECOMMENDATIONS AFTER PRODUCTION"):**
- Make clear the polarity for `U5`, `D19`, `D5`, `D6`, `D20`, `D7`, `D21`, `D18`.
- E-stop activating on cable disconnect was raised as a concern, then struck through with "nevermind, it does this" — i.e. confirmed as already working, not an open item.
- Make the CAN controller crystal value more clear — the note insists it must read 16MHz, not 12MHz.
- Open question: whether to invert CAN TX/RX LED polarity (via an inverting buffer part, or by rewiring the input) — "maybe inverted is best for fast cut-off?" is posed as a question, not decided.

**From `notes.txt` (motherboard section):**
- Fix the footprint/pad size for `C5` — "8mm diameter too small."
- "USB diode doesn't work, I guess need ideal diode to handle more power? LTC4412 controller and p-ch mosfet. need reverse current protection mostly" (cites TI app note slvae57b).
- Fork the board and flip the camera connectors; delete the camera connectors from the main board.
- Add camera LED control.
- Open question: "add something to the design to hold CM4 in reset until power is stabilized? why does it not always boot at power on?"
- Open question: "are any switches backwards?"
- Add ground test points.
- Check the size of the PTH holes used on the DC-DC converter.
- Open question: "consider a power on delay chip attached to GLOBAL_EN, or debug inconsistent power on condition. or is that due to incorrectly seated CM4?"

**From `notes.txt` (odrive aux board section — not part of this motherboard, noted for completeness):**
- "footprint for buffers is wrong, copy from motherboard."

**From `cm4_robot_board/TODO.txt`:**
- A link to an RTC part (`PCF85063ATAAZ`) and a Raspberry Pi forum thread on RTC support, with no further elaboration — read as a pointer/reference rather than a resolved decision.

**From `cm4_robot_board/new_notes.txt`:**
- `WL_nDisable` (logic high = Wi-Fi enabled) — "may want to connect it to an LED. can also be pulled low to disable wlan."
- `BT_nDisable` — same consideration as above, for Bluetooth.
- A note to use an Ethernet jack for RPi networking, with a specific Bel Fuse part link (`0826-1X1T-GH-F`).

None of the above open questions (power-on-delay chip for `GLOBAL_EN`, CAN LED polarity inversion, inconsistent CM4 boot behavior, "are any switches backwards") are answered elsewhere in the repo's text files; they are reported here as open, per the source.

---

## 4. Auxiliary boards

**`gps_adapter`** — The schematic (`gps_adapter.kicad_sch`) shows two GPS modules (`U1`, `U2`, both valued `GPS-RTK-SMA`), each with solder jumpers (`JP1`/`JP2`, type `SolderJumper_2_Open`) and a serial-input connector (`J3`, labeled "Serial Input"), plus mounting holes and standard `+5V`/`GND` power nets. Inferred: having two SMA-connector RTK GPS modules on one adapter board suggests a dual-antenna heading/attitude setup rather than a single positioning receiver, but no notes.txt entry or comment in this board's files states that rationale directly, so this is inference from the schematic layout alone, not a documented design reason.

**`supercap`** — Two schematic variants exist: `supercap/supercap/supercap.kicad_sch` (full) and `supercap/supercap_simple/supercap_simple.kicad_sch` (reduced). The full variant centers on an RP2040 microcontroller supervising a bank of eighteen 120F 2.3V supercapacitor cells, each shunted by a 2.4V zener diode for passive cell-voltage balancing, switched via multiple 100V/34A P-channel MOSFETs, with bidirectional-looking current sensing (`INA181A2` instrumentation amplifiers), ADCs (`ADS7822U`, `ADC081S021`), a USB-C input, isolated CAN connectivity (`+5V_ISO`, `GND_ISO`, an `EL357N` optocoupler, a "CAN2 PLUG" connector), on-board flash (`W25Q128JVS`), thermistors, and TVS/zener protection devices. The `supercap_simple` variant strips this down to essentially just the 18 supercapacitor cells, their balancing zeners, and a single `XT30PW` power connector plus mounting holes — i.e. a bare capacitor-bank module without the RP2040 monitoring/control circuitry. No notes.txt entry specific to this board was found in the repo; the component list above is read directly from the schematic, not from any stated rationale.

**`mag_sensor`** — The schematic (`mag_sensor.kicad_sch`) shows a `A1101LLHL` Allegro Hall-effect switch (datasheet linked directly in the schematic: `allegromicro.com/.../a110x-datasheet.ashx`) and a second part valued `MT9105ET` (no datasheet link present in the schematic), alongside a 3-pin connector (`Conn_01x03`), decoupling capacitors, and `+3V3`/`GND` nets. Inferred: given the board's name and the presence of a Hall-effect switch, this is almost certainly a magnetic wheel/shaft position or proximity sensor board, but no notes.txt or comment in the repo states its intended application (e.g. wheel odometry vs. a limit/home switch), so that specific use is inference, not a documented fact.

**`soft_start`** — The schematic (`soft_start.kicad_sch`) shows an RP2040 microcontroller, `INA181`/`INA181A2` current-sense amplifiers, `100V 34A PMOS` and NMOS (`Q_NMOS_GSD`) power switches, an inductor/crystal pair (`47uH`, `12MHz`), an `LD1117S33TR` 3.3V LDO, Schottky diodes (`SS310`, `MBR340`), on-board flash (`W25Q128JVSIQ`), USB ESD protection (`USBLC6-4SC6`), and 10V zener diodes — consistent with a microcontroller-supervised input soft-start/current-limiting circuit. `soft_start/issues.txt` states two specific, unresolved problems directly: "input mosfet arrangement incorrect - see https://www.ti.com/lit/an/slva948/slva948.pdf" and "current sensing should not be unidirectional for input power at least. and care must be taken to ensure that output current sensing is the correct direction (seems ok)" — i.e. the engineer flags the input-side MOSFET topology as wrong (citing a specific TI application note on the correct arrangement) and the input current sensing as needing to be bidirectional, while judging the output current-sense direction to be correct as-is. These are reported here as open issues, not fixed.
