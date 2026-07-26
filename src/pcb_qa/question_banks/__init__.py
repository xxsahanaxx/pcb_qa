"""Question bank generation, validation, and fixing utilities.

This module provides reusable classes and functions for working with PCB question banks:
- Question and QuestionBank data models
- Question generation from circuit JSON and SPICE simulation files
- Question validation against reference design data
- Question fixing based on validation results
"""

from pcb_qa.question_banks.generator import (
    DATASHEET_PROPERTIES,
    SPICE_QUESTION_TEMPLATES,
    VOLTAGE_LEVELS,
    expand_question_bank_for_project,
    extract_components_from_circuit,
    extract_nets_from_circuit,
    extract_nets_from_spice,
    format_property,
    generate_datasheet_questions_balanced,
    generate_layout_questions_balanced,
    generate_spice_questions_balanced,
    get_component_net_connections,
)
from pcb_qa.question_banks.validator import (
    CircuitQuestionValidator,
    validate_datasheet_question,
    validate_layout_question,
    validate_spice_question,
)
from pcb_qa.question_banks.fixer import (
    QuestionBankFixer,
    find_valid_net,
    fix_layout_question,
    fix_question_bank,
    fix_spice_question,
)
from pcb_qa.question_banks.models import (
    Question,
    QuestionBank,
)
from pcb_qa.question_banks.prompts import (
    get_prompts_path,
    get_prompts_text,
)

# Re-export load_spice_data from generator for backward compatibility
# (it's also available in validator)
from pcb_qa.question_banks.generator import load_spice_data as load_spice_data

__all__ = [
    # Data models
    "Question",
    "QuestionBank",
    # Generator exports
    "DATASHEET_PROPERTIES",
    "SPICE_QUESTION_TEMPLATES",
    "VOLTAGE_LEVELS",
    "expand_question_bank_for_project",
    "extract_components_from_circuit",
    "extract_nets_from_circuit",
    "extract_nets_from_spice",
    "format_property",
    "generate_datasheet_questions_balanced",
    "generate_layout_questions_balanced",
    "generate_spice_questions_balanced",
    "get_component_net_connections",
    "load_spice_data",
    # Validator exports
    "CircuitQuestionValidator",
    "validate_datasheet_question",
    "validate_layout_question",
    "validate_spice_question",
    # Fixer exports
    "QuestionBankFixer",
    "find_valid_net",
    "fix_layout_question",
    "fix_question_bank",
    "fix_spice_question",
    # Prompts exports
    "get_prompts_path",
    "get_prompts_text",
]
