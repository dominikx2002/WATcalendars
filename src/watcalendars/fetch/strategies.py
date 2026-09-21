"""Maps a strategy name to a fetcher, so FacultySpec can name one."""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

from watcalendars.fetch import browser, http

HTTP = "http"
BROWSER = "browser"
BROWSER_SLOW = "browser_slow"

VALID = (HTTP, BROWSER, BROWSER_SLOW)


def fetch(
    strategy: str,
    pairs: Sequence[Tuple[str, str]],
    concurrency: int = 10,
    label: str = "Fetching",
) -> Dict[str, Optional[str]]:
    if strategy == HTTP:
        return http.fetch_many(pairs, concurrency=concurrency, label=label)
    if strategy in (BROWSER, BROWSER_SLOW):
        return browser.fetch_many(
            pairs, concurrency=concurrency, label=label, strategy=strategy
        )
    raise ValueError(f"Unknown fetch strategy '{strategy}' (valid: {', '.join(VALID)})")
