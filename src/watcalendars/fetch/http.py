"""Plain HTTP fetching - no browser.

Most WAT schedule pages are static files or server-rendered HTML. Only
the sites behind Imperva/Incapsula actually need a real browser, so this
is the default and `browser` is the exception.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Sequence, Tuple

import requests

from watcalendars.core.logging import (
    DEBUG,
    ERROR,
    GET,
    INFO,
    OK,
    RESPONSE,
    WARNING,
    format_duration,
    format_size,
    get_logger,
)

log = get_logger()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}

_META_CHARSET = re.compile(
    rb"""<meta[^>]+charset\s*=\s*["']?\s*([a-zA-Z0-9_\-]+)""", re.IGNORECASE
)


def decode(body: bytes, header_charset: Optional[str] = None) -> str:
    """Decode a page body, trusting the document over the HTTP header.

    Plansoft pages are windows-1250 and declare it only in a <meta> tag,
    while sending no charset in the Content-Type header - requests would
    otherwise fall back to ISO-8859-1 and mangle every Polish character.
    """
    match = _META_CHARSET.search(body[:4096])
    candidates = []
    if match:
        candidates.append(match.group(1).decode("ascii", "ignore"))
    if header_charset:
        candidates.append(header_charset)
    candidates += ["utf-8", "windows-1250"]

    for charset in candidates:
        try:
            return body.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def fetch_one(url: str, timeout: int = 30, retries: int = 3) -> Optional[str]:
    """GET a single URL, returning decoded text or None.

    Every attempt is logged at DEBUG with status, size and elapsed time,
    which is what you need when one faculty starts failing at 00:00.
    """
    for attempt in range(1, retries + 1):
        started = time.monotonic()
        log.debug(f"{GET} attempt {attempt}/{retries} {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            elapsed_ms = (time.monotonic() - started) * 1000
            log.debug(
                f"{RESPONSE} {response.status_code} {url} "
                f"[{format_size(len(response.content))}, {elapsed_ms:.0f} ms, "
                f"type={response.headers.get('content-type', '?')}]"
            )
            response.raise_for_status()

            charset = None
            if "charset=" in response.headers.get("content-type", "").lower():
                charset = response.encoding
            text = decode(response.content, charset)
            log.debug(f"{DEBUG} decoded {len(text)} chars from {url}")
            return text
        except Exception as exc:
            elapsed_ms = (time.monotonic() - started) * 1000
            log.debug(
                f"{WARNING} GET failed (attempt {attempt}/{retries}, {elapsed_ms:.0f} ms) "
                f"{url}: {type(exc).__name__}: {exc}"
            )
            if attempt == retries:
                log.warning(
                    f"{ERROR} GET {url} gave up after {retries} attempts: "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                time.sleep(min(2 * attempt, 5))
    return None


def fetch_many(
    pairs: Sequence[Tuple[str, str]],
    concurrency: int = 10,
    label: str = "Fetching",
) -> Dict[str, Optional[str]]:
    """GET many (identifier, url) pairs in parallel."""
    results: Dict[str, Optional[str]] = {}
    total = len(pairs)
    started = time.monotonic()
    log.info(f"{INFO} {label}: {total} items over plain HTTP, concurrency={concurrency}")

    def work(item):
        identifier, url = item
        return identifier, url, fetch_one(url)

    failures = []
    total_bytes = 0
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        for done, (identifier, url, html) in enumerate(pool.map(work, pairs), 1):
            results[identifier] = html
            if html:
                total_bytes += len(html)
                log.info(
                    f"{OK} [{done}/{total}] {identifier} ({format_size(len(html))})"
                )
            else:
                failures.append(identifier)
                log.warning(f"{ERROR} [{done}/{total}] {identifier} FAILED - {url}")

    elapsed = time.monotonic() - started
    rate = total_bytes / elapsed if elapsed else 0
    log.info(
        f"{INFO} {label} done: {total - len(failures)}/{total} ok, "
        f"{format_size(total_bytes)} in {format_duration(elapsed)} "
        f"({format_size(int(rate))}/s)"
    )
    if failures:
        log.warning(f"{WARNING} Failed identifiers: {', '.join(failures[:20])}"
                    + (f" (+{len(failures) - 20} more)" if len(failures) > 20 else ""))

    return results
