"""Slow, browser-like fetching for WAF-protected faculties (WCY)."""
import threading

import pytest

from watcalendars.core import pipeline, registry
from watcalendars.core.models import FacultySpec
from watcalendars.fetch import http
from watcalendars.fetch.guard import FacultyBlocked

from test_guard import INCAPSULA_PAGE, FakeResponse, FakeSession


@pytest.fixture
def sleeps(monkeypatch):
    """Record time.sleep instead of sleeping; jitter fixed at its maximum."""
    recorded = []
    monkeypatch.setattr(http.time, "sleep", recorded.append)
    monkeypatch.setattr(http.random, "uniform", lambda low, high: high)
    return recorded


@pytest.fixture
def sessions(monkeypatch):
    """Every session created, with the URLs each one requested."""
    created = []
    lock = threading.Lock()

    def factory(responder):
        def new_session():
            session = FakeSession([], responder, lock)
            created.append(session)
            return session

        monkeypatch.setattr(http, "new_session", new_session)
        return created

    return factory


PAIRS = [(f"G{i}", f"https://x/{i}") for i in range(5)]


def test_delay_with_jitter_between_requests(sleeps, sessions):
    sessions(lambda url: FakeResponse(200))
    results = http.fetch_many(PAIRS, concurrency=1, delay=4)

    assert all(results.values())
    # Between requests, not before the first or after the last: n-1 pauses
    # of delay + uniform(0, delay/2) - here the maximum, 4 + 2.
    assert sleeps == [6.0] * (len(PAIRS) - 1)


def test_jitter_stays_within_delay_and_one_and_a_half_delay(monkeypatch):
    slept = []
    monkeypatch.setattr(http.time, "sleep", slept.append)
    for _ in range(200):
        http.polite_pause(4)
    assert all(4 <= s <= 6 for s in slept)
    assert len(set(slept)) > 1


def test_sequential_mode_is_one_at_a_time_in_order_on_one_session(sleeps, sessions):
    active = 0
    peak = 0
    lock = threading.Lock()

    def responder(url):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        # Hold the "request" open so overlapping calls would be seen.
        # Not time.sleep: the fixture patches it in the shared time module.
        threading.Event().wait(0.01)
        with lock:
            active -= 1
        return FakeResponse(200)

    created = sessions(responder)
    http.fetch_many(PAIRS, concurrency=1, delay=4)

    assert peak == 1
    assert len(created) == 1, "cookies must carry over: one session for the run"
    assert created[0].calls == [url for _, url in PAIRS]


def test_no_delay_keeps_the_fast_parallel_path(sleeps, sessions):
    sessions(lambda url: FakeResponse(200))
    http.fetch_many(PAIRS, concurrency=4, delay=0)
    assert sleeps == []


def test_no_pause_after_the_guard_trips(sleeps, sessions):
    created = sessions(lambda url: FakeResponse(403, INCAPSULA_PAGE))
    guard = http.WafGuard("T", threshold=3)
    pairs = [(f"G{i}", f"https://x/{i}") for i in range(20)]

    http.fetch_many(pairs, concurrency=1, delay=4, guard=guard)

    assert len(created[0].calls) == 3
    assert guard.skipped == 17
    # Pauses only between the three real requests - skipping is instant.
    assert len(sleeps) == 2


def test_headers_are_one_consistent_firefox():
    session = http.new_session()
    agent = session.headers["User-Agent"]
    assert "Firefox/" in agent and "Gecko/" in agent
    assert "Chrome" not in agent and "Safari" not in agent
    assert session.headers["Accept-Language"].startswith("pl-PL")
    assert "text/html" in session.headers["Accept"]


# --- spec -------------------------------------------------------------------

def test_wcy_is_slow_and_strict():
    spec = registry.FACULTIES["wcy"]
    assert spec.concurrency == 1
    assert spec.delay == 4
    assert spec.waf_threshold == 3
    assert "residential IP" in spec.notes


def test_spec_defaults():
    spec = FacultySpec("x", "X", "u", "u", None, lambda html: [])
    assert spec.delay == 0
    assert spec.waf_threshold == 8


def test_pipeline_uses_threshold_and_delay_from_spec(monkeypatch):
    spec = registry.FACULTIES["wcy"]
    monkeypatch.setattr(
        pipeline.groups_store, "load_groups",
        lambda code, sem: {"G1": spec.schedule_url, "G2": spec.schedule_url},
    )
    seen = {}

    def fetch(strategy, pairs, concurrency, label, guard=None, delay=0):
        seen.update(threshold=guard.threshold, delay=delay, concurrency=concurrency)
        return {group: None for group, _ in pairs}

    monkeypatch.setattr(pipeline.strategies, "fetch", fetch)
    monkeypatch.setattr(pipeline.ics, "write_all", lambda *a: {})

    with pytest.raises(FacultyBlocked):
        pipeline.run_calendars(spec)
    assert seen == {"threshold": 3, "delay": 4, "concurrency": 1}
