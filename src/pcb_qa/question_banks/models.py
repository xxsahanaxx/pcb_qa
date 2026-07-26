"""Question bank data model for structured representation of QA data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass
class Question:
    """Represents a single question in the question bank.

    Attributes
    ----------
    category : str
        The question category (component_datasheet, spice_behaviour, theory_layout).
    question : str
        The question text.
    answer : str
        The expected answer (YES or NO).
    """

    category: str
    question: str
    answer: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary format for JSON serialization.

        Returns
        -------
        dict
            Dictionary with category, question, and answer keys.
        """
        return {"category": self.category, "question": self.question, "answer": self.answer}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Question:
        """Create a Question from a dictionary.

        Parameters
        ----------
        data : dict
            Dictionary containing question data.

        Returns
        -------
        Question
            New Question instance.
        """
        return cls(
            category=data["category"],
            question=data["question"],
            answer=data.get("answer", ""),
        )


class QuestionBank:
    """A collection of questions organized by category.

    This class provides a structured interface for working with question banks,
    supporting iteration, filtering, and serialization. The internal questions
    are stored as plain dictionaries matching the JSON format:
    {"category": str, "question": str, "answer": str}
    """

    def __init__(self, questions: list[dict[str, str]] | None = None) -> None:
        """Initialize with optional list of question dictionaries.

        Parameters
        ----------
        questions : list[dict[str, str]] | None
            List of question dicts in JSON format.
        """
        self._questions: list[dict[str, str]] = questions if questions else []

    def add_question(self, question: dict[str, str]) -> None:
        """Add a question dict to the bank.

        Parameters
        ----------
        question : dict[str, str]
            The question dict to add (with category, question, answer keys).
        """
        self._questions.append(question)

    def get_by_category(self, category: str) -> list[dict[str, str]]:
        """Get all questions in a specific category.

        Parameters
        ----------
        category : str
            The category to filter by.

        Returns
        -------
        list[dict[str, str]]
            Questions in the specified category.
        """
        return [q for q in self._questions if q.get("category") == category]

    def count_by_category(self) -> dict[str, int]:
        """Get count of questions per category.

        Returns
        -------
        dict[str, int]
            Dictionary mapping category names to counts.
        """
        counts: dict[str, int] = {}
        for q in self._questions:
            cat = q.get("category", "")
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def count_answers_by_category(self) -> dict[str, dict[str, int]]:
        """Get count of YES/NO answers per category.

        Returns
        -------
        dict[str, dict[str, int]]
            Nested dictionary with category -> answer counts.
        """
        counts: dict[str, dict[str, int]] = {}
        for q in self._questions:
            cat = q.get("category", "")
            if cat not in counts:
                counts[cat] = {"YES": 0, "NO": 0}
            ans = q.get("answer", "")
            if ans in ("YES", "NO"):
                counts[cat][ans] += 1
        return counts

    def to_dict_list(self) -> list[dict[str, str]]:
        """Return the list of question dictionaries.

        Returns
        -------
        list[dict[str, str]]
            List of question dictionaries.
        """
        return self._questions.copy()

    def __iter__(self) -> Iterator[dict[str, str]]:
        """Iterate over questions."""
        return iter(self._questions)

    def __len__(self) -> int:
        """Return total number of questions."""
        return len(self._questions)

    def __getitem__(self, index: int) -> dict[str, str]:
        """Get question by index."""
        return self._questions[index]