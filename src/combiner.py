"""Combining notes for one JDK version into a single markdown file."""


def strip_frontmatter(note_text):
    raise NotImplementedError


def sort_notes_for_combine(note_paths):
    raise NotImplementedError


def combine_version(vault_dir, jdk_version, force=False):
    raise NotImplementedError
