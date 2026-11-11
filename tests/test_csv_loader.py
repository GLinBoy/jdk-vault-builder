"""Tests for the CSV loader module."""

import logging
from pathlib import Path

import pytest

from src.csv_loader import JdkLink, group_by_version, load_csv

SAMPLE_CSV = """\
jdk_version,link_type,jep_number,title,url
6,project_page,,JDK 6 Project Page,https://openjdk.org/projects/jdk6
6,release_notes,,Java SE 6 What's New,https://www.oracle.com/java/technologies/javase/features.html
9,project_page,,JDK 9 Project Page,https://openjdk.org/projects/jdk9
9,release_notes,,Java SE 9 What's New,https://www.oracle.com/java/technologies/javase/9-new-features.html
9,jep,102,Process API Updates,https://openjdk.org/jeps/102
9,jep,110,HTTP 2 Client,https://openjdk.org/jeps/110
"""


@pytest.fixture
def sample_csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "jdk_links.csv"
    path.write_text(SAMPLE_CSV, encoding="utf-8")
    return path


def test_load_csv_parses_all_rows(sample_csv_path: Path) -> None:
    links = load_csv(sample_csv_path)

    assert len(links) == 6
    assert all(isinstance(link, JdkLink) for link in links)
    assert links[0] == JdkLink(
        6, "project_page", None, "JDK 6 Project Page", "https://openjdk.org/projects/jdk6"
    )
    assert links[4].jdk_version == 9
    assert links[4].link_type == "jep"
    assert links[4].title == "Process API Updates"


def test_jep_number_none_and_int(sample_csv_path: Path) -> None:
    links = load_csv(sample_csv_path)
    six_rows = [link for link in links if link.jdk_version == 6]
    nine_rows = [link for link in links if link.jdk_version == 9]

    assert all(link.jep_number is None for link in six_rows)
    assert [link.jep_number for link in nine_rows if link.link_type == "jep"] == [102, 110]


def test_load_csv_rejects_malformed_row(tmp_path: Path) -> None:
    bad = (
        "jdk_version,link_type,jep_number,title,url\n"
        "6,project_page,,JDK 6 Project Page,https://openjdk.org/projects/jdk6\n"
        ",release_notes,,Missing Version,https://example.com/release\n"
    )
    path = tmp_path / "bad.csv"
    path.write_text(bad, encoding="utf-8")

    with pytest.raises(ValueError, match="Row 3"):
        load_csv(path)


def test_load_csv_rejects_unquoted_comma_in_title(tmp_path: Path) -> None:
    bad = (
        "jdk_version,link_type,jep_number,title,url\n"
        "27,jep,532,Primitive Types in Patterns, instanceof, and switch (Fifth Preview),"
        "https://openjdk.org/jeps/532\n"
    )
    path = tmp_path / "bad_comma.csv"
    path.write_text(bad, encoding="utf-8")

    with pytest.raises(ValueError, match="Row 2.*expected 5 columns.*quote"):
        load_csv(path)


def test_load_csv_accepts_quoted_comma_in_title(tmp_path: Path) -> None:
    good = (
        "jdk_version,link_type,jep_number,title,url\n"
        '26,jep,530,"Primitive Types in Patterns, instanceof, and switch (Fourth Preview)",'
        "https://openjdk.org/jeps/530\n"
    )
    path = tmp_path / "quoted_comma.csv"
    path.write_text(good, encoding="utf-8")

    links = load_csv(path)

    assert len(links) == 1
    assert links[0].title == "Primitive Types in Patterns, instanceof, and switch (Fourth Preview)"
    assert links[0].url == "https://openjdk.org/jeps/530"


def test_load_csv_rejects_wrong_header(tmp_path: Path) -> None:
    bad = "version,type,jep,title,link\n9,jep,110,HTTP 2 Client,https://openjdk.org/jeps/110\n"
    path = tmp_path / "bad_header.csv"
    path.write_text(bad, encoding="utf-8")

    with pytest.raises(ValueError, match="Header must be"):
        load_csv(path)


def test_load_csv_rejects_non_integer_jep_number(tmp_path: Path) -> None:
    bad = (
        "jdk_version,link_type,jep_number,title,url\n"
        "9,jep,notanumber,Bad JEP,https://example.com/jep\n"
    )
    path = tmp_path / "bad_jep.csv"
    path.write_text(bad, encoding="utf-8")

    with pytest.raises(ValueError, match="Row 2.*jep_number"):
        load_csv(path)


def test_load_csv_warns_on_duplicates_without_failing(
    sample_csv_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with sample_csv_path.open("a", encoding="utf-8") as f:
        f.write("9,jep,110,HTTP 2 Client,https://openjdk.org/jeps/110\n")

    with caplog.at_level(logging.WARNING, logger="src.csv_loader"):
        links = load_csv(sample_csv_path)

    assert len(links) == 6
    assert any("Duplicate" in record.message for record in caplog.records)


def test_group_by_version(sample_csv_path: Path) -> None:
    links = load_csv(sample_csv_path)
    grouped = group_by_version(links)

    assert set(grouped) == {6, 9}
    assert len(grouped[6]) == 2
    assert len(grouped[9]) == 4
    assert all(link.jdk_version == 6 for link in grouped[6])
    assert all(link.jdk_version == 9 for link in grouped[9])


def test_group_by_version_preserves_order(sample_csv_path: Path) -> None:
    links = load_csv(sample_csv_path)
    grouped = group_by_version(links)

    assert [link.title for link in grouped[9]] == [
        "JDK 9 Project Page",
        "Java SE 9 What's New",
        "Process API Updates",
        "HTTP 2 Client",
    ]
