"""XPSH - Expense sharing tool"""

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from .ledger import Account
from .ledger import Expense
from .ledger import IndexedLedgerEntry
from .ledger import Ledger
from .ledger import LedgerEntry
from .ledger import Transfer

VERSION = "0.10.0"
LOG_FORMAT = "%(asctime)s | [%(name)s] %(levelname)s - %(message)s"


def get_version() -> str:
    return VERSION


def get_resource(file_name: str) -> Path:
    """Returns file path from application resource file"""
    return Path(__file__).parent.parent / "resources" / file_name


def _init_logging() -> None:
    log_console = Console(stderr=True)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = RichHandler(console=log_console, omit_repeated_times=False)
    logger.addHandler(handler)


def add_file_handler(filename: Path) -> None:
    """Add FileHandler to existing logger."""
    logger = logging.getLogger(__name__)
    handler = logging.FileHandler(filename=filename, mode="w")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)


def set_logging_level(level: int = logging.DEBUG) -> None:
    logger = logging.getLogger(__name__)
    logger.setLevel(level)


_init_logging()

__all__ = ["Account", "Expense", "IndexedLedgerEntry", "Ledger", "LedgerEntry", "Transfer"]
