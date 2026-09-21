"""Reading and writing the {group: url} maps under db/groups_url."""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from watcalendars.core.logging import ERROR, INFO, SUCCESS, WARNING, get_logger
from watcalendars.core.paths import ensure_dir, groups_file

log = get_logger()


def save_groups(
    groups: List[str], code: str, schedule_url: str, semester: Optional[str] = None
) -> Dict[str, str]:
    """Write {group: schedule_url} for a faculty and return the mapping."""
    path = groups_file(code, semester)
    ensure_dir(os.path.dirname(path))

    mapping = {
        group: schedule_url.replace("{group}", group) for group in sorted(set(groups))
    }

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(mapping, handle, indent=2, ensure_ascii=False)

    log.info(f"{SUCCESS} Saved {len(mapping)} {code.upper()} groups to '{path}'")
    return mapping


def load_groups(code: str, semester: Optional[str] = None) -> Dict[str, str]:
    """Load {group: url} for a faculty.

    Unlike the old loader this does not guess which file to use: the
    semester decides, and a missing file is an explicit error rather
    than a silent fallback to whatever sorted first.
    """
    path = groups_file(code, semester)
    if not os.path.isfile(path):
        legacy = groups_file(code, None)
        if semester and os.path.isfile(legacy):
            log.warning(
                f"{WARNING} {path} missing, falling back to season-less '{legacy}'"
            )
            path = legacy
        else:
            raise FileNotFoundError(
                f"No groups file for {code.upper()}"
                + (f" ({semester})" if semester else "")
                + f": expected '{path}'. Run 'watcal groups {code}' first."
            )

    with open(path, "r", encoding="utf-8") as handle:
        mapping = json.load(handle)

    log.debug(f"{INFO} Loaded {len(mapping)} {code.upper()} groups from '{path}'")
    return mapping


def save_group_map(
    mapping: Dict[str, str], code: str, semester: Optional[str] = None
) -> Dict[str, str]:
    """Write an already-built {group: url} map (WIG holds absolute URLs)."""
    path = groups_file(code, semester)
    ensure_dir(os.path.dirname(path))
    ordered = dict(sorted(mapping.items()))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(ordered, handle, indent=2, ensure_ascii=False)
    log.info(f"{SUCCESS} Saved {len(ordered)} {code.upper()} groups to '{path}'")
    return ordered
