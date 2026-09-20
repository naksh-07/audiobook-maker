#!/usr/bin/env python3
"""
Audiobook Factory - Centralized Logging Engine.
Provides consistent, formatted, UTF-8 aware logging to both console and audiobooks/pipeline.log.
"""

import sys
import logging
from pathlib import Path

# Paths
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = WORKSPACE_DIR / "audiobooks"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "pipeline.log"

_initialized = False


def setup_logger(name: str = "AudiobookFactory", log_file: Path = LOG_FILE) -> logging.Logger:
    """Initialize and return a configured logger with console and file handlers."""
    global _initialized
    logger = logging.getLogger(name)

    if _initialized and logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Clear existing handlers if any
    logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File Handler
    try:
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"[WARN] Failed to attach FileHandler for {log_file}: {e}\n")

    # Console Handler (UTF-8 safe)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(fmt="%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    _initialized = True
    return logger


logger = setup_logger()
