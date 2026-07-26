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
│       ├── question_banks/
│       │   ├── __init__.py
│       │   ├── cli.py              # CLI for question bank operations
│       │   ├── generator.py        # Question generation utilities
│       │   ├── validator.py        # Question validation against ground truth
│       │   ├── fixer.py            # Question repair utilities
│       │   ├── models.py           # Question and QuestionBank dataclasses
│       │   ├── prompts.py          # Programmatic access to question generation prompts
│       │   └── question_generation_prompts.md  # Canonical LLM prompts for each question category
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── evaluator.py        # EvaluateResults metrics + CLI entry-point
│       │   ├── agents.py           # LLM agent runners (ask_agent, ask_agent_primitive, …)
│       │   └── runner.py           # Benchmark orchestration (run_benchmark)
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

The package exposes console scripts for various operations:

```bash
# List configured projects and their file paths
pcb-qa projects

# Initialise the kicad-cli symlink (requires KICAD_CLI_PATH)
pcb-qa init-kicad

# Embed datasheets for all projects (FAISS indexing for semantic search)
pcb-qa embed

# Run the full evaluation pipeline
pcb-qa evaluate
```

#### Question Bank Commands

Generate and manage question banks using the `pcb-qa-questions` CLI:

```bash
# Generate balanced question banks for all configured projects
pcb-qa-questions expand

# Validate existing question banks against reference designs
pcb-qa-questions validate

# Fix invalid questions in question banks
pcb-qa-questions fix
```

### Running Prompt Agents

The benchmark runner is integrated into the `pcb_qa` package and accessible via the CLI:

```bash
# Run the benchmarking loop directly (uses ask_agent_primitive by default)
pcb-qa run

# Run with a specific tool mode
pcb-qa run --mode NNet&PCir

# Resume from a specific question index
pcb-qa run --start 30
```

Alternatively, invoke it programmatically:

```python
from pcb_qa.evaluation.runner import run_benchmark
from pcb_qa.models.tool_definitions import ToolMode

run_benchmark(
    tool_mode=ToolMode.NNET_AND_NCIR,
    starting_index=0,
)
```

| Agent function | Default mode | Description | Location |
|----------------|--------------|-------------|----------|
| `ask_agent` | `NNET_AND_NCIR` | Full tool-calling agent (datasheets + SPICE + connectivity) | `pcb_qa.evaluation.agents` |
| `ask_agent_primitive` | `PNET_AND_PCIR` | Direct reasoning with raw netlist + SPICE contents | `pcb_qa.evaluation.agents` |
| `ask_agent_with_json_netlist_and_spice_circuit` | `NNET_AND_PCIR` | JSON netlist + raw SPICE tool calls | `pcb_qa.evaluation.agents` |
| `ask_agent_with_json_spice_and_netlist` | `PNET_AND_NCIR` | Raw netlist + JSON SPICE tool calls | `pcb_qa.evaluation.agents` |
| `ask_agent_with_schematic_as_pdf` | `PDF` | Vision-style PDF schematic input | `pcb_qa.evaluation.agents` |
| `run_benchmark` | `NNET_AND_NCIR` | Orchestrates agents across all projects & models | `pcb_qa.evaluation.runner` |

The `run_benchmark()` function loops over `DEFAULT_LLM_MODELS` and all configured projects, writing one JSON result per question to `<project>/<mode>/<model>/<category>/<idx>.json`.

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

### Creating & Managing Question Banks

The `pcb_qa.question_banks` package provides a complete toolkit for generating, validating, fixing, and documenting PCB question banks:

```
question_banks/
├── __init__.py                        # Public API exports
├── cli.py                             # CLI entry points (expand, validate, fix)
├── generator.py                       # Question generation from circuit & SPICE data
├── validator.py                       # Validation against ground-truth circuit/SPICE
├── fixer.py                           # Automated repair of invalid questions
├── models.py                          # Question & QuestionBank data classes
├── prompts.py                         # Programmatic access to LLM prompt templates
└── question_generation_prompts.md     # Canonical LLM prompts for each question category
```

#### Module Overview

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| `generator.py` | Generate balanced YES/NO questions from circuit JSON + SPICE data | `expand_question_bank_for_project()`, `generate_*_questions_balanced()` |
| `validator.py` | Validate questions against reference circuit/SPICE data | `CircuitQuestionValidator` |
| `fixer.py` | Automatically fix invalid net names and wrong answers | `QuestionBankFixer` |
| `models.py` | Data classes for structured question bank access | `Question`, `QuestionBank` |
| `prompts.py` | Load the canonical LLM prompt templates as Python resources | `get_prompts_path()`, `get_prompts_text()` |
| `cli.py` | Command-line interface (used via `pcb-qa-questions`) | `main()` (expand/validate/fix) |

#### Accessing the LLM Prompts

The `question_generation_prompts.md` document contains the canonical LLM prompts used to design each question category. Access it programmatically via the `prompts` module:

```python
from pcb_qa.question_banks import get_prompts_path, get_prompts_text

# Get the filesystem path (for passing to an LLM or other tools)
path = get_prompts_path()
print(f"Prompts file: {path}")

# Get the full markdown text
text = get_prompts_text()

# Print section headings to verify the content
for line in text.splitlines():
    if line.startswith("## "):
        print(line)
```

#### Generating Questions

Generate YES/NO-balanced question banks from your circuit and SPICE data:

```python
from pcb_qa.question_banks import (
    Question, QuestionBank,
    generate_datasheet_questions_balanced,
    generate_spice_questions_balanced,
    generate_layout_questions_balanced,
    CircuitQuestionValidator,
    QuestionBankFixer,
)
from pcb_qa.models.project import ProjectFiles

# Load a project
projects = ProjectFiles()
project = projects["AcornRobotElectronics"]

# 1. Component datasheet questions (about IC specifications)
components = ["U1", "U2", "U3", "R1", "C1"]  # From extract_components_from_circuit()
datasheet_questions = generate_datasheet_questions_balanced(components, count=80)

# 2. SPICE behaviour questions (about voltage levels in simulation)
nets = ["VCC", "GND", "CLK", "DATA"]  # From extract_nets_from_spice()
spice_questions = generate_spice_questions_balanced(nets, project.spice_json_file, count=80)

# 3. Theory/layout questions (about component-to-net connectivity)
connections = {"U1": ["VCC", "GND"], "R1": ["VCC"]}  # From get_component_net_connections()
layout_questions = generate_layout_questions_balanced(connections, nets, count=80)

# Combine all questions into a single list (the JSON format)
all_questions = datasheet_questions + spice_questions + layout_questions

# Optionally wrap with QuestionBank for easy counting and filtering
bank = QuestionBank(all_questions)
print(f"Total questions: {len(bank)}")
print(f"Per category: {bank.count_by_category()}")
print(f"Answer distribution: {bank.count_answers_by_category()}")

# Validate the question bank
validator = CircuitQuestionValidator(
    circuit_json_file=project.circuit_json_file,
    spice_json_file=project.spice_json_file,
)
report = validator.validate_questions(all_questions)
print(f"Valid questions: {report['categories']['spice_behaviour']['valid']}")

# Fix any invalid questions
fixer = QuestionBankFixer(
    circuit_json_file=project.circuit_json_file,
    spice_json_file=project.spice_json_file,
)
fixer.fix_question_bank(all_questions)

# Save to JSON (the JSON format is a plain list of dicts)
with open("questions.json", "w") as f:
    json.dump(all_questions, f, indent=2)
```

#### Question Categories

The framework generates three types of questions, each designed from the prompts in `question_generation_prompts.md`:

| Category | Description | Generated From |
|----------|-------------|--------------|
| `component_datasheet` | Questions about component specifications (temperature, voltage, current, interfaces, features) | IC component designators |
| `spice_behaviour` | Questions about SPICE simulation voltage levels on nets | SPICE simulation JSON |
| `theory_layout` | Questions about component-to-net connectivity | Circuit JSON connections |

Each question bank contains 240 questions (80 per category) with balanced YES/NO answers.

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

Tests live in `tests/` and mirror the package layout:

| Test file | Module under test |
|-----------|------------------|
| `test_circuit_json.py` | `parsers/circuit_json.py` |
| `test_config.py` | `config.py` |
| `test_evaluator.py` | `evaluation/evaluator.py` |
| `test_file_ops.py` | `utils/file_ops.py` |
| `test_kicad_cli.py` | `kicad/cli.py` |
| `test_logging_config.py` | `logging_config.py` |
| `test_main.py` | `__main__.py` |
| `test_project.py` | `models/project.py` |
| `test_prompt_runner.py` | *(stale — imports removed API; DEPRECATED)* |
| `test_spice.py` | `parsers/spice.py` |
| `test_tool_caller.py` | `tools/caller.py` |
| `test_tool_definitions.py` | `models/tool_definitions.py` |
| `test_question_banks_models.py` | `question_banks/models.py` |
| `test_question_banks_prompts.py` | `question_banks/prompts.py` |
| `test_question_banks_generator.py` | `question_banks/generator.py` |
| `test_question_banks_validator.py` | `question_banks/validator.py` |
| `test_question_banks_fixer.py` | `question_banks/fixer.py` |

Run tests for a specific module:

```bash
# All question_banks tests (94 tests)
uv run pytest tests/test_question_banks_*.py -v

# Or run the full suite
uv run pytest
```

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