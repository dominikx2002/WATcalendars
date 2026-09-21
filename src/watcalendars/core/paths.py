"""Every filesystem path in the project is computed here, once."""
from __future__ import annotations

import os
from typing import Optional

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.abspath(os.path.join(PACKAGE_DIR, "..", ".."))

# WATCALENDARS_DB_DIR redirects every output path, which makes it possible
# to run the full pipeline against a scratch directory without touching
# the repository's data.
DB_DIR = os.environ.get("WATCALENDARS_DB_DIR") or os.path.join(PROJECT_ROOT, "db")
GROUPS_DIR = os.path.join(DB_DIR, "groups_url")
CALENDARS_DIR = os.path.join(DB_DIR, "calendars")
CACHE_DIR = os.path.join(DB_DIR, "cache")
EMPLOYEES_FILE = os.path.join(DB_DIR, "employees.json")

GROUPS_CONFIG = os.path.join(DB_DIR, "url_for_group.json")
SCHEDULES_CONFIG = os.path.join(DB_DIR, "url_for_schedules.json")
EMPLOYEES_CONFIG = os.path.join(DB_DIR, "url_for_employees.json")


def groups_file(code: str, semester: Optional[str] = None) -> str:
    """Path of the JSON holding {group: url} for a faculty.

    Layout matches what the old writers produced, so existing files are
    picked up unchanged:
      db/groups_url/<code>_groups_url/<code>_groups[_<semester>]_url.json
    """
    suffix = f"_{semester}" if semester else ""
    return os.path.join(
        GROUPS_DIR, f"{code}_groups_url", f"{code}_groups{suffix}_url.json"
    )


def calendars_dir(code: str, semester: str) -> str:
    """Directory holding generated .ics files for a faculty and semester."""
    return os.path.join(
        CALENDARS_DIR, f"{code}_calendars", f"{code}_calendars_{semester}"
    )


def cache_dir(code: str) -> str:
    """Scratch space for downloaded source documents (e.g. WIG .docx)."""
    return os.path.join(CACHE_DIR, code)


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
