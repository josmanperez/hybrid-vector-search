from __future__ import annotations
import logging
import os
from datetime import datetime
from typing import Dict, Optional

_loggers: Dict[str, logging.Logger] = {}
_file_handler: Optional[logging.Handler] = None


def _current_log_path() -> str:
    log_dir = os.environ.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    date_stamp = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(log_dir, f"log-{date_stamp}.log")


def _ensure_file_handler() -> logging.Handler:
    global _file_handler  # pylint: disable=global-statement

    log_path = _current_log_path()
    if _file_handler and getattr(_file_handler, "baseFilename", None) == os.path.abspath(log_path):
        return _file_handler

    if _file_handler:
        _file_handler.close()

    handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _file_handler = handler
    return handler


def get_logger(name: str = "app") -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = _ensure_file_handler()
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(stream_handler)

    logger.propagate = False
    _loggers[name] = logger
    return logger
