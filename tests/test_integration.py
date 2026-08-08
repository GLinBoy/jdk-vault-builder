"""End-to-end integration tests for the full CLI pipeline."""

from pathlib import Path
from unittest.mock import Mock

import pytest

import main
from src.csv_loader import load_csv
from tests.test_csv_loader import SAMPLE_CSV

JDK6_TITLES = ["JDK 6 Project Page", "Java SE 6 What's New"]
JDK9_TITLES = [
    "JDK 9 Project Page",
    "Java SE 9 What's New",
    "Process API Updates",
    "HTTP 2 Client",
]


def _marker(title: str) -> str:
    return f"UNIQUE_MARKER_{title.upper().replace(' ', '_')}"


def _page_html(title: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        '<head><meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        "</head>\n"
        "<body>\n"
        "<main><article>\n"
        f"<h1>{title}</h1>\n"
        f"<p>{_marker(title)}: extracted body for {title}.</p>\n"
        "</article></main>\n"
        "</body>\n"
        "</html>\n"
    )


@pytest.fixture
def pipeline_paths(tmp_path: Path):
    csv_path = tmp_path / "jdk_links.csv"
    csv_path.write_text(SAMPLE_CSV, encoding="utf-8")
    cache_dir = tmp_path / "cache"
    vault_dir = tmp_path / "vault"
    return csv_path, cache_dir, vault_dir


@pytest.fixture
def offline_pipeline(mocker, pipeline_paths):
    csv_path, cache_dir, vault_dir = pipeline_paths
    responses = {
        link.url: Mock(status_code=200, text=_page_html(link.title)) for link in load_csv(csv_path)
    }

    mock_get = mocker.patch(
        "src.fetcher.requests.get",
        side_effect=lambda url, **kwargs: responses[url],
    )
    mocker.patch("src.fetcher._fetch_with_playwright")
    mocker.patch("src.fetcher.sleep")
    mocker.patch("src.fetcher.configure_logging")

    argv = [
        "all",
        "--csv",
        str(csv_path),
        "--cache-dir",
        str(cache_dir),
        "--vault",
        str(vault_dir),
    ]
    return mock_get, argv, cache_dir, vault_dir


def _assert_note_files(vault_dir: Path) -> None:
    for title in JDK6_TITLES:
        assert (vault_dir / "JDK 6" / f"{title}.md").is_file()
    for title in JDK9_TITLES:
        assert (vault_dir / "JDK 9" / f"{title}.md").is_file()


def test_all_end_to_end_builds_expected_vault(offline_pipeline) -> None:
    mock_get, argv, cache_dir, vault_dir = offline_pipeline

    exit_code = main.main(argv)

    assert exit_code == 0
    assert (vault_dir / "JDK 6").is_dir()
    assert (vault_dir / "JDK 9").is_dir()
    _assert_note_files(vault_dir)
    assert len(list(cache_dir.glob("*.html"))) == 6
    assert mock_get.call_count == 6


def test_all_combined_files_contain_all_notes(offline_pipeline) -> None:
    _, argv, _, vault_dir = offline_pipeline

    assert main.main(argv) == 0

    combined6 = vault_dir / "JDK 6" / "_combined" / "JDK 6 - Full.md"
    combined9 = vault_dir / "JDK 9" / "_combined" / "JDK 9 - Full.md"
    assert combined6.is_file()
    assert combined9.is_file()

    content6 = combined6.read_text(encoding="utf-8")
    content9 = combined9.read_text(encoding="utf-8")
    for title in JDK6_TITLES:
        assert f"## {title}" in content6
        assert _marker(title) in content6
    for title in JDK9_TITLES:
        assert f"## {title}" in content9
        assert _marker(title) in content9


def test_all_version_filter_builds_only_that_version(pipeline_paths, mocker) -> None:
    csv_path, cache_dir, vault_dir = pipeline_paths
    responses = {
        link.url: Mock(status_code=200, text=_page_html(link.title)) for link in load_csv(csv_path)
    }
    mocker.patch(
        "src.fetcher.requests.get",
        side_effect=lambda url, **kwargs: responses[url],
    )
    mocker.patch("src.fetcher._fetch_with_playwright")
    mocker.patch("src.fetcher.sleep")
    mocker.patch("src.fetcher.configure_logging")

    exit_code = main.main(
        [
            "all",
            "--csv",
            str(csv_path),
            "--cache-dir",
            str(cache_dir),
            "--vault",
            str(vault_dir),
            "--version",
            "9",
        ]
    )

    assert exit_code == 0
    assert (vault_dir / "JDK 9").is_dir()
    assert not (vault_dir / "JDK 6").exists()
    for title in JDK9_TITLES:
        assert (vault_dir / "JDK 9" / f"{title}.md").is_file()
    combined9 = vault_dir / "JDK 9" / "_combined" / "JDK 9 - Full.md"
    content = combined9.read_text(encoding="utf-8")
    assert "## JDK 9 Project Page" in content
    assert "## HTTP 2 Client" in content


def test_all_rerun_is_idempotent_and_recombine_prompts(offline_pipeline, mocker) -> None:
    mock_get, argv, _, vault_dir = offline_pipeline

    assert main.main(argv) == 0
    notes_before = sorted(
        path.read_text(encoding="utf-8") for path in (vault_dir / "JDK 9").glob("*.md")
    )

    input_mock = mocker.patch("builtins.input", return_value="n")
    assert main.main(argv) == 0

    assert mock_get.call_count == 6  # second run served entirely from cache
    assert (
        sorted(path.read_text(encoding="utf-8") for path in (vault_dir / "JDK 9").glob("*.md"))
        == notes_before
    )
    input_mock.assert_called()  # recombine prompted instead of overwriting silently
