"""Combining notes for one JDK version into a single markdown file."""

from functools import cache
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

_TEMPLATE_NAME = "combined.md.j2"

_TYPE_ORDER = {"project_page": 0, "release_notes": 1, "jep": 2}

_FRONTMATTER_OPEN = "---\n"
_FRONTMATTER_CLOSE = "\n---\n"


@cache
def _template_env() -> Environment:
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    return Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)


def strip_frontmatter(note_text: str) -> str:
    """Remove the leading YAML frontmatter block, returning only the body.

    Only a block that opens the file with ``"---\\n"`` and closes with a
    subsequent ``"\\n---\\n"`` is stripped. Any text without such a block is
    returned unchanged, and the separator blank line following the block is
    dropped so the body starts clean.
    """
    if not note_text.startswith(_FRONTMATTER_OPEN):
        return note_text
    end = note_text.find(_FRONTMATTER_CLOSE)
    if end == -1:
        return note_text
    return note_text[end + len(_FRONTMATTER_CLOSE) :].lstrip("\n")


def parse_frontmatter(note_text: str) -> dict[str, object]:
    """Parse the leading YAML block of ``note_text`` into a dict.

    Returns an empty dict if the text has no frontmatter block, has an
    unterminated block, or the block does not parse to a YAML mapping.
    """
    if not note_text.startswith(_FRONTMATTER_OPEN):
        return {}
    end = note_text.find(_FRONTMATTER_CLOSE)
    if end == -1:
        return {}
    data = yaml.safe_load(note_text[len(_FRONTMATTER_OPEN) : end])
    if not isinstance(data, dict):
        return {}
    return data


def _read_frontmatter(path: Path) -> dict[str, object]:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def _jep_sort_number(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _sort_key(path: Path) -> tuple[int, int, str]:
    """Return an ordering tuple for ``path``'s note.

    Ordering: project_page, release_notes, then jep entries by ascending
    jep_number, then any other link_type alphabetically by title.
    """
    meta = _read_frontmatter(path)
    link_type = str(meta.get("link_type", "") or "")
    title = str(meta.get("title", "") or path.stem)
    if link_type == "project_page":
        return (0, 0, "")
    if link_type == "release_notes":
        return (1, 0, "")
    if link_type == "jep":
        return (_TYPE_ORDER["jep"], _jep_sort_number(meta.get("jep_number")), title)
    return (_TYPE_ORDER.get(link_type, 3), 0, title)


def sort_notes_for_combine(note_paths: list[Path]) -> list[Path]:
    """Return ``note_paths`` in canonical combined-file order (see ``_sort_key``)."""

    return sorted(note_paths, key=_sort_key)


def combine_version(vault_dir: Path, jdk_version: int, force: bool = False) -> Path | None:
    """Merge all notes for ``jdk_version`` into a single markdown file.

    Rescans the ``vault_dir/JDK {jdk_version}/`` folder from scratch each run
    (no tracking of what was combined before). Returns the output path on
    success, or ``None`` if there was nothing to combine or the user declined
    to overwrite an existing output file.
    """
    version_dir = vault_dir / f"JDK {jdk_version}"
    output_path = version_dir / "_combined" / f"JDK {jdk_version} - Full.md"

    note_paths = [p for p in version_dir.glob("*.md") if p.parent != output_path.parent]
    if not note_paths:
        return None

    notes = []
    for path in sort_notes_for_combine(note_paths):
        note_text = path.read_text(encoding="utf-8")
        title = str(_read_frontmatter(path).get("title", "") or path.stem)
        notes.append({"title": title, "body": strip_frontmatter(note_text).strip()})

    rendered = (
        _template_env().get_template(_TEMPLATE_NAME).render(jdk_version=jdk_version, notes=notes)
    )

    if output_path.exists() and not force:
        answer = input(f"{output_path} exists. Overwrite? [y/N]: ").strip().lower()
        if answer != "y":
            return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return output_path
