"""Structural checks on the faculty registry.

These are the tests that matter when adding a ninth faculty: they catch
a malformed spec immediately instead of at 00:00 in CI.
"""
import pytest

from watcalendars.core import registry
from watcalendars.fetch import strategies

SPECS = [registry.FACULTIES[code] for code in registry.CODES]
IDS = registry.CODES


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_code_matches_registry_key(spec):
    assert registry.FACULTIES[spec.code] is spec


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_fetch_strategy_is_known(spec):
    assert spec.fetch_strategy in strategies.VALID + ("docx",)
    assert spec.groups_fetcher in strategies.VALID + ("docx",)


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_schedule_url_is_templated(spec):
    urls = (
        [spec.schedule_url]
        if isinstance(spec.schedule_url, str)
        else list(spec.schedule_url.values())
    )
    for url in urls:
        assert "{group}" in url, f"{spec.code}: schedule URL has no {{group}} slot"


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_seasonal_specs_cover_both_semesters(spec):
    if not spec.seasonal:
        return
    for which in ("groups", "schedule"):
        source = spec.groups_url if which == "groups" else spec.schedule_url
        assert isinstance(source, dict), f"{spec.code}: seasonal but {which} URL is flat"
        assert set(source) == {"zima", "lato"}, f"{spec.code}: {which} misses a semester"


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_parsers_are_callable(spec):
    assert callable(spec.parse_schedule)
    assert callable(spec.parse_groups) or spec.custom_groups_job is not None


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_non_seasonal_url_resolves_without_semester(spec):
    if spec.seasonal:
        with pytest.raises(ValueError):
            spec.url_for("groups", None)
    else:
        assert spec.url_for("groups", None)


def test_resolve_all_returns_every_faculty():
    assert len(registry.resolve(["all"])) == len(registry.CODES)
    assert len(registry.resolve([])) == len(registry.CODES)


def test_resolve_rejects_unknown_code():
    with pytest.raises(KeyError):
        registry.resolve(["nope"])
