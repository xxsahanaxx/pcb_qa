# PCB Question Answer Benchmark

A benchmarking framework for evaluating Large Language Models (LLMs) on their ability to analyse and answer questions about PCB circuit designs. Supports multiple design source formats including KiCad netlists, SPICE circuits, hierarchical JSON representations, and schematic PDFs.

The framework asks an LLM about the components, connectivity, and electrical behaviour of real open-source hardware designs and scores its responses against ground-truth answers across several input modalities (native vs. proposed netlist, native vs. proposed circuit, and schematic PDF).

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
│       ├── __main__.py             # CLI entry-point (run, evaluate, embed, …)
│       ├── config.py               # Central path, env & LLM configuration
│       ├── logging_config.py       # Structured logging setup
│       ├── models/
│       │   ├── __init__.py
│       │   ├── project.py          # Project & ProjectFiles dataclasses
│       │   └── tool_definitions.py # LLM tool schemas, ToolMode enum & tools_for_mode()
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── circuit_json.py     # Hierarchical circuit JSON parser + find_component()
│       │   ├── netlist.py          # KiCad .net → JSON converter
│       │   ├── netlist_sexp.py     # S-expression wrappers for netlists
│       │   ├── hierarchical_reader.py  # Sheet hierarchy analysis
│       │   └── spice.py            # SPICE .cir parser & simulator interface
│       ├── kicad/
│       │   ├── __init__.py
│       │   └── cli.py              # kicad-cli wrapper
│       ├── tools/
│       │   ├── __init__.py
│       │   └── caller.py           # LLM tool-calling interface
│       ├── evaluation/
│       │   ├── __init__.py
│       │   └── evaluator.py        # Benchmark evaluation, metrics & agent runners
│       └── utils/
│           ├── __init__.py
│           └── file_ops.py         # JSON & CSV file I/O helpers, save_debug_json()
├── tests/                          # Pytest suite (mirrors src/pcb_qa layout)
│   ├── conftest.py
│   ├── test_circuit_json.py
│   ├── test_config.py
│   ├── test_evaluator.py
│   ├── test_file_ops.py
│   ├── test_kicad_cli.py
│   ├── test_logging_config.py
│   ├── test_main.py
│   ├── test_project.py
│   ├── test_prompt_runner.py
│   ├── test_spice.py
│   ├── test_tool_caller.py
│   └── test_tool_definitions.py
├── OSHP_files/                     # Open-source hardware project files
└── outputs/                        # Generated outputs per project
```

---

## Supported Design Sources

| Format | Module | Description |
|--------|--------|-------------|
| KiCad Netlist (`.net`) | `parsers/netlist.py` | S-expression format from KiCad schematics |
| KiCad Schematic (`.kicad_sch`) | `kicad/cli.py` | Converted to `.net` / `.cir` via `kicad-cli` |
| SPICE Circuit (`.cir`) | `parsers/spice.py` | Circuit simulation descriptions |
| Hierarchical JSON | `parsers/circuit_json.py` | Structured circuit representation |

---

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

# Install test dependencies
uv sync --extra dev
# or
pip install pytest
```

The package targets **Python 3.13+**.

---

## Configuration

### Environment Variables

Copy the template and fill in your paths:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `KICAD_CLI_PATH` | Path to `kicad-cli` binary | — (required for KiCad exports) |
| `NGSPICE_PATH` | Path to `ngspice` binary | `ngspice` |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM calls | — (required for `pcb-qa run`) |
| `OPENROUTER_BASE_URL` | OpenRouter base URL | `https://openrouter.ai/api/v1` |
| `EMBEDDING_MODEL_NAME` | Sentence-transformer model for datasheet embeddings | `all-MiniLM-L6-v2` |

### Project Registry

Define test projects in `configs/projects.json`. Each entry maps a project name to its file layout:

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

These entries are loaded by `pcb_qa.config.load_projects_config()` and surfaced as `pcb_qa.models.project.Project` objects via the `ProjectFiles` registry.

---

## Usage

### CLI Commands

The package exposes two console scripts (see `pyproject.toml`):

```bash
# List configured projects and their file paths
pcb-qa projects

# Initialise the kicad-cli symlink (requires KICAD_CLI_PATH)
pcb-qa init-kicad

# Embed datasheets for all projects (FAISS indexing for semantic search)
pcb-qa embed

# Run the full evaluation pipeline (one CSV per (model, project, mode))
pcb-qa evaluate
```

A dedicated evaluator entry-point is also installed:

```bash
pcb-qa-evaluate
```

Both commands internally instantiate `pcb_qa.evaluation.evaluator.EvaluateResults` and run all five benchmark modes.

### Running Prompt Agents

The LLM agent functions live in `pcb_qa.evaluation.evaluator` and are accessible via the CLI:

```bash
# Run agents with the default mode (NNet&NCir)
pcb-qa run

# Run with a specific mode
pcb-qa run --tool-mode "NNet&PCir"
```

| Agent function | Default mode | Description |
|----------------|--------------|-------------|
| `ask_agent` | `NNET_AND_NCIR` | Full tool-calling agent (datasheets + SPICE + connectivity) |
| `ask_agent_primitive` | `PNET_AND_PCIR` | Direct reasoning with raw netlist + SPICE contents |
| `ask_agent_with_json_netlist_and_spice_circuit` | `NNET_AND_PCIR` | JSON netlist + raw SPICE tool calls |
| `ask_agent_with_json_spice_and_netlist` | `PNET_AND_NCIR` | Raw netlist + JSON SPICE tool calls |
| `ask_agent_with_schematic_as_pdf` | `PDF` | Vision-style PDF schematic input |

The CLI loops over `DEFAULT_LLM_MODELS` from `pcb_qa.config` and all configured projects, writing one JSON result per question to `<project>/<mode>/<model>/<category>/<idx>.json`.

### Python API

```python
from pcb_qa.config import load_projects_config
from pcb_qa.models.project import ProjectFiles
from pcb_qa.parsers.circuit_json import CircuitJSON
from pcb_qa.parsers.netlist import KiCadNetlistProcesser
from pcb_qa.parsers.spice import KiCadSPICECircuitProcesser
from pcb_qa.tools.caller import ToolCaller
from pcb_qa.evaluation.evaluator import EvaluateResults

# Load project configuration
projects = ProjectFiles()  # reads configs/projects.json
acorn = projects["AcornRobotElectronics"]

# Query a hierarchical circuit JSON
circuit = CircuitJSON(circuit_file=acorn.circuit_json_file)
is_connected = circuit.is_component_in_net_from_circuit("C18", "GND")

# Convert a KiCad netlist to hierarchical JSON
processer = KiCadNetlistProcesser(netlist_path=acorn.netlist_file)
processer.convert_project_netlist_to_circuit()
processer.export_circuit_to_file()

# Parse and simulate a SPICE circuit
spice = KiCadSPICECircuitProcesser(
    spice_circuit_path=acorn.spice_circuit_file,
    output_file=acorn.spice_json_file,
)
spice.run_ngspice_simulation(acorn.spice_circuit_file, "spice.log")
spice.parse_spice_simulated_data(acorn.spice_circuit_file.replace(".cir", "_raw.raw"))

# Expose analysis functions as LLM tools
caller = ToolCaller()
caller.embed_datasheet(acorn.datasheet_files[0])  # creates FAISS index
context_chunks = caller.get_relevant_context_from_question(
    question="Is C18 rated for 25V?",
    project_context={
        "circuit_json_file": acorn.circuit_json_file,
        "spice_json_file": acorn.spice_json_file,
        "datasheet_files": acorn.datasheet_files,
    },
    component_ref="C18",
)

# Score the LLM responses that the prompt runner wrote to disk
evaluator = EvaluateResults()
evaluator.write_nnet_and_ncir_responses_to_csv()
evaluator.write_nnet_and_pcir_responses_to_csv()
evaluator.write_pnet_and_ncir_responses_to_csv()
evaluator.write_pnet_and_pcir_responses_to_csv()
evaluator.write_schematic_as_pdfs_responses_to_csv()
```

---

## Benchmark Modes

Each mode is a value of the `pcb_qa.models.tool_definitions.ToolMode` enum and pairs one netlist format with one circuit format (`N` = native, `P` = proposed). The tool definitions for each mode are selected by `pcb_qa.models.tool_definitions.tools_for_mode()`.

| Mode | Netlist | Circuit | Description |
|------|---------|---------|-------------|
| `NNet&NCir` | KiCad `.net` | `.cir` | Native netlist + native SPICE circuit; full tool set |
| `NNet&PCir` | KiCad `.net` | JSON circuit | Native netlist + proposed JSON circuit |
| `PNet&NCir` | JSON netlist | `.cir` | Proposed JSON netlist + native circuit |
| `PNet&PCir` | JSON netlist | JSON circuit | Proposed JSON netlist + proposed JSON circuit |
| `PDF` | — | Schematic PDF | Vision-style: schematic rendered to PDF, sent to the LLM |

The evaluator writes one CSV per (model, project, mode) to `<project>/results/<mode>/<model>_<project>.csv`, containing per-question predictions plus an `Accuracy / Precision / Recall / F1` summary row.

---

## LLM Tools

The framework exposes the following tools to LLMs during question answering. Schemas live in `pcb_qa.models.tool_definitions.ToolDefinitions`; implementations live in `pcb_qa.tools.caller.ToolCaller`.

| Tool | Description |
|------|-------------|
| `get_relevant_context_from_question` | Semantic search over component datasheets (FAISS + `sentence-transformers`) |
| `calculate_spice_behaviour` | Verify steady-state voltage at a given net by reading the SPICE simulation JSON |
| `find_connections_for_component` | Check if a component reference is connected to a net in the hierarchical circuit JSON |

Each LLM call is expected to return a structured `QuestionReasoning` (`{answer: bool, reasoning: str, is_final: bool}`) which is normalised to `YES` / `NO` before being written to disk.

---

## LLM Models

By default, the benchmark runs against the models defined in `pcb_qa.config.DEFAULT_LLM_MODELS`:

- `claude-sonnet-4.6`
- `gemini-3-flash-preview`
- `gpt-5.4-nano`
- `llama-3.3-70b-instruct`

All LLM traffic is routed through OpenRouter (`OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL`).

---

## Test Projects

The included hardware projects live in `OSHP_files/` and are registered in `configs/projects.json`. Each project directory in `outputs/<Project>/` is expected to contain its `circuit_json_file`, `netlist_file`, `spice_circuit_file`, `spice_json_file`, `questions_json_file`, a `datasheets/` folder, and a `results/` tree.

| Project | Type |
|---------|------|
| `acorn-robot-electronics` | Solar-powered farming rover/robot with steering and drive motors per wheel |
| `CF-Chef` | Controller for custom composite curing ovens |
| `fan_controller` | Simple PWM fan controller for 5V or 12V fans with I2C support or potentiometer-based control |
| `HadesFCS` | Flight controller system with peripheral support |
| `Meshinger` | Handheld wireless router with a battery, eInk display, SD card and keyboard |
| `OPNhydro-r2` | Hydroponic systems controller, monitoring soil pH, humidity, air temperature and remote access |
| `PortalHardware` | Compact NFC-based hardware wallet to secure, store and transfer Bitcoin |
| `stack-chan` | Interactive robot programmed to emote for communicating with humans |

---

## Development

### Tests

Run the pytest suite (configured in `pyproject.toml` under `[tool.pytest.ini_options]`):

```bash
uv run pytest
# or
pytest
```

Tests live in `tests/` and mirror the package layout: `test_circuit_json.py`, `test_config.py`, `test_evaluator.py`, `test_file_ops.py`, `test_kicad_cli.py`, `test_logging_config.py`, `test_main.py`, `test_project.py`, `test_prompt_runner.py`, `test_spice.py`, `test_tool_caller.py`, `test_tool_definitions.py`.

### Logging

`pcb_qa.logging_config.setup_logging()` configures a single root logger named `pcb_qa` with a `StreamHandler` on `sys.stdout`. All modules use the module-level `logger = setup_logging()` instance for consistent log format (`%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`).

### Linting

Ruff is configured in `pyproject.toml` (target Python 3.13, line length 120, rules `E, F, W, I, N, UP`):

```bash
uv run ruff check .
uv run ruff format .
```

---

## Dependencies

Key packages (see `pyproject.toml`):

- `circuit-synth` — Circuit synthesis
- `skidl` — Schematic description & S-expression helpers
- `pyspice` / `spyci` — SPICE simulation and raw-file parsing
- `langchain` / `langchain-classic` / `langchain-ollama` — LLM framework integrations
- `openrouter` / `openai` — LLM client (OpenRouter-compatible)
- `faiss-cpu` — Vector similarity search
- `sentence-transformers` — Embedding generation
- `pdfplumber` — PDF text extraction (datasheet ingestion)
- `reportlab` / `matplotlib` — Schematic PDF rendering & plotting
- `pandas` / `numpy` / `scikit-learn` — Evaluation metrics
- `pydantic` — Data validation
- `simp_sexp` — S-expression parsing
- `wget` — Dataset download helper

---

## License

See individual project files for licensing information.