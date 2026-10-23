import os

import pytest


@pytest.fixture(autouse=True)
def _status_files_in_tmp(tmp_path, monkeypatch):
    """Keep per-faculty status.json writes out of the real db/calendars:
    anything that runs a scrape stage records one."""
    from watcalendars.store import index

    monkeypatch.setattr(
        index, "faculty_status_path",
        lambda code: os.path.join(str(tmp_path), "status", f"{code}.json"))
