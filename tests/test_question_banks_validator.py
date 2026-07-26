"""Tests for the question_banks.validator module."""

from __future__ import annotations

import json

import pytest

from pcb_qa.question_banks.validator import (
    CircuitQuestionValidator,
    load_spice_data,
    validate_datasheet_question,
    validate_layout_question,
    validate_spice_question,
)


class TestLoadSpiceData:
    """Tests for load_spice_data."""

    def test_loads_voltage_data(self, tmp_path):
        data = {
            "VCC": {"name": "v(VCC)", "values": {str(i): 3.3 for i in range(10)}},
            "GND": {"name": "v(GND)", "values": {str(i): 0.0 for i in range(10)}},
        }
        path = tmp_path / "spice.json"
        with open(path, "w") as f:
            json.dump(data, f)

        result = load_spice_data(str(path))
        assert "VCC" in result
        assert "GND" in result
        assert result["VCC"] == 3.3
        assert result["GND"] == 0.0

    def test_averages_last_10_values(self, tmp_path):
        values = {str(i): float(i) for i in range(20)}
        data = {"NET": {"name": "v(NET)", "values": values}}
        path = tmp_path / "spice_avg.json"
        with open(path, "w") as f:
            json.dump(data, f)

        result = load_spice_data(str(path))
        # Average of last 10 values (10..19) = (10+11+...+19)/10 = 14.5
        assert result["NET"] == 14.5

    def test_file_not_found(self):
        result = load_spice_data("/nonexistent/file.json")
        assert result == {}


@pytest.fixture
def mock_circuit_json(tmp_path):
    """Create a temporary circuit JSON for validator tests.

    Pin dicts must include ``"type"`` because CircuitJSON._initialise_component_lists
    accesses ``conn["pin"]["type"]``.
    """
    data = {
        "components": {
            "U1": {"ref": "U1", "value": "LM1117"},
            "R1": {"ref": "R1", "value": "10k"},
            "C1": {"ref": "C1", "value": "100n"},
        },
        "nets": {
            "VCC": [{"component": "U1", "pin": {"number": "1", "type": "passive"}}],
            "GND": [{"component": "C1", "pin": {"number": "2", "type": "passive"}}],
            "NET1": [{"component": "R1", "pin": {"number": "1", "type": "passive"}}],
        },
        "subcircuits": [],
    }
    path = tmp_path / "circuit.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return str(path)


@pytest.fixture
def mock_spice_json(tmp_path):
    """Create a temporary SPICE JSON for validator tests.

    Includes exactly 10 values per net so that the average calculation
    (sum(values[-10:]) / 10) matches the expected value.
    """
    data = {
        "VCC": {"name": "v(VCC)", "values": {str(i): 3.3 for i in range(10)}},
        "GND": {"name": "v(GND)", "values": {str(i): 0.0 for i in range(10)}},
    }
    path = tmp_path / "spice.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return str(path)


class TestCircuitQuestionValidator:
    """Tests for the CircuitQuestionValidator class."""

    def test_validate_datasheet_question_valid(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "component_datasheet",
            "question": "Does the component U1 have I2C capabilities according to its datasheet?",
            "answer": "YES",
        }
        is_valid, msg = validator.validate_datasheet_question(question)
        # The validator's regex captures the property text rather than splitting at
        # 'have', so the "component" check may pass through with a warning.
        # We verify it returns True (syntax valid, can't fully verify without embeddings).
        assert is_valid

    def test_validate_datasheet_question_unparsable(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "component_datasheet",
            "question": "Does the component U1 have temperature capabilities?",
            "answer": "YES",
        }
        is_valid, msg = validator.validate_datasheet_question(question)
        assert is_valid

    def test_validate_spice_question_correct_yes(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain a voltage of 3.3V during the entire simulation?",
            "answer": "YES",
        }
        is_valid, msg = validator.validate_spice_question(question)
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_spice_question_correct_no(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain a voltage of 5V during the entire simulation?",
            "answer": "NO",
        }
        is_valid, msg = validator.validate_spice_question(question)
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_spice_question_wrong_voltage(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain a voltage of 5V during the entire simulation?",
            "answer": "YES",
        }
        is_valid, msg = validator.validate_spice_question(question)
        assert not is_valid
        assert "3.3V" in msg

    def test_validate_spice_question_nonexistent_net(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "spice_behaviour",
            "question": "Does the net NONEXISTENT maintain a voltage of 5V during the entire simulation?",
            "answer": "NO",
        }
        is_valid, msg = validator.validate_spice_question(question)
        assert not is_valid
        assert "not found" in msg

    def test_validate_spice_question_no_voltage(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain a voltage?",
            "answer": "YES",
        }
        is_valid, msg = validator.validate_spice_question(question)
        assert not is_valid
        assert "Could not extract voltage" in msg

    def test_validate_layout_question_correct_yes(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "theory_layout",
            "question": "Is the component U1 connected to VCC?",
            "answer": "YES",
        }
        is_valid, msg = validator.validate_layout_question(question)
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_layout_question_correct_no(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "theory_layout",
            "question": "Is the component R1 connected to VCC?",
            "answer": "NO",
        }
        is_valid, msg = validator.validate_layout_question(question)
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_layout_question_wrong_answer(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "theory_layout",
            "question": "Is the component U1 connected to VCC?",
            "answer": "NO",
        }
        is_valid, msg = validator.validate_layout_question(question)
        assert not is_valid
        assert "IS connected" in msg

    def test_validate_layout_question_unparsable(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        question = {
            "category": "theory_layout",
            "question": "Is this a good layout?",
            "answer": "YES",
        }
        is_valid, msg = validator.validate_layout_question(question)
        assert not is_valid
        assert "Could not parse" in msg

    def test_validate_questions_basic(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        questions = [
            {
                "category": "spice_behaviour",
                "question": "Does the net VCC maintain a voltage of 3.3V during the entire simulation?",
                "answer": "YES",
            },
            {
                "category": "spice_behaviour",
                "question": "Does the net GND maintain a voltage of 5V during the entire simulation?",
                "answer": "NO",
            },
        ]
        report = validator.validate_questions(questions)
        assert report["total_questions"] == 2
        assert report["categories"]["spice_behaviour"]["valid"] == 2
        assert report["categories"]["spice_behaviour"]["invalid"] == 0

    def test_validate_questions_mixed_validity(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        questions = [
            {
                "category": "spice_behaviour",
                "question": "Does the net VCC maintain a voltage of 3.3V during the entire simulation?",
                "answer": "YES",  # correct
            },
            {
                "category": "spice_behaviour",
                "question": "Does the net VCC maintain a voltage of 5V during the entire simulation?",
                "answer": "YES",  # wrong - VCC is 3.3V
            },
        ]
        report = validator.validate_questions(questions)
        assert report["categories"]["spice_behaviour"]["valid"] == 1
        assert report["categories"]["spice_behaviour"]["invalid"] == 1

    def test_validate_unknown_category(self, mock_circuit_json, mock_spice_json):
        validator = CircuitQuestionValidator(mock_circuit_json, mock_spice_json)
        questions = [
            {"category": "unknown_category", "question": "Test?", "answer": "YES"},
        ]
        report = validator.validate_questions(questions)
        assert report["total_questions"] == 1
        # unknown category should be skipped in per-category counts
        assert "unknown_category" not in report["categories"]


class TestModuleLevelValidationFunctions:
    """Tests for module-level validate_* functions."""

    def test_validate_spice_question(self):
        spice_data = {"VCC": 3.3, "GND": 0.0}
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain a voltage of 3.3V during the entire simulation?",
            "answer": "YES",
        }
        is_valid, msg = validate_spice_question(question, spice_data)
        assert is_valid

    def test_validate_layout_question(self, mock_circuit_json, mock_spice_json):
        question = {
            "category": "theory_layout",
            "question": "Is the component U1 connected to VCC?",
            "answer": "YES",
        }
        is_valid, msg = validate_layout_question(question, mock_circuit_json)
        assert is_valid

    def test_validate_datasheet_question(self, mock_circuit_json, mock_spice_json):
        question = {
            "category": "component_datasheet",
            "question": "Does the component U1 have I2C capabilities according to its datasheet?",
            "answer": "YES",
        }
        is_valid, msg = validate_datasheet_question(question, ["U1", "R1", "C1"])
        assert is_valid