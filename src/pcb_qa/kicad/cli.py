"""KiCad CLI integration for exporting netlists and SPICE circuits.

Refactored from the original ``kicad_cli_helpers.py``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pcb_qa.logging_config import logger


class KiCadInterface:
    """Wrapper around the ``kicad-cli`` binary.

    On initialisation a symlink is created at ``<cwd>/kicad-cli`` pointing to
    the path specified in the ``KICAD_CLI_PATH`` environment variable.

    Parameters
    ----------
    kicad_cli_path:
        Override for the ``KICAD_CLI_PATH`` env var.
    """

    def __init__(self, kicad_cli_path: str | None = None) -> None:
        self.executable = os.getcwd() + "/kicad-cli"
        self._initialise_kicad_cli(kicad_cli_path)

    def _initialise_kicad_cli(self, override_path: str | None = None) -> None:
        cli_path = Path(override_path or os.getenv("KICAD_CLI_PATH", ""))
        if not cli_path.exists():
            logger.warning("KICAD_CLI_PATH not set or invalid; kicad-cli operations will fail.")
            return

        subprocess.run(["ln", "-sf", str(cli_path), "kicad-cli"], check=False)
        logger.info("Symlink created for kicad-cli at %s", self.executable)
        subprocess.run([self.executable, "-h"], check=False)

    def export_netlist_with_kicad_cli(self, project_name: str, output_file_name: str) -> None:
        """Export ``.kicad_sch`` / ``.pro`` to a KiCad sexpr netlist (``.net``)."""
        logger.info("Exporting netlist for %s -> %s", project_name, output_file_name)
        project_path = Path(project_name)
        if project_path.exists():
            subprocess.run(
                [self.executable, "sch", "export", "netlist", "--format", "kicadsexpr",
                 str(project_path), "--output", output_file_name],
                check=False,
            )
        else:
            raise FileNotFoundError(f"No valid schematic at {project_path}")

    def export_spice_with_kicad_cli(self, project_name: str, output_file_name: str) -> None:
        """Export ``.kicad_sch`` / ``.pro`` to a SPICE netlist (``.cir``)."""
        logger.info("Exporting SPICE for %s -> %s", project_name, output_file_name)
        project_path = Path(project_name)
        if project_path.exists():
            subprocess.run(
                [self.executable, "sch", "export", "netlist", "--format", "spice",
                 str(project_path), "--output", output_file_name],
                check=False,
            )
        else:
            raise FileNotFoundError(f"No valid schematic/project at {project_path}")