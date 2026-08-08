"""Tests for the vault organizer module."""

from pathlib import Path

import pytest

from src.csv_loader import JdkLink
from src.vault_organizer import (
    ensure_vault_root,
    ensure_version_folder,
    note_path_for,
    sanitize_filename,
)

# --- ensure_vault_root -------------------------------------------------------


def test_ensure_vault_root_creates_directory(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    assert not vault_dir.exists()

    ensure_vault_root(vault_dir)

    assert vault_dir.is_dir()


def test_ensure_vault_root_creates_nested_parents(tmp_path: Path) -> None:
    vault_dir = tmp_path / "a" / "b" / "vault"

    ensure_vault_root(vault_dir)

    assert vault_dir.is_dir()


def test_ensure_vault_root_is_noop_when_it_exists(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True)
    marker = vault_dir / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")

    ensure_vault_root(vault_dir)

    assert marker.read_text(encoding="utf-8") == "keep me"


# --- ensure_version_folder ---------------------------------------------------


@pytest.mark.parametrize("version", [6, 9, 17])
def test_ensure_version_folder_creates_jdk_folder(tmp_path: Path, version: int) -> None:
    vault_dir = tmp_path / "vault"
    ensure_vault_root(vault_dir)

    folder = ensure_version_folder(vault_dir, version)

    assert folder == vault_dir / f"JDK {version}"
    assert folder.is_dir()


def test_ensure_version_folder_creates_vault_root_implicitly(tmp_path: Path) -> None:
    vault_dir = tmp_path / "not" / "created" / "yet"

    folder = ensure_version_folder(vault_dir, 9)

    assert folder == vault_dir / "JDK 9"
    assert folder.is_dir()


def test_ensure_version_folder_returns_same_path_when_called_twice(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"

    first = ensure_version_folder(vault_dir, 9)
    second = ensure_version_folder(vault_dir, 9)

    assert first == second == vault_dir / "JDK 9"
    assert first.is_dir()


# --- sanitize_filename -------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("HTTP 2 Client", "HTTP 2 Client"),
        ("JDK 9 Project Page", "JDK 9 Project Page"),
        ("HTTP/2 Client", "HTTP 2 Client"),
        ("JEP-110: Process API Updates", "JEP-110 Process API Updates"),
        ("What's <New> | Here", "What's New Here"),
        ('bad"chars"*here', "bad chars here"),
        ("  extra   whitespace  here  ", "extra whitespace here"),
        ("Trailing dot.", "Trailing dot"),
        ("..hidden..", "hidden"),
    ],
)
def test_sanitize_filename_keeps_readable_titles(title: str, expected: str) -> None:
    assert sanitize_filename(title) == expected


@pytest.mark.parametrize("title", ["", "   ", "...", '?"<>|:*'])
def test_sanitize_filename_falls_back_for_all_invalid(title: str) -> None:
    assert sanitize_filename(title) == "untitled"


# --- note_path_for -----------------------------------------------------------


def test_note_path_for_uses_version_folder(tmp_path: Path) -> None:
    link = JdkLink(9, "jep", 110, "HTTP 2 Client", "https://openjdk.org/jeps/110")
    vault_dir = tmp_path / "vault"

    path = note_path_for(link, vault_dir)

    assert path == vault_dir / "JDK 9" / "HTTP 2 Client.md"


def test_note_path_for_sanitizes_title(tmp_path: Path) -> None:
    link = JdkLink(
        9,
        "jep",
        110,
        "JEP-110: HTTP/2 Client",
        "https://openjdk.org/jeps/110",
    )
    vault_dir = tmp_path / "vault"

    path = note_path_for(link, vault_dir)

    assert path == vault_dir / "JDK 9" / "JEP-110 HTTP 2 Client.md"


def test_note_path_for_does_not_create_directories(tmp_path: Path) -> None:
    link = JdkLink(9, "project_page", None, "JDK 9 Project Page", "https://openjdk.org/projects/jdk9")
    vault_dir = tmp_path / "vault"

    note_path_for(link, vault_dir)

    assert not vault_dir.exists()
