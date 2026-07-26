"""Tests for the question_banks.fixer module."""

from __future__ import annotations

import json

import pytest

from pcb_qa.question_banks.fixer import (
    QuestionBankFixer,
    find_valid_net,
    fix_layout_question,
    fix_spice_question,
)


class TestFindValidNet:
    """Tests for find_valid_net."""

    def test_exact_match(self):
        spice_data = {"VCC": 3.3, "GND": 0.0}
        result = find_valid_net("VCC", spice_data)
        assert result == "VCC"

    def test_hyphen_underscore_variation(self):
        spice_data = {"net_signal": 3.3}
        result = find_valid_net("net-signal", spice_data)
        assert result == "net_signal"

    def test_leading_slash(self):
        spice_data = {"VCC": 3.3}
        result = find_valid_net("/VCC", spice_data)
        assert result == "VCC"

    def test_slash_to_underscore(self):
        spice_data = {"a_b": 3.3}
        result = find_valid_net("a/b", spice_data)
        assert result == "a_b"

    def test_no_match(self):
        spice_data = {"VCC": 3.3}
        result = find_valid_net("NONEXISTENT", spice_data)
        assert result is None

    def test_empty_spice_data(self):
        result = find_valid_net("VCC", {})
        assert result is None


class TestFixSpiceQuestion:
    """Tests for fix_spice_question."""

    def test_fix_wrong_answer(self):
        spice_data = {"VCC": 3.3}
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain a voltage of 5V during the entire simulation?",
            "answer": "YES",  # wrong - VCC is 3.3V
        }
        modified = fix_spice_question(question, spice_data)
        assert modified
        assert question["answer"] == "NO"

    def test_no_fix_needed(self):
        spice_data = {"VCC": 3.3}
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain a voltage of 3.3V during the entire simulation?",
            "answer": "YES",
        }
        modified = fix_spice_question(question, spice_data)
        assert not modified
        assert question["answer"] == "YES"

    def test_no_voltage_in_question(self):
        spice_data = {"VCC": 3.3}
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC do something?",
            "answer": "YES",
        }
        modified = fix_spice_question(question, spice_data)
        assert not modified

    def test_nonexistent_net(self):
        spice_data = {"VCC": 3.3}
        question = {
            "category": "spice_behaviour",
            "question": "Does the net FAKE maintain a voltage of 3.3V during the entire simulation?",
            "answer": "YES",
        }
        modified = fix_spice_question(question, spice_data)
        assert not modified


class TestFixLayoutQuestion:
    """Tests for fix_layout_question."""

    def _write_circuit(self, tmp_path, data):
        """Helper to write a circuit JSON and return its path."""
        path = tmp_path / "circuit.json"
        with open(path, "w") as f:
            json.dump(data, f)
        return str(path)

    def test_fix_wrong_answer(self, tmp_path):
        path = self._write_circuit(tmp_path, {
            "components": {"U1": {}},
            "nets": {"VCC": [{"component": "U1", "pin": {"number": "1", "type": "passive"}}]},
            "subcircuits": [],
        })
        question = {
            "category": "theory_layout",
            "question": "Is the component U1 connected to VCC?",
            "answer": "NO",  # wrong - U1 IS connected to VCC
        }
        modified = fix_layout_question(question, str(path))
        assert modified
        assert question["answer"] == "YES"

    def test_no_fix_needed(self, tmp_path):
        path = self._write_circuit(tmp_path, {
            "components": {"U1": {}},
            "nets": {"VCC": [{"component": "U1", "pin": {"number": "1", "type": "passive"}}]},
            "subcircuits": [],
        })
        question = {
            "category": "theory_layout",
            "question": "Is the component U1 connected to VCC?",
            "answer": "YES",
        }
        modified = fix_layout_question(question, str(path))
        assert not modified

    def test_unparsable_question(self, tmp_path):
        path = self._write_circuit(tmp_path, {
            "components": {}, "nets": {}, "subcircuits": [],
        })
        question = {
            "category": "theory_layout",
            "question": "Is this a good layout?",
            "answer": "YES",
        }
        modified = fix_layout_question(question, str(path))
        assert not modified


class TestQuestionBankFixer:
    """Tests for the QuestionBankFixer class."""

    @pytest.fixture
    def fixer(self, tmp_path):
        circuit_data = {
            "components": {"U1": {}, "R1": {}},
            "nets": {
                "VCC": [{"component": "U1", "pin": {"number": "1", "type": "passive"}}],
                "GND": [{"component": "R1", "pin": {"number": "2", "type": "passive"}}],
            },
            "subcircuits": [],
        }
        circuit_path = tmp_path / "circuit.json"
        with open(circuit_path, "w") as f:
            json.dump(circuit_data, f)

        spice_data = {
            "VCC": {"name": "v(VCC)", "values": {str(i): 3.3 for i in range(10)}},
            "GND": {"name": "v(GND)", "values": {str(i): 0.0 for i in range(10)}},
        }
        spice_path = tmp_path / "spice.json"
        with open(spice_path, "w") as f:
            json.dump(spice_data, f)

        return QuestionBankFixer(str(circuit_path), str(spice_path))

    def test_fix_spice_behaviour_question(self, fixer):
        question = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain a voltage of 5V during the entire simulation?",
            "answer": "YES",
        }
        modified = fixer.fix_question(question)
        assert modified
        assert question["answer"] == "NO"

    def test_fix_layout_question(self, fixer):
        question = {
            "category": "theory_layout",
            "question": "Is the component U1 connected to VCC?",
            "answer": "NO",
        }
        modified = fixer.fix_question(question)
        assert modified
        assert question["answer"] == "YES"

    def test_datasheet_question_untouched(self, fixer):
        question = {
            "category": "component_datasheet",
            "question": "Does the component U1 have I2C capabilities?",
            "answer": "YES",
        }
        modified = fixer.fix_question(question)
        assert not modified

    def test_fix_question_bank_multiple(self, fixer):
        questions = [
            {
                "category": "spice_behaviour",
                "question": "Does the net VCC maintain a voltage of 5V during the entire simulation?",
                "answer": "YES",  # wrong
            },
            {
                "category": "spice_behaviour",
                "question": "Does the net GND maintain a voltage of 0V during the entire simulation?",
                "answer": "YES",  # correct
            },
            {
                "category": "theory_layout",
                "question": "Is the component R1 connected to VCC?",
                "answer": "YES",  # wrong - R1 not connected to VCC in this data
            },
        ]
        replaced, fixed = fixer.fix_question_bank(questions)
        # At least one net was replaced or one answer was fixed
        total_changes = replaced + fixed
        assert total_changes > 0