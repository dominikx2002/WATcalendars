"""The Plansoft index.xml parser, against a real captured index."""
import os

from watcalendars.faculties.plansoft import parse_index

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "plansoft_index.xml")


def load():
    with open(FIXTURE, "rb") as handle:
        return handle.read().decode("windows-1250")


def test_parses_all_groups():
    groups, period = parse_index(load())
    assert len(groups) == 95
    assert period == "WIM - zima 2026-27"


def test_identifier_comes_from_href_not_text():
    """text= keeps Polish diacritics; href= is the real filename.

    Using text= produces URLs that 404 - this is a regression guard.
    """
    groups, _ = parse_index(load())
    offending = [g for g in groups if any(c in g for c in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")]
    assert offending == [], f"diacritics leaked into identifiers: {offending}"


def test_groups_are_sorted_and_unique():
    groups, _ = parse_index(load())
    assert groups == sorted(set(groups))


def test_empty_and_broken_input_do_not_raise():
    assert parse_index("") == ([], None)
    assert parse_index("<not xml") == ([], None)
