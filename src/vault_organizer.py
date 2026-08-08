"""Vault folder organization and filename/path resolution."""

import re
from pathlib import Path

from src.csv_loader import JdkLink

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
_WHITESPACE = re.compile(r"\s+")


def ensure_vault_root(vault_dir: Path) -> None:
    """Create the vault root directory if it doesn't already exist."""

    vault_dir.mkdir(parents=True, exist_ok=True)


def ensure_version_folder(vault_dir: Path, jdk_version: int) -> Path:
    """Create and return the ``vault_dir/JDK {version}/`` folder."""

    folder = vault_dir / f"JDK {jdk_version}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def ensure_jep_folder(vault_dir: Path, jdk_version: int) -> Path:
    """Create and return the ``vault_dir/JDK {version}/jep/`` folder."""

    folder = ensure_version_folder(vault_dir, jdk_version) / "jep"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def sanitize_filename(title: str) -> str:
    """Return ``title`` safe to use as a file name while staying readable.

    Characters that are invalid in file names are replaced with spaces, runs of
    whitespace are collapsed, and leading/trailing dots are trimmed (a footgun
    on Windows and for hidden files). A title that sanitizes to an empty string
    falls back to ``"untitled"``.
    """

    cleaned = _INVALID_FILENAME_CHARS.sub(" ", title)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    cleaned = cleaned.strip(".")
    if not cleaned:
        return "untitled"
    return cleaned


def note_path_for(link: JdkLink, vault_dir: Path) -> Path:
    """Compute the full note file path for ``link``.

    Pure computation — does not create any directories. The parent version
    folder (and ``jep/`` subfolder for JEP links) must be ensured separately
    (see ``ensure_version_folder`` / ``ensure_jep_folder``).
    """

    folder = vault_dir / f"JDK {link.jdk_version}"
    if link.link_type == "jep":
        folder = folder / "jep"
    return folder / f"{sanitize_filename(link.title)}.md"
