"""Tests for the combiner module."""

from pathlib import Path

import pytest

from src.combiner import combine_version, sort_notes_for_combine, strip_frontmatter

SAMPLE_NOTE = """\
---
jdk_version: 9
link_type: jep
jep_number: 102
title: Process API Updates
source_url: https://openjdk.org/jeps/102
fetched: 2026-01-01
---

# Process API Updates

Body of Process API Updates.
"""


def _write_note(
    vault_dir: Path,
    jdk_version: int,
    *,
    link_type: str,
    title: str,
    jep_number: int | None = None,
    body: str | None = None,
) -> Path:
    folder = vault_dir / f"JDK {jdk_version}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{title}.md"
    if body is None:
        body = f"Body of {title}."
    jep_line = f"jep_number: {jep_number}" if jep_number is not None else "jep_number: None"
    path.write_text(
        f"""\
---
jdk_version: {jdk_version}
link_type: {link_type}
{jep_line}
title: {title}
source_url: https://example.com/{title}
fetched: 2026-01-01
---

# {title}

{body}
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def jdk9_vault(tmp_path: Path) -> Path:
    vault_dir = tmp_path / "vault"
    _write_note(
        vault_dir, 9, link_type="jep", jep_number=110, title="HTTP 2 Client", body="HTTP body."
    )
    _write_note(
        vault_dir,
        9,
        link_type="jep",
        jep_number=102,
        title="Process API Updates",
        body="Process body.",
    )
    _write_note(
        vault_dir,
        9,
        link_type="release_notes",
        title="Java SE 9 What's New",
        body="Release notes body.",
    )
    _write_note(
        vault_dir, 9, link_type="project_page", title="JDK 9 Project Page", body="Page body."
    )
    return vault_dir


# --- strip_frontmatter -------------------------------------------------------


def test_strip_frontmatter_removes_only_yaml_block() -> None:
    stripped = strip_frontmatter(SAMPLE_NOTE)

    assert stripped == "# Process API Updates\n\nBody of Process API Updates.\n"


def test_strip_frontmatter_returns_text_without_block_unchanged() -> None:
    text = "# Just a heading\n\nNo frontmatter here.\n"

    assert strip_frontmatter(text) == text


def test_strip_frontmatter_returns_text_with_unterminated_block_unchanged() -> None:
    text = "---\njdk_version: 9\nlink_type: jep\n"

    assert strip_frontmatter(text) == text


# --- sort_notes_for_combine --------------------------------------------------


def test_sort_notes_for_combine_orders_correctly(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    project = _write_note(vault_dir, 9, link_type="project_page", title="JDK 9 Project Page")
    release = _write_note(vault_dir, 9, link_type="release_notes", title="Java SE 9 What's New")
    jep_305 = _write_note(vault_dir, 9, link_type="jep", jep_number=305, title="Zebra")
    jep_110 = _write_note(vault_dir, 9, link_type="jep", jep_number=110, title="HTTP 2 Client")
    jep_102 = _write_note(
        vault_dir, 9, link_type="jep", jep_number=102, title="Process API Updates"
    )
    other_a = _write_note(vault_dir, 9, link_type="migration", title="Alpha Migration Guide")
    other_b = _write_note(vault_dir, 9, link_type="deprecation", title="Beta Deprecation Note")

    note_paths = [jep_110, other_a, project, jep_305, release, other_b, jep_102]

    ordered = sort_notes_for_combine(note_paths)

    assert ordered == [project, release, jep_102, jep_110, jep_305, other_a, other_b]


# --- combine_version ---------------------------------------------------------


def test_combine_version_writes_merged_file(jdk9_vault: Path) -> None:
    output_path = jdk9_vault / "JDK 9" / "_combined" / "JDK 9 - Full.md"

    result = combine_version(jdk9_vault, 9)

    assert result == output_path
    content = output_path.read_text(encoding="utf-8")
    assert content.startswith("# JDK 9 — Full Reference\n")
    section_order = [
        content.index(f"## {title}")
        for title in [
            "JDK 9 Project Page",
            "Java SE 9 What's New",
            "Process API Updates",
            "HTTP 2 Client",
        ]
    ]
    assert section_order == sorted(section_order)
    assert "Process body." in content
    assert "HTTP body." in content


def test_combine_version_does_not_prompt_when_output_is_absent(jdk9_vault: Path, mocker) -> None:
    input_mock = mocker.patch("builtins.input", side_effect=AssertionError("unexpected input"))

    result = combine_version(jdk9_vault, 9)

    assert result is not None
    input_mock.assert_not_called()


def test_combine_version_overwrites_when_confirmed(jdk9_vault: Path, mocker) -> None:
    output_path = jdk9_vault / "JDK 9" / "_combined" / "JDK 9 - Full.md"
    combine_version(jdk9_vault, 9)
    before = output_path.read_text(encoding="utf-8")

    input_mock = mocker.patch("builtins.input", return_value="y")
    result = combine_version(jdk9_vault, 9)

    assert result == output_path
    input_mock.assert_called_once_with(f"{output_path} exists. Overwrite? [y/N]: ")
    assert output_path.read_text(encoding="utf-8") == before
    assert "## JDK 9 - Full" not in output_path.read_text(encoding="utf-8")


def test_combine_version_declines_overwrite_on_n(jdk9_vault: Path, mocker) -> None:
    output_path = jdk9_vault / "JDK 9" / "_combined" / "JDK 9 - Full.md"
    combine_version(jdk9_vault, 9)
    before = output_path.read_text(encoding="utf-8")

    input_mock = mocker.patch("builtins.input", return_value="n")
    result = combine_version(jdk9_vault, 9)

    assert result is None
    input_mock.assert_called_once()
    assert output_path.read_text(encoding="utf-8") == before


def test_combine_version_declines_overwrite_on_empty_input(jdk9_vault: Path, mocker) -> None:
    output_path = jdk9_vault / "JDK 9" / "_combined" / "JDK 9 - Full.md"
    combine_version(jdk9_vault, 9)
    before = output_path.read_text(encoding="utf-8")

    mocker.patch("builtins.input", return_value="")
    result = combine_version(jdk9_vault, 9)

    assert result is None
    assert output_path.read_text(encoding="utf-8") == before


def test_combine_version_force_overwrites_without_prompt(jdk9_vault: Path, mocker) -> None:
    output_path = jdk9_vault / "JDK 9" / "_combined" / "JDK 9 - Full.md"
    combine_version(jdk9_vault, 9)
    before = output_path.read_text(encoding="utf-8")

    input_mock = mocker.patch("builtins.input", side_effect=AssertionError("unexpected input"))
    result = combine_version(jdk9_vault, 9, force=True)

    assert result == output_path
    input_mock.assert_not_called()
    assert output_path.read_text(encoding="utf-8") == before


def test_combine_version_returns_none_when_no_notes(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"

    assert combine_version(vault_dir, 9) is None
