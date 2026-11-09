"""Question bank validation utilities.

This module provides functions for validating questions against reference design data.

The module validates three types of questions:
- component_datasheet: Questions about component specifications
- spice_behaviour: Questions about SPICE simulation results
- theory_layout: Questions about component-to-net connectivity
"""

from __future__ import annotations

import json
import re
from typing import Any

from pcb_qa.parsers.circuit_json import CircuitJSON
from pcb_qa.question_banks.datasheet_lookup import match_property_text, verify_property
from pcb_qa.question_banks.models import Question


def load_spice_data(spice_json_file: str) -> dict[str, float]:
    """Load SPICE voltage data for all nets.

    Computes average voltage from the last 10 values of each net's time-series data.

    Args:
        spice_json_file: Path to the SPICE simulation JSON file.

    Returns:
        Dictionary mapping net names to average voltage values.
    """
    data: dict[str, float] = {}
    try:
        with open(spice_json_file, 'r') as f:
            raw = json.load(f)

        for key, entry in raw.items():
            if isinstance(entry, dict) and 'name' in entry:
                name = entry['name']
                if name.startswith('v('):
                    net = name[2:-1]
                    values = [float(v) for v in entry.get('values', {}).values()]
                    if values:
                        avg = sum(values[-10:]) / 10
                        data[net] = round(avg, 2)
    except Exception as e:
        print(f"Error loading SPICE data: {e}")

    return data


class CircuitQuestionValidator:
    """Validate questions against circuit and SPICE data.

    This class provides methods to validate questions from the three categories:
    - component_datasheet: Questions about component specifications
    - spice_behaviour: Questions about SPICE simulation results
    - theory_layout: Questions about component-to-net connectivity
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

    VALID_DATASHEET_PROPERTIES: list[str] = [
        "temperature", "voltage", "current", "i2c", "spi", "uart",
        "can", "usb", "ethernet", "wifi", "bluetooth", "flash",
        "memory", "pwm", "adc", "dac", "magnetic", "motion", "clock", "quiescent"
    ]

    def __init__(
        self,
        circuit_json_file: str,
        spice_json_file: str,
        embeddings_dir: str | None = None,
    ) -> None:
        """Initialize validator with circuit and SPICE data.

        Args:
            circuit_json_file: Path to the circuit JSON file.
            spice_json_file: Path to the SPICE simulation JSON file.
            embeddings_dir: Optional path to the project's ``embeddings/``
                directory, used to verify component_datasheet answers against
                real datasheet text. Without it, datasheet questions can only
                be syntax-checked (unchanged from previous behaviour).
        """
        self.circuit = CircuitJSON(circuit_file=circuit_json_file)
        self.spice_data = load_spice_data(spice_json_file)
        self._components = self._extract_components(circuit_json_file)
        self.embeddings_dir = embeddings_dir

    @staticmethod
    def _extract_components(circuit_json_file: str) -> list[str]:
        """Extract all component references from a circuit JSON file.

        Args:
            circuit_json_file: Path to the circuit JSON file.

        Returns:
            List of component reference designators.
        """
        try:
            with open(circuit_json_file, 'r') as f:
                data = json.load(f)

            components = list(data.get('components', {}).keys())
            for subcircuit in data.get('subcircuits', []):
                components.extend(subcircuit.get('components', {}).keys())
            return components
        except Exception:
            return []

    def validate_spice_question(self, question: dict[str, str]) -> tuple[bool, str]:
        """Validate a spice_behaviour question against SPICE data.

        Args:
            question: Question dictionary with 'question' and 'answer' keys.

        Returns:
            Tuple of (is_valid, error_message).
        """
        q_text = question.get("question", "")
        expected_answer = question.get("answer", "")

        voltage_match = re.search(r'(\d+(?:\.\d+)?)V', q_text)

        if not voltage_match:
            return False, f"Could not extract voltage from question: {q_text}"

        expected_voltage = float(voltage_match.group(1))

        net_name = self._extract_net_from_question(q_text)

        if not net_name:
            return False, f"Could not parse question format: {q_text}"

        actual_voltage = self._find_spice_voltage(net_name)

        if actual_voltage is None:
            return False, f"Net '{net_name}' not found in SPICE data"

        is_correct = abs(actual_voltage - expected_voltage) < 0.5

        if expected_answer == "YES":
            if not is_correct:
                return False, f"Expected {expected_voltage}V but net '{net_name}' has {actual_voltage}V"
        else:
            if is_correct:
                return False, f"Expected NOT {expected_voltage}V but net '{net_name}' actually has {actual_voltage}V"

        return True, "Valid"

    def validate_layout_question(self, question: dict[str, str]) -> tuple[bool, str]:
        """Validate a theory_layout question against circuit JSON.

        Args:
            question: Question dictionary with 'question' and 'answer' keys.

        Returns:
            Tuple of (is_valid, error_message).
        """
        q_text = question.get("question", "")
        expected_answer = question.get("answer", "")

        comp_match = re.search(r'component ([^?]+) connected', q_text, re.IGNORECASE)
        net_match = re.search(r'to ([^?]+)\?', q_text, re.IGNORECASE)

        if not comp_match or not net_match:
            return False, f"Could not parse component/net from question: {q_text}"

        component_ref = comp_match.group(1).strip()
        net_name = net_match.group(1).strip()

        is_connected = self.circuit.is_component_in_net_from_circuit(component_ref, net_name)

        if expected_answer == "YES":
            if not is_connected:
                return False, f"Component '{component_ref}' is NOT connected to net '{net_name}'"
        else:
            if is_connected:
                return False, f"Component '{component_ref}' IS connected to net '{net_name}'"

        return True, "Valid"

    def validate_datasheet_question(self, question: dict[str, str]) -> tuple[bool, str]:
        """Validate a component_datasheet question.

        When ``self.embeddings_dir`` is set and the question's property phrase
        matches a known template, the claimed value/capability is checked
        against the component's real embedded datasheet text. Otherwise this
        falls back to the previous syntax-only check.

        Args:
            question: Question dictionary with 'question' and 'answer' keys.

        Returns:
            Tuple of (is_valid, error_message).
        """
        q_text = question.get("question", "")
        expected_answer = question.get("answer", "")

        comp_match = re.search(r'component (\S+) (?:have|a|an)', q_text, re.IGNORECASE)
        if not comp_match:
            comp_match = re.search(r'Is the component (\S+) a', q_text, re.IGNORECASE)

        if not comp_match:
            return False, f"Could not extract component from question: {q_text}"

        component_ref = comp_match.group(1).strip()

        if component_ref not in self._components:
            ic_components = [c for c in self._components if c.startswith(('U', 'REG', 'SW', 'D'))]
            if component_ref not in ic_components and component_ref not in self._components:
                return True, f"Component '{component_ref}' not found (may be acceptable for IC templates)"

        isolated_match = re.search(r'have (?:a |an )?(.+?) according to its datasheet', q_text, re.IGNORECASE)
        if self.embeddings_dir and isolated_match:
            grounded_result = self._check_datasheet_ground_truth(
                component_ref, isolated_match.group(1), expected_answer
            )
            if grounded_result is not None:
                return grounded_result

        property_match = re.search(r'have (a |an )?([^?]+)', q_text, re.IGNORECASE)

        if property_match:
            prop_text = property_match.group(2)
            is_valid_prop = any(prop in prop_text.lower() for prop in self.VALID_DATASHEET_PROPERTIES)
            if is_valid_prop:
                return True, "Valid (cannot fully verify without datasheet embeddings)"

        return True, "Syntax valid (semantic validation requires embeddings)"

    def _check_datasheet_ground_truth(
        self, component_ref: str, prop_text: str, expected_answer: str
    ) -> tuple[bool, str] | None:
        """Check a datasheet claim against embedded datasheet text.

        Returns None when the property/component can't be matched or
        verified, so the caller falls back to the syntax-only check.
        """
        matched = match_property_text(prop_text)
        if matched is None:
            return None

        template, claimed_value = matched
        result = verify_property(component_ref, template, self.embeddings_dir)
        if result is None:
            return None

        if result["kind"] == "numeric":
            true_values = result["true_values"]
            if not true_values or claimed_value is None:
                return None
            is_match = any(abs(claimed_value - t) < 0.5 for t in true_values)
            if expected_answer == "YES" and not is_match:
                return False, (
                    f"Datasheet for '{component_ref}' shows {true_values} for this property, "
                    f"not the claimed {claimed_value}"
                )
            if expected_answer == "NO" and is_match:
                return False, f"Datasheet for '{component_ref}' DOES show {claimed_value} for this property"
            return True, "Valid (verified against embedded datasheet text)"

        found = result["found"]
        if expected_answer == "YES" and not found:
            return False, f"'{prop_text}' not found in '{component_ref}'s embedded datasheet text"
        if expected_answer == "NO" and found:
            return False, f"'{prop_text}' IS supported by '{component_ref}'s embedded datasheet text"
        return True, "Valid (verified against embedded datasheet text)"

    def _extract_net_from_question(self, q_text: str) -> str | None:
        """Extract net name from a SPICE question.

        Args:
            q_text: Question text.

        Returns:
            Net name or None if not found.
        """
        for pattern in self.SPICE_NET_PATTERNS:
            match = re.search(pattern, q_text)
            if match:
                return match.group(1).strip()
        return None

    def _find_spice_voltage(self, net_name: str) -> float | None:
        """Find voltage for a net in SPICE data, trying variations.

        Args:
            net_name: The net name to search for.

        Returns:
            Voltage value or None if not found.
        """
        actual_voltage = self.spice_data.get(net_name)

        if actual_voltage is None:
            actual_voltage = self.spice_data.get(net_name.lstrip('/'))

        if actual_voltage is None:
            for var in [net_name.replace('-', '_'), net_name.replace('_', '-')]:
                actual_voltage = self.spice_data.get(var)
                if actual_voltage is not None:
                    break

        if actual_voltage is None:
            normalized_question = net_name.lower().replace('-', '_').replace('net-_', '').replace('net--', '').replace('net__', '').lstrip('/')
            for spice_net in self.spice_data.keys():
                normalized_spice = spice_net.lower().replace('-', '_').replace('net-_', '').replace('net--', '').replace('net__', '')
                if normalized_question in normalized_spice or normalized_spice in normalized_question:
                    return self.spice_data[spice_net]

        return actual_voltage

    def validate_questions(self, questions: list[dict[str, str]]) -> dict[str, Any]:
        """Validate all questions and generate a report.

        Args:
            questions: List of question dictionaries to validate.

        Returns:
            Validation report dictionary with counts and errors per category.
        """
        report: dict[str, Any] = {
            "total_questions": len(questions),
            "categories": {
                "component_datasheet": {"total": 0, "valid": 0, "invalid": 0, "errors": []},
                "spice_behaviour": {"total": 0, "valid": 0, "invalid": 0, "errors": []},
                "theory_layout": {"total": 0, "valid": 0, "invalid": 0, "errors": []},
            }
        }

        for question in questions:
            category = question.get("category", "unknown")

            if category not in report["categories"]:
                continue

            report["categories"][category]["total"] += 1

            if category == "component_datasheet":
                is_valid, msg = self.validate_datasheet_question(question)
            elif category == "spice_behaviour":
                is_valid, msg = self.validate_spice_question(question)
            elif category == "theory_layout":
                is_valid, msg = self.validate_layout_question(question)
            else:
                continue

            if is_valid:
                report["categories"][category]["valid"] += 1
            else:
                report["categories"][category]["invalid"] += 1
                report["categories"][category]["errors"].append({
                    "question": question["question"],
                    "answer": question["answer"],
                    "error": msg
                })

        return report


# Module-level functions for backward compatibility
def validate_spice_question(question: dict[str, str], spice_data: dict[str, float]) -> tuple[bool, str]:
    """Validate a spice_behaviour question against SPICE data.

    Args:
        question: Question dictionary with 'question' and 'answer' keys.
        spice_data: Dictionary of net names to voltage values.

    Returns:
        Tuple of (is_valid, error_message).
    """
    q_text = question.get("question", "")
    expected_answer = question.get("answer", "")

    voltage_match = re.search(r'(\d+(?:\.\d+)?)V', q_text)

    if not voltage_match:
        return False, f"Could not extract voltage from question: {q_text}"

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
        return False, f"Could not parse question format: {q_text}"

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
        return False, f"Net '{net_name}' not found in SPICE data"

    is_correct = abs(actual_voltage - expected_voltage) < 0.5

    if expected_answer == "YES":
        if not is_correct:
            return False, f"Expected {expected_voltage}V but net '{net_name}' has {actual_voltage}V"
    else:
        if is_correct:
            return False, f"Expected NOT {expected_voltage}V but net '{net_name}' actually has {actual_voltage}V"

    return True, "Valid"


def validate_layout_question(question: dict[str, str], circuit_json_file: str) -> tuple[bool, str]:
    """Validate a theory_layout question against circuit JSON.

    Args:
        question: Question dictionary with 'question' and 'answer' keys.
        circuit_json_file: Path to the circuit JSON file.

    Returns:
        Tuple of (is_valid, error_message).
    """
    q_text = question.get("question", "")
    expected_answer = question.get("answer", "")

    comp_match = re.search(r'component ([^?]+) connected', q_text, re.IGNORECASE)
    net_match = re.search(r'to ([^?]+)\?', q_text, re.IGNORECASE)

    if not comp_match or not net_match:
        return False, f"Could not parse component/net from question: {q_text}"

    component_ref = comp_match.group(1).strip()
    net_name = net_match.group(1).strip()

    circuit = CircuitJSON(circuit_file=circuit_json_file)
    is_connected = circuit.is_component_in_net_from_circuit(component_ref, net_name)

    if expected_answer == "YES":
        if not is_connected:
            return False, f"Component '{component_ref}' is NOT connected to net '{net_name}'"
    else:
        if is_connected:
            return False, f"Component '{component_ref}' IS connected to net '{net_name}'"

    return True, "Valid"


def validate_datasheet_question(question: dict[str, str], components: list[str]) -> tuple[bool, str]:
    """Validate a component_datasheet question.

    Args:
        question: Question dictionary with 'question' and 'answer' keys.
        components: List of component references for validation context.

    Returns:
        Tuple of (is_valid, error_message).
    """
    q_text = question.get("question", "")

    comp_match = re.search(r'component (\S+) (?:have|a|an)', q_text, re.IGNORECASE)
    if not comp_match:
        comp_match = re.search(r'Is the component (\S+) a', q_text, re.IGNORECASE)

    if not comp_match:
        return False, f"Could not extract component from question: {q_text}"

    component_ref = comp_match.group(1).strip()

    if component_ref not in components:
        ic_components = [c for c in components if c.startswith(('U', 'REG', 'SW', 'D'))]
        if component_ref not in ic_components and component_ref not in components:
            return True, f"Component '{component_ref}' not found (may be acceptable for IC templates)"

    property_match = re.search(r'have (a |an )?([^?]+)', q_text, re.IGNORECASE)

    if property_match:
        prop_text = property_match.group(2)
        is_valid_prop = any(prop in prop_text.lower() for prop in [
            "temperature", "voltage", "current", "i2c", "spi", "uart",
            "can", "usb", "ethernet", "wifi", "bluetooth", "flash",
            "memory", "pwm", "adc", "dac", "magnetic", "motion", "clock", "quiescent"
        ])
        if is_valid_prop:
            return True, "Valid (cannot fully verify without datasheet embeddings)"

    return True, "Syntax valid (semantic validation requires embeddings)"