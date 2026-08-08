"""Generating the vault root-level home page."""

from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.combiner import parse_frontmatter

_TEMPLATE_NAME = "home.md.j2"


@cache
def _template_env() -> Environment:
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    return Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)


def _version_folders(vault_dir: Path) -> list[Path]:
    """Return the ``vault_dir/JDK {n}/`` folders, sorted by version number."""

    if not vault_dir.is_dir():
        return []
    folders = [
        folder
        for folder in vault_dir.iterdir()
        if folder.is_dir() and folder.name.startswith("JDK ") and folder.name[4:].isdigit()
    ]
    return sorted(folders, key=lambda folder: int(folder.name[4:]))


def _note_paths(version_dir: Path) -> list[Path]:
    """Return all note files under ``version_dir``, excluding ``_combined/``."""

    return [p for p in version_dir.rglob("*.md") if p.parent.name != "_combined"]


def summarize_version(version_dir: Path) -> dict[str, object]:
    """Aggregate note counts for one version folder.

    Reads each note's YAML frontmatter to tally ``link_type`` values, and
    reports whether the version's combined NotebookLM file exists.
    """

    counts: dict[str, int] = {}
    for path in _note_paths(version_dir):
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        link_type = str(meta.get("link_type") or "unknown")
        counts[link_type] = counts.get(link_type, 0) + 1
    return {
        "jdk_version": int(version_dir.name[4:]),
        "total": sum(counts.values()),
        "project_page": counts.get("project_page", 0),
        "release_notes": counts.get("release_notes", 0),
        "jep": counts.get("jep", 0),
        "has_combined": (version_dir / "_combined").is_dir(),
    }


def build_home(vault_dir: Path) -> Path:
    """Render and write ``vault_dir/Home.md`` from the current vault contents.

    Always overwritten (like the combiner's output) so the home page reflects
    the latest vault state on every run.
    """

    vault_dir.mkdir(parents=True, exist_ok=True)
    versions = [summarize_version(folder) for folder in _version_folders(vault_dir)]
    rendered = _template_env().get_template(_TEMPLATE_NAME).render(versions=versions)
    home_path = vault_dir / "Home.md"
    home_path.write_text(rendered, encoding="utf-8")
    return home_path
