"""The list of faculties. Adding one means adding a line here."""
from __future__ import annotations

from typing import Dict, List

from watcalendars.core.models import FacultySpec
from watcalendars.faculties import ioe, wcy, wel, wig, wim, wlo, wml, wtc

FACULTIES: Dict[str, FacultySpec] = {
    spec.code: spec
    for spec in (
        ioe.SPEC,
        wcy.SPEC,
        wel.SPEC,
        wig.SPEC,
        wim.SPEC,
        wlo.SPEC,
        wml.SPEC,
        wtc.SPEC,
    )
}

CODES: List[str] = sorted(FACULTIES)


def get(code: str) -> FacultySpec:
    try:
        return FACULTIES[code.lower()]
    except KeyError:
        raise KeyError(
            f"Unknown faculty '{code}'. Available: {', '.join(CODES)}"
        ) from None


def resolve(codes) -> List[FacultySpec]:
    """Turn 'all' or a list of codes into specs, preserving CODES order."""
    if not codes or codes == ["all"]:
        return [FACULTIES[code] for code in CODES]
    return [get(code) for code in codes]
