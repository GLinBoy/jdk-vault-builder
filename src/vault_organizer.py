"""Vault folder organization and filename/path resolution."""


def ensure_vault_root(vault_dir):
    raise NotImplementedError


def ensure_version_folder(vault_dir, jdk_version):
    raise NotImplementedError


def sanitize_filename(title):
    raise NotImplementedError


def note_path_for(link, vault_dir):
    raise NotImplementedError
