"""Playwright fetching - for sites that a plain GET cannot reach.

Only needed where Imperva/Incapsula sits in front of the faculty site
(IOE, WEL, WLO, WML, WTC): those reject plain requests with 403 even
with a full set of browser headers, because they fingerprint TLS and
require the JS challenge to run.
"""
from __future__ import annotations

import asyncio
from typing import Dict, Optional, Sequence, Tuple

from watcalendars.core.logging import DEBUG, ERROR, INFO, OK, WARNING, get_logger
from watcalendars.fetch.http import decode

log = get_logger()

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--ignore-certificate-errors",
]


async def _request(context, url, timeout=90000):
    """Fetch a URL through the browser's network stack, without rendering.

    This is the workhorse. Imperva/Incapsula rejects plain `requests`
    because of its TLS fingerprint, but accepts the browser's - and the
    browser's APIRequestContext gives us the bytes as served, which is
    what we want: page.content() would hand back the rendered DOM, so an
    XML file would arrive as the browser's HTML rendering of it.
    """
    response = await context.request.get(url, timeout=timeout)
    body = await response.body()
    return response.status, body


async def _fetch_via_request(context, page, identifier, url):
    status, body = await _request(context, url)
    if status == 200:
        log.debug(f"{DEBUG} {identifier}: raw body {len(body)} bytes")
        return decode(body)
    if status == 404:
        # Worth shouting about: a seasonal faculty that has not published
        # this semester yet looks exactly like this.
        log.warning(
            f"{WARNING} {identifier}: HTTP 404 - {url} does not exist "
            f"(semester not published, or the address changed?)"
        )
    else:
        log.debug(f"{WARNING} {identifier}: HTTP {status} on direct request")
    return None


async def _fetch_via_challenge(context, page, identifier, url):
    """Fallback: navigate so the WAF sets its cookies, then re-request."""
    log.debug(f"{DEBUG} {identifier}: clearing JS challenge via navigation")
    await asyncio.sleep(2)
    try:
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
    except Exception as exc:
        log.debug(f"{WARNING} {identifier}: navigation failed: {exc}")

    for _ in range(8):
        await asyncio.sleep(2)
        status, body = await _request(context, url)
        if status == 200 and b"Incapsula" not in body[:4000]:
            log.debug(f"{DEBUG} {identifier}: challenge cleared, {len(body)} bytes")
            return decode(body)
    return None


STRATEGY_FETCHERS = {
    "browser": _fetch_via_request,
    "browser_slow": _fetch_via_request,
}


async def _scrape_async(
    pairs: Sequence[Tuple[str, str]],
    concurrency: int,
    label: str,
    strategy: str,
    retries: int = 3,
) -> Dict[str, Optional[str]]:
    from playwright.async_api import async_playwright

    fetcher = STRATEGY_FETCHERS[strategy]
    results: Dict[str, Optional[str]] = {}
    semaphore = asyncio.Semaphore(max(1, concurrency))
    total = len(pairs)
    done = 0
    lock = asyncio.Lock()

    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True, args=BROWSER_ARGS)
        context = await browser.new_context()
        log.info(
            f"{label} ({total} items) via browser [{strategy}], concurrency={concurrency}..."
        )

        async def worker(item):
            nonlocal done
            identifier, url = item
            async with semaphore:
                page = await context.new_page()
                html = None
                try:
                    for attempt in range(1, retries + 1):
                        try:
                            html = await fetcher(context, page, identifier, url)
                            if not html and attempt == 1:
                                # Direct request refused - try clearing the
                                # JS challenge once before giving up.
                                html = await _fetch_via_challenge(
                                    context, page, identifier, url
                                )
                            if html:
                                break
                            log.debug(
                                f"{WARNING} {identifier}: empty result "
                                f"(attempt {attempt}/{retries})"
                            )
                        except Exception as exc:
                            log.debug(
                                f"{WARNING} {identifier}: {exc} "
                                f"(attempt {attempt}/{retries})"
                            )
                        if attempt < retries:
                            await asyncio.sleep(2)
                finally:
                    await page.close()

                async with lock:
                    done += 1
                    position = done
                results[identifier] = html
                if html:
                    log.info(f"{OK} [{position}/{total}] {identifier} fetched ({len(html)} bytes)")
                else:
                    log.warning(f"{ERROR} [{position}/{total}] {identifier} failed")

        try:
            await asyncio.gather(*(worker(item) for item in pairs))
        finally:
            await browser.close()

    return results


async def _download_async(pairs, concurrency, label, warmup_url=None):
    from playwright.async_api import async_playwright

    results = {}
    total = len(pairs)
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True, args=BROWSER_ARGS)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        log.info(f"{INFO} {label}: {total} documents via browser")

        if warmup_url:
            # Clear the WAF challenge once, then reuse the cookies for
            # every download instead of paying the cost per file.
            log.debug(f"{DEBUG} warming up session on {warmup_url}")
            try:
                await page.goto(warmup_url, timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
            except Exception as exc:
                log.debug(f"{WARNING} warm-up failed: {exc}")

        try:
            for index, (identifier, url) in enumerate(pairs, 1):
                try:
                    response = await context.request.get(url, timeout=60000)
                    body = await response.body()
                    if response.status == 200 and body[:2] == b"PK":
                        results[identifier] = body
                        log.info(f"{OK} [{index}/{total}] {identifier} ({len(body)} bytes)")
                        continue
                    log.warning(
                        f"{ERROR} [{index}/{total}] {identifier}: HTTP {response.status}, "
                        f"{len(body)} bytes, not a document"
                    )
                except Exception as exc:
                    log.warning(f"{ERROR} [{index}/{total}] {identifier}: {exc}")
                results[identifier] = None
                await asyncio.sleep(1)
        finally:
            await browser.close()
    return results


def download_many(pairs, concurrency=1, label="Downloading", warmup_url=None):
    """Fetch binary documents (WIG's .docx) through the browser session."""
    return asyncio.run(_download_async(pairs, concurrency, label, warmup_url))


def fetch_many(
    pairs: Sequence[Tuple[str, str]],
    concurrency: int = 10,
    label: str = "Fetching",
    strategy: str = "browser",
) -> Dict[str, Optional[str]]:
    """Blocking wrapper so the pipeline does not care about asyncio."""
    return asyncio.run(_scrape_async(pairs, concurrency, label, strategy))
