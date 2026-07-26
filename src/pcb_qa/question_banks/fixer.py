"""Question bank fixing utilities.

This module provides functions for fixing invalid questions based on validation results.

The module fixes three types of questions:
- component_datasheet: Questions about component specifications
- spice_behaviour: Questions about SPICE simulation results
- theory_layout: Questions about component-to-net connectivity
"""

from __future__ import annotations

import json
import re
from typing import Any

from pcb_qa.parsers.circuit_json import CircuitJSON
from pcb_qa.question_banks.validator import load_spice_data


def find_valid_net(net_name: str, spice_data: dict[str, float]) -> str | None:
    """Find a valid net name that matches the given net_name from SPICE data.

    Tries various normalization variations to find a matching net.

    Args:
        net_name: The net name to search for.
        spice_data: Dictionary of net names to voltage values.

    Returns:
        Valid net name if found, None otherwise.
    """
    if net_name in spice_data:
        return net_name

    variations = [
        net_name,
        net_name.replace('-', '_'),
        net_name.replace('_', '-'),
        net_name.lstrip('/'),
        net_name.replace('/', '_'),
        net_name.replace('/', '-'),
    ]

    for var in variations:
        if var in spice_data:
            return var

    normalized_question = net_name.lower().replace('-', '_').replace('net-_', '').replace('net--', '').replace('net__', '').lstrip('/')

    for spice_net in spice_data.keys():
        normalized_spice = spice_net.lower().replace('-', '_').replace('net-_', '').replace('net--', '').replace('net__', '')
        if normalized_question == normalized_spice or normalized_question in normalized_spice or normalized_spice in normalized_question:
            return spice_net

    return None


def find_valid_net_and_update_question(question: dict[str, str], spice_data: dict[str, float]) -> bool:
    """Find valid net and update question text if needed.

    Args:
        question: Question dictionary to potentially modify.
        spice_data: Dictionary of net names to voltage values.

    Returns:
        True if question was modified, False otherwise.
    """
    q_text = question.get("question", "")

    net_name = None
    patterns = [
        r'Does the net ([^?]+?) maintain',
        r'Does the net ([^?]+?) obtain',
        r'Does the net ([^?]+?) reach',
        r'Does the ([^?]+?) signal maintain',
        r'Is the ([^?]+?) signal at',
        r'Is the ([^?]+?) power rail stable',
        r'Is the net ([^?]+?) at',
    ]

    for pattern in patterns:
        match = re.search(pattern, q_text)
        if match:
            net_name = match.group(1).strip()
            break

    if not net_name:
        return False

    valid_net = find_valid_net(net_name, spice_data)

    if valid_net and valid_net != net_name:
        question["question"] = q_text.replace(net_name, valid_net)
        return True

    return False


def fix_spice_question(question: dict[str, str], spice_data: dict[str, float]) -> bool:
    """Fix SPICE question by correcting the answer based on actual SPICE data.

    Args:
        question: Question dictionary to potentially modify.
        spice_data: Dictionary of net names to voltage values.

    Returns:
        True if question was modified, False otherwise.
    """
    q_text = question.get("question", "")
    expected_answer = question.get("answer", "")

    voltage_match = re.search(r'(\d+(?:\.\d+)?)V', q_text)
    if not voltage_match:
        return False

    expected_voltage = float(voltage_match.group(1))

    net_name = None
    patterns = [
        r'Does the net ([^?]+?) maintain',
        r'Does the net ([^?]+?) obtain',
        r'Does the net ([^?]+?) reach',
        r'Does the ([^?]+?) signal maintain',
        r'Is the ([^?]+?) signal at',
        r'Is the ([^?]+?) power rail stable',
        r'Is the net ([^?]+?) at',
    ]

    for pattern in patterns:
        match = re.search(pattern, q_text)
        if match:
            net_name = match.group(1).strip()
            break

    if not net_name:
        return False

    actual_voltage = spice_data.get(net_name)

    if actual_voltage is None:
        actual_voltage = spice_data.get(net_name.lstrip('/'))

    if actual_voltage is None:
        for var in [net_name.replace('-', '_'), net_name.replace('_', '-')]:
            actual_voltage = spice_data.get(var)
            if actual_voltage is not None:
                break

    if actual_voltage is None:
        normalized_question = net_name.lower().replace('-', '_').replace('net-_', '').replace('net--', '').replace('net__', '').lstrip('/')
        for spice_net in spice_data.keys():
            normalized_spice = spice_net.lower().replace('-', '_').replace('net-_', '').replace('net--', '').replace('net__', '')
            if normalized_question in normalized_spice or normalized_spice in normalized_question:
                actual_voltage = spice_data[spice_net]
                break

    if actual_voltage is None:
        return False

    is_correct_voltage = abs(actual_voltage - expected_voltage) < 0.5
    correct_answer = "YES" if is_correct_voltage else "NO"

    if correct_answer != expected_answer:
        question["answer"] = correct_answer
        return True

    return False


def fix_layout_question(question: dict[str, str], circuit_json_file: str) -> bool:
    """Fix layout question by correcting the answer based on circuit JSON data.

    Args:
        question: Question dictionary to potentially modify.
        circuit_json_file: Path to the circuit JSON file.

    Returns:
        True if question was modified, False otherwise.
    """
    q_text = question.get("question", "")
    expected_answer = question.get("answer", "")

    comp_match = re.search(r'component ([^?]+) connected', q_text, re.IGNORECASE)
    net_match = re.search(r'to ([^?]+)\?', q_text, re.IGNORECASE)

    if not comp_match or not net_match:
        return False

    component_ref = comp_match.group(1).strip()
    net_name = net_match.group(1).strip()

    circuit = CircuitJSON(circuit_file=circuit_json_file)
    is_connected = circuit.is_component_in_net_from_circuit(component_ref, net_name)

    correct_answer = "YES" if is_connected else "NO"

    if correct_answer != expected_answer:
        question["answer"] = correct_answer
        return True

    return False


class QuestionBankFixer:
    """Fix invalid questions in question bank files.

    This class provides methods to fix questions based on ground truth data from
    SPICE simulations and circuit JSON files.
    """

    SPICE_NET_PATTERNS: list[str] = [
        r'Does the net ([^?]+?) maintain',
        r'Does the net ([^?]+?) obtain',
        r'Does the net ([^?]+?) reach',
        r'Does the ([^?]+?) signal maintain',
        r'Is the ([^?]+?) signal at',
        r'Is the ([^?]+?) power rail stable',
        r'Is the net ([^?]+?) at',
    ]

    def __init__(self, circuit_json_file: str, spice_json_file: str) -> None:
        """Initialize fixer with circuit and SPICE data.

        Args:
            circuit_json_file: Path to the circuit JSON file.
            spice_json_file: Path to the SPICE simulation JSON file.
        """
        self.circuit_json_file = circuit_json_file
        self.spice_json_file = spice_json_file
        self.spice_data = load_spice_data(spice_json_file)

    def fix_question(self, question: dict[str, str]) -> bool:
        """Fix a single question based on its category.

        Args:
            question: Question dictionary to potentially modify.

        Returns:
            True if question was modified, False otherwise.
        """
        category = question.get("category", "unknown")

        if category == "spice_behaviour":
            modified = find_valid_net_and_update_question(question, self.spice_data)
            if modified:
                return True
            return fix_spice_question(question, self.spice_data)
        elif category == "theory_layout":
            return fix_layout_question(question, self.circuit_json_file)

        return False

    def fix_question_bank(self, questions: list[dict[str, str]]) -> tuple[int, int]:
        """Fix all questions in a question bank.

        Args:
            questions: List of question dictionaries to fix (modified in place).

        Returns:
            Tuple of (replaced_count, fixed_count) for net replacements and answer fixes.
        """
        replaced_count = 0
        fixed_count = 0

        for question in questions:
            category = question.get("category", "unknown")

            if category == "spice_behaviour":
                if find_valid_net_and_update_question(question, self.spice_data):
                    replaced_count += 1
                if fix_spice_question(question, self.spice_data):
                    fixed_count += 1
            elif category == "theory_layout":
                if fix_layout_question(question, self.circuit_json_file):
                    fixed_count += 1

        return replaced_count, fixed_count


def fix_question_bank(questions_file: str, circuit_json_file: str, spice_json_file: str) -> None:
    """Fix all invalid questions in a question bank file.

    Reads a question bank JSON file, fixes invalid questions, and writes back.

    Args:
        questions_file: Path to the questions JSON file.
        circuit_json_file: Path to the circuit JSON file.
        spice_json_file: Path to the SPICE simulation JSON file.
    """
    with open(questions_file, 'r') as f:
        questions = json.load(f)

    spice_data = load_spice_data(spice_json_file)
    circuit = CircuitJSON(circuit_file=circuit_json_file)

    fixer = QuestionBankFixer(circuit_json_file, spice_json_file)
    replaced_count, fixed_count = fixer.fix_question_bank(questions)

    if replaced_count > 0 or fixed_count > 0:
        with open(questions_file, 'w') as f:
            json.dump(questions, f, indent=2)