"""Citation consistency tests — the core anti-fabrication guarantees."""

import pytest

from agents.comparison_agent import classify_licence
from utils.citations import (
    check_consistency,
    find_citations,
    keep_valid_ids,
    strip_invalid_citations,
)
from tests.fakes import make_sources


def test_grouped_citations_are_normalised():
    assert find_citations("A [S1, S2] and B [S3;S4] and C [S5]") == ["S1", "S2", "S3", "S4", "S5"]


def test_unknown_citations_are_stripped():
    text, removed = strip_invalid_citations("Fact one [S1]. Invented fact [S99].", {"S1"})
    assert removed == ["S99"]
    assert "[S99]" not in text and "[S1]" in text


def test_keep_valid_ids_dedupes_and_filters():
    assert keep_valid_ids(["S2", "[S2]", "S7", "S1"], {"S1", "S2"}) == ["S2", "S1"]


def test_consistency_check_flags_unknown_and_uncited():
    sources = make_sources()  # S1..S3
    result = check_consistency("Claim [S1]. Other claim [S9].", sources)
    assert result == {"cited": ["S1"], "unknown": ["S9"], "uncited": ["S2", "S3"]}


@pytest.mark.parametrize(
    "licence, expected",
    [
        ("Apache-2.0", "Open source (OSI-approved licence)"),
        ("MIT", "Open source (OSI-approved licence)"),
        ("Apache-2.0 (Qwen2.5-VL-7B)", "Open source (OSI-approved licence)"),
        ("Qwen License", "Open weights (custom / restricted licence)"),
        ("Llama 3.2 Community License", "Open weights (custom / restricted licence)"),
        ("Gemma Terms of Use (custom)", "Open weights (custom / restricted licence)"),
        ("CC-BY-NC-4.0", "Open weights (custom / restricted licence)"),
        ("Not documented in retrieved sources", "Unknown"),
        ("NOASSERTION", "Unknown"),
    ],
)
def test_licence_classification_never_overclaims_open_source(licence, expected):
    assert classify_licence(licence) == expected
