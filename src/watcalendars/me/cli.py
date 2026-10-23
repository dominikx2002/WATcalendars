"""`watcal-me` - build YOUR OWN WCY calendar from the e-Dziekanat.

Logs in with your e-Dziekanat credentials, reads your group's plan and
writes a .ics. Meant to be run by one student on their own machine; the
plan of a study group is the same for everyone in it, so the resulting
.ics is valid for the whole group and can be committed to the shared
repo.

Credentials come from the environment (WATCAL_ME_USER / WATCAL_ME_PASS)
or an interactive prompt. They are never stored or logged.

    watcal-me --group WCY22KC2S0
    watcal-me --group WCY22KC2S0 --out my_plan.ics
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from datetime import date

from watcalendars.core.logging import (ERROR, INFO, OK as OK_, SUCCESS,
                                        WARNING, get_logger, setup_logging)
from watcalendars.core.paths import calendars_dir, ensure_dir
from watcalendars.me.parse_edziekanat import parse
from watcalendars.me.session import BASE as _BASE
from watcalendars.me.session import (LoginError, derive_exv, fetch_logged,
                                     group_codes, login, login_and_fetch_plan,
                                     looks_like_plan)
from watcalendars.store.ics import build_calendar, write_calendar

log = get_logger()


def _academic_start_year(today: date) -> int:
    """Year the current autumn term began (Sep-Dec: this year, else last)."""
    return today.year if today.month >= 9 else today.year - 1


def _credentials(args) -> tuple:
    user = args.user or os.environ.get("WATCAL_ME_USER")
    password = os.environ.get("WATCAL_ME_PASS")
    if not user:
        user = input("e-Dziekanat identyfikator (Imię Nazwisko): ").strip()
    if not password:
        password = getpass.getpass("e-Dziekanat hasło: ")
    return user, password


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="watcal-me",
                                description="Build your own WCY calendar "
                                            "from the e-Dziekanat")
    p.add_argument("--group",
                   help="your study group code, used as the calendar name "
                        "and .ics filename (e.g. WCY22KC2S0)")
    p.add_argument("--all-groups", action="store_true",
                   help="fetch EVERY WCY group from the 'Plan zajęć grupy "
                        "dziekańskiej' chooser and write one .ics each")
    p.add_argument("--groups-iid", type=int, default=20261,
                   help="term id of the group chooser (default 20261; "
                        "changes each semester)")
    p.add_argument("--delay", type=float, default=4.0,
                   help="seconds between groups in --all-groups (default 4)")
    p.add_argument("--limit", type=int,
                   help="in --all-groups, only do the first N groups "
                        "(for a quick dry run)")
    p.add_argument("--user", help="e-Dziekanat identifier; else "
                                  "$WATCAL_ME_USER or a prompt")
    p.add_argument("--out", help="output .ics path; default: the WCY "
                                 "calendars dir inside the repo")
    p.add_argument("--semester", default="zima", choices=("zima", "lato"),
                   help="which semester folder to write into (default zima)")
    p.add_argument("--year", type=int, help="academic start year "
                                            "(default: inferred from today)")
    p.add_argument("--exv", help="group selector for a group other than "
                                 "your own (copy from the e-Dziekanat URL)")
    p.add_argument("--mid", type=int, help="menu id override (auto-detected)")
    p.add_argument("--iid", type=int, help="term id override (auto-detected)")
    p.add_argument("--dump", help="also save the raw fetched page here, for "
                                  "debugging when the plan is not recognised")
    p.add_argument("--with-rooms", action="store_true",
                   help="try to read room numbers (unreliable in the "
                        "simplified view; off by default)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--log-file")
    return p


def session_base():
    return _BASE


def _run_all_groups(args, user, password, year) -> int:
    """Log in once, then fetch every group's plan from the chooser."""
    mid = args.mid or 328
    plan_iid = args.iid or 20264
    try:
        session, sid = login(user, password)
    except LoginError as exc:
        log.error(f"{ERROR} {exc}")
        return 1
    except Exception as exc:
        log.error(f"{ERROR} could not reach the e-Dziekanat: "
                  f"{type(exc).__name__}: {exc}")
        return 1

    log.info(f"{INFO} Loading the group chooser (mid={mid}, "
             f"iid={args.groups_iid})...")
    chooser = fetch_logged(session, session_base(), sid, mid, args.groups_iid)
    codes = group_codes(chooser)
    if not codes:
        log.error(f"{ERROR} no groups found on the chooser page - the "
                  f"--groups-iid ({args.groups_iid}) may be wrong for this "
                  f"semester.")
        return 1
    if args.limit:
        codes = codes[:args.limit]
    log.info(f"{INFO} {len(codes)} groups to fetch, {args.delay}s apart "
             f"(~{len(codes) * args.delay / 60:.0f} min)")

    target_dir = calendars_dir("wcy", args.semester)
    ensure_dir(target_dir)
    done = {"added": 0, "changed": 0, "unchanged": 0, "empty": 0, "error": 0}
    for i, code in enumerate(codes, 1):
        if i > 1:
            time.sleep(args.delay)
        try:
            html = fetch_logged(session, session_base(), sid, mid, plan_iid,
                                exv=derive_exv(code))
            lessons = [x for x in parse(html, academic_start_year=year,
                                        with_rooms=args.with_rooms) if x.is_valid]
        except Exception as exc:
            log.warning(f"{ERROR} [{i}/{len(codes)}] {code}: "
                        f"{type(exc).__name__}: {exc}")
            done["error"] += 1
            continue
        if not lessons:
            log.warning(f"{WARNING} [{i}/{len(codes)}] {code}: 0 events - "
                        f"keeping the old .ics")
            done["empty"] += 1
            continue
        status = write_calendar(code, lessons, target_dir)
        done[status] += 1
        log.info(f"{OK_} [{i}/{len(codes)}] {code}: {status} "
                 f"({len(lessons)} events)")

    log.info(f"{SUCCESS} All groups done: "
             + ", ".join(f"{k}={v}" for k, v in done.items()))
    # fail the run only if nothing at all came through
    return 0 if (done["added"] + done["changed"] + done["unchanged"]) else 1


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(verbose=args.verbose, logfile=args.log_file)

    year = args.year or _academic_start_year(date.today())
    user, password = _credentials(args)
    if not user or not password:
        log.error(f"{ERROR} No credentials given.")
        return 2

    if args.all_groups:
        return _run_all_groups(args, user, password, year)

    if not args.group:
        log.error(f"{ERROR} --group is required (or use --all-groups).")
        return 2

    log.info(f"{INFO} Logging in to the e-Dziekanat as '{user}'...")
    try:
        html = login_and_fetch_plan(user, password, semester=args.semester,
                                    mid=args.mid, iid=args.iid, exv=args.exv)
    except LoginError as exc:
        log.error(f"{ERROR} {exc}")
        return 1
    except Exception as exc:  # network, Imperva, timeouts
        log.error(f"{ERROR} could not reach the e-Dziekanat: "
                  f"{type(exc).__name__}: {exc}")
        return 1

    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as handle:
            handle.write(html)
        log.info(f"{INFO} Saved raw page to {args.dump} ({len(html)} chars)")

    if not looks_like_plan(html):
        log.error(f"{ERROR} logged in, but the page is not the schedule - "
                  f"the 'Rozkład zajęć' view may need to be opened "
                  f"differently. Nothing was written.")
        return 1

    lessons = parse(html, academic_start_year=year, with_rooms=args.with_rooms)
    valid = [x for x in lessons if x.is_valid]
    log.info(f"{INFO} Parsed {len(valid)} events for {args.group}")

    if not valid:
        # Same rule as the faculty scrapers: never overwrite a good old
        # calendar with an empty one.
        log.error(f"{ERROR} no events parsed - keeping the existing .ics, "
                  f"if any. (Did the plan layout change?)")
        return 1

    target_dir = (os.path.dirname(os.path.abspath(args.out)) if args.out
                  else calendars_dir("wcy", args.semester))
    ensure_dir(target_dir)

    if args.out:
        content = build_calendar(args.group, valid)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(content)
        log.info(f"{SUCCESS} Wrote {args.out} ({len(valid)} events)")
    else:
        status = write_calendar(args.group, valid, target_dir)
        log.info(f"{SUCCESS} {args.group}.ics {status} ({len(valid)} events) "
                 f"in {target_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
