"""Tests for the question_banks.models module (Question & QuestionBank)."""

from __future__ import annotations

import pytest

from pcb_qa.question_banks.models import Question, QuestionBank


class TestQuestion:
    """Unit tests for the Question dataclass."""

    def test_to_dict(self) -> None:
        q = Question(category="spice_behaviour", question="Does the net VCC maintain 3.3V?", answer="YES")
        expected = {
            "category": "spice_behaviour",
            "question": "Does the net VCC maintain 3.3V?",
            "answer": "YES",
        }
        assert q.to_dict() == expected

    def test_from_dict(self) -> None:
        data = {
            "category": "component_datasheet",
            "question": "Does the component U1 have I2C capabilities?",
            "answer": "NO",
        }
        q = Question.from_dict(data)
        assert q.category == "component_datasheet"
        assert q.question == "Does the component U1 have I2C capabilities?"
        assert q.answer == "NO"

    def test_from_dict_missing_answer(self) -> None:
        data = {
            "category": "theory_layout",
            "question": "Is the component R1 connected to GND?",
        }
        q = Question.from_dict(data)
        assert q.answer == ""

    def test_str_representation(self) -> None:
        q = Question(category="spice_behaviour", question="Test?", answer="YES")
        s = repr(q)
        assert "Test?" in s
        assert "spice_behaviour" in s


class TestQuestionBank:
    """Unit tests for the QuestionBank collection class."""

    def test_empty_bank(self) -> None:
        bank = QuestionBank()
        assert len(bank) == 0
        assert list(bank) == []

    def test_add_question(self) -> None:
        bank = QuestionBank()
        bank.add_question({"category": "spice_behaviour", "question": "Q?", "answer": "YES"})
        assert len(bank) == 1

    def test_get_by_category(self) -> None:
        questions = [
            {"category": "spice_behaviour", "question": "Q1", "answer": "YES"},
            {"category": "component_datasheet", "question": "Q2", "answer": "NO"},
            {"category": "spice_behaviour", "question": "Q3", "answer": "NO"},
            {"category": "theory_layout", "question": "Q4", "answer": "YES"},
        ]
        bank = QuestionBank(questions)

        spice_qs = bank.get_by_category("spice_behaviour")
        assert len(spice_qs) == 2

        layout_qs = bank.get_by_category("theory_layout")
        assert len(layout_qs) == 1

        datasheet_qs = bank.get_by_category("component_datasheet")
        assert len(datasheet_qs) == 1

    def test_get_by_category_empty(self) -> None:
        bank = QuestionBank()
        assert bank.get_by_category("spice_behaviour") == []

    def test_count_by_category(self) -> None:
        questions = [
            {"category": "spice_behaviour", "question": "Q1", "answer": "YES"},
            {"category": "component_datasheet", "question": "Q2", "answer": "NO"},
            {"category": "spice_behaviour", "question": "Q3", "answer": "YES"},
        ]
        bank = QuestionBank(questions)
        counts = bank.count_by_category()
        assert counts == {"spice_behaviour": 2, "component_datasheet": 1}

    def test_count_answers_by_category(self) -> None:
        questions = [
            {"category": "spice_behaviour", "question": "Q1", "answer": "YES"},
            {"category": "spice_behaviour", "question": "Q2", "answer": "NO"},
            {"category": "component_datasheet", "question": "Q3", "answer": "YES"},
        ]
        bank = QuestionBank(questions)
        counts = bank.count_answers_by_category()

        assert counts["spice_behaviour"]["YES"] == 1
        assert counts["spice_behaviour"]["NO"] == 1
        assert counts["component_datasheet"]["YES"] == 1
        assert counts["component_datasheet"]["NO"] == 0

    def test_to_dict_list(self) -> None:
        questions = [
            {"category": "spice_behaviour", "question": "Q1", "answer": "YES"},
        ]
        bank = QuestionBank(questions)
        result = bank.to_dict_list()
        assert result == questions
        # Ensure it's a copy, not the same list
        result.append({"new": "item"})
        assert len(bank) == 1

    def test_index_access(self) -> None:
        questions = [
            {"category": "spice_behaviour", "question": "Q1", "answer": "YES"},
            {"category": "component_datasheet", "question": "Q2", "answer": "NO"},
        ]
        bank = QuestionBank(questions)
        assert bank[0]["question"] == "Q1"
        assert bank[1]["category"] == "component_datasheet"

    def test_index_out_of_range(self) -> None:
        bank = QuestionBank()
        with pytest.raises(IndexError):
            _ = bank[0]

    def test_iteration(self) -> None:
        questions = [
            {"category": "spice_behaviour", "question": "Q1", "answer": "YES"},
            {"category": "component_datasheet", "question": "Q2", "answer": "NO"},
        ]
        bank = QuestionBank(questions)
        collected = [q for q in bank]
        assert len(collected) == 2

    def test_len(self) -> None:
        bank = QuestionBank([{"q": "1"}, {"q": "2"}, {"q": "3"}])
        assert len(bank) == 3


class TestQuestionCompatibility:
    """Verify Question and QuestionBank work together."""

    def test_question_to_bank(self) -> None:
        q = Question(category="spice_behaviour", question="Test?", answer="YES")
        bank = QuestionBank()
        bank.add_question(q.to_dict())
        assert len(bank) == 1
        assert bank[0]["category"] == "spice_behaviour"

    def test_bank_to_question(self) -> None:
        bank = QuestionBank([
            {"category": "component_datasheet", "question": "Datasheet Q?", "answer": "NO"},
        ])
        q = Question.from_dict(bank[0])
        assert q.category == "component_datasheet"
        assert q.answer == "NO"