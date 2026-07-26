"""Access to question generation prompts as a packaged resource.

This module provides programmatic access to the question generation prompts
document (question_generation_prompts.md), which contains the canonical
LLM prompts for generating PCB question bank questions across all three
categories:

- component_datasheet: Questions about component specifications
- spice_behaviour: Questions about SPICE simulation voltage levels
- theory_layout: Questions about component-to-net connectivity

Usage
-----
    from pcb_qa.question_banks.prompts import get_prompts_path, get_prompts_text

    # Get the file path (useful for passing to an LLM context)
    path = get_prompts_path()

    # Get the full text content
    text = get_prompts_text()
"""

from __future__ import annotations

import pathlib

_PROMPTS_FILENAME = "question_generation_prompts.md"

#: The directory where this module (prompts.py) lives — i.e. the
#: ``pcb_qa/question_banks/`` package directory.
_MODULE_DIR = pathlib.Path(__file__).resolve().parent


def get_prompts_path() -> pathlib.Path:
    """Return the filesystem path to the question generation prompts markdown file.

    Returns
    -------
    pathlib.Path
        Absolute path to ``question_generation_prompts.md``.
    """
    return _MODULE_DIR / _PROMPTS_FILENAME


def get_prompts_text() -> str:
    """Read and return the full text of the question generation prompts file.

    Returns
    -------
    str
        The complete markdown content of the prompts document.
    """
    return get_prompts_path().read_text(encoding="utf-8")