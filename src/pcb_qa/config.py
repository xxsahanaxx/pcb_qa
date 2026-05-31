"""Central configuration for the PCB QA framework.

All path conventions and default settings are defined here so that individual
modules never hard-code paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
"""Repository root (two levels up from ``src/pcb_qa``)."""

CONFIGS_DIR = PROJECT_ROOT / "configs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DEFAULT_PROJECTS_FILE = CONFIGS_DIR / "projects.json"

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _env(key: str, default: str | None = None) -> str | None:
    """Read an environment variable with an optional default."""
    return os.getenv(key, default)


KICAD_CLI_PATH: str | None = _env("KICAD_CLI_PATH")
NGSPICE_PATH: str | None = _env("NGSPICE_PATH", "ngspice")

# ---------------------------------------------------------------------------
# LLM / API configuration
# ---------------------------------------------------------------------------

OPENROUTER_API_KEY: str | None = _env("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL: str = _env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
EMBEDDING_MODEL_NAME: str = _env("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# ---------------------------------------------------------------------------
# LLM defaults
# ---------------------------------------------------------------------------

DEFAULT_LLM_MODELS: list[str] = [
    "claude-sonnet-4.6",
    "gemini-3-flash-preview",
    "gpt-5.4-nano",
    "llama-3.3-70b-instruct",
]

# ---------------------------------------------------------------------------
# Project file helpers
# ---------------------------------------------------------------------------


def load_projects_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the projects JSON configuration.

    Parameters
    ----------
    path:
        Path to a JSON file.  Falls back to ``configs/projects.json``.
    """
    config_path = Path(path) if path else DEFAULT_PROJECTS_FILE
    with open(config_path, "r", encoding="utf-8") as fh:
        return json.load(fh)