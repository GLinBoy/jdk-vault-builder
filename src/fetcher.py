"""Throttled HTTP fetching with a disk cache and headless-browser fallback."""


def url_to_cache_path(url, cache_dir):
    raise NotImplementedError


def fetch_url(url, cache_dir):
    raise NotImplementedError
