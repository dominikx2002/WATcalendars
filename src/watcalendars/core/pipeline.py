"""The pipeline every faculty runs through.

This module replaces the eight near-identical `main()` functions that
used to live in calendar_*.py and groups_*.py. Everything that differed
between them is now a field on FacultySpec.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from watcalendars.core.logging import (
    DEBUG,
    ERROR,
    INFO,
    OK,
    SUCCESS,
    WARNING,
    context,
    format_size,
    get_logger,
    step,
    table,
    timed,
)
from watcalendars.core.models import FacultySpec, Lesson
from watcalendars.core.paths import cache_dir, ensure_dir
from watcalendars.core.semester import current_semester
from watcalendars.fetch import strategies
from watcalendars.store import groups as groups_store
from watcalendars.store import ics

log = get_logger()


def semester_for(spec: FacultySpec) -> Optional[str]:
    return current_semester() if spec.seasonal else None


def build_pairs(spec: FacultySpec, mapping: Dict[str, str]) -> List[Tuple[str, str]]:
    """(group, url) pairs, URL-encoding the group where it is templated."""
    pairs = []
    for group, url in sorted(mapping.items()):
        if "{group}" in url:
            url = url.format(group=quote(str(group), safe="*"))
        pairs.append((group, url))
    return pairs


def run_groups(spec: FacultySpec) -> Dict[str, str]:
    """Discover a faculty's groups and write the {group: url} map."""
    with timed(f"{spec.code.upper()} groups", tag=spec.code):
        semester = semester_for(spec)
        _log_spec(spec, semester)

        if spec.custom_groups_job is not None:
            log.debug(f"{INFO} {spec.code}: using custom groups job")
            mapping = spec.custom_groups_job(spec, semester)
            if not mapping:
                log.error(f"{ERROR} {spec.code.upper()}: no groups collected")
                return {}
            return groups_store.save_group_map(mapping, spec.code, semester)

        url = spec.url_for("groups", semester)
        log.info(f"{INFO} Group index: {url}")

        pages = strategies.fetch(
            spec.groups_fetcher, [(spec.code, url)], 1, f"{spec.code.upper()} group index"
        )
        html = pages.get(spec.code)
        if not html:
            log.error(f"{ERROR} {spec.code.upper()}: could not fetch group index")
            return {}

        log.debug(f"{DEBUG} Fetched {format_size(len(html))} of group index")
        with step(f"parse group index with {spec.parse_groups.__module__}"):
            found = spec.parse_groups(html)
        log.info(f"{SUCCESS} {spec.code.upper()}: {len(found)} groups found")
        log.debug(f"{DEBUG} Groups: {', '.join(found[:15])}"
                  + (f" (+{len(found) - 15} more)" if len(found) > 15 else ""))
        if not found:
            return {}

        return groups_store.save_groups(
            found, spec.code, spec.url_for("schedule", semester), semester
        )


def _fetch_documents(spec, pairs, label):
    """Download .docx schedules; returns {group: local path}.

    Goes through the browser's session (the WIG site sits behind
    Incapsula, which 403s plain requests and never fires a download
    event, so the old listener just timed out 30 s per file).
    """
    from watcalendars.fetch.browser import download_many

    target = ensure_dir(cache_dir(spec.code))
    warmup = spec.url_for("groups", None) if isinstance(spec.groups_url, str) else None
    blobs = download_many(pairs, spec.concurrency, label, warmup_url=warmup)

    results = {}
    for group, body in blobs.items():
        if not body:
            results[group] = None
            continue
        path = os.path.join(target, f"{group}.docx")
        with open(path, "wb") as handle:
            handle.write(body)
        results[group] = path

    saved = len([p for p in results.values() if p])
    log.info(f"{INFO} Saved {saved}/{len(pairs)} documents into '{target}'")
    return results


def run_calendars(spec: FacultySpec) -> Dict[str, List[str]]:
    """Fetch, parse and write .ics for every group of a faculty."""
    with timed(f"{spec.code.upper()} calendars", tag=spec.code):
        semester = semester_for(spec)
        _log_spec(spec, semester)

        with step("load group map"):
            mapping = groups_store.load_groups(spec.code, semester)
        pairs = build_pairs(spec, mapping)
        if not pairs:
            log.error(f"{ERROR} {spec.code.upper()}: no groups to process")
            return {}

        log.info(f"{INFO} Groups to process: {len(pairs)}")
        log.debug(f"{DEBUG} First URL: {pairs[0][1]}")
        label = f"Scraping {spec.code.upper()}"

        if spec.fetch_strategy == "docx":
            sources = _fetch_documents(spec, pairs, label)
        else:
            sources = strategies.fetch(
                spec.fetch_strategy, pairs, spec.concurrency, label
            )

        schedules = _parse_all(spec, sources)
        summary = ics.write_all(schedules, spec.code, semester or current_semester())
        _log_summary(spec, summary)
        return summary


def _log_spec(spec: FacultySpec, semester: Optional[str]) -> None:
    """Dump the effective configuration - the first thing you want when
    a faculty misbehaves."""
    log.info(f"{INFO} Semester: {(semester or current_semester()).upper()}")
    log.debug(f"{DEBUG} Faculty : {spec.name}")
    log.debug(f"{DEBUG} Fetch   : {spec.fetch_strategy} (groups: {spec.groups_fetcher})")
    log.debug(f"{DEBUG} Conc.   : {spec.concurrency}")
    log.debug(f"{DEBUG} Seasonal: {spec.seasonal}")
    if spec.notes:
        log.debug(f"{DEBUG} Notes   : {spec.notes}")


def _log_summary(spec: FacultySpec, summary: Dict[str, List[str]]) -> None:
    """Per-faculty result table, and the names behind each bucket."""
    rows = [(name, len(summary.get(name, []))) for name in
            ("added", "changed", "unchanged", "skipped")]
    table(rows, ["status", "groups"])
    for name in ("added", "changed", "skipped"):
        entries = summary.get(name) or []
        if entries:
            log.debug(f"{DEBUG} {name}: {', '.join(entries[:25])}"
                      + (f" (+{len(entries) - 25} more)" if len(entries) > 25 else ""))


def _parse_all(spec: FacultySpec, sources: Dict[str, Optional[str]]):
    """Run the faculty parser over every fetched source."""
    log.info(
        f"{INFO} Parsing {len(sources)} sources with "
        f"{spec.parse_schedule.__module__}.{spec.parse_schedule.__name__}"
    )
    schedules: Dict[str, List[Lesson]] = {}
    total_events = 0
    failures = 0
    dropped_total = 0
    empty_groups = []

    for group in sorted(sources):
        source = sources[group]
        if not source:
            log.debug(f"{WARNING} {group}: nothing fetched, skipping parse")
            schedules[group] = []
            failures += 1
            continue
        try:
            raw = spec.parse_schedule(source) or []
        except Exception as exc:
            log.warning(f"{ERROR} {group}: parser raised {type(exc).__name__}: {exc}")
            log.debug("parser traceback", exc_info=True)
            schedules[group] = []
            failures += 1
            continue

        parsed = [Lesson.from_dict(item) for item in raw]
        lessons = [lesson for lesson in parsed if lesson.is_valid]
        dropped = len(parsed) - len(lessons)
        dropped_total += dropped
        schedules[group] = lessons
        total_events += len(lessons)
        if not lessons:
            empty_groups.append(group)
        detail = f"{len(lessons)} events"
        if dropped:
            detail += f" ({dropped} dropped: missing start/end)"
        log.debug(f"{OK} {group}: {detail}")

    with_events = len([g for g, l in schedules.items() if l])
    if total_events:
        log.info(
            f"{SUCCESS} Parsed {total_events} events across {with_events} groups"
            + (f" | {failures} failed" if failures else "")
            + (f" | {dropped_total} lessons dropped" if dropped_total else "")
        )
        if empty_groups:
            log.warning(
                f"{WARNING} {len(empty_groups)} groups parsed to zero events: "
                + ", ".join(empty_groups[:20])
                + (f" (+{len(empty_groups) - 20} more)" if len(empty_groups) > 20 else "")
            )
    else:
        log.error(f"{ERROR} No events parsed at all - parser or source changed?")
    return schedules
