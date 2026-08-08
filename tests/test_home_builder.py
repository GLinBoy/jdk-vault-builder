"""Tests for the home page builder module."""

from pathlib import Path

from src.home_builder import build_home, summarize_version
from src.vault_organizer import ensure_version_folder


def _write_note(
    vault_dir: Path,
    jdk_version: int,
    *,
    link_type: str,
    title: str,
) -> Path:
    folder = vault_dir / f"JDK {jdk_version}"
    if link_type == "jep":
        folder = folder / "jep"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{title}.md"
    path.write_text(
        f"""\
---
jdk_version: {jdk_version}
link_type: {link_type}
title: {title}
source_url: https://example.com/{title}
fetched: 2026-01-01
---

# {title}

Body of {title}.
""",
        encoding="utf-8",
    )
    return path


def _sample_vault(tmp_path: Path) -> Path:
    vault_dir = tmp_path / "vault"
    _write_note(vault_dir, 6, link_type="project_page", title="JDK 6 Project Page")
    _write_note(vault_dir, 6, link_type="release_notes", title="Java SE 6 What's New")
    _write_note(vault_dir, 9, link_type="project_page", title="JDK 9 Project Page")
    _write_note(vault_dir, 9, link_type="release_notes", title="Java SE 9 What's New")
    _write_note(vault_dir, 9, link_type="jep", title="Process API Updates")
    _write_note(vault_dir, 9, link_type="jep", title="HTTP 2 Client")
    return vault_dir


# --- summarize_version -------------------------------------------------------


def test_summarize_version_counts_by_link_type(tmp_path: Path) -> None:
    vault_dir = _sample_vault(tmp_path)

    summary = summarize_version(vault_dir / "JDK 9")

    assert summary == {
        "jdk_version": 9,
        "total": 4,
        "project_page": 1,
        "release_notes": 1,
        "jep": 2,
        "has_combined": False,
    }


def test_summarize_version_reports_combined_file(tmp_path: Path) -> None:
    vault_dir = _sample_vault(tmp_path)
    combined_dir = ensure_version_folder(vault_dir, 9) / "_combined"
    combined_dir.mkdir()
    (combined_dir / "JDK 9 - Full.md").write_text("# JDK 9\n", encoding="utf-8")

    summary = summarize_version(vault_dir / "JDK 9")

    assert summary["has_combined"] is True
    assert summary["total"] == 4  # the combined file itself is excluded


# --- build_home --------------------------------------------------------------


def test_build_home_writes_home_md(tmp_path: Path) -> None:
    vault_dir = _sample_vault(tmp_path)

    path = build_home(vault_dir)

    assert path == vault_dir / "Home.md"
    content = path.read_text(encoding="utf-8")
    assert "# JDK Vault" in content
    assert "JDK 6" in content
    assert "JDK 9" in content


def test_build_home_lists_versions_in_order(tmp_path: Path) -> None:
    vault_dir = _sample_vault(tmp_path)

    content = build_home(vault_dir).read_text(encoding="utf-8")

    assert content.index("JDK 6") < content.index("JDK 9")


def test_build_home_reports_counts_per_version(tmp_path: Path) -> None:
    vault_dir = _sample_vault(tmp_path)

    content = build_home(vault_dir).read_text(encoding="utf-8")

    jdk6_row = next(line for line in content.splitlines() if line.startswith("| [[JDK 6"))
    jdk9_row = next(line for line in content.splitlines() if line.startswith("| [[JDK 9"))
    assert "| 1 | 1 | 0 | 2 |" in jdk6_row
    assert "| 1 | 1 | 2 | 4 |" in jdk9_row


def test_build_home_shows_combined_link_only_when_present(tmp_path: Path) -> None:
    vault_dir = _sample_vault(tmp_path)
    build_home(vault_dir)
    before = (vault_dir / "Home.md").read_text(encoding="utf-8")
    assert "[[JDK 6 - Full]]" not in before
    assert "—" in before

    combined_dir = ensure_version_folder(vault_dir, 6) / "_combined"
    combined_dir.mkdir()
    (combined_dir / "JDK 6 - Full.md").write_text("# JDK 6\n", encoding="utf-8")
    build_home(vault_dir)
    after = (vault_dir / "Home.md").read_text(encoding="utf-8")

    assert "[[JDK 6 - Full]]" in after


def test_build_home_always_overwrites_existing_home(tmp_path: Path) -> None:
    vault_dir = _sample_vault(tmp_path)
    build_home(vault_dir)
    first = (vault_dir / "Home.md").read_text(encoding="utf-8")

    _write_note(vault_dir, 17, link_type="project_page", title="JDK 17 Project Page")
    build_home(vault_dir)
    second = (vault_dir / "Home.md").read_text(encoding="utf-8")

    assert first != second
    assert "JDK 17" in second


def test_build_home_creates_vault_root_when_missing(tmp_path: Path) -> None:
    vault_dir = tmp_path / "nonexistent" / "vault"

    path = build_home(vault_dir)

    assert path.exists()
    assert vault_dir.is_dir()


def test_build_home_on_empty_vault_writes_minimal_home(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"

    content = build_home(vault_dir).read_text(encoding="utf-8")

    assert "# JDK Vault" in content
    assert "## Versions" in content
