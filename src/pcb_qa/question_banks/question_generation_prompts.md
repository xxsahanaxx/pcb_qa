# LLM Prompts for Generating PCB Design Questions

Based on analysis of the question files in `outputs/` folder, there are **3 distinct categories** of questions. Below are recommended prompts for generating questions in each category.

---

## Category 1: `component_datasheet`

### Purpose
Questions that verify component specifications, characteristics, and capabilities by referencing component datasheets.

### Key Observations from Existing Questions
- Focuses on IC/component properties: temperature ratings, voltage limits, communication interfaces (I2C, SPI, UART, CAN, USB, Ethernet, WiFi, Bluetooth)
- Tests for component capabilities: flash, memory, PWM module, magnetic sensor, motion sensor
- Uses component references (U1, U2, U3, U6, U8, U9, U12, U25, U32, U33, REG1, REG2, SW2, SW3, D1, etc.)
- Format: `"Does the component {REF} have {PROPERTY} according to its datasheet?"`
- Expected answers: YES or NO

### LLM Prompt for Generating `component_datasheet` Questions

```
You are a PCB design verification assistant. Generate questions that test whether a component has specific characteristics or capabilities based on its datasheet.

**Input Context:**
- A KiCad schematic JSON file containing component references, values, and properties
- Component datasheets in PDF format for integrated circuits (ICs)
- Available properties from component descriptions include: temperature ratings, voltage ratings, current ratings, communication interfaces, special capabilities

**Rules for Question Generation:**
1. Select a component reference (e.g., U1, U2, U3, U6, U8, U9, U12, REG1, REG2, etc.)
2. Formulate a question about ONE specific property or capability
3. Use clear, verifiable properties from the datasheet such as:
   - Temperature specifications (max/min operating/junction temperature, °C)
   - Voltage specifications (max/min supply voltage, V)
   - Current specifications (max current, quiescent current, µA/A)
   - Communication interfaces (I2C, SPI, UART, CAN, USB, Ethernet, WiFi, Bluetooth)
   - Special capabilities (flash, memory, PWM, ADC, DAC, sensor types)
   - Physical characteristics (output voltage, dropout voltage, dielectric strength)

**Question Format:**
"Does the component {COMPONENT_REF} have {PROPERTY} according to its datasheet?"

**Examples:**
- "Does the component U3 have a maximum operating temperature of 125°C according to its datasheet?"
- "Does the component U6 have I2C capabilities according to its datasheet?"
- "Does the component U12 have a minimum operating ambient temperature of -30°C according to its datasheet?"
- "Does the component REG2 have a maximum current of 1.5A according to its datasheet?"

Generate 20 unique questions of this format. Vary the components, properties, and values. Provide only the question text and indicate the answer should be YES or NO.
```

---

## Category 2: `spice_behaviour`

### Purpose
Questions that verify SPICE circuit simulation results - checking if signals maintain specific voltage levels throughout the simulation.

### Key Observations from Existing Questions
- Focuses on nets and signals in the circuit
- Tests voltage levels: 0V, 3.3V, 5V, 12V, ~25V
- Uses net names like: `serial_can_pwr_3.3v`, `net-_q9-g_`, `scl0_gpio45`, `+12v`, `+3v3`, `vbus`, `bat+`, etc.
- Format variants:
  - "Does the net {NET_NAME} maintain a voltage of X V during the entire simulation?"
  - "Does the {SIGNAL_NAME} signal maintain a voltage of ~X V during the entire simulation?"
  - "Does the net {NET_NAME} obtain a steady state of ~X V after the entire simulation?"
- Expected answers: YES or NO

### LLM Prompt for Generating `spice_behaviour` Questions

```
You are a PCB circuit simulation verification assistant. Generate questions that test SPICE simulation results by verifying signal voltage levels throughout the simulation.

**Input Context:**
- A SPICE circuit netlist file (.cir)
- A SPICE simulation results JSON file containing time-series voltage data for each net
- Power rails typically identified: +3.3V, +5V, +12V, VBUS, BAT+, etc.
- Signal nets have names like: net-*, signal names with underscores

**Rules for Question Generation:**
1. Select a net or signal name from the circuit
2. Choose a target voltage level (typically 0V, 3.3V, 5V, or 12V)
3. Formulate YES/NO questions about voltage stability or steady state

**Question Formats:**
- "Does the net {NET_NAME} maintain a voltage of {VOLTAGE}V during the entire simulation?"
- "Does the {SIGNAL_NAME} signal maintain a voltage of ~{VOLTAGE}V during the entire simulation?"
- "Does the net {NET_NAME} obtain a steady state of ~{VOLTAGE}V after the entire simulation?"
- "Is the {SIGNAL_NAME} signal at {VOLTAGE}V for the entire simulation?"
- "Is the {POWER_RAIL} power rail stable at approximately {VOLTAGE}V throughout the simulation?"

**Voltage Levels to Use:**
- 0V (ground/reference signals)
- 3.3V (logic level signals)
- 5V (legacy logic/IO signals)
- 12V (power rails)
- ~1.2V (special cases like feedback nets)

Generate 20 unique questions. Mix different net names and voltage levels to cover both true and false cases.
```

---

## Category 3: `theory_layout`

### Purpose
Questions that verify physical connections between components and nets in the PCB layout.

### Key Observations from Existing Questions
- Focuses on component-to-net connectivity
- Uses component references (J1, J2, J3, R1, R2, R3, C1, C2, U1, U4, Q1, Q2, Y1, Y2, TR1, etc.)
- Tests connections to specific nets/signals like: GND, _p_5V, _p_3V3, RX4, USBC_VBUS_IN, etc.
- Format: `"Is the component {COMPONENT} connected to {NET_NAME}?"`
- Expected answers: YES or NO

### LLM Prompt for Generating `theory_layout` Questions

```
You are a PCB layout verification assistant. Generate questions that verify whether components are physically connected to specific nets in the circuit schematic.

**Input Context:**
- A KiCad schematic JSON file with component references and net connections
- Nets are identified by names like: GND, _p_5V, _p_3V3, RX4, USBC_VBUS_IN, WS2812, etc.
- Components have pins connected to various nets in the design

**Rules for Question Generation:**
1. Select a component reference (e.g., J1, J2, J3, R1, R2, R3, C1, C2, U1, U6, Q1, Q2, Y1, Y2, TR1, etc.)
2. Select a net name that exists in the circuit
3. Formulate YES/NO questions about connectivity

**Question Format:**
"Is the component {COMPONENT_REF} connected to {NET_NAME}?"

**Component Types to Include:**
- Connectors (J1, J2, J3, etc.)
- Resistors (R1, R2, R3, etc.)
- Capacitors (C1, C2, C3, etc.)
- Integrated circuits (U1, U2, U3, etc.)
- Transistors (Q1, Q2, etc.)
- Crystals (Y1, Y2, etc.)
- Test points (TP1, TP2, TP3)
- Switches (SW1, SW2, SW3)
- LEDs (LED1, LED2, LED3)
- Modules/Feedback components (FB1, FB, Module1)

**Net Types to Include:**
- Power nets: GND, _p_5V, _p_3V3, +3V3, +5V, +12V
- Signal nets: RX, TX, SCK, CS, SDA, SCL (with specific bus designations)
- Interface nets: USB_DM, USB_DP, I2C_SCL, SPI_MISO, UART_RX
- Special function nets: HEATER, PWM, RESET, BOOT, ENABLE

Generate 20 unique questions. Ensure questions test real connections that exist in the circuit to create meaningful YES/NO answers.
```

---

## Summary Table

| Category | Data Source | Question Focus | Typical Properties/Elements |
|----------|-------------|----------------|----------------------------|
| `component_datasheet` | Datasheet PDFs + Component descriptions | Component specifications and capabilities | Temperature, voltage, current, interfaces (I2C/SPI/UART), special features |
| `spice_behaviour` | SPICE simulation JSON + Netlist | Signal voltage behavior over time | Net voltage levels (0V, 3.3V, 5V, 12V), stability, steady state |
| `theory_layout` | Circuit JSON (schematic) | Physical component-net connections | Component references (J, R, C, U, Q, Y) connected to specific nets |

---

## Recommended Workflow

1. **Extract available data:** Parse the circuit JSON to get component references and net names
2. **Generate questions per category:** Use appropriate prompt for each category
3. **Validate against source data:** Ensure questions can be answered from the actual circuit/datasheet/SPICE files
4. **Balance YES/NO answers:** Create a mix of true and false questions for meaningful benchmarking