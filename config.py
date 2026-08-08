"""Central configuration: paths, throttle settings, and bot-challenge markers.

All filesystem locations and fetch-related constants used across the project
are defined here so that modules never hard-code paths.
"""

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent

CSV_PATH: Path = PROJECT_ROOT / "data" / "jdk_links.csv"
CACHE_DIR: Path = PROJECT_ROOT / "cache"
VAULT_DIR: Path = PROJECT_ROOT / "vault"

FETCH_DELAY_SECONDS: float = 1.0
FETCH_TIMEOUT_SECONDS: float = 15.0
PLAYWRIGHT_TIMEOUT_MS: int = 30_000

USER_AGENT: str = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

BOT_CHALLENGE_MARKERS: list[str] = [
    "Just a moment",
    "cf-chl",
    "captcha",
]
