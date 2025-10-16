"""Structured logging utilities for the trading bot."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict

from rich.console import Console
from rich.logging import RichHandler


_console = Console()


def get_logger(name: str, logs_dir: Path) -> logging.Logger:
    """Return configured logger with console and file handlers."""

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    logs_dir.mkdir(parents=True, exist_ok=True)

    rich_handler = RichHandler(console=_console, show_time=True, rich_tracebacks=True)
    rich_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(logs_dir / f"{name}.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)

    return logger


def setup_category_loggers(logs_dir: Path) -> Dict[str, logging.Logger]:
    """Create loggers per category used across the bot."""

    categories = ["trades", "errors", "api_calls", "system"]
    return {category: get_logger(category, logs_dir) for category in categories}


def set_log_level(level: str) -> None:
    """Set log level for root logger."""

    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    logging.getLogger().setLevel(numeric_level)


