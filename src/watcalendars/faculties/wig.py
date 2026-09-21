"""WIG - Wydział Inżynierii Lądowej i Geodezji.

The odd one out: schedules are Word documents, reached through a
two-level Joomla listing (subcategory -> group -> .docx download). Its
irregularity is contained here instead of leaking into the pipeline.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Optional

from watcalendars.core.logging import ERROR, INFO, OK, SUCCESS, WARNING, get_logger
from watcalendars.core.models import FacultySpec
from watcalendars.core.paths import GROUPS_DIR, ensure_dir, groups_file
from watcalendars.parsers.groups.wig import parse_wig_groups_from_subcategory
from watcalendars.parsers.groups.wig_subcategory import parse_wig_subcategories

log = get_logger()


def parse_wig_docx(path):
    """Lazy import: python-docx is only needed when WIG actually runs."""
    from watcalendars.parsers.schedule.wig import parse_wig_docx as _parse

    return _parse(path)

SUBCATEGORY_URL = (
    "https://www.wig.wat.edu.pl/cpp/index.php/studenci/"
    "plany-rozklady-terminy/rozklady-zajec"
)


def collect_groups(spec: FacultySpec, semester: Optional[str]) -> Dict[str, str]:
    """Walk subcategories, collecting every group's download URL."""
    from watcalendars.fetch import strategies

    log.info(f"{INFO} WIG: fetching subcategory index")
    index = strategies.fetch(
        spec.groups_fetcher, [("subcategories", SUBCATEGORY_URL)], 1, "WIG subcategories"
    )
    html = index.get("subcategories")
    if not html:
        log.error(f"{ERROR} WIG: could not fetch subcategory index")
        return {}

    subcategories = parse_wig_subcategories(html)
    log.info(f"{OK} WIG: {len(subcategories)} subcategories")
    if not subcategories:
        return {}

    pages = strategies.fetch(
        spec.groups_fetcher,
        list(subcategories.items()),
        spec.concurrency,
        "WIG subcategory pages",
    )

    groups: Dict[str, str] = {}
    by_subcategory: Dict[str, Dict[str, str]] = {}
    for name, page_html in pages.items():
        if not page_html:
            log.warning(f"{WARNING} WIG: subcategory '{name}' returned nothing")
            continue
        found = parse_wig_groups_from_subcategory(page_html)
        by_subcategory[name] = found
        for group, url in found.items():
            if group in groups and groups[group] != url:
                log.debug(f"{WARNING} WIG: duplicate '{group}', keeping first URL")
                continue
            groups.setdefault(group, url)
        log.debug(f"{OK} WIG: '{name}' -> {len(found)} groups")

    _save_by_subcategory(by_subcategory)
    log.info(f"{SUCCESS} WIG: {len(groups)} groups across {len(by_subcategory)} subcategories")
    return dict(sorted(groups.items()))


def _save_by_subcategory(by_subcategory: Dict[str, Dict[str, str]]) -> None:
    """Keep the per-subcategory breakdown that the old script produced."""
    import unicodedata

    target = ensure_dir(
        os.path.join(GROUPS_DIR, "wig_groups_url", "wig_groups_by_subcategory")
    )
    for name, groups in by_subcategory.items():
        ascii_name = (
            unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode()
        )
        safe = "".join(c for c in ascii_name if c.isalnum() or c in " _").strip()
        path = os.path.join(target, safe.replace(" ", "_") + "_url.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(groups, handle, indent=2, ensure_ascii=False)


SPEC = FacultySpec(
    code="wig",
    name="Wydział Inżynierii Lądowej i Geodezji",
    groups_url=SUBCATEGORY_URL,
    schedule_url="{group}",  # the group map already holds absolute URLs
    parse_groups=None,
    parse_schedule=parse_wig_docx,
    seasonal=False,
    concurrency=6,
    fetch_strategy="docx",
    groups_fetch_strategy="browser",
    custom_groups_job=collect_groups,
    notes="Two-stage Joomla listing; schedules are .docx, not HTML.",
)
