"""Structured application logging."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure a consistent log format for the whole application."""
    root = logging.getLogger()
    if root.handlers:  # already configured (e.g. under uvicorn reload)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
