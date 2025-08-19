"""Logging utilities for I3 Gateway."""

import logging
import sys
from pathlib import Path

import structlog
from structlog.types import Processor


def setup_logging(
    level: str = "INFO", format_type: str = "json", log_file: str | None = None
) -> None:
    """Configure structured logging for the application."""
    # Convert string level to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]

    # Add appropriate renderer
    if format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Setup file logging if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(log_level)

        # Add file handler to root logger
        logging.root.addHandler(file_handler)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)
