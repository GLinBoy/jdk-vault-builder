"""Tests for the fetcher and cache module."""

import logging
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

import config
from src import fetcher
from src.fetcher import FetchResult, fetch_url, url_to_cache_path

CLEAN_HTML = "<html><body><p>real content</p></body></html>"
CHALLENGE_HTML = "<html><body>Just a moment, verifying you are human... cf-chl</body></html>"


@pytest.fixture(autouse=True)
def _no_real_network_or_sleep():
    with patch("src.fetcher.requests.get"), patch("src.fetcher.sleep"):
        fetcher._last_request_time = 0.0
        yield


# --- url_to_cache_path -------------------------------------------------------


def test_url_to_cache_path_is_stable_and_scoped(tmp_path: Path) -> None:
    url = "https://openjdk.org/jeps/102"
    p1 = url_to_cache_path(url, tmp_path)
    p2 = url_to_cache_path(url, tmp_path)
    p3 = url_to_cache_path("https://openjdk.org/jeps/110", tmp_path)

    assert p1 == p2
    assert p1 != p3
    assert p1.suffix == ".html"
    assert p1.parent == tmp_path


def test_url_to_cache_path_uses_sha256(tmp_path: Path) -> None:
    import hashlib

    url = "https://openjdk.org/jeps/102"
    expected = hashlib.sha256(url.encode("utf-8")).hexdigest()
    assert url_to_cache_path(url, tmp_path).name == f"{expected}.html"


# --- fetch_url: 200 clean ----------------------------------------------------


def test_fetch_200_clean_saves_and_returns_fetched(tmp_path: Path) -> None:
    url = "https://example.com/page"
    with patch("src.fetcher.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=200, text=CLEAN_HTML)
        result = fetch_url(url, tmp_path)

    assert result.status == "fetched"
    assert result.error is None
    assert result.html_path is not None
    assert result.html_path.exists()
    assert result.html_path.read_text(encoding="utf-8") == CLEAN_HTML
    mock_get.assert_called_once_with(
        url,
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.FETCH_TIMEOUT_SECONDS,
    )


# --- fetch_url: 404 ----------------------------------------------------------


def test_fetch_404_returns_not_found(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    url = "https://example.com/missing"
    with patch("src.fetcher.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=404, text="Not Found")
        with caplog.at_level(logging.WARNING, logger="src.fetcher"):
            result = fetch_url(url, tmp_path)

    assert result.status == "not_found"
    assert result.error is None
    assert result.html_path is None
    assert not list(tmp_path.glob("*.html"))
    assert any("404" in record.message for record in caplog.records)


# --- fetch_url: blocked + playwright fallback --------------------------------


def test_fetch_blocked_then_playwright_succeeds(tmp_path: Path) -> None:
    url = "https://example.com/challenge"
    with (
        patch("src.fetcher.requests.get") as mock_get,
        patch("src.fetcher._fetch_with_playwright", return_value=CLEAN_HTML) as mock_playwright,
    ):
        mock_get.return_value = Mock(status_code=200, text=CHALLENGE_HTML)
        result = fetch_url(url, tmp_path)

    assert result.status == "fetched"
    assert result.error is None
    assert result.html_path is not None
    assert result.html_path.read_text(encoding="utf-8") == CLEAN_HTML
    mock_get.assert_called_once()
    mock_playwright.assert_called_once_with(url)


def test_fetch_blocked_and_playwright_fails(tmp_path: Path) -> None:
    url = "https://example.com/challenge2"
    with (
        patch("src.fetcher.requests.get") as mock_get,
        patch("src.fetcher._fetch_with_playwright", return_value=None) as mock_playwright,
    ):
        mock_get.return_value = Mock(status_code=200, text=CHALLENGE_HTML)
        result = fetch_url(url, tmp_path)

    assert result.status == "blocked"
    assert result.html_path is None
    assert result.error == "Bot challenge could not be bypassed"
    assert not list(tmp_path.glob("*.html"))
    mock_playwright.assert_called_once_with(url)


def test_fetch_blocked_playwright_still_challenged(tmp_path: Path) -> None:
    url = "https://example.com/challenge3"
    with (
        patch("src.fetcher.requests.get") as mock_get,
        patch("src.fetcher._fetch_with_playwright", return_value=CHALLENGE_HTML) as mock_playwright,
    ):
        mock_get.return_value = Mock(status_code=200, text=CHALLENGE_HTML)
        result = fetch_url(url, tmp_path)

    assert result.status == "blocked"
    assert result.html_path is None
    mock_playwright.assert_called_once_with(url)


# --- fetch_url: network / status errors --------------------------------------


def test_fetch_request_exception_returns_blocked(tmp_path: Path) -> None:
    url = "https://example.com/down"
    with patch(
        "src.fetcher.requests.get", side_effect=requests.ConnectionError("boom")
    ) as mock_get:
        result = fetch_url(url, tmp_path)

    assert result.status == "blocked"
    assert result.error == "boom"
    assert result.html_path is None
    mock_get.assert_called_once_with(
        url,
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.FETCH_TIMEOUT_SECONDS,
    )


def test_fetch_unexpected_status_returns_blocked(tmp_path: Path) -> None:
    url = "https://example.com/oops"
    with patch("src.fetcher.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=500, text="server error")
        result = fetch_url(url, tmp_path)

    assert result.status == "blocked"
    assert result.error == "Unexpected HTTP status 500"
    assert result.html_path is None


# --- cache-hit short-circuit -------------------------------------------------


def test_second_call_is_cache_hit_without_extra_network(tmp_path: Path) -> None:
    url = "https://example.com/once"
    with patch("src.fetcher.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=200, text=CLEAN_HTML)
        first = fetch_url(url, tmp_path)
        assert first.status == "fetched"

        second = fetch_url(url, tmp_path)

    assert second.status == "cached"
    assert second.html_path == first.html_path
    assert second.error is None
    mock_get.assert_called_once()


def test_cache_hit_does_not_call_network_or_sleep(tmp_path: Path) -> None:
    url = "https://example.com/cached"
    url_to_cache_path(url, tmp_path).write_text(CLEAN_HTML, encoding="utf-8")

    with patch("src.fetcher.requests.get") as mock_get, patch("src.fetcher.sleep") as mock_sleep:
        result = fetch_url(url, tmp_path)

    assert result.status == "cached"
    assert result.html_path is not None
    assert result.html_path.exists()
    mock_get.assert_not_called()
    mock_sleep.assert_not_called()


# --- throttle ----------------------------------------------------------------


def test_throttle_sleeps_to_enforce_one_request_per_second(tmp_path: Path) -> None:
    with patch("src.fetcher.requests.get") as mock_get, patch("src.fetcher.sleep") as mock_sleep:
        mock_get.return_value = Mock(status_code=200, text=CLEAN_HTML)

        fetcher._last_request_time = 0.0
        fetch_url("https://example.com/a", tmp_path)
        mock_sleep.assert_not_called()  # first request: nothing to throttle

        fetcher._last_request_time = time.monotonic()  # pretend a request just happened
        fetch_url("https://example.com/b", tmp_path)

    mock_sleep.assert_called_once()
    wait = mock_sleep.call_args.args[0]
    assert 0.0 < wait <= config.FETCH_DELAY_SECONDS


# --- playwright lazy import --------------------------------------------------


def test_playwright_fallback_imports_lazily_and_navigates(tmp_path: Path) -> None:
    fake_playwright = MagicMock()
    page = Mock()
    page.goto.return_value = None
    page.content.return_value = CLEAN_HTML
    browser = Mock()
    browser.new_page.return_value = page
    chromium = Mock()
    chromium.launch.return_value = browser
    fake_playwright.chromium = chromium
    fake_playwright.__enter__.return_value = fake_playwright
    fake_playwright.__exit__.return_value = False
    fake_sync_api = types.SimpleNamespace(sync_playwright=lambda: fake_playwright)

    with patch.dict(sys.modules, {"playwright.sync_api": fake_sync_api}):
        html = fetcher._fetch_with_playwright("https://example.com/rendered")

    assert html == CLEAN_HTML
    chromium.launch.assert_called_once_with(headless=True)
    page.goto.assert_called_once()
    browser.close.assert_called_once()


def test_fetch_result_defaults() -> None:
    result = FetchResult(url="https://example.com", status="cached")
    assert result.html_path is None
    assert result.error is None


# --- logging configuration ---------------------------------------------------


def test_configure_logging_writes_console_and_fetch_log(tmp_path: Path) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        fetcher.configure_logging(tmp_path)
        log_path = tmp_path / "fetch.log"
        assert log_path.exists()
        assert any(
            isinstance(h, logging.FileHandler) for h in root.handlers
        ), "file handler should be attached"
        assert any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in root.handlers
        ), "console handler should be attached"

        logging.getLogger("src.fetcher").info("probe log message")
        assert "probe log message" in log_path.read_text(encoding="utf-8")
    finally:
        root.handlers[:] = original_handlers
        root.setLevel(original_level)


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        fetcher.configure_logging(tmp_path)
        count = len(root.handlers)
        fetcher.configure_logging(tmp_path)
        assert len(root.handlers) == count
    finally:
        root.handlers[:] = original_handlers
