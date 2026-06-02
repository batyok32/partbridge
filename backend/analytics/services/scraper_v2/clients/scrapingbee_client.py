"""ScrapingBee HTTP client with rate limiting and retry logic."""

import asyncio
import logging
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from ..config import Settings, get_settings
from ..models import ScraperMetrics
from ..utils import async_retry

logger = logging.getLogger(__name__)


class ScrapingBeeClient:
    """
    Client for ScrapingBee API with rate limiting and proper resource management.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        metrics: Optional[ScraperMetrics] = None,
    ):
        """
        Initialize ScrapingBee client.

        Args:
            settings: Configuration settings
            metrics: Metrics tracker
        """
        self.settings = settings or get_settings()
        self.metrics = metrics or ScraperMetrics()
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(self.settings.SCRAPINGBEE_MAX_CONCURRENT)

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure session exists and return it."""
        if self._session is None or self._session.closed:
            headers = {
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            timeout = aiohttp.ClientTimeout(total=120)
            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            # Give time for connections to close
            await asyncio.sleep(0.25)

    def build_params(
        self,
        url: str,
        render_js: bool = True,
        wait_for: Optional[str] = None,
        wait_ms: Optional[int] = None,
    ) -> dict:
        """
        Build ScrapingBee API parameters.

        Args:
            url: Target URL to scrape
            render_js: Whether to render JavaScript
            wait_for: CSS selector to wait for
            wait_ms: Milliseconds to wait

        Returns:
            Dictionary of API parameters
        """
        params = {
            "api_key": self.settings.SCRAPING_BEE_API_KEY,
            "url": url,
            "render_js": str(render_js).lower(),
            "country_code": self.settings.SCRAPINGBEE_COUNTRY_CODE,
            "wait": str(wait_ms or self.settings.SCRAPINGBEE_DEFAULT_WAIT_MS),
            "cookies": "lc=en-US;ebay=%5Esbf%3D%2340000000000100000000007089ed9fff%5E",
            "forward_headers": "true",
        }

        if wait_for:
            params["wait_for"] = wait_for

        return params

    @async_retry(max_attempts=5, initial_delay=1.0, max_delay=10.0)
    async def fetch_page(
        self,
        url: str,
        wait_for: Optional[str] = None,
    ) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a page using ScrapingBee.

        Args:
            url: Target URL
            wait_for: CSS selector to wait for

        Returns:
            Parsed BeautifulSoup object or None on failure
        """
        # Use semaphore to limit concurrent requests
        async with self._semaphore:
            params = self.build_params(url, wait_for=wait_for)
            session = await self._ensure_session()

            self.metrics.add_scrapingbee_call()

            try:
                async with session.get(
                    self.settings.SCRAPINGBEE_API_URL,
                    params=params,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.warning(
                            f"ScrapingBee request failed (status={response.status}): "
                            f"{error_text[:200]}"
                        )
                        # Raise to trigger retry
                        response.raise_for_status()

                    content = await response.read()

                    # Add delay between requests
                    await asyncio.sleep(self.settings.SCRAPINGBEE_REQUEST_DELAY)

                    return BeautifulSoup(content, "html.parser")

            except Exception as exc:
                logger.error(f"ScrapingBee request failed: {exc}")
                self.metrics.add_error(f"ScrapingBee error: {str(exc)}")
                raise

    async def fetch_pages_parallel(
        self,
        urls: list[tuple[str, Optional[str]]],
    ) -> list[Optional[BeautifulSoup]]:
        """
        Fetch multiple pages in parallel with rate limiting.

        Args:
            urls: List of (url, wait_for_selector) tuples

        Returns:
            List of BeautifulSoup objects (or None for failures)
        """
        tasks = [self.fetch_page(url, wait_for) for url, wait_for in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to None
        return [
            result if not isinstance(result, Exception) else None
            for result in results
        ]
