"""Tests for pcb_qa.logging_config."""

from __future__ import annotations

import logging
import sys

from pcb_qa.logging_config import logger, setup_logging


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_returns_logger_instance(self) -> None:
        result = setup_logging()
        assert isinstance(result, logging.Logger)

    def test_logger_name(self) -> None:
        result = setup_logging()
        assert result.name == "pcb_qa"

    def test_default_log_level(self) -> None:
        result = setup_logging()
        assert result.level == logging.INFO

    def test_custom_log_level(self) -> None:
        result = setup_logging(level=logging.DEBUG)
        assert result.level == logging.DEBUG

    def test_has_stream_handler(self) -> None:
        result = setup_logging()
        stream_handlers = [h for h in result.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_handler_writes_to_stdout(self) -> None:
        result = setup_logging()
        for handler in result.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                assert handler.stream is sys.stdout

    def test_handler_has_formatter(self) -> None:
        result = setup_logging()
        for handler in result.handlers:
            assert handler.formatter is not None

    def test_formatter_contains_levelname(self) -> None:
        result = setup_logging()
        handler = result.handlers[0]
        assert handler.formatter is not None
        fmt = handler.formatter._fmt
        assert "%(levelname)s" in fmt or "%(levelname)-8s" in fmt

    def test_idempotent_setup(self) -> None:
        """Calling setup_logging multiple times should not duplicate handlers."""
        initial_handler_count = len(logger.handlers)
        setup_logging()
        setup_logging()
        # After calling setup_logging again, no new handlers should be added
        assert len(logger.handlers) == initial_handler_count


class TestModuleLevelLogger:
    """Tests for the module-level logger."""

    def test_module_logger_exists(self) -> None:
        assert logger is not None

    def test_module_logger_name(self) -> None:
        assert logger.name == "pcb_qa"

    def test_module_logger_can_log(self, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="pcb_qa"):
            logger.info("Test message")
        assert "Test message" in caplog.text