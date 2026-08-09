"""Rendering of individual Obsidian notes from templates."""

from datetime import datetime, timezone
from functools import cache
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from src.content_extractor import ExtractedContent
from src.csv_loader import JdkLink
from src.vault_organizer import ensure_jep_folder, ensure_version_folder, note_path_for

_TEMPLATE_NAME = "note.md.j2"


def _yaml_scalar(value: object) -> str:
    """Render ``value`` as a single-line YAML scalar (quoted only when needed).

    Plain strings stay unquoted; values that would be ambiguous in YAML (e.g.
    titles containing ``": "`` or special characters) are quoted so the
    frontmatter always parses back to the original string.
    """
    dumped = yaml.safe_dump(value, default_flow_style=False).removesuffix("\n...\n")
    return dumped.rstrip("\n")


@cache
def _template_env() -> Environment:
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)
    env.filters["yaml_scalar"] = _yaml_scalar
    return env


def find_project_page_title(links: list[JdkLink], jdk_version: int) -> str | None:
    """Return the title of the ``project_page`` row for ``jdk_version``.

    Returns ``None`` if the version has no ``project_page`` row. JEP and
    ``release_notes`` notes use this as their ``parent`` frontmatter property.
    """
    for link in links:
        if link.jdk_version == jdk_version and link.link_type == "project_page":
            return link.title
    return None


def build_note(
    link: JdkLink,
    extracted: ExtractedContent,
    all_links: list[JdkLink],
    vault_dir: Path,
) -> Path:
    """Render and write a note for ``link`` unless it already exists on disk.

    Idempotent: if the target file exists, it is returned untouched and nothing
    is rendered or written — per the project rule that a note on disk means it
    has already been processed.
    """
    path = note_path_for(link, vault_dir)
    if path.exists():
        return path

    if link.link_type == "jep":
        ensure_jep_folder(vault_dir, link.jdk_version)
    else:
        ensure_version_folder(vault_dir, link.jdk_version)
    parent_title = find_project_page_title(all_links, link.jdk_version)
    rendered = (
        _template_env()
        .get_template(_TEMPLATE_NAME)
        .render(
            link=link,
            tags=[f"jdk_{link.jdk_version}", link.link_type],
            parent_title=parent_title,
            extracted_text=extracted.text,
            fetched_date=datetime.now(timezone.utc).date().isoformat(),
        )
    )
    path.write_text(rendered, encoding="utf-8")
    return path
