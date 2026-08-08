"""Rendering of individual Obsidian notes from templates."""

from datetime import datetime, timezone
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.content_extractor import ExtractedContent
from src.csv_loader import JdkLink
from src.vault_organizer import ensure_version_folder, note_path_for

_TEMPLATE_NAME = "note.md.j2"


@cache
def _template_env() -> Environment:
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    return Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)


def find_parent_links(links: list[JdkLink], jdk_version: int) -> list[JdkLink]:
    """Return the project_page/release_notes rows for ``jdk_version`` (backlinks)."""

    return [
        link
        for link in links
        if link.jdk_version == jdk_version and link.link_type in {"project_page", "release_notes"}
    ]


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

    ensure_version_folder(vault_dir, link.jdk_version)
    rendered = (
        _template_env()
        .get_template(_TEMPLATE_NAME)
        .render(
            link=link,
            parent_links=find_parent_links(all_links, link.jdk_version),
            extracted_text=extracted.text,
            fetched_date=datetime.now(timezone.utc).date().isoformat(),
        )
    )
    path.write_text(rendered, encoding="utf-8")
    return path
