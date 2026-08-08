"""Tests for the content extractor module."""

import logging
from pathlib import Path

import pytest

from src.content_extractor import ExtractedContent, extract_content

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# --- happy path ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "expected_substring", "expected_title"),
    [
        ("simple_page.html", "REAL_CONTENT_MARKER", "JDK 9 What's New"),
        (
            "ad_heavy_page.html",
            "THIS_IS_THE_KNOWN_RELEASE_NOTES_MARKER",
            "Java SE 6 Release Notes",
        ),
        ("minimal_page.html", "EXPECTED_HTTP2_MARKER", "JEP 110: HTTP/2 Client"),
    ],
)
def test_extract_content_keeps_real_content(
    fixture: str, expected_substring: str, expected_title: str
) -> None:
    result = extract_content(_read_fixture(fixture))

    assert result.text
    assert expected_substring in result.text
    assert result.page_title == expected_title


@pytest.mark.parametrize(
    ("fixture", "absent_substrings"),
    [
        ("simple_page.html", ["Download", "newsletter", "All rights reserved"]),
        ("ad_heavy_page.html", ["Sponsored link", "Fictional Vendor", "Products"]),
        ("minimal_page.html", ["cookies", "Accept to continue"]),
    ],
)
def test_extract_content_removes_nav_and_boilerplate(
    fixture: str, absent_substrings: list[str]
) -> None:
    result = extract_content(_read_fixture(fixture))

    for boilerplate in absent_substrings:
        assert boilerplate.lower() not in result.text.lower()


# --- degenerate input ---------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    ["", "   \n\n   ", "this is not html at all <<<>>> ===="],
)
def test_extract_content_empty_input_returns_empty(
    html: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="src.content_extractor"):
        result = extract_content(html)

    assert result == ExtractedContent(text="", page_title=None)
    assert any("Could not extract" in record.message for record in caplog.records)


def test_extract_content_does_not_raise_on_malformed_html() -> None:
    result = extract_content("<html><body><p>unclosed <div>tags")

    assert isinstance(result, ExtractedContent)


def test_extract_content_missing_title_returns_none_title() -> None:
    html = "<html><head></head><body><article><p>some real content here</p></article></body></html>"

    result = extract_content(html)

    assert result.text
    assert result.page_title is None
