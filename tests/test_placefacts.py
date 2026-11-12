"""F-222/F-223: the fun facts a place tells while the matrix loads, hand-written and each with the source it was checked against."""
from pathlib import Path

import pytest

from gitaway import placeart, placefacts

DOC = (Path(__file__).resolve().parent.parent / "docs" / "research" / "place-facts.md").read_text(encoding="utf-8")


def test_the_ten_places_with_art_each_have_three_to_five_facts():
    assert set(placefacts.SLUGS) == set(placeart.SLUGS)
    for slug in placefacts.SLUGS:
        assert 3 <= len(placefacts.facts(slug)) <= 5, slug


@pytest.mark.parametrize("slug", placefacts.SLUGS)
def test_every_fact_is_short_plain_and_has_an_https_source_the_research_lists(slug):
    for fact in placefacts.facts(slug):
        assert fact.source.startswith("https://") and " " not in fact.source
        assert fact.source in DOC, f"docs/research/place-facts.md lists {fact.source}"
        assert fact.text in DOC, f"docs/research/place-facts.md records {fact.text!r}"
        assert 20 <= len(fact.text) <= 120 and fact.text[-1] in ".!", fact.text
        assert all(ord(c) < 0x2190 for c in fact.text), "no emoji or symbols"


def test_names_and_dashes_find_the_same_facts_and_an_unknown_place_has_none():
    assert placefacts.facts("San Diego") == placefacts.facts("san-diego") == placefacts.facts("sandiego")
    assert placefacts.facts("Boise") == () and placefacts.facts("") == () and placefacts.facts(None) == ()


def test_facts_are_fixed_tuples_never_written_at_runtime():
    assert isinstance(placefacts.facts("yosemite"), tuple)
    src = Path(placefacts.__file__).read_text(encoding="utf-8")
    assert "import ai" not in src and "from gitaway import ai" not in src and "requests" not in src
