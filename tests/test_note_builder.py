"""Tests for the note builder module."""

from pathlib import Path

import pytest
import yaml

from src.content_extractor import ExtractedContent
from src.csv_loader import JdkLink, load_csv
from src.note_builder import build_note
from tests.test_csv_loader import SAMPLE_CSV


@pytest.fixture
def all_links(tmp_path: Path) -> list[JdkLink]:
    csv_path = tmp_path / "jdk_links.csv"
    csv_path.write_text(SAMPLE_CSV, encoding="utf-8")
    return load_csv(csv_path)


def _link_named(links: list[JdkLink], title: str) -> JdkLink:
    return next(link for link in links if link.title == title)


# --- build_note --------------------------------------------------------------


def test_build_note_renders_frontmatter_tags_and_no_wikilinks(
    all_links: list[JdkLink], tmp_path: Path
) -> None:
    vault_dir = tmp_path / "vault"
    link = _link_named(all_links, "HTTP 2 Client")
    extracted = ExtractedContent(text="Some extracted body text.", page_title="HTTP/2 Client")

    path = build_note(link, extracted, vault_dir)

    content = path.read_text(encoding="utf-8")
    assert "jdk_version: 9" in content
    assert "link_type: jep" in content
    assert "jep_number: 110" in content
    assert "title: HTTP 2 Client" in content
    assert "source_url: https://openjdk.org/jeps/110" in content
    assert "fetched:" in content
    assert "# HTTP 2 Client" in content
    assert "Some extracted body text." in content
    assert "tags: [jdk_9, jep]" in content
    assert "Tags: #jdk_9" in content
    assert "Tags: #link-type/jep" not in content
    assert "[[" not in content


def test_build_note_jep_writes_into_jep_subfolder(
    all_links: list[JdkLink], tmp_path: Path
) -> None:
    vault_dir = tmp_path / "vault"
    link = _link_named(all_links, "Process API Updates")
    extracted = ExtractedContent(text="body", page_title=None)

    path = build_note(link, extracted, vault_dir)

    assert path == vault_dir / "JDK 9" / "jep" / "Process API Updates.md"
    assert path.exists()


def test_build_note_non_jep_writes_into_version_folder(
    all_links: list[JdkLink], tmp_path: Path
) -> None:
    vault_dir = tmp_path / "vault"
    link = _link_named(all_links, "JDK 9 Project Page")
    extracted = ExtractedContent(text="body", page_title=None)

    path = build_note(link, extracted, vault_dir)

    assert path == vault_dir / "JDK 9" / "JDK 9 Project Page.md"
    assert path.exists()


def test_build_note_has_no_links_and_has_tags(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    link = JdkLink(17, "jep", 305, "Pattern Matching", "https://openjdk.org/jeps/305")
    extracted = ExtractedContent(text="body text", page_title=None)

    path = build_note(link, extracted, vault_dir)

    content = path.read_text(encoding="utf-8")
    assert "[[" not in content
    assert "## Extracted Content" in content
    assert "body text" in content
    assert "tags: [jdk_17, jep]" in content
    assert "Tags: #jdk_17" in content


def test_build_note_quotes_title_with_yaml_special_chars(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    link = JdkLink(9, "jep", 222, "jshell: The Java Shell (Read-Eval-Print Loop)", "https://openjdk.org/jeps/222")
    extracted = ExtractedContent(text="body text", page_title=None)

    path = build_note(link, extracted, vault_dir)

    content = path.read_text(encoding="utf-8")
    frontmatter = content[len("---\n") : content.index("\n---\n")]
    meta = yaml.safe_load(frontmatter)
    assert meta["title"] == "jshell: The Java Shell (Read-Eval-Print Loop)"
    assert meta["source_url"] == "https://openjdk.org/jeps/222"


def test_build_note_does_not_overwrite_existing_note(
    all_links: list[JdkLink], tmp_path: Path, mocker
) -> None:
    vault_dir = tmp_path / "vault"
    link = _link_named(all_links, "HTTP 2 Client")
    first_extracted = ExtractedContent(text="first body", page_title=None)

    first_path = build_note(link, first_extracted, vault_dir)
    content_after_first = first_path.read_text(encoding="utf-8")

    second_extracted = ExtractedContent(text="changed body", page_title=None)
    template_env = mocker.patch("src.note_builder._template_env")

    second_path = build_note(link, second_extracted, vault_dir)

    assert second_path == first_path
    assert second_path.read_text(encoding="utf-8") == content_after_first
    assert "changed body" not in content_after_first
    template_env.assert_not_called()
