"""Single entry point for the whole project.

    watcal groups wcy            discover WCY groups
    watcal calendars wcy wel     build calendars for two faculties
    watcal run all               groups + calendars for everything
    watcal list                  show what is configured

Replaces the seventeen separate console scripts, eight of which were
broken because pyproject pointed at a `main` that did not exist.
"""
from __future__ import annotations

import argparse
import sys
import time

from watcalendars.core import registry
from watcalendars.core.logging import (
    ERROR,
    INFO,
    SUCCESS,
    WARNING,
    format_duration,
    get_logger,
    setup_logging,
)
from watcalendars.core.pipeline import run_calendars, run_groups
from watcalendars.core.semester import current_semester

log = get_logger()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watcal", description="WAT schedule scraper and ICS generator"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--log-file", help="also write logs to this file")
    parser.add_argument(
        "--semester",
        choices=("zima", "lato"),
        help="override the auto-detected semester",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("groups", "discover groups and write the group/url map"),
        ("calendars", "fetch schedules and write .ics files"),
        ("run", "groups then calendars"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument(
            "faculties",
            nargs="*",
            default=["all"],
            help=f"faculty codes or 'all' ({', '.join(registry.CODES)})",
        )

    sub.add_parser("employees", help="scrape the USOSweb staff list")
    sub.add_parser("list", help="show configured faculties")
    return parser


def cmd_list() -> int:
    log.info(f"{INFO} Detected semester: {current_semester().upper()}")
    log.info("")
    header = f"{'code':6} {'seasonal':9} {'fetch':14} {'conc':5} name"
    log.info(header)
    log.info("-" * len(header))
    for code in registry.CODES:
        spec = registry.FACULTIES[code]
        log.info(
            f"{spec.code:6} {str(spec.seasonal):9} {spec.fetch_strategy:14} "
            f"{spec.concurrency:<5} {spec.name}"
        )
    return 0


# Imperva tracks reputation per IP: hammering six protected faculties
# back to back got us 403s on whichever ran last. A short pause between
# faculties costs nothing on a nightly job and avoids the cascade.
PAUSE_BETWEEN_FACULTIES = 20


def _run_stage(stage: str, specs) -> int:
    failures = []
    for position, spec in enumerate(specs):
        if position and spec.fetch_strategy != "http":
            log.debug(
                f"{INFO} Pausing {PAUSE_BETWEEN_FACULTIES}s before "
                f"{spec.code.upper()} to stay under the WAF's rate limits"
            )
            time.sleep(PAUSE_BETWEEN_FACULTIES)
        try:
            if stage in ("groups", "run"):
                run_groups(spec)
            if stage in ("calendars", "run"):
                run_calendars(spec)
        except Exception as exc:
            failures.append(spec.code)
            log.error(f"{ERROR} {spec.code.upper()} failed: {type(exc).__name__}: {exc}")
            log.debug("traceback", exc_info=True)

    if failures:
        log.warning(
            f"{WARNING} Finished with failures: {', '.join(sorted(failures))} "
            f"({len(specs) - len(failures)}/{len(specs)} succeeded)"
        )
        return 1
    log.info(f"{SUCCESS} All {len(specs)} faculties completed.")
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(verbose=args.verbose, logfile=args.log_file)

    if args.semester:
        import os

        os.environ["WATCALENDARS_SEMESTER"] = args.semester

    if args.command == "list":
        return cmd_list()

    if args.command == "employees":
        # Imported here: the employee scraper needs Playwright, and the
        # HTTP-only faculties must stay usable without it.
        from watcalendars.core.employees import run_employees

        return 0 if run_employees() else 1

    try:
        specs = registry.resolve(args.faculties)
    except KeyError as exc:
        log.error(f"{ERROR} {exc}")
        return 2

    started = time.time()
    code = _run_stage(args.command, specs)
    log.info(f"{INFO} Total time: {format_duration(time.time() - started)}")
    return code


if __name__ == "__main__":
    sys.exit(main())
