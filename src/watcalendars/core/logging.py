"""Logging for the whole project.

Design goals, in order:

1. A developer debugging a broken faculty can see every request, its
   status, size and timing, and every parse decision - by adding -v.
2. The default (INFO) output stays readable in the GitHub Actions log.
3. A log file always captures DEBUG, whatever the console shows, so a
   failed nightly run can be diagnosed after the fact.

Replaces the `logs.append(msg); print(msg)` idiom that appeared in a
dozen modules and threw its collected messages away.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Optional

LOGGER_NAME = "watcalendars"


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    GREY = "\033[90m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _supports_colour() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("GITHUB_ACTIONS"):
        return True
    return sys.stdout.isatty()


_COLOUR = _supports_colour()


def paint(text: str, colour: str) -> str:
    return f"{colour}{text}{Colors.RESET}" if _COLOUR else text


OK = paint("[OK]", Colors.GREEN)
ERROR = paint("[ERROR]", Colors.RED)
WARNING = paint("[WARNING]", Colors.YELLOW)
INFO = paint("[INFO]", Colors.CYAN)
DEBUG = paint("[DEBUG]", Colors.GREY)
SUCCESS = paint("[SUCCESS]", Colors.GREEN)
GET = paint("[GET]", Colors.MAGENTA)
RESPONSE = paint("[RESPONSE]", Colors.MAGENTA)
CHANGED = paint("changed", Colors.YELLOW)
UNCHANGED = paint("unchanged", Colors.GREEN)
ADDED = paint("added", Colors.YELLOW)


# --------------------------------------------------------------------------
# Context: every line emitted inside a faculty run is tagged with its code,
# so interleaved or long logs stay attributable.
# --------------------------------------------------------------------------

_context: list = []


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.context = f"{_context[-1]}" if _context else "-"
        return True


@contextmanager
def context(name: str):
    _context.append(name)
    try:
        yield
    finally:
        _context.pop()


class _ConsoleFormatter(logging.Formatter):
    """Plain messages at INFO; time/level/context prefix at DEBUG."""

    def __init__(self, verbose: bool):
        super().__init__()
        self.verbose = verbose

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        if not self.verbose:
            return message
        stamp = time.strftime("%H:%M:%S", time.localtime(record.created))
        ctx = getattr(record, "context", "-")
        prefix = paint(f"{stamp} {record.levelname:<7} {ctx:<4}", Colors.GREY)
        return f"{prefix} {message}"


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(verbose: bool = False, logfile: Optional[str] = None) -> logging.Logger:
    """Configure the project logger. Safe to call more than once."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)  # handlers decide what is shown
    logger.handlers.clear()
    logger.filters.clear()
    logger.propagate = False
    logger.addFilter(_ContextFilter())

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(_ConsoleFormatter(verbose))
    logger.addHandler(console)

    if logfile:
        os.makedirs(os.path.dirname(os.path.abspath(logfile)) or ".", exist_ok=True)
        handler = logging.FileHandler(logfile, encoding="utf-8")
        handler.setLevel(logging.DEBUG)  # the file always gets everything
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s [%(context)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.debug(f"{DEBUG} Log file: {os.path.abspath(logfile)} (level=DEBUG)")

    logger.debug(
        f"{DEBUG} Logging ready | console={'DEBUG' if verbose else 'INFO'} "
        f"colour={_COLOUR} pid={os.getpid()}"
    )
    return logger


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------


def format_duration(seconds: float) -> str:
    """'05s', '02m10s', '01h02m03s' - was copy-pasted into 8 scrapers."""
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02}h{minutes:02}m{secs:02}s"
    if minutes:
        return f"{minutes:02}m{secs:02}s"
    return f"{secs:02}s"


def format_size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} kB"
    return f"{num_bytes} B"


def banner(text: str) -> None:
    log = get_logger()
    log.info("")
    log.info(paint(f"═══ {text} ═══", Colors.BOLD))


def table(rows, headers) -> None:
    """Log an aligned table - used for run summaries."""
    log = get_logger()
    widths = [
        max(len(str(headers[i])), *(len(str(r[i])) for r in rows)) if rows
        else len(str(headers[i]))
        for i in range(len(headers))
    ]
    line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    log.info(paint(line, Colors.BOLD))
    log.info("-" * len(line))
    for row in rows:
        log.info("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))


@contextmanager
def timed(label: str, tag: Optional[str] = None):
    """Banner + duration footer that every old scraper hand-rolled."""
    log = get_logger()
    started = time.time()
    with context(tag or "-"):
        log.info("")
        log.info(f"------[{time.strftime('%Y-%m-%d %H:%M')}] Start {label}:------")
        log.info("")
        failed = False
        try:
            yield
        except Exception:
            failed = True
            raise
        finally:
            duration = format_duration(time.time() - started)
            log.info("")
            status = f"{ERROR} failed" if failed else "finished"
            log.info(
                f"{INFO} [{time.strftime('%Y-%m-%d %H:%M')}] {label} {status} "
                f"(duration: {duration})"
            )
            log.info("")


@contextmanager
def step(description: str):
    """Log a sub-step with its own timing at DEBUG level."""
    log = get_logger()
    started = time.time()
    log.debug(f"{DEBUG} -> {description}")
    try:
        yield
    finally:
        elapsed = (time.time() - started) * 1000
        log.debug(f"{DEBUG} <- {description} ({elapsed:.0f} ms)")
