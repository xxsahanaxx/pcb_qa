"""Centralised logging configuration for the PCB QA framework."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the root logger for the package.

    Parameters
    ----------
    level:
        The minimum log level to emit.  Defaults to ``logging.INFO``.
    """
    logger = logging.getLogger("pcb_qa")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger


# Module-level convenience logger
logger = setup_logging()