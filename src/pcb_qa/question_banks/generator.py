"""Question bank generation utilities.

This module provides functions for generating questions from PCB circuit JSON and SPICE simulation files.

The module generates three types of questions:
- component_datasheet: Questions about component specifications (temperature, voltage, current, interfaces, features)
- spice_behaviour: Questions about SPICE simulation results (voltage levels on nets)
- theory_layout: Questions about component-to-net connectivity

The complete LLM prompts used to design these generation templates are available in
:mod:`pcb_qa.question_banks.prompts` (``question_generation_prompts.md``).
"""

from __future__ import annotations

import json
import random

from pcb_qa.question_banks.validator import load_spice_data

# Question templates based on question_generation_prompts.md
DATASHEET_PROPERTIES = [
    ("temperature", "maximum operating temperature of {value}°C"),
    ("temperature", "minimum operating temperature of {value}°C"),
    ("temperature", "maximum junction temperature of {value}°C"),
    ("temperature", "minimum operating ambient temperature of {value}°C"),
    ("voltage", "maximum supply voltage of {value}V"),
    ("voltage", "minimum operating voltage of {value}V"),
    ("current", "maximum current of {value}A"),
    ("current", "quiescent current of {value}µA"),
    ("interface", "I2C capabilities"),
    ("interface", "SPI capabilities"),
    ("interface", "UART capabilities"),
    ("interface", "CAN capabilities"),
    ("interface", "USB capabilities"),
    ("interface", "Ethernet capabilities"),
    ("interface", "WiFi capabilities"),
    ("interface", "Bluetooth capabilities"),
    ("feature", "flash capabilities"),
    ("feature", "memory capabilities"),
    ("feature", "PWM module"),
    ("feature", "ADC capabilities"),
    ("feature", "DAC capabilities"),
    ("feature", "magnetic sensor capabilities"),
    ("feature", "motion sensor capabilities"),
    ("feature", "internal CAN clock"),
]

VOLTAGE_LEVELS = ["0", "3.3", "5", "12"]

SPICE_QUESTION_TEMPLATES = [
    "Does the net {net_name} maintain a voltage of {voltage}V during the entire simulation?",
    "Does the {signal_name} signal maintain a voltage of ~{voltage}V during the entire simulation?",
    "Does the net {net_name} obtain a steady state of ~{voltage}V after the entire simulation?",
    "Is the {signal_name} signal at {voltage}V for the entire simulation?",
    "Is the {power_rail} power rail stable at approximately {voltage}V throughout the simulation?",
]


def extract_components_from_circuit(circuit_json_file: str) -> list[str]:
    """Extract all component references from a circuit JSON file.

    Args:
        circuit_json_file: Path to the circuit JSON file.

    Returns:
        List of component reference designators (e.g., ['R1', 'C2', 'U3']).
    """
    try:
        with open(circuit_json_file, 'r') as f:
            data = json.load(f)

        components = list(data.get('components', {}).keys())
        for subcircuit in data.get('subcircuits', []):
            components.extend(subcircuit.get('components', {}).keys())
        return components
    except Exception as e:
        print(f"Error extracting components: {e}")
        return []


def extract_nets_from_circuit(circuit_json_file: str) -> list[str]:
    """Extract all net names from a circuit JSON file.

    Args:
        circuit_json_file: Path to the circuit JSON file.

    Returns:
        List of net names.
    """
    try:
        with open(circuit_json_file, 'r') as f:
            data = json.load(f)

        nets = list(data.get('nets', {}).keys())
        for subcircuit in data.get('subcircuits', []):
            nets.extend(subcircuit.get('nets', {}).keys())
        return list(set(nets))
    except Exception as e:
        print(f"Error extracting nets: {e}")
        return []


def extract_nets_from_spice(spice_json_file: str) -> list[str]:
    """Extract all net names from SPICE JSON simulation data.

    Args:
        spice_json_file: Path to the SPICE simulation JSON file.

    Returns:
        List of net names found in the SPICE data.
    """
    try:
        with open(spice_json_file, 'r') as f:
            data = json.load(f)

        nets = []
        for key, entry in data.items():
            if isinstance(entry, dict) and 'name' in entry:
                name = entry['name']
                if name.startswith('v('):
                    net = name[2:-1]  # Remove 'v(' and ')'
                    nets.append(net)
        return nets
    except Exception as e:
        print(f"Error extracting SPICE nets: {e}")
        return []


def get_component_net_connections(circuit_json_file: str) -> dict[str, list[str]]:
    """Get a mapping of component -> list of connected nets.

    Args:
        circuit_json_file: Path to the circuit JSON file.

    Returns:
        Dictionary mapping component references to lists of connected net names.
    """
    try:
        with open(circuit_json_file, 'r') as f:
            data = json.load(f)

        connections: dict[str, list[str]] = {}

        all_comps = set(data.get('components', {}).keys())
        for subcircuit in data.get('subcircuits', []):
            all_comps.update(subcircuit.get('components', {}).keys())

        for comp in all_comps:
            comp_nets = []
            for net_name, connections_list in data.get('nets', {}).items():
                for conn in connections_list:
                    if comp in conn.get('component', ''):
                        comp_nets.append(net_name)
            for subcircuit in data.get('subcircuits', []):
                for net_name, connections_list in subcircuit.get('nets', {}).items():
                    for conn in connections_list:
                        if comp in conn.get('component', ''):
                            comp_nets.append(net_name)

            if comp_nets:
                connections[comp] = list(set(comp_nets))

        return connections
    except Exception as e:
        print(f"Error getting component connections: {e}")
        return {}


def format_property(prop_template: str, prop_type: str) -> str:
    """Format property template with appropriate random values.

    Args:
        prop_template: Property template string with optional {value} placeholder.
        prop_type: Type of property (temperature, voltage, current, interface, feature).

    Returns:
        Formatted property string with value filled in if applicable.
    """
    if "{value}" in prop_template:
        if "temperature" in prop_type:
            value = random.choice(["85", "100", "125", "150", "-40", "-30", "-55"])
        elif "voltage" in prop_type:
            value = random.choice(["3.3", "5", "12", "63", "25"])
        elif "current" in prop_type:
            if "µA" in prop_template:
                value = random.choice(["100", "200", "500", "1000"])
            else:
                value = random.choice(["1.0", "1.5", "2.0", "3.0"])
        else:
            value = "N/A"
        return prop_template.format(value=value)
    return prop_template


def generate_datasheet_questions_balanced(
    components: list[str],
    count: int = 80
) -> list[dict[str, str]]:
    """Generate exactly balanced component_datasheet questions with YES and NO answers.

    Args:
        components: List of component reference designators.
        count: Total number of questions to generate (default: 80, with 40 YES and 40 NO).

    Returns:
        List of question dictionaries with category, question, and answer keys.
    """
    questions: list[dict[str, str]] = []

    ic_components = [c for c in components if c.startswith(('U', 'REG', 'SW', 'D'))]

    if len(ic_components) < 2:
        return questions

    # Generate 40 YES questions
    yes_generated = 0
    attempts = 0
    while yes_generated < count // 2 and attempts < count * 20:
        attempts += 1
        comp = random.choice(ic_components)
        prop_type, prop_template = random.choice(DATASHEET_PROPERTIES)
        prop = format_property(prop_template, prop_type)
        question = f"Does the component {comp} have {prop} according to its datasheet?"
        if not any(q['question'] == question for q in questions):
            questions.append({
                "category": "component_datasheet",
                "question": question,
                "answer": "YES"
            })
            yes_generated += 1

    # Generate 40 NO questions
    no_generated = 0
    attempts = 0
    while no_generated < count // 2 and attempts < count * 20:
        attempts += 1
        comp = random.choice(ic_components)
        prop_type, prop_template = random.choice(DATASHEET_PROPERTIES)
        prop = format_property(prop_template, prop_type)
        question = f"Does the component {comp} have {prop} according to its datasheet?"
        if not any(q['question'] == question for q in questions):
            questions.append({
                "category": "component_datasheet",
                "question": question,
                "answer": "NO"
            })
            no_generated += 1

    return questions[:count]


def generate_spice_questions_balanced(
    nets: list[str],
    spice_json_file: str,
    count: int = 80
) -> list[dict[str, str]]:
    """Generate exactly balanced spice_behaviour questions with YES and NO answers.

    Uses ground truth SPICE data to determine correct answers.

    Args:
        nets: List of net names to generate questions about.
        spice_json_file: Path to SPICE simulation JSON file.
        count: Total number of questions to generate (default: 80).

    Returns:
        List of question dictionaries with category, question, and answer keys.
    """
    questions: list[dict[str, str]] = []

    if not nets:
        return questions

    # Load SPICE data once
    spice_data = load_spice_data(spice_json_file)

    # First, generate 40 YES questions (matching actual voltage)
    yes_generated = 0
    attempts = 0
    while yes_generated < count // 2 and attempts < count * 20:
        attempts += 1
        net = random.choice(nets)
        actual_v = spice_data.get(net)

        if actual_v is None:
            continue

        voltage_str = str(int(actual_v)) if actual_v == int(actual_v) else str(actual_v)
        voltage = voltage_str

        template = random.choice(SPICE_QUESTION_TEMPLATES)

        question = template.format(
            net_name=net,
            signal_name=net.replace('/', '').replace('-', '_'),
            power_rail=net,
            voltage=voltage
        )

        if not any(q['question'] == question for q in questions):
            questions.append({
                "category": "spice_behaviour",
                "question": question,
                "answer": "YES"
            })
            yes_generated += 1

    # Then, generate 40 NO questions (mismatched voltage)
    no_generated = 0
    attempts = 0
    while no_generated < count // 2 and attempts < count * 20:
        attempts += 1
        net = random.choice(nets)
        actual_v = spice_data.get(net)

        if actual_v is None:
            continue

        all_voltages = ["0", "3.3", "5", "12"]
        mismatched = [v for v in all_voltages if abs(float(v) - actual_v) > 0.1]
        if not mismatched:
            mismatched = all_voltages

        voltage = random.choice(mismatched)
        template = random.choice(SPICE_QUESTION_TEMPLATES)

        question = template.format(
            net_name=net,
            signal_name=net.replace('/', '').replace('-', '_'),
            power_rail=net,
            voltage=voltage
        )

        if not any(q['question'] == question for q in questions):
            questions.append({
                "category": "spice_behaviour",
                "question": question,
                "answer": "NO"
            })
            no_generated += 1

    return questions[:count]


def generate_layout_questions_balanced(
    component_connections: dict[str, list[str]],
    available_nets: list[str],
    count: int = 80
) -> list[dict[str, str]]:
    """Generate exactly balanced theory_layout questions with YES and NO answers.

    Uses ground truth circuit data to determine correct answers.

    Args:
        component_connections: Dictionary mapping components to their connected nets.
        available_nets: List of all available net names.
        count: Total number of questions to generate (default: 80).

    Returns:
        List of question dictionaries with category, question, and answer keys.
    """
    questions: list[dict[str, str]] = []

    if not component_connections or not available_nets:
        return questions

    components = list(component_connections.keys())
    yes_count = 0
    no_count = 0
    attempts = 0
    max_attempts = count * 20

    while len(questions) < count and attempts < max_attempts:
        attempts += 1

        if yes_count >= count // 2:
            want_true = False
        elif no_count >= count // 2:
            want_true = True
        else:
            want_true = random.random() > 0.5

        if want_true:
            comp = random.choice(components)
            if component_connections[comp]:
                net = random.choice(component_connections[comp])
            else:
                continue
        else:
            comp = random.choice(components)
            possible_nets = [n for n in available_nets if n not in component_connections.get(comp, [])]
            if not possible_nets:
                continue
            net = random.choice(possible_nets)

        question = f"Is the component {comp} connected to {net}?"

        if any(q['question'] == question for q in questions):
            continue

        questions.append({
            "category": "theory_layout",
            "question": question,
            "answer": "YES" if want_true else "NO"
        })

        if want_true:
            yes_count += 1
        else:
            no_count += 1

    return questions[:count]


def expand_question_bank_for_project(
    circuit_json_file: str,
    spice_json_file: str,
    existing_questions_file: str | None = None,
    output_file: str | None = None,
    total_questions: int = 240,
    shuffle: bool = True
) -> list[dict[str, str]]:
    """Generate exactly balanced questions for a project with deduplication and shuffling.

    Args:
        circuit_json_file: Path to the circuit JSON file.
        spice_json_file: Path to the SPICE simulation JSON file.
        existing_questions_file: Optional path to existing questions file for deduplication.
        output_file: Optional path to save the generated questions.
        total_questions: Total number of questions to generate (default: 240).
        shuffle: Whether to shuffle the final question list (default: True).

    Returns:
        List of question dictionaries with balanced YES/NO answers across categories.
    """
    components = extract_components_from_circuit(circuit_json_file)
    nets = extract_nets_from_circuit(circuit_json_file)
    spice_nets = extract_nets_from_spice(spice_json_file)
    component_connections = get_component_net_connections(circuit_json_file)

    all_nets = list(set(nets + spice_nets))

    # Calculate questions per category
    questions_per_category = total_questions // 3

    # Load existing questions for deduplication if file provided
    existing_questions: set[str] = set()
    if existing_questions_file:
        try:
            with open(existing_questions_file, 'r') as f:
                existing_data = json.load(f)
                existing_questions = {q['question'] for q in existing_data if 'question' in q}
                print(f"    Loaded {len(existing_questions)} existing questions for deduplication")
        except Exception as e:
            print(f"    Warning: Could not load existing questions: {e}")

    # Also deduplicate against questions already generated in this session
    generated_questions: set[str] = set()

    def deduplicate_questions(questions: list[dict[str, str]]) -> list[dict[str, str]]:
        """Remove duplicate questions against existing and previously generated ones."""
        unique = []
        for q in questions:
            q_text = q.get('question', '')
            if q_text and q_text not in existing_questions and q_text not in generated_questions:
                unique.append(q)
                generated_questions.add(q_text)
        return unique

    def take_balanced(questions: list[dict[str, str]], count: int) -> list[dict[str, str]]:
        """Take exactly *count* questions with equal YES and NO answers.

        Splits by answer, takes ``count // 2`` from each half, then
        interleaves so the result is balanced regardless of ordering.
        """
        half = count // 2
        yes_qs = [q for q in questions if q.get('answer') == 'YES'][:half]
        no_qs = [q for q in questions if q.get('answer') == 'NO'][:half]
        result = yes_qs + no_qs
        random.shuffle(result)
        return result

    # Generate questions for each category with deduplication
    datasheet_qs = generate_datasheet_questions_balanced(components, questions_per_category * 2)  # Generate extra to account for deduplication
    datasheet_qs = take_balanced(deduplicate_questions(datasheet_qs), questions_per_category)

    spice_qs = generate_spice_questions_balanced(all_nets, spice_json_file, questions_per_category * 2)
    spice_qs = take_balanced(deduplicate_questions(spice_qs), questions_per_category)

    layout_qs = generate_layout_questions_balanced(
        component_connections, all_nets, questions_per_category * 2
    )
    layout_qs = take_balanced(deduplicate_questions(layout_qs), questions_per_category)

    all_questions = datasheet_qs + spice_qs + layout_qs

    # Shuffle questions if requested
    if shuffle:
        random.shuffle(all_questions)

    datasheet_counts = {"YES": sum(1 for q in datasheet_qs if q['answer'] == 'YES'),
                       "NO": sum(1 for q in datasheet_qs if q['answer'] == 'NO')}
    spice_counts = {"YES": sum(1 for q in spice_qs if q['answer'] == 'YES'),
                   "NO": sum(1 for q in spice_qs if q['answer'] == 'NO')}
    layout_counts = {"YES": sum(1 for q in layout_qs if q['answer'] == 'YES'),
                     "NO": sum(1 for q in layout_qs if q['answer'] == 'NO')}

    print(f"    Datasheet: {datasheet_counts} (generated {len(datasheet_qs)}/{questions_per_category})")
    print(f"    SPICE: {spice_counts} (generated {len(spice_qs)}/{questions_per_category})")
    print(f"    Layout: {layout_counts} (generated {len(layout_qs)}/{questions_per_category})")
    print(f"    Total: {len(all_questions)} questions")

    # Save to file if output path provided
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(all_questions, f, indent=2)
        print(f"    Saved to: {output_file}")

    return all_questions
