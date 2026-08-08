"""Throttled HTTP fetching with a disk cache and headless-browser fallback."""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Literal

import requests

import config

logger = logging.getLogger(__name__)

RequestStatus = Literal["cached", "fetched", "not_found", "blocked"]

# Global throttle state: timestamp of the last real request, shared by every
# fetch_url() call so a 1 req/sec rate holds across a whole batch run.
_last_request_time: float = 0.0


@dataclass
class FetchResult:
    """Outcome of a fetch_url() call.

    ``html_path`` points to the cached HTML file when one exists (including on
    cache hits); ``error`` carries a message for ``blocked`` results.
    """

    url: str
    status: RequestStatus
    html_path: Path | None = None
    error: str | None = None


def configure_logging(log_dir: Path | None = None) -> None:
    """Configure console and file logging (``cache/fetch.log`` by default).

    Idempotent: calling it more than once reuses existing handlers. Intended to
    be invoked once at CLI startup, not at import time, so tests never write
    into the real ``cache/`` directory.
    """
    log_dir = log_dir or config.CACHE_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "fetch.log"

    root = logging.getLogger()
    if not _has_file_handler(root, log_path):
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(file_handler)
    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(console)
    root.setLevel(logging.INFO)


def _has_file_handler(root: logging.Logger, log_path: Path) -> bool:
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler):
            base = getattr(handler, "baseFilename", None)
            if base is not None and Path(base).resolve() == log_path.resolve():
                return True
    return False


def url_to_cache_path(url: str, cache_dir: Path) -> Path:
    """Return the cache file path for ``url`` (sha256 hash of the URL + ``.html``)."""

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.html"


def _throttle() -> None:
    """Sleep just enough to keep a global 1 request/second rate."""

    global _last_request_time
    elapsed = monotonic() - _last_request_time
    if elapsed < config.FETCH_DELAY_SECONDS:
        sleep(config.FETCH_DELAY_SECONDS - elapsed)
    _last_request_time = monotonic()


def _has_challenge(text: str) -> bool:
    """Return True if any bot-challenge marker appears in ``text``."""

    lowered = text.lower()
    return any(marker.lower() in lowered for marker in config.BOT_CHALLENGE_MARKERS)


def _save_html(cache_dir: Path, cache_path: Path, html: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(html, encoding="utf-8")


def _fetch_with_playwright(url: str) -> str | None:
    """Fetch rendered HTML via a lazily-imported headless Chromium.

    Playwright is only imported here, never at module level, so normal runs
    never pay the headless-browser startup cost. Returns the rendered HTML or
    ``None`` if the fallback fails for any reason.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, timeout=config.PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
                return page.content()
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 - fallback must never crash the pipeline
        logger.warning("Playwright fallback failed for %s: %s", url, exc)
        return None


def fetch_url(url: str, cache_dir: Path) -> FetchResult:
    """Fetch ``url`` into ``cache_dir``, serving cached copies when present.

    Cache hits return immediately with ``status="cached"`` — no network call,
    no throttle sleep. Otherwise a global 1 req/sec throttle is enforced before
    the real ``requests.get``. Responses are checked against the configured
    bot-challenge markers; a detected challenge is retried once via a lazily
    imported headless browser.
    """
    cache_path = url_to_cache_path(url, cache_dir)
    if cache_path.exists():
        return FetchResult(url=url, status="cached", html_path=cache_path)

    try:
        _throttle()
        response = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.FETCH_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Request failed for %s: %s", url, exc)
        return FetchResult(url=url, status="blocked", error=str(exc))

    if response.status_code == 404:
        logger.warning("404 not found: %s", url)
        return FetchResult(url=url, status="not_found")

    if response.status_code == 200 and not _has_challenge(response.text):
        _save_html(cache_dir, cache_path, response.text)
        return FetchResult(url=url, status="fetched", html_path=cache_path)

    if _has_challenge(response.text):
        logger.warning("Bot challenge detected for %s; trying headless browser", url)
        rendered = _fetch_with_playwright(url)
        if rendered is not None and not _has_challenge(rendered):
            _save_html(cache_dir, cache_path, rendered)
            return FetchResult(url=url, status="fetched", html_path=cache_path)
        return FetchResult(
            url=url,
            status="blocked",
            error="Bot challenge could not be bypassed",
        )

    logger.warning("Unexpected HTTP status %d for %s", response.status_code, url)
    return FetchResult(
        url=url,
        status="blocked",
        error=f"Unexpected HTTP status {response.status_code}",
    )
