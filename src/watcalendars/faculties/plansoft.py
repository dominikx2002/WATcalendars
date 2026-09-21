"""Shared logic for the six faculties that publish with Plansoft.org.

IOE, WEL, WIM, WLO, WML and WTC all serve the same artefacts:

    index.xml          <- the group list, real XML
    <GROUP>.htm        <- one schedule per group, static HTML

The group list used to be scraped out of the XSLT-rendered view by
hunting for <td valign=TOP>. Parsing the XML directly is shorter, more
robust, and also yields the period name ("WIM - zima 2026-27").
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

from watcalendars.core.logging import ERROR, OK, WARNING, get_logger

log = get_logger()

_DECLARED_ENCODING = re.compile(r'encoding=["\']([\w\-]+)["\']', re.IGNORECASE)


def _strip_declaration(xml_text: str) -> str:
    """ElementTree refuses a declared encoding on an already-decoded str."""
    return _DECLARED_ENCODING.sub("", xml_text, count=1)


HTML_EXTENSIONS = ("htm", "html")


def parse_index(
    xml_text: str, accept: Tuple[str, ...] = HTML_EXTENSIONS
) -> Tuple[List[str], Optional[str]]:
    """Return (group names, period label) from a Plansoft index.xml.

    `accept` lists the href extensions that count as a group schedule.
    It defaults to HTML only, because some faculties list supplementary
    PDFs (timetable grids, academic-year calendars) next to the real
    groups - see WTC and IOE for the two opposite cases.
    """
    if not xml_text:
        log.error(f"{ERROR} Empty index.xml")
        return [], None

    try:
        root = ET.fromstring(_strip_declaration(xml_text))
    except ET.ParseError as exc:
        log.error(f"{ERROR} index.xml is not valid XML: {exc}")
        return [], None

    period = None
    period_node = root.find("period")
    if period_node is not None:
        period = period_node.get("name")

    groups = []
    skipped = {}
    for node in root.iter("gro"):
        # The identifier must come from href, not text: href is the actual
        # filename on the server (ASCII-transliterated), while text keeps
        # Polish diacritics and would produce a 404 when used in a URL.
        href = (node.get("href") or "").strip()
        if not href:
            continue
        stem, _, extension = href.rpartition(".")
        extension = extension.lower()
        if extension not in accept:
            # Some faculties have switched to PDF; the HTML parsers
            # cannot read those, so say so instead of emitting dead URLs.
            skipped[extension] = skipped.get(extension, 0) + 1
            continue
        groups.append("_".join((stem or href).split()))

    if skipped:
        detail = ", ".join(f"{count}x .{ext}" for ext, count in sorted(skipped.items()))
        log.warning(
            f"{WARNING} index.xml: skipped {sum(skipped.values())} non-HTML entries "
            f"({detail}) - no parser for these formats"
        )

    log.debug(f"{OK} index.xml: {len(groups)} groups, period={period!r}")
    if not groups:
        log.warning(f"{WARNING} index.xml parsed but contained no <gro> entries")

    return sorted(set(groups)), period


def parse_groups(xml_text: str, accept: Tuple[str, ...] = HTML_EXTENSIONS) -> List[str]:
    """FacultySpec.parse_groups entry point."""
    groups, period = parse_index(xml_text, accept=accept)
    if period:
        log.info(f"{OK} Plansoft period: {period}")
    return groups
