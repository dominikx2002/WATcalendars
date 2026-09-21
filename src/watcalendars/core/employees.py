"""Employee pipeline - scrapes USOSweb for staff names and titles.

Lecturer names on WCY schedules are matched against this list, which is
why it runs before the calendars in CI.
"""
from __future__ import annotations

from watcalendars.core.logging import ERROR, INFO, OK, SUCCESS, WARNING, get_logger, timed
from watcalendars.core.paths import EMPLOYEES_CONFIG
from watcalendars.parsers.employee import (
    detect_total_pages,
    parse_employees_page,
    scrape_employees_html,
)
from watcalendars.store.employees_writer import save_employees_to_json
from watcalendars.core.config_files import load_url_from_config

log = get_logger()

EXPECTED_MIN_PAGES = 54


def run_employees() -> int:
    """Scrape every USOSweb staff page; returns how many were collected."""
    with timed("WAT employees"):
        url, description = load_url_from_config(EMPLOYEES_CONFIG, "usos", "url")
        if not url:
            log.error(f"{ERROR} No employees URL configured in {EMPLOYEES_CONFIG}")
            return 0

        log.info(f"{INFO} Source: {description or url}")
        total_pages = detect_total_pages(url)

        if total_pages <= 0:
            log.error(f"{ERROR} Could not detect page count - aborting")
            return 0
        if total_pages < EXPECTED_MIN_PAGES:
            log.warning(
                f"{WARNING} Detected {total_pages} pages, expected at least "
                f"{EXPECTED_MIN_PAGES} - the page layout may have changed"
            )
        else:
            log.info(f"{OK} Detected {total_pages} pages")

        employees = []
        for page in range(1, total_pages + 1):
            page_url = f"{url}&page={page}"
            log.debug(f"{INFO} [{page}/{total_pages}] GET {page_url}")
            html = scrape_employees_html(page_url)
            if not html:
                log.warning(f"{WARNING} [{page}/{total_pages}] returned nothing")
                continue
            found = parse_employees_page(html, page, total_pages)
            employees.extend(found)
            log.debug(f"{OK} [{page}/{total_pages}] {len(found)} employees")

        if not employees:
            log.error(f"{ERROR} No employees scraped.")
            return 0

        save_employees_to_json(employees)
        log.info(f"{SUCCESS} Collected {len(employees)} employees")
        return len(employees)
