# PCB Question Answer Benchmark

A benchmarking framework for evaluating Large Language Models (LLMs) on their ability to analyse and answer questions about PCB circuit designs. Supports multiple design source formats including KiCad netlists, SPICE circuits, hierarchical JSON representations, and schematic PDFs.

---

## Project Structure

```
pcb_qa/
├── pyproject.toml                  # Package metadata & dependencies
├── README.md
├── .env.example                    # Environment variable template
├── configs/
│   └── projects.json               # Project file-path registry
├── src/
│   └── pcb_qa/                     # Main package (src-layout)
│       ├── __init__.py
│       ├── __main__.py             # CLI entry-point
│       ├── config.py               # Central path & env configuration
│       ├── logging_config.py       # Structured logging setup
│       ├── models/
│       │   ├── project.py          # Project & ProjectFiles dataclasses
│       │   └── tool_definitions.py # LLM tool schemas (Pydantic)
│       ├── parsers/
│       │   ├── circuit_json.py     # Hierarchical circuit JSON parser
│       │   ├── netlist.py          # KiCad .net → JSON converter
│       │   ├── netlist_sexp.py     # S-expression wrappers for netlists
│       │   ├── hierarchical_reader.py  # Sheet hierarchy analysis
│       │   └── spice.py            # SPICE .cir parser & simulator interface
│       ├── kicad/
│       │   └── cli.py              # kicad-cli wrapper
│       ├── tools/
│       │   └── caller.py           # LLM tool-calling interface
│       ├── evaluation/
│       │   └── evaluator.py        # Benchmark evaluation & metrics
│       └── utils/
│           └── file_ops.py         # JSON & CSV file I/O helpers
├── tools.json                      # Tool definitions (for reference)
├── OSHP_files/                     # Open-source hardware project files
└── outputs/                        # Generated outputs per project
```

## Supported Design Sources

| Format | Module | Description |
|--------|--------|-------------|
| KiCad Netlist (`.net`) | `parsers/netlist.py` | S-expression format from KiCad schematics |
| KiCad Schematic (`.kicad_sch`) | `kicad/cli.py` | Converted to `.net` / `.cir` via `kicad-cli` |
| SPICE Circuit (`.cir`) | `parsers/spice.py` | Circuit simulation descriptions |
| Hierarchical JSON | `parsers/circuit_json.py` | Structured circuit representation |

## Installation

```bash
# Clone the repository
git clone https://github.com/xxsahanaxx/pcb_qa.git
cd pcb_qa

# Install with uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Or install with pip
pip install -e .
```

## Configuration

### Environment Variables

Copy the template and fill in your paths:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `KICAD_CLI_PATH` | Path to `kicad-cli` binary | — (required for exports) |
| `NGSPICE_PATH` | Path to `ngspice` binary | `ngspice` |

### Project Registry

Define test projects in `configs/projects.json`:

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
            "./outputs/AcornRobotElectronics/datasheets/U3.pdf"
        ]
    }
}
```

## Usage

### CLI Commands

```bash
# List configured projects and their file paths
pcb-qa projects

# Initialise KiCad CLI symlink (requires KICAD_CLI_PATH)
pcb-qa init-kicad

# Embed datasheets for semantic search (FAISS indexing)
pcb-qa embed

# Run the full evaluation pipeline
pcb-qa evaluate
```

### Python API

```python
from pcb_qa.parsers.circuit_json import CircuitJSON
from pcb_qa.parsers.netlist import KiCadNetlistProcesser
from pcb_qa.parsers.spice import KiCadSPICECircuitProcesser
from pcb_qa.models.project import ProjectFiles
from pcb_qa.tools.caller import ToolCaller
from pcb_qa.evaluation.evaluator import EvaluateResults

# Load project configuration
projects = ProjectFiles()
acorn = projects["AcornRobotElectronics"]

# Parse a circuit JSON
circuit = CircuitJSON(circuit_file=acorn.circuit_json_file)
print(circuit.is_component_in_net_from_circuit("C18", "GND"))

# Convert netlist to hierarchical JSON
processer = KiCadNetlistProcesser(netlist_path=acorn.netlist_file)
processer.convert_project_netlist_to_circuit()
processer.export_circuit_to_file()

# Use LLM tools
tool_caller = ToolCaller()
is_connected = tool_caller.find_connections_for_component(
    circuit_json_file=acorn.circuit_json_file,
    component_ref="C18",
    net_name="GND"
)

# Evaluate results
evaluator = EvaluateResults()
evaluator.write_nnet_and_ncir_responses_to_csv()
```

## Benchmark Modes

| Mode | Description |
|------|-------------|
| `NNet&NCir` | Normalised Netlist & Normalised Circuit |
| `NNet&PCir` | Normalised Netlist & Primitive Circuit |
| `PNet&NCir` | Primitive Netlist & Normalised Circuit |
| `PNet&PCir` | Primitive Netlist & Primitive Circuit |
| `PDF` | Schematic exported as PDF |

## LLM Tools

The framework exposes three tools to LLMs during question answering:

| Tool | Description |
|------|-------------|
| `get_relevant_context_from_question` | Semantic search over component datasheets (FAISS + sentence-transformers) |
| `calculate_spice_behaviour` | Verify steady-state voltage at a given net |
| `find_connections_for_component` | Check if a component is connected to a net |

## Test Projects

Included hardware projects in `OSHP_files/`:

| Project | Type |
|---------|------|
| `HadesFCS` | Flight Control Computer |
| `acorn-robot-electronics` | CM4 Robot Board |
| `OPNhydro` | Hydroponic Controller |
| `CF-Chef` | Controller Board |
| `Meshinger` | Mesh Networking Board |
| `PortalHardware` | NFC Hardware Wallet |
| `stack-chan` | Pan/Tilt Robot |

## Dependencies

Key packages (see `pyproject.toml`):

- `circuit-synth` — Circuit synthesis
- `skidl` — Schematic description
- `pyspice` — SPICE simulation
- `langchain` — LLM framework
- `faiss-cpu` — Vector similarity search
- `sentence-transformers` — Embedding generation
- `scikit-learn` — Evaluation metrics
- `pydantic` — Data validation

## License

See individual project files for licensing information.