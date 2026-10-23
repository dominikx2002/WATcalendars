"""Fail-fast on WAF blocks: the guard, the fetchers and the pipeline."""
import dataclasses
import os
import subprocess
import sys
import threading
from datetime import datetime

import pytest
import requests

from watcalendars import cli
from watcalendars.core import pipeline, registry
from watcalendars.fetch import http
from watcalendars.fetch.guard import FacultyBlocked, WafGuard, is_waf_block

INCAPSULA_PAGE = (
    b"<html><body>Request unsuccessful. Incapsula incident ID: "
    b"1234-5678</body></html>"
)


class FakeResponse:
    def __init__(self, status, body=b"<html>ok</html>"):
        self.status_code = status
        self.content = body
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(http.time, "sleep", lambda seconds: None)


class FakeSession:
    """Stands in for requests.Session; every instance shares `calls`."""

    def __init__(self, calls, responder, lock):
        self.calls, self.responder, self.lock = calls, responder, lock
        self.headers = dict(http.HEADERS)

    def get(self, url, timeout=None):
        with self.lock:
            self.calls.append(url)
        return self.responder(url)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def fake_get(monkeypatch, responder):
    """Patch the HTTP session; returns the list of URLs requested."""
    calls = []
    lock = threading.Lock()
    monkeypatch.setattr(http, "new_session", lambda: FakeSession(calls, responder, lock))
    return calls


# --- is_waf_block ---------------------------------------------------------

def test_incapsula_403_is_a_block():
    assert is_waf_block(403, INCAPSULA_PAGE)


def test_short_403_is_a_block():
    assert is_waf_block(403, b"<html>Forbidden</html>")


def test_challenge_served_with_200_is_a_block():
    assert is_waf_block(200, b"<script src='/_Incapsula_Resource?x'></script>")


def test_real_content_is_not_a_block():
    assert not is_waf_block(200, b"<html>" + b"x" * 5000 + b"</html>")
    assert not is_waf_block(404, INCAPSULA_PAGE)
    assert not is_waf_block(403, b"x" * 5000)


# --- WafGuard -------------------------------------------------------------

def test_guard_trips_after_threshold_consecutive_403s():
    guard = WafGuard("T", threshold=8)
    for _ in range(7):
        guard.record(403)
    assert not guard.tripped
    guard.record(403)
    assert guard.tripped
    assert guard.skip() and guard.skip()
    assert guard.skipped == 2


def test_guard_streak_resets_on_any_other_status():
    guard = WafGuard("T", threshold=3)
    for status in (403, 403, 200, 403, 403, 404, 403, 403, 500):
        guard.record(status)
    assert not guard.tripped
    assert not guard.skip()
    assert guard.blocked == 6


def test_guard_is_thread_safe():
    guard = WafGuard("T", threshold=1000)
    threads = [
        threading.Thread(target=lambda: [guard.record(403) for _ in range(100)])
        for _ in range(10)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert guard.blocked == 1000
    assert guard.tripped


# --- http.fetch_one: what gets retried --------------------------------------

@pytest.mark.parametrize("status", [403, 404])
def test_403_and_404_are_not_retried(monkeypatch, no_sleep, status):
    calls = fake_get(monkeypatch, lambda url: FakeResponse(status, INCAPSULA_PAGE))
    assert http.fetch_one("https://x/a", retries=3) is None
    assert len(calls) == 1


def test_5xx_is_retried(monkeypatch, no_sleep):
    statuses = iter([503, 502, 200])
    calls = fake_get(monkeypatch, lambda url: FakeResponse(next(statuses)))
    assert http.fetch_one("https://x/a", retries=3) == "<html>ok</html>"
    assert len(calls) == 3


def test_timeouts_and_connection_errors_are_retried(monkeypatch, no_sleep):
    outcomes = iter([requests.Timeout("slow"), requests.ConnectionError("reset"),
                     FakeResponse(200)])

    def responder(url):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    calls = fake_get(monkeypatch, responder)
    assert http.fetch_one("https://x/a", retries=3) == "<html>ok</html>"
    assert len(calls) == 3


# --- http.fetch_many with a guard -------------------------------------------

def test_fetch_many_stops_requesting_once_the_guard_trips(monkeypatch, no_sleep):
    calls = fake_get(monkeypatch, lambda url: FakeResponse(403, INCAPSULA_PAGE))
    pairs = [(f"G{i:02}", f"https://x/{i}") for i in range(30)]
    guard = WafGuard("T", threshold=8)

    results = http.fetch_many(pairs, concurrency=1, guard=guard)

    assert len(calls) == 8
    assert guard.tripped and guard.skipped == 22
    assert set(results) == {group for group, _ in pairs}
    assert not any(results.values())


def test_isolated_403s_do_not_stop_the_faculty(monkeypatch, no_sleep):
    # Every third group is forbidden; the rest load fine.
    def responder(url):
        index = int(url.rsplit("/", 1)[1])
        return FakeResponse(403) if index % 3 == 0 else FakeResponse(200)

    fake_get(monkeypatch, responder)
    pairs = [(f"G{i:02}", f"https://x/{i}") for i in range(30)]
    guard = WafGuard("T", threshold=8)

    results = http.fetch_many(pairs, concurrency=4, guard=guard)

    assert not guard.tripped
    assert len([r for r in results.values() if r]) == 20


# --- pipeline: save what got through, then fail ---------------------------

def _lesson(group):
    return {
        "start": datetime(2026, 10, 1, 8),
        "end": datetime(2026, 10, 1, 9, 35),
        "subject": f"S-{group}",
    }


@pytest.fixture
def fake_faculty(monkeypatch):
    """WCY spec with a stub parser, a 20-group map and a captured writer."""
    spec = dataclasses.replace(
        registry.FACULTIES["wcy"], parse_schedule=lambda html: [_lesson(html)]
    )
    mapping = {f"G{i:02}": spec.schedule_url for i in range(20)}
    monkeypatch.setattr(pipeline.groups_store, "load_groups", lambda code, sem: mapping)

    written = {}

    def write_all(schedules, code, semester):
        written.update({g: l for g, l in schedules.items() if l})
        return {"added": sorted(written), "changed": [], "unchanged": [],
                "skipped": sorted(g for g, l in schedules.items() if not l)}

    monkeypatch.setattr(pipeline.ics, "write_all", write_all)
    return spec, written


def test_run_calendars_writes_partial_results_then_raises(monkeypatch, fake_faculty):
    spec, written = fake_faculty

    def fetch(strategy, pairs, concurrency, label, guard=None, delay=0):
        results = {}
        for index, (group, url) in enumerate(pairs):
            if guard.skip():
                results[group] = None
            elif index < 5:
                guard.record(200)
                results[group] = group
            else:
                guard.record(403)
                results[group] = None
        return results

    monkeypatch.setattr(pipeline.strategies, "fetch", fetch)

    with pytest.raises(FacultyBlocked, match="WAF"):
        pipeline.run_calendars(spec)
    assert sorted(written) == ["G00", "G01", "G02", "G03", "G04"]


def test_run_calendars_raises_when_nothing_was_fetched(monkeypatch, fake_faculty):
    spec, written = fake_faculty
    monkeypatch.setattr(
        pipeline.strategies, "fetch",
        lambda strategy, pairs, concurrency, label, guard=None, delay=0: {g: None for g, _ in pairs},
    )
    with pytest.raises(FacultyBlocked, match="nothing fetched"):
        pipeline.run_calendars(spec)
    assert written == {}


def test_run_calendars_succeeds_when_everything_loads(monkeypatch, fake_faculty):
    spec, written = fake_faculty
    monkeypatch.setattr(
        pipeline.strategies, "fetch",
        lambda strategy, pairs, concurrency, label, guard=None, delay=0: {g: g for g, _ in pairs},
    )
    pipeline.run_calendars(spec)
    assert len(written) == 20


def test_cli_reports_blocked_faculty_as_failure(monkeypatch):
    def run_calendars(spec):
        if spec.code == "wcy":
            raise FacultyBlocked("WCY: blocked by WAF")

    monkeypatch.setattr(cli, "run_calendars", run_calendars)
    specs = [registry.FACULTIES["wcy"], registry.FACULTIES["wim"]]
    assert cli._run_stage("calendars", specs) == (1, ["wcy"])

    # each faculty's dot on the website gets its own verdict
    from watcalendars.store.index import read_faculty_status
    assert read_faculty_status("wcy")["ok"] is False
    assert read_faculty_status("wcy")["detail"] == "zablokowane przez WAF"
    assert read_faculty_status("wim")["ok"] is True


# --- the Raspberry Pi path must not need Playwright -----------------------

def test_http_path_and_index_do_not_import_playwright(tmp_path):
    """WCY scraping and `watcal index` must work with Playwright absent.

    Runs in a fresh interpreter where importing playwright raises, so a
    stray module-level import anywhere on the path fails the test.
    """
    script = (
        "import sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] == 'playwright':\n"
        "            raise ImportError('playwright blocked by test')\n"
        "sys.meta_path.insert(0, Block())\n"
        "from watcalendars import cli\n"
        "from watcalendars.fetch import strategies\n"
        "from watcalendars.faculties import wcy\n"
        "assert cli.main(['index']) == 0\n"
        "assert not [m for m in sys.modules if m.startswith('playwright')]\n"
    )
    env = {**os.environ, "WATCALENDARS_DB_DIR": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
