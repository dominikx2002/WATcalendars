"""Fail fast when a WAF has blocked us.

Imperva/Incapsula blocks GitHub Actions' address ranges outright: every
request gets a ~800 B 403 page with an "Incapsula incident ID". Retrying
that is pointless - one blocked faculty used to burn 70+ minutes on
retries, hit the job timeout and starve the faculties queued after it.

A WafGuard is shared by every request of one faculty run. After
`threshold` 403s in a row it trips, and the remaining groups are skipped
instead of fetched. Any other response resets the streak, so a few
isolated 403s (a group that genuinely forbids access) never trip it.
"""
from __future__ import annotations

import threading
from typing import Optional

from watcalendars.core.logging import ERROR, get_logger

log = get_logger()

DEFAULT_THRESHOLD = 8

# Markers of an Imperva/Incapsula block or challenge page.
_WAF_MARKERS = (b"Incapsula incident ID", b"_Incapsula_Resource", b"Incapsula")


class FacultyBlocked(RuntimeError):
    """A faculty could not be scraped: WAF block, or nothing came back."""


def is_waf_block(status: Optional[int], body: Optional[bytes] = b"") -> bool:
    """True if a response looks like a WAF block rather than real content.

    A 403 with an Incapsula marker is a block; so is a short 403 page
    (the block page is ~800 B, a real 403 from the origin rarely matters
    here anyway). A 200 carrying the Incapsula challenge is a block too.
    """
    head = (body or b"")[:4096]
    if isinstance(head, str):
        head = head.encode("utf-8", "ignore")
    marked = any(marker in head for marker in _WAF_MARKERS)
    if status == 403:
        return marked or len(head) < 2048
    return status == 200 and marked


class WafGuard:
    """Counts consecutive 403s across threads; trips at `threshold`."""

    def __init__(self, label: str = "", threshold: int = DEFAULT_THRESHOLD):
        self.label = label
        self.threshold = max(1, threshold)
        self._lock = threading.Lock()
        self._streak = 0
        self._tripped = False
        self.blocked = 0
        self.skipped = 0

    @property
    def tripped(self) -> bool:
        with self._lock:
            return self._tripped

    def record(self, status: Optional[int]) -> None:
        """Feed one HTTP status. Only 403 extends the streak."""
        with self._lock:
            if status != 403:
                self._streak = 0
                return
            self.blocked += 1
            self._streak += 1
            just_tripped = not self._tripped and self._streak >= self.threshold
            if just_tripped:
                self._tripped = True
        if just_tripped:
            log.error(
                f"{ERROR} {self.label or 'faculty'}: {self.threshold} requests in a "
                f"row got HTTP 403 - looks like a WAF block, skipping the rest"
            )

    def skip(self) -> bool:
        """True (and counted) if the caller should not fetch at all."""
        with self._lock:
            if self._tripped:
                self.skipped += 1
                return True
            return False
