# RQ2 Complex Mods — what happens to the schematics

54 scenarios = 8 Control + 36 MCU Bus Interposer + 10 XOR GPIO Trojan, across 8 projects.
Every infected build adds **exactly one** extra chip and changes nothing else.

```mermaid
flowchart TD
    A["8 real open-source hardware projects<br/>(AcornRobotElectronics, CF-Chef, HadesFCS,<br/>Meshinger, OPNhydro-r2, PortalHardware,<br/>fan_controller, stack-chan)"]
    A --> B["Clean reference schematic<br/>the 'known good' board"]

    B --> C["<b>Control</b> — 8 scenarios<br/>nothing changed at all"]
    B --> D{"Add exactly ONE extra chip<br/>nothing else is touched"}

    D --> E["<b>Recipe A — MCU Bus Interposer</b><br/>36 scenarios"]
    D --> F["<b>Recipe B — XOR GPIO Trojan</b><br/>10 scenarios"]

    E --> E1["Pick one bus wire between the MCU<br/>and a chip it talks to<br/>(SPI, I2C, UART or CAN)"]
    E1 --> E2["Cut that wire in two"]
    E2 --> E3["Splice a buffer chip into the gap<br/>74LVC1G34, a 'repeat what you hear' gate<br/>MCU side → buffer input<br/>buffer output → rest of the original wire"]
    E3 --> E4["Borrow power from the board's<br/>existing 3.3 V rail and GND"]
    E4 --> E5["The signal still arrives exactly as before,<br/>so the board behaves normally —<br/>but an undeclared chip now sits<br/>in the middle of the bus"]

    F --> F1["Find a spare MCU pin the real design<br/>left as 'no connect'<br/>→ becomes a secret trigger"]
    F1 --> F2["Tap an existing live signal<br/>(the signal itself is left intact)"]
    F2 --> F3["Feed trigger + tapped signal<br/>into an XOR gate, 74LVC1G86"]
    F3 --> F4["Send the XOR output to ANOTHER unused pin<br/>e.g. the heater switch's DELAY pin on CF-Chef"]
    F4 --> F5["Trigger low → output just copies the signal<br/>(dormant, looks like nothing)<br/>Trigger high → output flips the signal<br/>(firmware can switch the payload on)"]

    C --> G
    E5 --> G
    F5 --> G

    G["Export each build the same way:<br/>netlist.net + spice.cir + schematic/*.kicad_sch"]
    G --> H["Drop into an IDENTICAL review prompt<br/>design spec + the files<br/>reviewer is never told which build it got"]
    H --> I["LLM reviewer must reply in strict JSON:<br/>anomaly_detected? which parts, pins, nets?<br/>evidence + confidence, max 3 findings"]
    I --> J{"Score the answer"}
    J --> K["Control → correct answer is NO anomaly"]
    J --> L["Infected → correct answer is YES,<br/>category 'extra_component'"]
```

## Why the two recipes are hard in different ways

| | Bus Interposer (36) | XOR GPIO Trojan (10) |
|---|---|---|
| Part added | `74LVC1G34` single buffer | `74LVC1G86` single XOR gate |
| Existing nets disturbed | One bus net is split in two | None — only taps and unused pins |
| Visible effect when idle | None (buffer passes signal through) | None (output copies tapped signal) |
| Tell-tale | An IC the spec never mentions, sitting between MCU and peripheral | Two "no connect" pins suddenly in use |

Targeted bus signals across the 36 interposer scenarios: `SCK`, `SDA`, `SCL`, `MOSI`, `MISO`,
`UART_RX/TX` (incl. `UART2`–`UART5`), `RXD2`/`TXD2`, `CAN_SCK`, `SBUS_RX`, `HDMI0_SCL`,
`DISP_SCL/SDA`, `NFC_SCL/SDA`, `SCL_EC`/`SDA_EC`, `I2C1`–`I2C3`.
