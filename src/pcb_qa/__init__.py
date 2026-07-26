"""PCB Question Answer Benchmark - A benchmarking framework for evaluating LLMs on PCB circuit analysis."""

__version__ = "0.1.0"

# Question bank utilities
from pcb_qa.question_banks import (
    # Data models
    Question,
    QuestionBank,
    # Generator exports
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
    load_spice_data,
    # Validator exports
    CircuitQuestionValidator,
    validate_datasheet_question,
    validate_layout_question,
    validate_spice_question,
    # Fixer exports
    QuestionBankFixer,
    find_valid_net,
    fix_layout_question,
    fix_question_bank,
    fix_spice_question,
)

__all__ = [
    "__version__",
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
]