# PCB Question Answer Benchmark

A benchmarking method for evaluating Large Language Models (LLMs)' ability to analyse and answer questions about PCB circuit designs using various design sources (netlist files, SPICE circuit descriptions, hierarchical JSON representations, and combinations thereof).

## Overview

This project consists of the following subprocesses:

- **Circuit JSON generation** — Convert KiCad netlists to hierarchical JSON
- **Question generation** — YES/NO design questions manually generated as ground truth
- **Metrics computation** — Accuracy, precision, recall, F1 scores

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

### 3. Run the Benchmark

```bash
uv run --env-file .env python prompt_runner.py
```

## Project Structure

```
test_circuit_synth_and_skidl/
├── main.py                          # Entry point
├── preprocess_netlists.py          # Core netlist processing
├── kicad_netlist_processer.py       # High-level netlist wrapper
├── circuit_json.py                 # Circuit JSON representation
├── kicad_spice_circuit_processer.py # SPICE processing
├── prompt_runner.py                # LLM integration
├── design_question_answerer.py     # Question answering agent
├── evaluate_results.py              # Metrics computation
├── project_files.py                 # Project configuration
├── agents/
│   └── design_question_generator.py
├── OSHP_files/                      # Test hardware projects
│   ├── HadesFCS_hardware/
│   ├── acorn-robot-electronics/
│   ├── CF-Chef/
│   └── ...
├── outputs/                         # Generated outputs
└── docs/                            # Documentation
    ├── architecture.md
    ├── schema.md
    ├── workflow.md
    ├── evaluation.md
    └── troubleshooting.md
```

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# LLM Provider API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...

# Vector Store
FAISS_INDEX_PATH=vector_store/faiss.index
```

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

## Usage

### Netlist Export

```python
from kicad_cli_helpers import export_netlist

export_netlist(
    schematic_path="OSHP_files/HadesFCS_hardware/FCC.kicad_sch",
    output_path="outputs/FCC.net"
)
```

### Circuit JSON Generation

```python
from preprocess_netlists import NetlistPreprocesser

preprocessor = NetlistPreprocesser()
circuit_json = preprocessor.process(
    netlist_path="outputs/FCC.net",
    output_path="outputs/FCC.json"
)
```

### Question Generation

```python
from agents.design_question_generator import DesignQuestionGenerationAgent

agent = DesignQuestionGenerationAgent(model="gpt-4o")
questions = agent.generate_basic_questions(circuit_json)
agent.save_questions(questions, "outputs/questions.json")
```

### LLM Evaluation

```python
from prompt_runner import PromptRunner

runner = PromptRunner(model="claude-sonnet")
results = runner.evaluate_questions(
    questions_path="outputs/questions.json",
    circuit_json_path="outputs/circuit.json"
)
```

### Metrics Computation

```python
from evaluate_results import EvaluateResults

evaluator = EvaluateResults()
metrics = evaluator.compute_metrics(
    results_dir="outputs/results/",
    project_name="HadesFCS"
)

print(f"Accuracy: {metrics['accuracy']:.2%}")
print(f"F1 Score: {metrics['f1']:.2%}")
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