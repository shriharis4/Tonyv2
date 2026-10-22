"""
Structured logging setup for Tony.

Replaces ad hoc `print(f"[ROUTER] ...")` / `print(f"[TOOL] ...")` calls with
Python's `logging` module, writing to a rotating file so post-hoc debugging
doesn't depend on a live console. Also logs every
(transcript -> matched intent -> tool -> result) tuple to a dedicated
logger for offline accuracy review and future regression-corpus building.

Usage:
    from core.logging_config import get_logger, log_turn_outcome
    logger = get_logger(__name__)
    logger.info("...")
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

_MAIN_LOG_FILE = LOG_DIR / "tony.log"
_ACCURACY_LOG_FILE = LOG_DIR / "routing_accuracy.log"

_configured = False
_accuracy_logger = None


def _configure_root_once():
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger("tony")
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        _MAIN_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    root.addHandler(console_handler)

    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a module-scoped logger under the shared 'tony' root logger,
    writing to a rotating file (logs/tony.log) and the console."""
    _configure_root_once()
    if not name.startswith("tony"):
        name = f"tony.{name}"
    return logging.getLogger(name)


def _get_accuracy_logger() -> logging.Logger:
    global _accuracy_logger
    if _accuracy_logger is not None:
        return _accuracy_logger

    logger = logging.getLogger("tony.accuracy")
    logger.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(
        _ACCURACY_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.propagate = False
    _accuracy_logger = logger
    return logger


def log_turn_outcome(transcript: str, matched_intent: str, tool_name: str, result_ok: bool, detail: str = "") -> None:
    """Log one (transcript -> matched intent -> tool -> result) tuple for
    offline accuracy review and regression-corpus building."""
    logger = _get_accuracy_logger()
    status = "OK" if result_ok else "FAIL"
    safe_transcript = (transcript or "").replace("\n", " ")[:300]
    safe_detail = (detail or "").replace("\n", " ")[:300]
    logger.info(f"transcript='{safe_transcript}' | intent={matched_intent} | tool={tool_name} | status={status} | detail={safe_detail}")
