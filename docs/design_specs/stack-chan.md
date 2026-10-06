# Stack-chan Pan-Tilt Carrier Board — Design Specification

Source: `OSHP_files/Clean/stack-chan/schematics/m5-pantilt/` (KiCad project `m5-pantilt`), cross-checked against `schematics/README.md`, the top-level `README.md`, `case/README.md`, and the project `CLAUDE.md`.

## 1. TL;DR

The `m5-pantilt` board is a small carrier PCB that stacks onto the bottom bus connector of an M5Stack Core (Basic/Gray/Go/Fire/Core2/CoreS3) and breaks it out to drive the two servos (pan + tilt) of the Stack-chan robot head. It supports two mutually-exclusive servo interface modes, selected at assembly time by populating different 0 Ω jumper resistors:

- **PWM mode**: two independent PWM channels (for low-cost SG90-class hobby servos) wired straight through to the two 3-pin servo headers.
- **Serial mode**: the two servo signal pins are bridged into one shared half-duplex TTL serial bus, driven through a MAX3485 RS-485/RS-422 transceiver, for ID-addressed serial servos (RS304MD / RS30X family, SCS0009, etc.).

Power can come from either (a) a LiPo battery routed through the M5Stack Core's own bus/charging path, switchable with an optional on-board slide switch, or (b) an external 5V supply input, diode-isolated from the M5Stack 5V rail. (Firmware driver support for `pwm`, `scservo`, `dynamixel`, and `rs30x` servo types is listed in the project's `CLAUDE.md`, consistent with this PWM/serial split.)

## 2. Component Table

| Ref | Part | Role (from schematic/netlist) |
|---|---|---|
| J1 / J2 | `Conn_02x15_Odd_Even` (2×15, labelled "M-BUS" in schematic) | Top and bottom M5Stack bus connectors; identical nets on both so the board can be stacked between the M5Stack Core and a lower module (pass-through). Carries +5V, +3V3, BAT, GND, GPIO/UART pins (TXD2/RXD2 = PortC UART, two PortB GPIOs) through to J6. |
| J3, J8 | `Conn_01x03` | Servo header, channel 1 (J3) and channel 2 (J8). Pin 3 is the signal pin, routed to either PWM or shared-serial bus depending on jumpering (see §3). |
| J5 | `Conn_01x02`, labelled `BAT` | Battery input connector, gated through Q1 to the M5Stack bus BAT pin. |
| J6 | `Conn_01x04` | M5Unit PortB breakout (GND, +5V, two GPIOs), passed through from J1/J2. |
| J7 | `Conn_01x02`, labelled `5V_POWER` | External 5V power input. |
| D1 | SS54 (5A Schottky) | Series diode between J7 (external 5V in) and the board's `+5V` rail — blocks backfeed from the +5V rail out through the external-power jack. Schematic note nearby: "forward voltage > 0.6V". |
| D2 | PMEG3030EP Schottky, schematic note "3A 360mV" | Diode from `+5V` into the servo power rail (feeding J3/J8 pin 2 and the C1–C4 bank), selected for a low (≈360 mV @ 3A) forward drop. |
| C1–C4 | 100 µF × 4 | Bulk capacitance on the servo power rail (downstream of D2), buffering the high inrush current of PWM servos. |
| C5 | 0.1 µF | Decoupling cap on `+3V3` (MAX3485 supply). |
| Q1 | IRLML6402 (P-ch MOSFET) | High-side battery disconnect switch: gates the battery connector (J5) onto the `/BAT` bus net. |
| SW1 | SPDT switch | Optional manual power switch; pulls Q1's gate low (via R5, 47k) to turn the battery path on. |
| Q2 | BC857 (PNP) | Auto TX/RX direction-control transistor: driven from `/TXD2` (via R1 10k, R2 5.1k) to toggle the MAX3485 DE/RE enable pins. |
| U1 | MAX3485 (half-duplex RS-485/RS-422 transceiver) | Converts the M5Stack's UART (TXD2/RXD2, PortC) to the shared single-wire TTL serial servo bus. |
| R1, R2 | 10k, 5.1k | Bias/divider from `/TXD2` into Q2's base. |
| R6, R7, R8, R15 | 2k, 20k, 2.2k, 2.2k | Bias/pull network on the MAX3485 A/B differential lines and DE/RE enable line. |
| R3, R4 | 1k each | Series resistors from the PWM1/PWM2 GPIO nets to J3 pin 3 / J8 pin 3 respectively. |
| R9–R12 | 0 Ω (jumpers) | Select which M5Stack bus pin (pin 19/21 for ch.1, pin 20/22 for ch.2) supplies PWM1/PWM2 — schematic note: "Short R10, R10 for Core2 and CoreS3 / Short R9, R11 for others" (i.e., GPIO-to-bus-pin mapping differs by M5Stack core variant). |
| R13, R14 | 0 Ω (jumpers) | When shorted, bridge J3-pin3 and J8-pin3 together and onto the MAX3485 TTL bus — schematic note: "Short R13, R14 for Serial Servo". |

## 3. Servo Interface Trade-off

`schematics/README.md` states the feature directly: the board can "Drive two servos: PWM × 2ch or Serial × 2ch", and documents the trade-off that this hardware implements:

> **PWM (SG90)** — Pros: very low cost (~500 yen), easy to find, and PortC (serial communication) remains available for the user's own M5Units. Cons: difficult to change angle smoothly; inrush current is high and may cause the M5Stack to power down in rare cases; SG90 can get very hot and may emit smoke when overloaded (e.g. past its physical angle limits); torque cannot be switched off, so twisting the head while torque is on may damage the servo.
>
> **Serial (RS304MD)** — Pros: complex control (e.g. speed limiting) is possible, and because the current angle can be read back, richer behaviors (e.g. reacting to head direction) are possible. Cons: more expensive (~3,000 yen), the user loses PortC, and RS304MD's larger size makes it stick out slightly behind the body.

This maps directly onto the jumper-selectable signal path at J3/J8 pin 3:

- **PWM mode** (populate R3/R4, and the appropriate R9–R12 pair for the Core variant; leave R13/R14 open): each servo header's signal pin gets its own independent 1 kΩ-buffered GPIO line (`/PWM1` → J3 pin3, `/PWM2` → J8 pin3) straight from the M5Stack bus. PortC (the UART pins feeding U1) is left completely unused, matching the README's claim that PWM mode frees PortC for the user.
- **Serial mode** (populate R13/R14, per the explicit schematic annotation "Short R13, R14 for Serial Servo"): J3-pin3 and J8-pin3 are tied together into one shared bus node and driven by U1 (MAX3485), fed from the M5Stack's PortC UART (`/TXD2`/`/RXD2`, J1/J2 pins 15/16) with Q2 auto-switching the transceiver's DE/RE pins based on TX activity. This matches `case/README.md`'s statement that "Serial servos share a signal line. It's necessary to specify ID for controlling each servo" (ID1 = pan/foot, ID2 = tilt/face) — consistent with the two servo headers being electrically merged into a single addressable bus rather than two independent channels.

Inferred: the exact bias/pull-up resistor values on the MAX3485 A/B lines (R6, R7, R8, R15) and the PNP-based auto-direction-control topology around Q2 are a standard half-duplex RS-485 "self-switching from TX" pattern; no comment in the schematic states this rationale explicitly, so it is inferred from the circuit topology (DE and /RE tied together, driven from the UART TX line) rather than sourced from project text.

## 4. Power

`schematics/README.md` lists the power features as: "M5Unit PortB", "External 5V Power Supply", "Battery, which can be charged through M5Stack", and "(Optional) Power switch". The schematic implements these as two parallel supply paths:

**Battery path (charge-through-M5Stack):** The battery connects at J5, through Q1 (IRLML6402 P-MOSFET) acting as a high-side disconnect switch, onto the `/BAT` net, which is wired straight to pin 29 of the M5Stack bus connectors (J1/J2) — i.e., the board does not implement its own battery charger; it simply presents the battery to the M5Stack Core's own BAT bus pin, letting the Core's internal charge circuitry handle charging when USB power is present, matching the README's "charged through M5Stack" wording. SW1, an SPDT switch, is the optional power switch: closing it pulls Q1's gate (through R5, 47k) low enough to turn the P-FET on and connect the battery; leaving it open keeps Q1 off and the battery disconnected. This switch and its position (populate or omit SW1) is literally the "(Optional) Power switch" feature named in the README.

**External 5V path:** J7 (labelled `5V_POWER`) feeds the board's `+5V` rail through D1 (SS54 Schottky), which blocks current from flowing back out of the external-power jack when the board is instead being powered from the M5Stack/battery side. The same `+5V` net is also tied directly to J1/J2 pin 27 (the M5Stack bus's 5V pin), so `+5V` is effectively the logical OR of "M5Stack-supplied 5V" and "external 5V input via D1".

**Servo power buffering:** From `+5V`, a second diode D2 (PMEG3030EP, annotated "3A 360mV" in the schematic — a low-forward-voltage-drop Schottky) feeds a dedicated servo power rail backed by four 100 µF capacitors (C1–C4) before reaching J3/J8 pin 2. Inferred: this diode-plus-bulk-capacitor arrangement exists to isolate and buffer the servo supply from the high inrush current that `schematics/README.md` warns about for PWM servos ("Inrush current is high and may cause the M5Stack to power down in rare cases"); the README states the problem, but does not explicitly say D2/C1–C4 are the fix, so that specific causal link is inferred from the component choice and placement rather than directly stated.

**M5Unit PortB:** J6 (4-pin) carries GND, +5V, and two GPIOs (`/PORTB1`, `/PORTB2`) through from J1/J2, implementing the "M5Unit PortB" feature listed in the README for connecting additional M5Stack accessory units.

---

### Summary of Inferred items (not directly sourced)

- The specific causal link between D2 + C1–C4 (servo rail buffering) and the README's stated PWM-servo inrush-current risk.
- The auto half-duplex direction-control behavior of Q2/R1/R2/R7 around the MAX3485 DE/RE pins (standard pattern, inferred from topology, not commented in-schematic).
- The bias/fail-safe purpose of the A/B line pull resistors (R6, R8, R15) on the MAX3485.

### Directly sourced items

- PWM-vs-serial servo trade-off (cost, inrush/smoke risk, torque control vs. closed-loop angle feedback, PortC availability) — from `schematics/README.md`.
- "Short R13, R14 for Serial Servo" and "Short R10, R10 for Core2 and CoreS3 / Short R9, R11 for others" — literal schematic text annotations.
- D1/D2 forward-voltage schematic annotations ("forward voltage > 0.6V", "3A 360mV").
- Battery-charged-through-M5Stack, external 5V supply, optional power switch, and M5Unit PortB — from `schematics/README.md` feature list, matched to J5/Q1/SW1, J7/D1, and J6 respectively.
- Serial servos sharing one signal line and needing per-servo IDs (pan = ID1, tilt = ID2) — from `case/README.md`.
