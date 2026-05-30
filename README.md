# PCB Question Answer Benchmark

A benchmarking method for evaluating Large Language Models (LLMs)' ability to analyse and answer questions about PCB circuit designs using various design sources (netlist files, SPICE circuit descriptions, hierarchical JSON representations, and combinations thereof).

## Supported Design Sources

| Format | Module | Description |
|--------|--------|-------------|
| KiCad Netlist (.net) | `kicad_netlist_processer.py` | S-expression format from KiCad schematics |
| KiCad Schematic (.kicad_sch) | `kicad_cli_helpers.py` | Converted to .net via kicad-cli |
| SPICE Circuit (.cir) | `kicad_spice_circuit_processer.py` | Circuit simulation descriptions |
| Hierarchical JSON | `circuit_json.py` | Structured circuit representation |

## Quick Start

### 1. Install Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add 'circuit-synth' and 'skidl'
uv add circuit-synth skidl
```

### 2. Initialize KiCad CLI

```bash
uv run --env-file .env python initialise_kicad_cli.py
```

This creates a symlink at `<project_directory>/kicad-cli`.

### Project Configuration

Define test projects in `project_files.json`:

```json
{
    "AcornRobotElectronics": {
      "parent_directory": "./outputs/AcornRobotElectronics",
      "circuit_json_file": "./outputs/AcornRobotElectronics/cm4-robot.json",
      "netlist_file": "./outputs/AcornRobotElectronics/cm4-robot.net",
      "spice_circuit_file": "./outputs/AcornRobotElectronics/cm4_robot_board.cir",
      "spice_json_file": "./outputs/AcornRobotElectronics/cm4-robot_SPICE_circuit.json",
      "questions_json_file": "./outputs/AcornRobotElectronics/cm4-robot_60_questions.json",
      "datasheet_files": [
         "./outputs/AcornRobotElectronics/datasheets/C18.pdf",
         "./outputs/AcornRobotElectronics/datasheets/U3.pdf",
         "./outputs/AcornRobotElectronics/datasheets/U6.pdf",
         "./outputs/AcornRobotElectronics/datasheets/U12.pdf",
         "./outputs/AcornRobotElectronics/datasheets/U25.pdf",
         "./outputs/AcornRobotElectronics/datasheets/U28.pdf",
         "./outputs/AcornRobotElectronics/datasheets/U32.pdf",
         "./outputs/AcornRobotElectronics/datasheets/U33.pdf"
      ]
   }
}
```

## Test Projects

Included hardware projects in `OSHP_files/`:

| Project | Type |
|---------|------|
| `HadesFCS_hardware` | Flight Control Computer |
| `acorn-robot-electronics` | CM4 Robot Board |
| `OPNhydro` | Hydroponic Controller |

## Dependencies

Key packages (see `pyproject.toml`):

- `circuit-synth` — Circuit synthesis
- `skidl` — Schematic description
- `pyspice` — SPICE simulation
- `langchain` — LLM framework
- `faiss-cpu` — Vector similarity search
- `sentence-transformers` — Embedding generation

## License

See individual project files for licensing information.