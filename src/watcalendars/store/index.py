"""Builds db/calendars/index.json - the file the website reads.

The site is static and served from the same repository, so it cannot
run a directory listing. This turns the calendar tree into one small
JSON document: every faculty, every group, how many events it holds and
when it was written.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict

from watcalendars.core.logging import INFO, SUCCESS, WARNING, get_logger
from watcalendars.core.paths import CALENDARS_DIR
from watcalendars.core.semester import current_semester

log = get_logger()

INDEX_FILE = os.path.join(CALENDARS_DIR, "index.json")
STATUS_FILE = os.path.join(CALENDARS_DIR, "status.json")
_CALNAME = re.compile(r"^X-WR-CALNAME:(.*)$", re.MULTILINE)


def _scan_calendar(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    match = _CALNAME.search(content)
    return {
        "events": content.count("BEGIN:VEVENT"),
        "name": match.group(1).strip() if match else None,
    }


def _source_urls(code: str, semester: str) -> Dict[str, str]:
    """{group: source page} so the site can link back to the original.

    Missing or unreadable maps are not fatal - the link is a nicety, the
    calendar itself is the point.
    """
    from watcalendars.store.groups import load_groups

    for argument in (semester, None):
        try:
            return load_groups(code, argument)
        except Exception:
            continue
    return {}


def _derive_template(groups, sources) -> str:
    """Infer "...{group}.htm" from the group URLs, if one shape fits most."""
    counts = {}
    for row in groups:
        url = sources.get(row[0])
        if not url or row[0] not in url:
            continue
        candidate = url.replace(row[0], "{group}")
        counts[candidate] = counts.get(candidate, 0) + 1

    if not counts:
        return ""
    best, hits = max(counts.items(), key=lambda item: item[1])
    return best if hits >= 2 else ""


def build_index() -> Dict:
    """Scan db/calendars and write index.json. Returns the document."""
    from watcalendars.core.registry import FACULTIES, CODES

    document = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "current_semester": current_semester(),
        "faculties": {},
    }

    total_groups = 0
    for code in CODES:
        spec = FACULTIES[code]
        entry = {"name": spec.name, "semesters": {}}

        for semester in ("zima", "lato"):
            directory = os.path.join(
                CALENDARS_DIR, f"{code}_calendars", f"{code}_calendars_{semester}"
            )
            if not os.path.isdir(directory):
                continue

            sources = _source_urls(code, semester)
            groups = []
            for filename in sorted(os.listdir(directory)):
                if not filename.endswith(".ics"):
                    continue
                path = os.path.join(directory, filename)
                try:
                    details = _scan_calendar(path)
                except Exception as exc:
                    log.warning(f"{WARNING} Could not read {path}: {exc}")
                    continue
                # [id, event count, source url] instead of an object per
                # group: with ~2000 groups the object form tripled the
                # file the site downloads on every visit. The .ics
                # filename is id + ".ics"; the URL may be absent.
                group_id = filename[:-4]
                row = [group_id, details["events"]]
                source = sources.get(group_id)
                if source:
                    row.append(source)
                groups.append(row)
                del source

            if not groups:
                continue

            # Source URLs are near-identical per faculty - "...{group}.htm".
            # Storing the template once and dropping the per-group copies
            # keeps index.json small (131 kB -> ~45 kB); only the groups
            # that deviate (WIG's absolute Joomla links) keep their own.
            template = _derive_template(groups, sources)
            if template:
                entry.setdefault("url_template", {})[semester] = template
                for row in groups:
                    if len(row) > 2 and row[2] == template.replace("{group}", row[0]):
                        row.pop()

            entry["semesters"][semester] = groups
            total_groups += len(groups)

        if entry["semesters"]:
            document["faculties"][code] = entry

    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(INDEX_FILE) / 1024
    log.info(
        f"{SUCCESS} Wrote index.json: {len(document['faculties'])} faculties, "
        f"{total_groups} groups ({size_kb:.1f} kB)"
    )
    return document


def write_status(ok: bool, detail: str = "", run_url: str = "") -> Dict:
    """Record how the last scrape went, for the website's status dot.

    Written next to the calendars so the page can read it from its own
    origin: polling the GitHub API instead would burn the 60 requests
    per hour that unauthenticated callers get, shared across every
    visitor behind the same address.
    """
    document = {
        "conclusion": "success" if ok else "failure",
        "finished": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "detail": detail,
    }
    if run_url:
        document["run_url"] = run_url

    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, separators=(",", ":"))

    log.info(f"{INFO} Scrape status: {document['conclusion']}"
             + (f" ({detail})" if detail else ""))
    return document
