# Question Bank Generation Workflow

This document explains how to use `question_generation_prompts.md` to generate questions and integrate them into the question_banks directory.

## Overview

The question generation workflow uses three categories of questions defined in `question_generation_prompts.md`:

1. **component_datasheet**: Questions about component specifications verified against datasheets
2. **spice_behaviour**: Questions about SPICE simulation voltage levels
3. **theory_layout**: Questions about component-to-net connectivity in the PCB layout

## How to Use question_generation_prompts.md

The `question_generation_prompts.md` file serves as the authoritative reference for question generation. It contains:

- Purpose and scope for each question category
- Key observations from existing question banks
- Recommended LLM prompts for generating questions
- Question format templates
- Example questions

### Accessing the Prompts

```python
from pcb_qa.question_banks.prompts import get_prompts_path, get_prompts_text

# Get the file path
path = get_prompts_path()
print(f"Prompts file located at: {path}")

# Get the full text content
text = get_prompts_text()
print(text)
```

### Using Prompts with LLMs

When using an LLM to generate questions, pass the entire `question_generation_prompts.md` content as context:

```python
from pcb_qa.question_banks.prompts import get_prompts_text

# Load prompts
prompts_text = get_prompts_text()

# Include in LLM prompt
llm_prompt = f"""
{prompts_text}

Now generate questions for the following project data:
[Insert project-specific circuit data here]
"""
```

## Generating Questions

### Basic Usage

Generate 240 balanced questions (80 per category) for all configured projects:

```bash
python -m pcb_qa.question_banks.cli expand
```

This command:
1. Reads project configurations from `configs/projects.json`
2. Generates 80 questions per category for each project
3. Deduplicates against existing question files
4. Shuffles the final question list
5. Saves to `{project}_60_questions_balanced.json`

### Programmatic Usage

```python
from pcb_qa.question_banks import expand_question_bank_for_project

# Generate questions for a single project
questions = expand_question_bank_for_project(
    circuit_json_file="./outputs/CF-Chef/controller.json",
    spice_json_file="./outputs/CF-Chef/CF-Chef_SPICE_circuit.json",
    existing_questions_file="./outputs/CF-Chef/CF-Chef_60_questions.json",
    output_file="./outputs/CF-Chef/CF-Chef_240_questions_balanced.json",
    total_questions=240,
    shuffle=True
)

print(f"Generated {len(questions)} questions")
```

### Customization Options

```python
questions = expand_question_bank_for_project(
    circuit_json_file="path/to/circuit.json",
    spice_json_file="path/to/spice.json",
    existing_questions_file=None,  # No deduplication against existing file
    output_file="custom_output.json",  # Save to specific file
    total_questions=120,  # Generate 120 questions (40 per category)
    shuffle=False  # Keep questions ordered by category
)
```

## Question Validation

All generated questions can be validated against the JSON design files:

```bash
python -m pcb_qa.question_banks.cli validate
```

This validates:
- **component_datasheet**: Checks component references exist in circuit JSON
- **spice_behaviour**: Verifies voltage claims against SPICE simulation data
- **theory_layout**: Confirms connectivity claims against circuit JSON

### Programmatic Validation

```python
from pcb_qa.question_banks import CircuitQuestionValidator

validator = CircuitQuestionValidator(
    circuit_json_file="./outputs/CF-Chef/controller.json",
    spice_json_file="./outputs/CF-Chef/CF-Chef_SPICE_circuit.json"
)

report = validator.validate_questions(questions)
print(f"Valid: {report['categories']['spice_behaviour']['valid']}")
print(f"Invalid: {report['categories']['spice_behaviour']['invalid']}")
```

## Fixing Invalid Questions

If validation finds invalid questions, fix them:

```bash
python -m pcb_qa.question_banks.cli fix
```

This corrects:
- Invalid net names in SPICE questions
- Incorrect answers based on actual SPICE data
- Wrong connectivity claims in layout questions

## Deduplication Mechanism

The workflow includes automatic deduplication at multiple levels:

### 1. Within-Generation Deduplication

Each question generation function maintains a set of already-generated questions to avoid duplicates within the same session:

```python
# In generate_datasheet_questions_balanced()
if not any(q['question'] == question for q in questions):
    questions.append({...})
```

### 2. Cross-File Deduplication

The `expand_question_bank_for_project()` function loads existing questions and filters duplicates:

```python
existing_questions: set[str] = set()
if existing_questions_file:
    with open(existing_questions_file, 'r') as f:
        existing_data = json.load(f)
        existing_questions = {q['question'] for q in existing_data if 'question' in q}
```

### 3. Session-Wide Deduplication

A `generated_questions` set tracks all questions generated in the current session to prevent duplicates across categories:

```python
generated_questions: set[str] = set()

def deduplicate_questions(questions):
    unique = []
    for q in questions:
        q_text = q.get('question', '')
        if q_text not in existing_questions and q_text not in generated_questions:
            unique.append(q)
            generated_questions.add(q_text)
    return unique
```

## Question Shuffling

The final question list is shuffled to prevent ordering biases:

```python
import random

# Shuffle is enabled by default
questions = expand_question_bank_for_project(
    ...,
    shuffle=True  # Randomizes question order
)

# Disable shuffling if needed
questions = expand_question_bank_for_project(
    ...,
    shuffle=False  # Keeps questions grouped by category
)
```

The shuffling uses Python's `random.shuffle()` which provides uniform randomization.

## JSON Design File Querying for Answer Verification

### SPICE Data Queries

SPICE questions are verified against simulation results:

```python
from pcb_qa.question_banks.validator import load_spice_data

# Load SPICE voltage data
spice_data = load_spice_data("./outputs/CF-Chef/CF-Chef_SPICE_circuit.json")

# Check if net voltage matches expected value
net_name = "+3v3"
actual_voltage = spice_data.get(net_name)
print(f"Net {net_name} has voltage: {actual_voltage}V")
```

### Circuit JSON Queries

Layout questions are verified against the circuit schematic:

```python
from pcb_qa.parsers.circuit_json import CircuitJSON

circuit = CircuitJSON(circuit_file="./outputs/CF-Chef/controller.json")

# Check if component is connected to a net
is_connected = circuit.is_component_in_net_from_circuit("U1", "GND")
print(f"U1 connected to GND: {is_connected}")
```

## Complete Workflow Example

```python
from pcb_qa.question_banks import (
    expand_question_bank_for_project,
    CircuitQuestionValidator,
    QuestionBankFixer
)

# Step 1: Generate questions
questions = expand_question_bank_for_project(
    circuit_json_file="./outputs/CF-Chef/controller.json",
    spice_json_file="./outputs/CF-Chef/CF-Chef_SPICE_circuit.json",
    existing_questions_file="./outputs/CF-Chef/CF-Chef_60_questions.json",
    output_file="./outputs/CF-Chef/CF-Chef_240_questions_balanced.json",
    total_questions=240,
    shuffle=True
)

# Step 2: Validate questions
validator = CircuitQuestionValidator(
    circuit_json_file="./outputs/CF-Chef/controller.json",
    spice_json_file="./outputs/CF-Chef/CF-Chef_SPICE_circuit.json"
)
report = validator.validate_questions(questions)

# Step 3: Fix invalid questions (if any)
if report['categories']['spice_behaviour']['invalid'] > 0:
    fixer = QuestionBankFixer(
        circuit_json_file="./outputs/CF-Chef/controller.json",
        spice_json_file="./outputs/CF-Chef/CF-Chef_SPICE_circuit.json"
    )
    replaced_count, fixed_count = fixer.fix_question_bank(questions)

    # Save fixed questions
    with open("./outputs/CF-Chef/CF-Chef_240_questions_balanced.json", 'w') as f:
        json.dump(questions, f, indent=2)

# Step 4: Verify final counts
print(f"Total questions: {len(questions)}")
print(f"Datasheet: {report['categories']['component_datasheet']['valid']} valid")
print(f"SPICE: {report['categories']['spice_behaviour']['valid']} valid")
print(f"Layout: {report['categories']['theory_layout']['valid']} valid")
```

## Answer Verification Strategy

The system uses multiple strategies to ensure answer correctness:

### YES Answers

**component_datasheet**: Questions with YES answers follow the datasheet property templates. While full semantic validation requires LLM-based datasheet analysis, the system ensures:
- Component references are valid
- Property names are from the approved list
- Format is consistent

**spice_behaviour**: YES answers are verified by comparing the voltage in the question against actual SPICE simulation data:
```python
actual_voltage = spice_data[net_name]
expected_voltage = float(voltage_match.group(1))
is_correct = abs(actual_voltage - expected_voltage) < 0.5
```

**theory_layout**: YES answers are verified by querying the circuit JSON:
```python
is_connected = circuit.is_component_in_net_from_circuit(component_ref, net_name)
```

### NO Answers

NO answers are the logical inverse:
- **spice_behaviour**: The voltage in the question does NOT match actual SPICE data
- **theory_layout**: The component is NOT connected to the specified net

## Best Practices

1. **Always validate after generation**: Run validation to catch any invalid questions
2. **Use deduplication**: Always provide existing question files to avoid duplicates
3. **Shuffle questions**: Enable shuffling for unbiased evaluation
4. **Balance categories**: Generate equal numbers per category for fair benchmarking
5. **Verify file paths**: Ensure circuit JSON and SPICE JSON files exist before generation
6. **Check output counts**: Monitor that each category generates the expected number of questions

## Troubleshooting

### Not enough unique questions generated

If deduplication prevents reaching the target count:
- Increase the generation multiplier (currently 2x)
- Check if existing question files are too large
- Verify that the circuit has enough components/nets

### Validation failures

If many questions fail validation:
- Verify circuit JSON file is correct
- Check SPICE simulation completed successfully
- Ensure net names are consistent between files

### Invalid answers after fixing

If fixes don't work:
- Run validation again to see remaining issues
- Manually inspect the circuit JSON for the specific components/nets
- Check SPICE data format and units