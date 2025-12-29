"""HTTP utilities with caching, retries, and rate limiting."""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from tahoe_conditions.config import (
    USER_AGENT,
    REQUEST_TIMEOUT,
    RATE_LIMIT_DELAY,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    CACHE_DIR,
    CONDITIONS_CACHE_TTL,
    NWS_CACHE_TTL,
)

logger = logging.getLogger(__name__)

# Check if Playwright is available
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.debug("Playwright not installed - headless fetching disabled")

# Track last request time per host for rate limiting
_last_request_time: dict[str, float] = {}


def _get_cache_path(url: str, cache_key_suffix: str = "") -> Path:
    """Generate cache file path for a URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"{date_key}_{url_hash}{cache_key_suffix}.cache"
    return CACHE_DIR / filename


def _read_cache(cache_path: Path, ttl_seconds: int) -> Optional[str]:
    """Read from cache if valid and not expired."""
    if not cache_path.exists():
        return None

    try:
        stat = cache_path.stat()
        age = time.time() - stat.st_mtime
        if age > ttl_seconds:
            return None
        return cache_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.debug(f"Cache read error: {e}")
        return None


def _write_cache(cache_path: Path, content: str) -> None:
    """Write content to cache."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.debug(f"Cache write error: {e}")


def _rate_limit(url: str) -> None:
    """Enforce rate limiting per host."""
    host = urlparse(url).netloc
    now = time.time()
    last = _last_request_time.get(host, 0)
    elapsed = now - last

    if elapsed < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - elapsed
        logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {host}")
        time.sleep(sleep_time)

    _last_request_time[host] = time.time()


class FetchError(Exception):
    """Error fetching URL."""
    pass


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=RETRY_BACKOFF_BASE, min=1, max=30),
    retry=retry_if_exception_type((requests.exceptions.RequestException,)),
    reraise=True,
)
def _fetch_with_retry(url: str, headers: dict) -> requests.Response:
    """Fetch URL with retry logic."""
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

    # Retry on 5xx errors
    if 500 <= response.status_code < 600:
        raise requests.exceptions.RequestException(f"Server error: {response.status_code}")

    return response


def fetch(
    url: str,
    ttl_seconds: int = CONDITIONS_CACHE_TTL,
    cache_key_suffix: str = "",
    use_cache: bool = True,
) -> str:
    """
    Fetch URL content with caching, rate limiting, and retries.

    Args:
        url: URL to fetch
        ttl_seconds: Cache TTL in seconds
        cache_key_suffix: Optional suffix for cache key
        use_cache: Whether to use caching

    Returns:
        Response text content

    Raises:
        FetchError: If fetch fails after retries
    """
    cache_path = _get_cache_path(url, cache_key_suffix)

    # Try cache first
    if use_cache:
        cached = _read_cache(cache_path, ttl_seconds)
        if cached is not None:
            logger.debug(f"Cache hit: {url}")
            return cached

    # Rate limit
    _rate_limit(url)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        logger.debug(f"Fetching: {url}")
        response = _fetch_with_retry(url, headers)
        response.raise_for_status()
        content = response.text

        # Cache successful response
        if use_cache:
            _write_cache(cache_path, content)

        return content

    except requests.exceptions.RequestException as e:
        raise FetchError(f"Failed to fetch {url}: {e}") from e


def fetch_json(url: str, ttl_seconds: int = NWS_CACHE_TTL) -> dict:
    """
    Fetch JSON from URL with caching and retries.

    Args:
        url: URL to fetch
        ttl_seconds: Cache TTL in seconds

    Returns:
        Parsed JSON as dict

    Raises:
        FetchError: If fetch or parse fails
    """
    cache_path = _get_cache_path(url, "_json")

    # Try cache first
    cached = _read_cache(cache_path, ttl_seconds)
    if cached is not None:
        logger.debug(f"Cache hit (JSON): {url}")
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass  # Cache corrupted, refetch

    # Rate limit
    _rate_limit(url)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json,application/json",
    }

    try:
        logger.debug(f"Fetching JSON: {url}")
        response = _fetch_with_retry(url, headers)
        response.raise_for_status()
        data = response.json()

        # Cache successful response
        _write_cache(cache_path, json.dumps(data))

        return data

    except requests.exceptions.RequestException as e:
        raise FetchError(f"Failed to fetch {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise FetchError(f"Invalid JSON from {url}: {e}") from e


def fetch_headless(
    url: str,
    ttl_seconds: int = CONDITIONS_CACHE_TTL,
    cache_key_suffix: str = "_headless",
    use_cache: bool = True,
    wait_for_selector: Optional[str] = None,
    wait_timeout: int = 10000,
) -> str:
    """
    Fetch URL content using headless browser (Playwright).

    Use this for JavaScript-rendered pages that can't be scraped with requests.

    Args:
        url: URL to fetch
        ttl_seconds: Cache TTL in seconds
        cache_key_suffix: Suffix for cache key
        use_cache: Whether to use caching
        wait_for_selector: CSS selector to wait for before extracting content
        wait_timeout: Timeout in ms for waiting on selector

    Returns:
        Rendered HTML content

    Raises:
        FetchError: If fetch fails or Playwright not available
    """
    if not HAS_PLAYWRIGHT:
        raise FetchError("Playwright not installed - cannot fetch JavaScript-rendered pages")

    cache_path = _get_cache_path(url, cache_key_suffix)

    # Try cache first
    if use_cache:
        cached = _read_cache(cache_path, ttl_seconds)
        if cached is not None:
            logger.debug(f"Cache hit (headless): {url}")
            return cached

    # Rate limit
    _rate_limit(url)

    try:
        logger.debug(f"Fetching (headless): {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()

            # Navigate and wait for content
            page.goto(url, timeout=REQUEST_TIMEOUT * 1000)

            if wait_for_selector:
                try:
                    page.wait_for_selector(wait_for_selector, timeout=wait_timeout)
                except Exception as e:
                    logger.warning(f"Selector wait timeout for {wait_for_selector}: {e}")

            # Give JS a moment to finish rendering
            page.wait_for_timeout(1000)

            content = page.content()
            browser.close()

        # Cache successful response
        if use_cache:
            _write_cache(cache_path, content)

        return content

    except Exception as e:
        raise FetchError(f"Headless fetch failed for {url}: {e}") from e
